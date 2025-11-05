""" wrapper for the youtube API """

import logging
import os
import pickle

import google.auth.transport.requests
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

LOG_LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]
LOGGER = logging.getLogger(__name__)

# Disable OAuthlib's HTTPS verification when running locally.
# DO NOT leave this setting enabled in production.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

CLIENT_SECRETS_FILE = "client.json"  # Downloaded from Google Cloud Console
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CREDENTIALS_FILE = 'token.pickle'


def add_arguments(parser):
    """ Add arguments to an argparse.ArgumentParser """
    parser.add_argument("--client_json", help="Path to the client secrets file",
                        default=os.path.join(APP_DIR, CLIENT_SECRETS_FILE))
    parser.add_argument("--login_token", help="Path to the login token",
                        default=os.path.join(APP_DIR, CREDENTIALS_FILE))

    parser.add_argument(
        "--verbosity",
        "-v",
        action="count",
        help="Increase output logging level",
        default=0,
    )


def get_client(options):
    """ Get the YouTube API client """

    logging.basicConfig(
        level=LOG_LEVELS[min(options.verbosity, len(
            LOG_LEVELS) - 1)], format="%(message)s"
    )

    credentials = None

    store = options.login_token
    if os.path.exists(store):
        LOGGER.debug("Reusing stored token: %s", store)
        with open(store, 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                options.client_json, SCOPES)
            credentials = flow.run_local_server(port=0)

        with open(store, 'wb') as token:
            pickle.dump(credentials, token)
            LOGGER.info("Credentials saved/updated to %s", store)
    else:
        LOGGER.info("Reusing saved credentials")

    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
