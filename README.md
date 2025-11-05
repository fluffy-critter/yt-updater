# yt_updater

Useful tools for bulk-updating YouTube playlists and scheduling publication en masse

## Usage synopsis

1. Set up a youtube v3 data API app (todo: insert information here) and download the client secrets JSON file.

2. Upload all of your track videos as drafts, and bulk-add them to a playlist (which can remain private) and set their video category.

3. Run `getPlaylist playlist_id > playlist.json` to generate your playlist JSON

4. Run `updateVideos -n playlist.json album.json` to see what changes the script will make; remove the `-n` and run again if you approve. `updateVideos --help` will give you a bunch more useful options for things like generating video descriptions, scheduling the videos' publications (with an optional inter-track time offset to make the playlist management a little easier or even letting you stagger them by minutes/hours/etc.) and so on.

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

