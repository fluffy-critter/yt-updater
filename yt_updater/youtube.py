""" wrapper for the youtube API """

import logging
import os
import pickle
import argparse
import typing
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

LOG_LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]
LOGGER = logging.getLogger(__name__)

# Disable OAuthlib's HTTPS verification when running locally.
# DO NOT leave this setting enabled in production.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "client.json"  # Downloaded from Google Cloud Console
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CREDENTIALS_FILE = 'token.json'


def add_arguments(parser):
    """ Add arguments to an argparse.ArgumentParser """
    parser.add_argument("--client-json", help="Path to the client secrets file",
                        default=CLIENT_SECRETS_FILE)
    parser.add_argument("--login-token", help="Path to the login token",
                        default=CREDENTIALS_FILE)

    parser.add_argument(
        "--verbosity",
        "-v",
        action="count",
        help="Increase output logging level",
        default=0,
    )

def get_options(*args):
    """ Get a minimal set of arguments, useful for REPL """
    parser = argparse.ArgumentParser(__name__)
    add_arguments(parser)
    return parser.parse_args(*args)

def get_client(options:typing.Optional[argparse.Namespace]=None):
    """ Get the YouTube API client """

    if options is None:
        options = get_options()

    logging.basicConfig(
        level=LOG_LEVELS[min(options.verbosity, len(
            LOG_LEVELS) - 1)], format="%(message)s"
    )

    credentials = None

    store = options.login_token
    if os.path.exists(store):
        LOGGER.debug("Reusing stored token: %s", store)
        credentials = Credentials.from_authorized_user_file(store)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                options.client_json, SCOPES)
            credentials = flow.run_local_server(port=0)

        with open(store, 'w') as token:
            token.write(credentials.to_json())
            LOGGER.info("Credentials saved/updated to %s", store)
    else:
        LOGGER.info("Reusing saved credentials")

    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
