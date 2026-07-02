from pathlib import Path
from tempfile import TemporaryDirectory

import yt_dlp
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from backend.recognizer import SongRecognizer
from backend.microphone import record_microphone_clip
from backend.db import DBManager
from backend.main import fingerprint_file
from scripts.serve_web import get_lan_ip, open_lan


class RecognitionWorker(QThread):
    result_ready = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, db_path: str | Path, mode: str, wav_path: str | None = None):
        super().__init__()
        self.db_path = db_path
        self.mode = mode
        self.wav_path = wav_path

    def run(self):
        temp_path: Path | None = None
        try:
            if self.mode == "microphone":
                temp_path = record_microphone_clip()
                source_path = temp_path
                source_label = "microphone recording"
            elif self.wav_path is not None:
                source_path = self.wav_path
                source_label = f"loaded {self.wav_path}"
            else:
                raise RuntimeError("No audio source was selected.")

            recognizer = SongRecognizer(self.db_path)
            candidates = recognizer.recognize_file(source_path)
            self.result_ready.emit(candidates, source_label)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


class ServerThread(QThread):
    server_started = pyqtSignal(str)

    def run(self):
        self.server_started.emit(f"https://{get_lan_ip()}:8443")
        open_lan()


class YouTubeSearchWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 8):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(
                    f"ytsearch{self.limit}:{self.query}",
                    download=False,
                )

            results = []
            for entry in data.get("entries", []):
                if not entry:
                    continue
                video_id = entry.get("id")
                url = entry.get("url") or entry.get("webpage_url")
                if video_id:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                results.append(
                    {
                        "title": entry.get("title"),
                        "artist": entry.get("uploader"),
                        "duration": entry.get("duration"),
                        "webpage_url": url,
                    }
                )
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class YouTubeStreamWorker(QObject):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, result: dict):
        super().__init__()
        self.result = result

    def run(self):
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(self.result["webpage_url"], download=False)

            stream_url = data.get("url")
            if not stream_url and data.get("formats"):
                stream_url = data["formats"][-1].get("url")
            if not stream_url:
                print("error with the url")

            resolved = dict(self.result)
            resolved["stream_url"] = stream_url
            self.finished.emit(resolved)
        except Exception as exc:
            self.failed.emit(str(exc))


class PlaylistDownloadWorker(QThread):
    result_ready = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, tracks: list[dict], destination: str | Path):
        super().__init__()
        self.tracks = tracks
        self.destination = Path(destination)

    def run(self):
        try:
            options = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
                "noplaylist": True,
                "outtmpl": str(self.destination / "%(title)s [%(id)s].%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",
                    }
                ],
                "postprocessor_args": {"ffmpeg": ["-ac", "1"]},
            }
            urls = [track["webpage_url"] for track in self.tracks]
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download(urls)
            self.result_ready.emit(f"Downloaded {len(urls)} songs.")
        except Exception as exc:
            self.failed.emit(str(exc))


class PlaylistFingerprintWorker(QThread):
    result_ready = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, tracks: list[dict], db_path: str):
        super().__init__()
        self.tracks = tracks
        self.db_path = db_path

    def run(self):
        try:
            db = DBManager(self.db_path)
            with TemporaryDirectory() as dir:
                temp_dir = Path(dir)
                for index, track in enumerate(self.tracks):
                    output_base = temp_dir / f"track_{index}"
                    options = {
                        "quiet": True,
                        "no_warnings": True,
                        "format": "bestaudio/best",
                        "noplaylist": True,
                        "outtmpl": f"{output_base}.%(ext)s",
                        "postprocessors": [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "wav",
                            }
                        ],
                        "postprocessor_args": {"ffmpeg": ["-ac", "1"]},
                    }
                    with yt_dlp.YoutubeDL(options) as downloader:
                        downloader.download([track["webpage_url"]])

                    song_id = track["webpage_url"]
                    hashes = fingerprint_file(output_base.with_suffix(".wav"), song_id)
                    db.replace_hashes(song_id, hashes)

            self.result_ready.emit(f"Fingerprinted {len(self.tracks)} songs.")
        except Exception as exc:
            self.failed.emit(str(exc))
