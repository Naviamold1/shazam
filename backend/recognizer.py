import sys
import shutil
import subprocess
import sounddevice as sd
from scipy.io import wavfile
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
    def __init__(self, db_path: str | Path = "data.db"):
        self.db = DBManager(db_path)

    def recognize_file(self, path: str | Path, limit: int = 5) -> list[SongCandidate]:
        hashes = fingerprint_file(path, None)
        if not hashes or limit <= 0:
            return []

        matches = {}
        titles = {}

        # SeekTune looks up every fingerprint and keeps all matching time pairs.
        for address, recording_time in hashes:
            rows = self.db.conn.execute(
                """
                SELECT h.song_id, s.song_name, h.time
                FROM hashes h
                JOIN songs s ON s.id = h.song_id
                WHERE h.hash = ?
                """,
                (address,),
            )
            for song_id, title, db_time in rows:
                song_id = str(song_id)
                titles[song_id] = str(title)
                matches.setdefault(song_id, []).append(
                    (int(recording_time), int(db_time))
                )

        candidates = []
        for song_id, time_pairs in matches.items():
            offset_buckets = {}
            for recording_time, db_time in time_pairs:
                offset = db_time - recording_time
                bucket = int(offset / 100)
                offset_buckets.setdefault(bucket, []).append(
                    (recording_time, db_time)
                )

            winning_pairs = max(offset_buckets.values(), key=len)
            recording_time, db_time = min(winning_pairs, key=lambda pair: pair[1])
            candidates.append(
                SongCandidate(
                    song_id=song_id,
                    title=titles[song_id],
                    db_time=db_time,
                    recording_time=recording_time,
                    offset=db_time - recording_time,
                    votes=len(winning_pairs),
                    confidence=0.0,
                )
            )

        candidates.sort(key=lambda candidate: candidate.votes, reverse=True)
        candidates = candidates[:limit]
        if not candidates:
            return []

        strongest_vote_count = candidates[0].votes
        return [
            SongCandidate(
                song_id=candidate.song_id,
                title=candidate.title,
                db_time=candidate.db_time,
                recording_time=candidate.recording_time,
                offset=candidate.offset,
                votes=candidate.votes,
                confidence=(candidate.votes / strongest_vote_count) * 100.0,
            )
            for candidate in candidates
        ]


def record_microphone_clip(
    duration_seconds: float = 6.0, sample_rate: int = 44_100
) -> Path:
    frames = int(duration_seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()

    temp_file = NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    wavfile.write(temp_path, sample_rate, recording)
    return temp_path


def _get_ffmpeg() -> str | None:
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    ext = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    bundled_path = Path(__file__).parent / "bin" / ext
    return str(bundled_path)


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
    except subprocess.CalledProcessError as err:
        temp_input_path.unlink(missing_ok=True)
        temp_output_path.unlink(missing_ok=True)
        raise RuntimeError(f"Could not decode the recording: {err}")

    temp_input_path.unlink(missing_ok=True)
    return temp_output_path
