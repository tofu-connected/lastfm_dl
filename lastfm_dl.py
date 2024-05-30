#
# Save loved last.fm tracks as tagged mp3's!
# Dependencies: pylast requests pytube mutagen pillow
# ffmpeg must be installed in the system!
#
# DISCLAIMER: It takes the first result from YouTube search so it often gets it wrong. Check your audio!
#
import os
import pylast
import requests
import re
from pytube import YouTube
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from mutagen.mp3 import MP3
from io import BytesIO
from PIL import Image
import subprocess
import difflib
import shutil
from datetime import datetime

LASTFM_API_KEY = "YOUR_LASTFM_API_KEY"
LASTFM_API_SECRET = "YOUR_LASTFM_API_SHARED_SECRET"
LASTFM_USERNAME = "LASTFM_USERNAME"
DL_DIR = "lastfm_dl"
MAX_LENGTH = 600
FROM_DATE = "01-01-1900"

def search_youtube_link(search_query):
    url = f"https://www.youtube.com/results?search_query={search_query}"
    response = requests.get(url)
    if response.status_code == 200:
        video_ids = re.findall(r'\"url\":\"\/watch\?v=(.{11})', response.text)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
    return None


def write_mp3_tags(filename, artist_name, track_name, thumbnail_data):
    audio = MP3(filename, ID3=ID3)

    audio.tags.add(TPE1(encoding=3, text=[artist_name]))
    audio.tags.add(TIT2(encoding=3, text=[track_name]))

    thumbnail = Image.open(thumbnail_data)
    thumbnail = thumbnail.resize(
        (500, 500), Image.LANCZOS)
    thumbnail = thumbnail.crop((0, 0, 500, 500))
    thumbnail_bytes = BytesIO()
    thumbnail.save(thumbnail_bytes, format='PNG')
    thumbnail_bytes = thumbnail_bytes.getvalue()
    audio.tags.add(APIC(3, 'image/png', 3, 'cover', thumbnail_bytes))

    audio.save()

def is_processed(artist_name: str, track_name: str):
    for file in os.listdir(DL_DIR):
        if file.endswith(".mp3"):
            mp3 = MP3(f"{DL_DIR}\\{file}", ID3=ID3)
            if "TPE1" in mp3.tags and mp3.tags["TPE1"].text[0] == artist_name and "TIT2" in mp3.tags and mp3.tags["TIT2"][0] == track_name:
               return True 
    return False


def main():
    if not shutil.which("ffmpeg"):
        raise Exception("ffmpeg not found!")

    network = pylast.LastFMNetwork(
        api_key=LASTFM_API_KEY,
        api_secret=LASTFM_API_SECRET
    )
    user = network.get_user(LASTFM_USERNAME)

    loved_tracks = user.get_loved_tracks(limit=None)

    from_date = datetime.strptime(FROM_DATE, '%d-%m-%Y')
    loved_tracks = [track for track in loved_tracks if datetime.strptime(track.date, '%d %b %Y, %H:%M') >= from_date]

    for i, track in enumerate(loved_tracks):
        artist_name = track.track.artist.name
        track_name = track.track.title

        progress = f"{i+1}/{len(loved_tracks)}"

        if is_processed(artist_name, track_name):
            print(f"⏩ {progress} Skipped: {artist_name} - {track_name}")
            continue

        search_query = f"{track_name} {artist_name}"

        youtube_link = search_youtube_link(search_query)

        if youtube_link:
            yt = YouTube(youtube_link)

            video_title = yt.title

            if yt.length > MAX_LENGTH:
                print(f"❌ {progress} Maximum length exceeded. Searched '{track_name} {artist_name}', found '{video_title}'")
                continue

            audio = sorted(yt.streams.filter(type="audio"), key=lambda s: int(
                str(s.abr).rstrip("kbps")), reverse=True
            )[0]

            filename = video_title
            filename = "".join(
                [x if x not in "\\/:?\"<>|*" else "_" for x in filename]
            )
            filename = f"{DL_DIR}\\{filename}"
            filename_mp3 = f"{filename}.mp3"

            if not os.path.exists(DL_DIR):
                os.makedirs(DL_DIR)

            audio.download(output_path=".", filename=filename)

            if audio.audio_codec in ["opus", "mp4a.40.2"]:
                command = ["ffmpeg", "-i", filename, "-vn", "-ar", "44100", "-ac", "2", "-b:a",
                           "160k", "-f", "mp3", filename_mp3, "-y", "-hide_banner", "-loglevel", "error"]
                subprocess.call(command, shell=True)
                os.remove(filename)

                matcher = difflib.SequenceMatcher(
                    None, search_query.lower(), video_title.lower())
                diff_ratio = matcher.ratio()

                print(
                    f"{'✅' if diff_ratio > 0.3 else '🤔'} {progress} Searched '{track_name} {artist_name}', found '{video_title}' (similarity {round(diff_ratio, 2)})   Converted [{audio.audio_codec}, {audio.abr}] to [mp3, 160kbps]")
            else:
                print(f"❓ {progress} Unknown audio codec: {audio.audio_codec}")
                continue

            thumbnail_data = requests.get(yt.thumbnail_url, stream=True)
            thumbnail_data.raw.decode_content = True

            write_mp3_tags(filename_mp3, artist_name,
                           track_name, thumbnail_data.raw)
        else:
            print(f"❌ {progress} No YouTube video found for '{artist_name} - {track_name}'")


if __name__ == "__main__":
    main()
