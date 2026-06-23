import sounddevice as sd

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO

import numpy as np
from scipy.io import wavfile

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

    return _handle_recorded_audio(recording, sample_rate)


def _handle_recorded_audio(
    recording: np.ndarray | bytes | bytearray | memoryview | BinaryIO,
    sample_rate: int = 44_100,
) -> Path:
    if isinstance(recording, bytes | bytearray | memoryview):
        data = bytes(recording)
        if not data.startswith(b"RIFF"):
            raise ValueError("Expected WAV bytes from the websocket recording.")

        temp_file = NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = Path(temp_file.name)
        with temp_file:
            temp_file.write(data)
        return temp_path

    if hasattr(recording, "read"):
        return _handle_recorded_audio(recording.read(), sample_rate)

    audio = np.squeeze(recording)
    audio = np.clip(audio, -1.0, 1.0)
    pcm_audio = (audio * np.iinfo(np.int16).max).astype(np.int16)

    temp_file = NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    wavfile.write(temp_path, sample_rate, pcm_audio)
    return temp_path
