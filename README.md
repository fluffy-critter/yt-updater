# YouTube Updater

Useful tools for bulk-updating YouTube playlists and scheduling publication en masse

## Setup

### Installation

I recommend installing this in one of a few ways:

* **poetry sandbox** (most recommended): Clone this repo, install [poetry](https://python-poetry.org), and then run `make install`; after this you can run the scripts with e.g. `poetry run getPlaylist` or `poetry run getVideos` from within the source directory. This approach will always give you the latest version of the code, with updates a `git pull && poetry install` away.

* **venv sandbox**: Create a [virtualenv](https://docs.python.org/3/library/venv.html) and, after activating it, run `pip install yt-updater`. This will give you the latest "stable" release which may be a bit outdated, but will keep it sandboxed away from the rest of your system.

* **pipx install** (least recommended): Using [pipx](https://pipx.pypa.io/) install this as `yt-updater` and its scripts will appear in your global path. This has the disadvantages of the venv sandbox as well as possibly putting stuff on your global path that you don't want there.

### Configuration

You will need to create an application for the [YouTube Data API](https://developers.google.com/youtube/v3). See the [getting started guide](https://developers.google.com/youtube/v3/getting-started) for more information.

You'll need to create an OAuth 2.0 client set as a "Desktop app." After creating an OAuth 2.0 client, download its client data and save it as `client.json` or the like. If you need multiple registered apps for some reason, you can specify your client file with the `--client-json` option.

When you first use the application, it will prompt you to log in and grant access to your channel. If you want to switch between multiple channels, you can specify different login tokens with the `--login-token` option (the specified file will be created if it doesn't yet exist).

Also note that if you register the application as a test application, you'll need to add your Google account to the allow list.

## Usage

1. Upload all of your track videos as drafts, and bulk-add them to a playlist (which can remain private) and set their video category.

2. Run `getPlaylist playlist_id > playlist.json` to generate your playlist JSON

3. Run `updateVideos -n playlist.json album.json` to see what changes the script will make; remove the `-n` and run again if you approve. `updateVideos --help` will give you a bunch more useful options for things like generating video descriptions, scheduling the videos' publications (with an optional inter-track time offset to make the playlist management a little easier or even letting you stagger them by minutes/hours/etc.) and so on.

Note that even in `-n` mode this will still make API requests which will drain your [daily request quota](#quota-limits).

## Scripts

This package provides the following scripts:

* `getPlaylist`: Given a playlist ID, download the necessary information into a JSON file
* `updateVideos`: Given a playlist JSON file and an album descriptor, update the videos on the playlist with the descriptor.

The album descriptor is a JSON file that contains a property bag with the following properties:

* `tracks`: Maps to an array of track, in the order of the album. Each track is a property bag with the following properties:
    * `title`: The title of the track
    * Other properties as appropriate, e.g. `lyrics`, `description`, etc.

These descriptor files can be created and edited using [Bandcrash](https://fluffy.itch.io/bandcrash).

The title templates are strings which can embed the following template items (as Python formatters):

* `{tnum}`: The track number on the album
* `{title}`: The plaintext title of the track
* `{filename}`: A filename-compatible version of the track title, as slugified by Bandcrash

The description template is a file in [Jinja2](https://jinja.palletsprojects.com/en/stable/) format. When it's run, it's given the following template items:

* `album`: The top-level album descriptor
* `tnum`: The track number on the album
* `track`: The track data from the album descriptor
* `video`: The original YouTube item details

There is also a filter, `cleanup`, which will do some helpful cleanup steps on the generated description.

An example template is in `templates/description.txt`.

## <span id="quota-limits">YouTube API quota limits</span>

By default, YouTube API gives you 10,000 units of work per day. For the purposes of these scripts, they cost the following:

* `getPlaylist`: 1 unit per 50 videos in the playlist
* `updateVideos`: 1 unit per 50 videos in the playlist + 50 units per video when not doing a dry run

The 50-unit per update cost tends to run out very quickly; for example, on a 20-track album, every attempt at updating or scheduling the publication will cost 1001 units (1 for the bulk update request + 20⨉50 for the individual videos), so you only get 9 tries per day to get things the way you want them.

This is also why I have no plans to make a public web-based version of this script.

## Disclaimer

This software was partially written with the help of Google's AI chatbot, because life's too short to try to wade through Google's incomprehensibly-dense-yet-vague API documentation. [I'm not happy about it either](https://beesbuzz.biz/code/16680-On-LLM-based-programming).

