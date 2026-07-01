from backend.db import DBManager


def test_history_returns_newest_entries_and_unknown_artist(tmp_path):
    db = DBManager(tmp_path / "history.db")

    db.add_history_entry("First", None, "https://example.com/first")
    db.add_history_entry("Second", "Artist", "https://example.com/second")

    history = db.get_history()

    assert [entry["title"] for entry in history] == ["Second", "First"]
    assert history[0]["artist"] == "Artist"
    assert history[1]["artist"] == "Unknown artist"
    assert all(entry["played_at"] for entry in history)
    assert db.get_history(limit=1) == history[:1]


def test_replaying_a_song_adds_history_without_duplicating_song(tmp_path):
    db = DBManager(tmp_path / "history.db")

    db.add_history_entry("Original title", "Artist", "song-url")
    db.add_history_entry("Changed title", "Different artist", "song-url")

    assert db.conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 2
    assert {entry["title"] for entry in db.get_history()} == {"Original title"}


def test_playlist_tracks_are_returned_once_with_display_defaults(tmp_path):
    db = DBManager(tmp_path / "playlists.db")
    db.add_songs([("song-url", "A song", None, None)])
    db.create_playlist("Favorites")
    playlist_id, name, created_at = db.get_playlists()[0]

    db.add_track_to_playlist(playlist_id, "song-url")
    db.add_track_to_playlist(playlist_id, "song-url")

    assert name == "Favorites"
    assert created_at
    assert db.get_playlist_tracks(playlist_id) == [
        {
            "title": "A song",
            "artist": "Unknown artist",
            "webpage_url": "song-url",
            "duration": None,
        }
    ]


def test_replace_hashes_removes_old_fingerprints(tmp_path):
    db = DBManager(tmp_path / "fingerprints.db")
    db.add_songs([("song-1", "A song", "Artist", None)])
    db.add_hashes([("old", 10, "song-1")])

    db.replace_hashes(
        "song-1",
        [("new-1", 20, "song-1"), ("new-2", 30, "song-1")],
    )

    rows = db.conn.execute(
        "SELECT hash, time, song_id FROM hashes ORDER BY time"
    ).fetchall()
    assert rows == [("new-1", 20, "song-1"), ("new-2", 30, "song-1")]
