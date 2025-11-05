"""Retrieve a playlist"""

import argparse
import json
import logging

import googleapiclient.errors

from . import youtube

LOGGER = logging.getLogger(__name__)


def get_options(*args):
    """ Set options for the CLI """
    parser = argparse.ArgumentParser("get_playlist")
    parser.add_argument("playlist_id", help="YouTube playlist ID")

    youtube.add_arguments(parser)

    return parser.parse_args(*args)


def get_playlist(client, playlist_id):
    """ Fetch a playlist's items """
    playlist_items = []
    next_page_token = None

    while True:
        try:
            request = client.playlistItems().list(
                part="snippet,contentDetails,status",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response['items']:
                video_id = item['contentDetails']['videoId']
                video_title = item['snippet']['title']
                LOGGER.info("ID: %s  Title: %s", video_id, video_title)
                playlist_items.append(item)

            next_page_token = response.get('nextPageToken')

            if not next_page_token:
                break

        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
            break
        except Exception as e:  # pylint:disable=broad-exception-caught
            print(f"An unexpected error occurred: {e}")
            break

    return playlist_items


def main():
    """ entry point """
    options = get_options()
    client = youtube.get_client(options)
    items = get_playlist(client, options.playlist_id)
    print(json.dumps(items))


if __name__ == '__main__':
    main()
