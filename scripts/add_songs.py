from backend.db import DBManager
from backend.main import fingerprint_file
import os
import yt_dlp


def get_song_urls():
    with open("backend/scripts/list.txt", "r") as f:
        data = f.read().splitlines()
    return data


def download_songs(songs):
    ydl_opts = {
        # Extract audio only
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "outtmpl": "assets/%(playlist)s/%(id)s`%(title)s.%(ext)s",
        # Explicitly allow downloading the whole playlist
        "noplaylist": False,
        # Continue downloading remaining videos if one fails
        "ignoreerrors": True,
        # mono
        "postprocessor_args": {"ffmpeg": ["-ac", "1"]},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(songs)


# download_songs(
#     ["https://www.youtube.com/playlist?list=PL1tiBqitg38_Rsqb2qiTvm3hKX2Y2qUgg"]
# )


def fingerprint_files():
    songs_ids = []
    hashes = []
    num = 0
    for file in os.scandir("assets"):
        num += 1
        songId = file.name.split(" - ")[0]
        songs_ids.append((songId, file.name, None, None))
        hash = fingerprint_file(file.path, songId)
        hashes.extend(hash)
        print(num)

    print(len(hashes))
    db = DBManager()
    db.add_songs(songs_ids)
    db.add_hashes(hashes)
    print("added hashes")
    
    # songs = [x.name for x in os.scandir("assets")]
    # obj.add_songs([(song.name.split(" - ")[0], song.name, None, None)])
    # obj.add_hashes(hash)
    # fingerprint_file((os.scandir("assets")[0]).name)


fingerprint_files()
