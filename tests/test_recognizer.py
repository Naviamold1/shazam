import pytest

from backend.recognizer import SongCandidate, SongRecognizer


def test_recognize_file_ranks_consistent_offsets_and_sets_confidence(
    monkeypatch,
    tmp_path,
):
    recognizer = SongRecognizer(tmp_path / "recognizer.db")
    recognizer.db.add_songs(
        [
            ("song-a", "Best match", "Artist A", None),
            ("song-b", "Weaker match", "Artist B", None),
        ]
    )
    recognizer.db.add_hashes(
        [
            ("hash-1", 1_000, "song-a"),
            ("hash-2", 1_100, "song-a"),
            ("hash-3", 1_200, "song-a"),
            ("hash-1", 500, "song-b"),
            ("hash-2", 600, "song-b"),
        ]
    )
    monkeypatch.setattr(
        "backend.recognizer.fingerprint_file",
        lambda path, song_id: [
            ("hash-1", 200),
            ("hash-2", 300),
            ("hash-3", 400),
        ],
    )

    candidates = recognizer.recognize_file("clip.wav")

    assert candidates == [
        SongCandidate(
            song_id="song-a",
            title="Best match",
            db_time=1_000,
            recording_time=200,
            offset=800,
            votes=3,
            confidence=100.0,
        ),
        SongCandidate(
            song_id="song-b",
            title="Weaker match",
            db_time=500,
            recording_time=200,
            offset=300,
            votes=2,
            confidence=pytest.approx(200 / 3),
        ),
    ]


@pytest.mark.parametrize("hashes, limit", [([], 5), ([("hash", 0)], 0)])
def test_recognize_file_returns_no_candidates_without_work(
    monkeypatch,
    tmp_path,
    hashes,
    limit,
):
    monkeypatch.setattr(
        "backend.recognizer.fingerprint_file",
        lambda path, song_id: hashes,
    )
    recognizer = SongRecognizer(tmp_path / "recognizer.db")

    assert recognizer.recognize_file("clip.wav", limit=limit) == []


def test_recognize_file_respects_candidate_limit(monkeypatch, tmp_path):
    recognizer = SongRecognizer(tmp_path / "recognizer.db")
    recognizer.db.add_songs(
        [
            ("song-a", "Song A", None, None),
            ("song-b", "Song B", None, None),
        ]
    )
    recognizer.db.add_hashes(
        [
            ("shared", 100, "song-a"),
            ("shared", 200, "song-b"),
        ]
    )
    monkeypatch.setattr(
        "backend.recognizer.fingerprint_file",
        lambda path, song_id: [("shared", 0)],
    )

    assert len(recognizer.recognize_file("clip.wav", limit=1)) == 1


def test_song_candidate_is_immutable():
    candidate = SongCandidate("id", "Title", 1, 2, -1, 3, 100.0)

    with pytest.raises(AttributeError):
        candidate.votes = 4
