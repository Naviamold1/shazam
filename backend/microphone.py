import sys
import shutil
import subprocess
import sounddevice as sd
from scipy.io import wavfile
from tempfile import NamedTemporaryFile
from pathlib import Path


def record_microphone_clip(duration_seconds: float = 6.0, sample_rate: int = 44_100):
    frames = int(duration_seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()

    with NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    wavfile.write(temp_path, sample_rate, recording)
    return temp_path


def _get_ffmpeg():
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    ext = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    bundled_path = Path(__file__).parent / "bin" / ext
    return str(bundled_path)


def _handle_recorded_audio(
    recording: bytes,
):
    data = bytes(recording)
    if data.startswith(b"RIFF"):
        with NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(data)
        return Path(temp_file.name)

    with NamedTemporaryFile(suffix=".webm", delete=False) as temp_input:
        temp_input_path = Path(temp_input.name)
        temp_input.write(data)

    ffmpeg = _get_ffmpeg()
    if ffmpeg is None:
        temp_input_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg is required")

    with NamedTemporaryFile(suffix=".wav", delete=False) as temp_output:
        temp_output_path = Path(temp_output.name)

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
        print(f"Could not decode the recording: {err}")

    temp_input_path.unlink(missing_ok=True)
    return temp_output_path
