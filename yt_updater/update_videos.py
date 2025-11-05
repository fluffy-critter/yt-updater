""" update videos in bulk """

import argparse
import json
import logging
import re
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
    parser.add_argument("--date", type=str,
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


def make_snippet_update(options, template, item, idx, track, album) -> dict:
    """ Build snippet update """
    # pylint:disable=too-many-arguments,too-many-positional-arguments

    ytid = item['id']

    snippet = item['snippet']

    snippet['title'] = options.output_title.format(
        tnum=idx, title=track['title'])

    if template:
        snippet['description'] = template.render(
            album=album, tnum=idx, track=track, item=item)

    return {
        'id': ytid,
        'snippet': snippet
    }


def make_schedule_update(options, item, idx) -> dict:
    """ build an update to schedule a video """
    status = item['status']

    pub_date = arrow.get(options.date).shift(
        seconds=(idx - 1)*options.date_incr).to('UTC')
    status['publishAt'] = pub_date.isoformat().replace('+00:00', 'Z')
    return {
        'id': item['id'],
        'status': status
    }


def get_template(options) -> typing.Optional[jinja2.Template]:
    """ Load the description template """
    if not options.description:
        return None

    env = jinja2.Environment()
    with open(options.description, 'r', encoding='utf-8') as file:
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

    template = get_template(options)

    def send_batch(updates, part):
        batch = client.new_batch_http_request(callback=update_callback)
        for body in updates:
            batch.add(client.videos().update(part=part, body=body))
        LOGGER.info("Sending %d updates...", len(updates))
        batch.execute()
        LOGGER.info("Updates submitted")

    snippets = [
        make_snippet_update(options, template, item, idx, track, album)
        for item, idx, track in matches
    ]
    LOGGER.info("##### Snippet updates: %s", json.dumps(snippets, indent=3))
    if snippets and not options.dry_run:
        send_batch(snippets, 'snippet')
    else:
        print("##### Snippets #####")
        print(json.dumps(snippets, indent=3))

    if options.date:
        statuses = [
            make_schedule_update(options, item, idx) for item, idx, _ in matches
            if item['status']['privacyStatus'] == 'private'
        ]
        LOGGER.info("##### Schedule updates: %s",
                    json.dumps(statuses, indent=3))
        if statuses and not options.dry_run:
            send_batch(statuses, 'status')
        else:
            print("##### Statuses #####")
            print(json.dumps(statuses, indent=3))


def main():
    """ entry point """
    options = get_options()
    client = youtube.get_client(options)
    update_playlist(options, client)


if __name__ == "__main__":
    main()
