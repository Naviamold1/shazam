from backend.recognizer import SongCandidate
from backend.web import _candidate_to_json


def test_candidate_to_json_exposes_public_match_fields():
    candidate = SongCandidate(
        song_id="song-1",
        title="A song",
        db_time=1_250,
        recording_time=250,
        offset=1_000,
        votes=7,
        confidence=87.5,
    )

    assert _candidate_to_json(candidate) == {
        "song_id": "song-1",
        "title": "A song",
        "votes": 7,
        "confidence": 87.5,
        "offset": 1_000,
    }
