""" update videos in bulk """

import argparse
import json
import logging
import re
import typing

import arrow
import jinja2
import Levenshtein
import pytimeparse
import unidecode

from . import youtube

LOGGER = logging.getLogger(__name__)

TITLE_PATH = ('snippet', 'title')
YTID_PATH = ('contentDetails', 'videoId')

PlaylistItem = typing.Tuple[str, str]
Playlist = typing.List[PlaylistItem]
MatchItem = typing.Tuple[str, int, dict]
MatchList = typing.List[MatchItem]
DetailList = typing.Dict[str, dict]
IndexedTrackList = typing.List[typing.Tuple[int, dict]]


def get_options(*args):
    """ Set options for the CLI """
    parser = argparse.ArgumentParser("update_videos")
    parser.add_argument("playlist_json", help="YouTube playlist JSON")
    parser.add_argument("album_json", help="Bandcrash JSON file for the album")
    parser.add_argument("--date", "-d", type=str,
                        help="Scheduled release date", default=None)
    parser.add_argument("--date-incr", type=str,
                        help="Time between track updates", default="15m")
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


def read_playlist(playlist_path):
    """ Given a path to a playlist JSON file, return a list of (ytid, upload_title) """
    with open(playlist_path, 'r', encoding='utf-8') as file:
        playlist = json.loads(file.read())

    return [(item['contentDetails']['videoId'], item['snippet']['title']) for item in playlist]


def read_album(album_path):
    """ Given a path to an album spec, return its data """
    with open(album_path, 'r', encoding='utf-8') as file:
        return json.loads(file.read())


def get_value(item, path, default=None):
    """ Get a value from a JSON dictionary """
    for key in path:
        if not isinstance(item, dict) or not key in item:
            return default
        item = item[key]
    return item


def cleanup_filter(text: str) -> str:
    """ Clean up common turds that sneak into descriptions """

    # Limit spans of newlines to two
    text = re.sub(r'\n\n+', r'\n\n', text)

    # Convert Markdown-style links into plaintext ones
    text = re.sub(r'\[([^\]]*)\]\(', r'\1 (', text)

    return text


def load_template(path) -> typing.Optional[jinja2.Template]:
    """ Load the description template """
    if not path:
        return None

    env = jinja2.Environment()

    env.filters['cleanup'] = cleanup_filter

    with open(path, 'r', encoding='utf-8') as file:
        return env.from_string(file.read())


class VideoUpdater:
    """ Encapsulates the video update process """

    def __init__(self, options):
        if options.date:
            self.start_date: typing.Optional[arrow.Arrow] = arrow.get(
                options.date)
            if self.start_date < arrow.get():
                raise ValueError(
                    f"Scheduled date ({arrow.get(options.date)}) is in the past!")

            self.date_incr = pytimeparse.parse(options.date_incr)
            if not self.date_incr:
                try:
                    self.date_incr = int(options.date_incr)
                    LOGGER.warning(
                        "Treating time increment as a value in seconds")
                except ValueError as exc:
                    raise ValueError(
                        f"Don't know how to parse {options.date_incr} as seconds") from exc
        else:
            self.start_date = None
            self.date_incr = 0

        if options.description:
            self.template = load_template(options.description)

        self.match_distance = options.max_distance

        self.upload_title_fmt = options.input_title
        self.output_title_fmt = options.output_title

    def map_tracks(self, playlist, album) -> MatchList:
        """ Given a parsed playlist and an album spec, return a list of (part, body) updates """

        matches = []
        tracks = list(enumerate(album.get('tracks', []), start=1))
        LOGGER.debug("Candidate tracklist: %s", [
                     (idx, track.get('title')) for idx, track in tracks])

        for item in playlist:
            ytid, upload_title = item

            distance, tnum, track = self.best_match(item, tracks)
            LOGGER.debug("best match: %s %s %s", distance, tnum, track)

            if track:
                if distance < self.match_distance:
                    LOGGER.info("Best match for %s[%s]: %d. %s (Distance = %d)",
                                ytid, upload_title, tnum, track.get('title'), distance)
                    matches.append((ytid, tnum, track))
                else:
                    LOGGER.warning("%s[%s]: Best match had distance of %d (%s); skipping",
                                   ytid, upload_title, distance, track.get('title'))
            else:
                LOGGER.warning("Could not find match for %s[%s]",
                               ytid, upload_title)

        return matches

    def best_match(self, item: PlaylistItem,
                   tracks: IndexedTrackList) -> typing.Tuple[typing.Optional[int], int, dict]:
        """ Find the best match for a playlist track.
        Returns tuple of (distance,tnum,track) """

        ytid, upload_title = item
        upload_title = upload_title.casefold()
        LOGGER.debug("Matching %s[%s]", ytid, upload_title)

        best_track: typing.Tuple[int, dict] = (0, {})
        best_distance: typing.Optional[int] = None

        for tnum, track in tracks:
            check_title = self.upload_title_fmt.format(
                tnum=tnum,
                title=track.get(
                    'title', '').casefold(),
                filename=slugify_filename(track.get('title', '').casefold()))

            distance = Levenshtein.distance(upload_title, check_title)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_track = (tnum, track)

        tnum, track = best_track
        if best_distance is not None:
            LOGGER.debug("Best match for %s[%s]: %d[%s] (distance=%d)",
                         ytid, upload_title, tnum, track.get('title'), best_distance)
        else:
            LOGGER.warning("No match found for %s[%s]", ytid, upload_title)

        return best_distance, tnum, track

    @staticmethod
    def get_details(client, matches: MatchList) -> DetailList:
        """ Get the current snippets for a matchlist """
        details: dict[str, dict] = {}

        fetch_ids = [ytid for ytid, _, _ in matches]

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

    def make_updates(self, matches: MatchList, details: DetailList, album: dict):
        """ Build the update list """
        updates: typing.List[typing.Tuple[str, dict]] = []

        for ytid, tnum, track in matches:
            part, body = self.build_update(details[ytid], album, tnum, track)
            if part:
                updates.append((part, body))

        return updates

    def build_update(self, video: dict, album: dict, tnum: int, track: dict):
        """ Build an update for a video detail """
        LOGGER.info("Building update for %s (%s)",
                    video['id'], track.get('title', video['snippet']['title']))

        update = {
            'id': video['id']
        }

        parts = set()

        snippet = video['snippet']

        title = self.output_title_fmt.format(
            tnum=tnum, title=track['title']).strip()
        if title != video.get('title'):
            LOGGER.info("Changed title: %s -> %s", snippet['title'], title)

            parts.add('snippet')
            snippet['title'] = title

        if self.template:
            description = self.template.render(
                album=album, tnum=tnum, track=track, video=video).strip()
            if description != snippet.get('description'):
                LOGGER.info("Updated description")
                LOGGER.debug("----- OLD\n%s\n----- NEW\n%s",
                             snippet.get('description'),
                             description)

                parts.add('snippet')
                snippet['description'] = description

        if 'snippet' in parts:
            update['snippet'] = snippet

        status = video['status']

        if self.start_date is not None:
            pub_date = self.start_date.shift(seconds=tnum*self.date_incr)

            if status['privacyStatus'] == 'public':
                LOGGER.info("Not scheduling update for public video")
            elif status['privacyStatus'] != 'private' or arrow.get(status['publishAt']) != pub_date:
                LOGGER.info("Scheduling update for %s (%s)",
                            pub_date, pub_date.humanize())

            parts.add('status')
            status['privacyStatus'] = 'private'
            status['publishAt'] = pub_date.to(
                'UTC').isoformat().replace('+00:00', 'Z')

        if 'status' in parts:
            update['status'] = status

        return ','.join(parts), update


def update_callback(request_id, response, exception):
    """ Retrieve batch update status """
    if exception is not None:
        LOGGER.warning("Got error on request_id %s: %s", request_id, exception)
    else:
        LOGGER.info("Successfully updated video %s: %s",
                    request_id, json.dumps(response, indent=3))


def send_updates(client, updates):
    """ Send a batch of video updates """
    batch = client.new_batch_http_request(callback=update_callback)
    for part, body in updates:
        batch.add(client.videos().update(part=part, body=body))

    LOGGER.info("Sending %d updates...", len(updates))
    batch.execute()
    LOGGER.info("Updates submitted")


def main():
    """ entry point """
    options = get_options()
    client = youtube.get_client(options)

    playlist = read_playlist(options.playlist_json)
    album = read_album(options.album_json)

    updater = VideoUpdater(options)

    matches = updater.map_tracks(playlist, album)
    LOGGER.info("Matched %d/%d playlist tracks", len(matches), len(playlist))

    details = updater.get_details(client, matches)

    updates = updater.make_updates(matches, details, album)

    if options.dry_run:
        print(json.dumps(updates, indent=3))
    else:
        send_updates(client, updates)


if __name__ == "__main__":
    main()
