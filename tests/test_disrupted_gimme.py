from pathlib import Path

from backend.recognizer import SongRecognizer


def test_disrupted_gimme_matches():
    root = Path(__file__).parents[1]
    results = SongRecognizer(root / "data.db").recognize_file(
        root / "tests/disrupted_gimme.wav"
    )

    assert results[0].song_id == "gimme.wav"
