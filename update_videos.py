""" update videos in bulk """

import youtube
import argparse

def get_options(*args):
    """ Set options for the CLI """
    parser = argparse.ArgumentParser("update_videos")
    parser.add_argument("album_json", help="Bandcrash JSON file for the album")
    parser.add_argument("playlist_json", help="YouTube playlist JSON")
    parser.add_argument("--date", type=str, help="Scheduled release date", default=None)
    parser.add_argument("--dry-run", "-n", type=bool, action="store_true", help="Don't execute the update", default=False)
    parser.add_argument("--template", "-D", type=str, help="Jinja2 template for the description", default=None)



def update_video_description(youtube, video_id, new_description):
    try:
        # Retrieve the existing video details to get the current snippet
        # This is important because videos.update replaces the entire snippet
        response = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()

        if not response['items']:
            print(f"Video with ID {video_id} not found.")
            return

        video_snippet = response['items'][0]['snippet']
        video_snippet['description'] = new_description

        # Update the video
        request = youtube.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": video_snippet
            }
        )
        response = request.execute()
        print(f"Video description updated for video ID: {video_id}")
        print(f"New description: {response['snippet']['description']}")

    except googleapiclient.errors.HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()


    youtube = get_authenticated_service()
    # Replace with your video ID and desired new description
    video_to_update = "YOUR_VIDEO_ID"
    updated_desc = "This is my new updated video description from my Python app!"
    update_video_description(youtube, video_to_update, updated_desc)
