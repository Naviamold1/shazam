from pathlib import Path

import yt_dlp
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from backend.recognizer import SongRecognizer, record_microphone_clip
from scripts.serve_web import get_lan_ip, open_lan


class RecognitionWorker(QObject):
    finished = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, db_path: Path, mode: str, wav_path: Path | None = None):
        super().__init__()
        self.db_path = db_path
        self.mode = mode
        self.wav_path = wav_path

    def run(self) -> None:
        temp_path: Path | None = None
        try:
            if self.mode == "microphone":
                temp_path = record_microphone_clip()
                source_path = temp_path
                source_label = "microphone recording"
            elif self.wav_path is not None:
                source_path = self.wav_path
                source_label = self.wav_path.name
            else:
                raise RuntimeError("No audio source was selected.")

            recognizer = SongRecognizer(self.db_path)
            self.finished.emit(recognizer.recognize_file(source_path), source_label)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


class ServerThread(QThread):
    server_started = pyqtSignal(str)

    def run(self) -> None:
        self.server_started.emit(f"https://{get_lan_ip()}:8443")
        open_lan()


class YouTubeSearchWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 8):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self) -> None:
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
                video_id = entry.get("id") or ""
                url = entry.get("url") or entry.get("webpage_url") or ""
                if video_id and not str(url).startswith("http"):
                    url = f"https://www.youtube.com/watch?v={video_id}"
                results.append(
                    {
                        "title": entry.get("title") or "Untitled",
                        "artist": entry.get("uploader") or "YouTube",
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

    def run(self) -> None:
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
                raise RuntimeError("Could not resolve an audio stream for this video.")

            resolved = dict(self.result)
            resolved["stream_url"] = stream_url
            self.finished.emit(resolved)
        except Exception as exc:
            self.failed.emit(str(exc))
