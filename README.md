# yt_updater

Useful tools for bulk-updating YouTube playlists and scheduling publication en masse

## Setup

### Installation

I recommend installing this in one of a few ways:

* **poetry sandbox**: Clone the repo, install [poetry](https://python-poetry.org), and then run `make install`; after this you can run the scripts with e.g. `poetry run getPlaylist` or `poetry run getVideos` from within the source directory.

* **venv sandbox**: Create a [virtualenv](https://docs.python.org/3/library/venv.html) and, after activating it, run `pip install yt_updater`

* **pipx install** (less recommended): Using [pipx](https://pipx.pypa.io/) install this as `yt_updater` and it will appear in your global path

### Configuration

You will need to create an application for the [YouTube Data API](https://developers.google.com/youtube/v3). See the [getting started guide](https://developers.google.com/youtube/v3/getting-started) for more information.

You'll need to create an OAuth 2.0 client set as a "Desktop app." After creating an OAuth 2.0 client, download its client data and save it as `client.json` or the like. If you need multiple registered apps for some reason, you can specify your client file with the `--client-json` option.

When you first use the application, it will prompt you to log in and grant access to your channel. If you want to switch between multiple channels, you can specify different login tokens with the `--login-token` option (the specified file will be created if it doesn't yet exist).

Also note that if you register the application as a test application, you'll need to add your Google account to the allow list.

## Usage

1. Upload all of your track videos as drafts, and bulk-add them to a playlist (which can remain private) and set their video category.

2. Run `getPlaylist playlist_id > playlist.json` to generate your playlist JSON

3. Run `updateVideos -n playlist.json album.json` to see what changes the script will make; remove the `-n` and run again if you approve. `updateVideos --help` will give you a bunch more useful options for things like generating video descriptions, scheduling the videos' publications (with an optional inter-track time offset to make the playlist management a little easier or even letting you stagger them by minutes/hours/etc.) and so on.

Note that even in `-n` mode this will still make API requests which will drain your daily request quota.

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
* `item`: The original YouTube item data from the playlist file

An example template is in `templates/description.txt`.

## Disclaimer

This software was partially written with the help of Google's AI chatbot, because life's too short to try to wade through Google's incomprehensibly-dense-yet-vague API documentation.

