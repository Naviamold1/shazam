import sys
import shutil
import subprocess
import sounddevice as sd
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from backend.db import DBManager
from backend.main import fingerprint_file


@dataclass(frozen=True)
class SongCandidate:
    song_id: str
    title: str
    db_time: int
    recording_time: int
    offset: int
    votes: int
    confidence: float


class SongRecognizer:
    def __init__(self, db_path: str | Path = "data1.db"):
        self.db = DBManager(db_path)

    def recognize_file(self, path: str | Path, limit: int = 5) -> list[SongCandidate]:
        hashes = fingerprint_file(path, None)
        rows = []
        seen_song_ids = set()
        print(self.db.find_song(hashes))
        for row in self.db.find_song(hashes):
            song_id = str(row[0])
            if song_id in seen_song_ids:
                continue
            seen_song_ids.add(song_id)
            rows.append(row)
            if len(rows) >= limit:
                break

        if not rows:
            return []

        strongest_vote_count = max(int(row[5]) for row in rows) or 1
        return [
            SongCandidate(
                song_id=str(row[0]),
                title=str(row[1]),
                db_time=int(row[2]),
                recording_time=int(row[3]),
                offset=int(row[4]),
                votes=int(row[5]),
                confidence=min(100.0, (int(row[5]) / strongest_vote_count) * 100.0),
            )
            for row in rows
        ]


def record_microphone_clip(
    duration_seconds: float = 6.0, sample_rate: int = 44_100
) -> Path:
    frames = int(duration_seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()

    return _handle_recorded_audio(recording)


def _get_ffmpeg() -> str:
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    ext = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    return str(Path(__file__).parent / "bin" / ext)


def _handle_recorded_audio(
    recording: bytes,
) -> Path:
    data = bytes(recording)
    if data.startswith(b"RIFF"):
        temp_file = NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = Path(temp_file.name)
        with temp_file:
            temp_file.write(data)
        return temp_path

    temp_input = NamedTemporaryFile(suffix=".webm", delete=False)
    temp_input_path = Path(temp_input.name)
    with temp_input:
        temp_input.write(data)

    ffmpeg = _get_ffmpeg()
    if ffmpeg is None:
        temp_input_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg is required to convert websocket audio recordings.")

    temp_output = NamedTemporaryFile(suffix=".wav", delete=False)
    temp_output_path = Path(temp_output.name)
    temp_output.close()

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(temp_input_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "11025",
                str(temp_output_path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        temp_input_path.unlink(missing_ok=True)
        temp_output_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg failed to convert the recording: {exc.stderr.decode(errors='ignore')}"
        ) from exc

    temp_input_path.unlink(missing_ok=True)
    return temp_output_path
