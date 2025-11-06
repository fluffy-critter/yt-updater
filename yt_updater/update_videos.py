""" update videos in bulk """

import argparse
import json
import logging
import re
import sys
import typing

import arrow
import jinja2
import Levenshtein
import unidecode

from . import youtube

LOGGER = logging.getLogger(__name__)

TITLE_PATH = ('snippet', 'title')
YTID_PATH = ('contentDetails', 'videoId')


def get_options(*args):
    """ Set options for the CLI """
    parser = argparse.ArgumentParser("update_videos")
    parser.add_argument("playlist_json", help="YouTube playlist JSON")
    parser.add_argument("album_json", help="Bandcrash JSON file for the album")
    parser.add_argument("--date", "-d", type=str,
                        help="Scheduled release date", default=None)
    parser.add_argument("--date-incr", type=int,
                        help="Track-number date increment, in seconds", default=60)
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Don't execute the update", default=False)
    parser.add_argument("--description", "-D", type=str,
                        help="Jinja2 template for the description", default=None)
    parser.add_argument("--max-distance", "-l", type=int,
                        help="Maximum Levenshtein distance for title reconciliation", default=5)
    parser.add_argument("--input-title", type=str, help="Format for the playlist's video title",
                        default="{tnum:02} {filename}")
    parser.add_argument("--output-title", type=str, help="Format for the updated title",
                        default="{title}")

    youtube.add_arguments(parser)

    return parser.parse_args(*args)


def slugify_filename(fname: str) -> str:
    """ Generate a safe filename """

    # remove control characters
    fname = fname.translate(dict.fromkeys(range(32)))

    # translate unicode to ascii
    fname = unidecode.unidecode(fname)

    # collapse/convert whitespace
    fname = ' '.join(fname.split())

    # convert runs of problematic characters to -
    fname = re.sub(r'[\-\$/\\:\<\>\*\"\|&]+', '-', fname)

    return fname


def get_value(item, path, default=None):
    """ Get a value from a JSON dictionary """
    for key in path:
        if not isinstance(item, dict) or not key in item:
            return default
        item = item[key]
    return item


def match_item(options, item, tracks) -> typing.Tuple[int, dict]:
    """ Build an update for a single item based on the tracks """
    best_track: typing.Tuple[int, dict] = (0, {})
    best_distance = None
    best_title = None

    item_title = get_value(item, TITLE_PATH).casefold()
    for idx, track in tracks:
        filename = slugify_filename(track.get('title', ''))
        check_title = options.input_title.format(tnum=idx,
                                                 title=track.get('title', ''),
                                                 filename=filename.casefold())
        distance = Levenshtein.distance(item_title, check_title)
        if best_distance is None or distance < best_distance:
            best_track = (idx, track)
            best_distance = distance
            best_title = check_title

    if best_distance > options.max_distance:
        LOGGER.warning("%s (%s): Best match has distance of %d (%s), not updating",
                       get_value(item, YTID_PATH), item_title, best_distance, best_title)
        return (0, {})

    return best_track


def make_item_update(options, template, item, idx, track, album) -> typing.Tuple[str, dict]:
    """ Build an item update """
    # pylint:disable=too-many-arguments,too-many-positional-arguments,too-many-locals

    LOGGER.debug("===== Building update for %s (%s)",
                 item['id'], item['snippet']['title'])

    update = {
        'id': item['id']
    }

    parts = set()

    snippet = item['snippet']

    title = options.output_title.format(tnum=idx, title=track['title']).strip()
    if title != snippet.get('title'):
        LOGGER.debug("----- Updating title:\nold: %s\nnew: %s",
                     snippet['title'], title)

        parts.add('snippet')
        snippet['title'] = title

    if template:
        description = template.render(
            album=album, tnum=idx, track=track, item=item).strip()
        if description != snippet.get('description'):
            LOGGER.debug("----- Updating description:\n### OLD \n%s\n### NEW\n%s",
                         snippet.get('description'),
                         description)

            parts.add('snippet')
            snippet['description'] = description

    if 'snippet' in parts:
        update['snippet'] = snippet

    status = item['status']

    if options.date and status['privacyStatus'] in ('private', 'draft'):
        pub_date = arrow.get(options.date).shift(
            seconds=(idx - 1)*options.date_incr)
        LOGGER.debug("----- Scheduling for %s (%s)",
                     pub_date.format(), pub_date.humanize())
        parts.add('status')
        status['privacyStatus'] = 'private'
        status['publishAt'] = pub_date.to(
            'UTC').isoformat().replace('+00:00', 'Z')

    if 'status' in parts:
        update['status'] = status

    return ','.join(parts), update


def cleanup_filter(text: str) -> str:
    """ Clean up common turds that sneak into descriptions """

    # Limit spans of newlines to two
    text = re.sub(r'\n\n+', r'\n\n', text)

    # Convert Markdown-style links into plaintext ones
    text = re.sub(r'\[([^\]]*)\]\(', r'\1 (', text)

    return text


def get_template(path) -> typing.Optional[jinja2.Template]:
    """ Load the description template """
    if not path:
        return None

    env = jinja2.Environment()

    env.filters['cleanup'] = cleanup_filter

    with open(path, 'r', encoding='utf-8') as file:
        return env.from_string(file.read())


def update_callback(request_id, response, exception):
    """ Retrieve batch update status """
    if exception is not None:
        LOGGER.warning("Got error on request_id %s: %s", request_id, exception)
    else:
        LOGGER.info("Successfully updated video %s: %s",
                    request_id, json.dumps(response, indent=3))


def get_video_details(client, fetch_ids: list[str]) -> dict[str, dict]:
    """ Get the current information for all of the videos in the playlist """
    details: dict[str, dict] = {}

    for pos in range(0, len(fetch_ids), 50):
        chunk = fetch_ids[pos:pos+50]
        LOGGER.debug("Retrieving chunk %d [%s]", pos, chunk)
        request = client.videos().list(part='snippet,status,contentDetails',
                                       id=','.join(chunk))
        response = request.execute()
        for item in response['items']:
            LOGGER.debug("%s", json.dumps(item, indent=3))
            details[item['id']] = item

    return details


def update_playlist(options, client) -> None:
    """ Update process """
    # pylint:disable=too-many-locals

    with open(options.playlist_json, "r", encoding="utf-8") as file:
        playlist = json.load(file)

    with open(options.album_json, "r", encoding="utf-8") as file:
        album = json.load(file)

    tracks: typing.List[typing.Tuple[int, dict]] = [
        *enumerate(typing.cast(typing.List[dict], album.get('tracks', [])), start=1)]

    # Match all of the playlist items to their album tracks
    matches = [(item, *match_item(options, item, tracks)) for item in playlist]

    # Filter out the non-matching items
    matches = [(item, idx, track) for item, idx, track in matches if track]

    # Update the playlist items with their current details
    LOGGER.info("##### Updating playlist content (%d items)", len(matches))
    current_data = get_video_details(client, [item['contentDetails']['videoId']
                                              for item, _, _ in matches])

    # Update the playlist data with the current retrieved data; this converts
    # the items into a video rather than a playlistItem, so from now on the video
    # ID is in item['id']
    for item, _, _ in matches:
        item.update(**current_data[item['contentDetails']['videoId']])

    LOGGER.info("##### Current playlist data: %s",
                json.dumps(matches, indent=3))

    template = get_template(options.description)

    def send_batch(updates):
        batch = client.new_batch_http_request(callback=update_callback)
        for part, body in updates:
            if part:
                batch.add(client.videos().update(part=part, body=body))
        LOGGER.info("Sending %d updates...", len(updates))
        batch.execute()
        LOGGER.info("Updates submitted")

    updates = [
        make_item_update(options, template, item, idx, track, album)
        for item, idx, track in matches
    ]
    LOGGER.info("##### Updates: %s", json.dumps(updates, indent=3))
    if updates and not options.dry_run:
        send_batch(updates)
    else:
        print("##### Updates #####")
        print(json.dumps(updates, indent=3))


def main():
    """ entry point """
    options = get_options()

    if options.date and arrow.get(options.date) < arrow.get():
        sys.exit(f"Scheduled date ({arrow.get(options.date)}) is in the past!")

    client = youtube.get_client(options)
    update_playlist(options, client)


if __name__ == "__main__":
    main()
