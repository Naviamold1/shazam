from pathlib import Path
import sqlite3


class DBManager:
    def __init__(self, db_path: str | Path = "data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id TEXT PRIMARY KEY,
                song_name TEXT NOT NULL,
                song_author TEXT,
                song_genre TEXT
            );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT NOT NULL,
            time INTEGER NOT NULL,
            song_id TEXT NOT NULL,
            FOREIGN KEY(song_id) REFERENCES songs(id)
            );
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS hash_idx ON hashes (hash)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id TEXT NOT NULL,
            playlist_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(playlist_id, song_id),
            FOREIGN KEY(song_id) REFERENCES songs(id),
            FOREIGN KEY(playlist_id) REFERENCES playlists(id)
        )
        """)

        self.conn.commit()
        cursor.close()

    def add_songs(
        self,
        params: list[tuple[str, str, str | None, str | None]],
    ):
        """
        [(song_id, song_name, song_author, song_genre), ...]
        """
        curr = self.conn.cursor()
        try:
            curr.executemany(
                """
            INSERT OR IGNORE INTO songs (id, song_name, song_author, song_genre) VALUES (
                ?, ?, ?, ?
            )
            """,
                params,
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def add_hashes(self, hashes: list[tuple[str, int, str]]):
        curr = self.conn.cursor()

        try:
            curr.executemany(
                """
            INSERT INTO hashes (hash, time, song_id) VALUES (
                ?, ?, ?
            )
            """,
                hashes,
            )
            self.conn.commit()
        except Exception as e:
            print(e)

    def replace_hashes(self, song_id: str, hashes: list[tuple[str, int, str]]):
        curr = self.conn.cursor()

        curr.execute("DELETE FROM hashes WHERE song_id = ?", (song_id,))
        curr.executemany(
            "INSERT INTO hashes (hash, time, song_id) VALUES (?, ?, ?)",
            hashes,
        )

    def create_playlist(self, name: str):
        curr = self.conn.cursor()
        curr.execute(
            "INSERT INTO playlists (playlist_name) VALUES (?)",
            (name,),
        )
        self.conn.commit()

    def get_playlists(self) -> list[tuple[int, str, str]]:
        curr = self.conn.cursor()
        return curr.execute(
            """
            SELECT id, playlist_name, created_at
            FROM playlists
            ORDER BY id DESC
            """
        ).fetchall()

    def add_track_to_playlist(
        self,
        playlist_id: int,
        title: str,
        artist: str | None,
        webpage_url: str,
    ):
        curr = self.conn.cursor()
        self.add_songs([(webpage_url, title, artist, None)])

        curr.execute(
            """
            INSERT OR IGNORE INTO playlist_entries (song_id, playlist_id)
            VALUES (?, ?)
            """,
            (webpage_url, playlist_id),
        )
        self.conn.commit()

    def get_playlist_tracks(self, playlist_id: int) -> list[dict]:
        curr = self.conn.cursor()
        rows = curr.execute(
            """
            SELECT s.song_name, s.song_author, s.id
            FROM playlist_entries e
            JOIN songs s ON s.id = e.song_id
            WHERE e.playlist_id = ?
            ORDER BY e.created_at
            """,
            (playlist_id,),
        ).fetchall()
        return [
            {
                "title": title,
                "artist": artist or "Unknown artist",
                "webpage_url": webpage_url,
                "duration": None,
            }
            for title, artist, webpage_url in rows
        ]

    def add_history_entry(
        self,
        title: str,
        artist: str | None,
        webpage_url: str,
    ):
        curr = self.conn.cursor()
        curr.execute(
            """
            INSERT OR IGNORE INTO songs (id, song_name, song_author, song_genre)
            VALUES (?, ?, ?, NULL)
            """,
            (webpage_url, title, artist),
        )
        curr.execute(
            "INSERT INTO history (song_id) VALUES (?)",
            (webpage_url,),
        )
        self.conn.commit()

    def get_history(self, limit: int = 100) -> list[dict]:
        curr = self.conn.cursor()
        rows = curr.execute(
            """
            SELECT s.song_name, s.song_author, s.id, h.created_at
            FROM history h
            JOIN songs s ON s.id = h.song_id
            ORDER BY h.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "title": title,
                "artist": artist or "Unknown artist",
                "webpage_url": webpage_url,
                "duration": None,
                "played_at": played_at,
            }
            for title, artist, webpage_url, played_at in rows
        ]
