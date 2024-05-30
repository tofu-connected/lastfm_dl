#
# Save loved last.fm tracks as tagged mp3's! 
# Dependencies: pylast requests pytube mutagen pillow
# ffmpeg must be installed in the system!
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

lastfm_api_key = "YOUR_LASTFM_API_KEY"
lastfm_api_secret = "YOUR_LASTFM_API_SHARED_SECRET"
lastfm_username = "LASTFM_USERNAME"

network = pylast.LastFMNetwork(api_key=lastfm_api_key, api_secret=lastfm_api_secret)
user = network.get_user(lastfm_username)

loved_tracks = user.get_loved_tracks(limit=None)

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

    audio.tags.add(TPE1(encoding=3, text=[artist_name]))  # Artist
    audio.tags.add(TIT2(encoding=3, text=[track_name]))   # Track title

    thumbnail = Image.open(thumbnail_data)
    thumbnail = thumbnail.resize((500, 500), Image.LANCZOS)  # Resize to 500x500
    thumbnail = thumbnail.crop((0, 0, 500, 500))  # Crop to square
    thumbnail_bytes = BytesIO()
    thumbnail.save(thumbnail_bytes, format='PNG')
    thumbnail_bytes = thumbnail_bytes.getvalue()
    audio.tags.add(APIC(3, 'image/png', 3, 'Front cover', thumbnail_bytes))

    audio.save()

for i, track in enumerate(loved_tracks):
    artist_name = track.track.artist.name
    track_name = track.track.title
    progress = f"{i+1}/{len(loved_tracks)}"
    filename = f"{artist_name} - {track_name}"
    filename = "".join([x if x not in "\\/:?\"<>|*" else "_" for x in filename])
    filename = f"lastfm_dl\\{filename}"
    filename_mp3 = f"{filename}.mp3"
    if os.path.isfile(filename_mp3):
      print(f"⏩ {progress} Skipped: {filename_mp3}")
      continue

    search_query = f"{track_name} {artist_name}"
    youtube_link = search_youtube_link(search_query)

    if youtube_link:
        yt = YouTube(youtube_link)
        audio = sorted(yt.streams.filter(type="audio"), key=lambda s: int(str(s.abr).rstrip("kbps")), reverse=True)[0]

        video_title = yt.title

        audio.download(output_path=".", filename=filename)

        if audio.audio_codec == "opus":
          command = ["ffmpeg", "-i", filename, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "160k", "-f", "mp3", filename_mp3, "-y", "-hide_banner", "-loglevel", "error"]
          subprocess.call(command,shell=True)
          os.remove(filename)

          matcher = difflib.SequenceMatcher(None, search_query.lower(), video_title.lower())
          diff_ratio = matcher.ratio()

          print(f"{'✅' if diff_ratio > 0.3 else '🤔'} {progress} Searched '{track_name} {artist_name}', found '{video_title}' (similarity {round(diff_ratio, 2)})   Converted [{audio.audio_codec}, {audio.abr}] to [mp3, 160kbps]")
        else:
          print(f"❓{progress} Unknown audio codec: {audio.audio_codec}")
        
        thumbnail_data = requests.get(yt.thumbnail_url, stream=True)
        thumbnail_data.raw.decode_content = True

        write_mp3_tags(filename_mp3, artist_name, track_name, thumbnail_data.raw)
    else:
        print(f"❌ {progress} No YouTube video found for '{artist_name} - {track_name}'")