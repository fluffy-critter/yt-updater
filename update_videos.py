""" update videos in bulk """

import argparse
import json
import logging

import bandcrash.util
import Levenshtein

import youtube

LOGGER = logging.getLogger(__name__)

TITLE_PATH = ('snippet', 'title')
YTID_PATH = ('contentDetails', 'videoId')


def get_options(*args):
    """ Set options for the CLI """
    parser = argparse.ArgumentParser("update_videos")
    parser.add_argument("playlist_json", help="YouTube playlist JSON")
    parser.add_argument("album_json", help="Bandcrash JSON file for the album")
    parser.add_argument("--date", type=str,
                        help="Scheduled release date", default=None)
    parser.add_argument("--date-incr", type=int,
                        help="Track-number date increment, in seconds", default=60)
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Don't execute the update", default=False)
    parser.add_argument("--template", "-D", type=str,
                        help="Jinja2 template for the description", default=None)
    parser.add_argument("--max-distance", "-l", type=int,
                        help="Maximum Levenshtein distance for title reconciliation", default=5)
    parser.add_argument("--input-title", type=str, help="Format for the playlist's video title",
                        default="{track:02} {filename}")
    parser.add_argument("--output-title", type=str, help="Format for the updated title",
                        default="{title}")

    youtube.add_arguments(parser)

    return parser.parse_args(*args)


def get_value(item, path, default=None):
    """ Get a value from a JSON dictionary """
    for key in path:
        if not isinstance(item, dict) or not key in item:
            return default
        item = item[key]
    return item


def match_item(options, item, tracks):
    """ Build an update for a single item based on the tracks """
    best_track = (None, None)
    best_distance = None
    best_title = None

    item_title = get_value(item, TITLE_PATH)
    for idx, track in tracks:
        check_title = options.input_title.format(track=idx, title=track.get(
            'title', ''), filename=bandcrash.util.slugify_filename(track.get('title', '')))
        distance = Levenshtein.distance(item_title, check_title)
        if best_distance is None or distance < best_distance:
            best_track = (idx, track)
            best_distance = distance
            best_title = check_title

    if best_distance > options.max_distance:
        LOGGER.warning("%s (%s): Best match has distance of %d (%s), not updating",
                       get_value(item, YTID_PATH), item_title, best_distance, best_title)
        return None, None

    return best_track


def update_playlist(options, client):
    """ Update process """

    with open(options.playlist_json, "r", encoding="utf-8") as file:
        playlist = json.load(file)

    with open(options.album_json, "r", encoding="utf-8") as file:
        album = json.load(file)

    tracks = [*enumerate(album.get('tracks', []), start=1)]

    matches = [(item, *match_item(options, item, tracks)) for item in playlist]
    matches = [(item, idx, track) for item, idx, track in matches if track]

    for item, idx, track in matches:
        LOGGER.info("%s: %s -> %d. %s", get_value(item, YTID_PATH), get_value(
            item, TITLE_PATH), idx, track.get('title'))


def main():
    """ entry point """
    options = get_options()
    client = youtube.get_client(options)
    update_playlist(options, client)

if __name__ == "__main__":
    main()