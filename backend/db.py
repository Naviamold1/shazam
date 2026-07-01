import sqlite3
from pathlib import Path


class DBManager:
    def __init__(self, db_path: str | Path = "data.db"):
        self.db_path = Path(db_path)
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
            track_order INTEGER,
            playlist_id INTEGER NOT NULL,
            UNIQUE(playlist_id, track_order),
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
            INSERT INTO songs (id, song_name, song_author, song_genre) VALUES (
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
        with self.conn:
            self.conn.execute("DELETE FROM hashes WHERE song_id = ?", (song_id,))
            self.conn.executemany(
                "INSERT INTO hashes (hash, time, song_id) VALUES (?, ?, ?)",
                hashes,
            )

    def find_song(self, hashes: list[tuple[str, int]]):
        hashes = list(hashes)
        if not hashes:
            return []

        curr = self.conn.cursor()

        curr.execute("DROP TABLE IF EXISTS temp_hashes_list")
        curr.execute("""
        CREATE TEMP TABLE temp_hashes_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            hash TEXT,
            time INTEGER
        )
        """)

        curr.executemany(
            """
        INSERT INTO temp_hashes_list (hash, time) VALUES (?, ?)
        """,
            [(i[0], i[1]) for i in hashes],
        )

        res = curr.execute(
            """
        SELECT
            h.song_id,
            s.song_name,
            h.time AS db_time,
            t.time AS recording_time,
            (h.time - t.time) AS delta,
            COUNT(*) as votes
        FROM hashes h JOIN songs s ON h.song_id = s.id
        JOIN temp_hashes_list t ON h.hash = t.hash
        GROUP BY h.song_id, delta
        ORDER BY votes DESC
        LIMIT 5
        """,
        ).fetchall()

        curr.execute("""
        DROP TABLE temp_hashes_list
        """)

        return res

    def create_playlist(self, name: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO playlists (playlist_name) VALUES (?)",
            (name,),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def get_playlists(self) -> list[tuple[int, str, str]]:
        return self.conn.execute(
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
    ) -> bool:
        existing = self.conn.execute(
            """
            SELECT 1 FROM playlist_entries
            WHERE playlist_id = ? AND song_id = ?
            """,
            (playlist_id, webpage_url),
        ).fetchone()
        if existing:
            return False

        self.conn.execute(
            """
            INSERT OR IGNORE INTO songs (id, song_name, song_author, song_genre)
            VALUES (?, ?, ?, NULL)
            """,
            (webpage_url, title, artist),
        )
        next_order = self.conn.execute(
            """
            SELECT COALESCE(MAX(track_order), 0) + 1
            FROM playlist_entries
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()[0]
        self.conn.execute(
            """
            INSERT INTO playlist_entries (song_id, track_order, playlist_id)
            VALUES (?, ?, ?)
            """,
            (webpage_url, next_order, playlist_id),
        )
        self.conn.commit()
        return True

    def get_playlist_tracks(self, playlist_id: int) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT s.song_name, s.song_author, s.id
            FROM playlist_entries e
            JOIN songs s ON s.id = e.song_id
            WHERE e.playlist_id = ?
            ORDER BY e.track_order
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
        self.conn.execute(
            """
            INSERT OR IGNORE INTO songs (id, song_name, song_author, song_genre)
            VALUES (?, ?, ?, NULL)
            """,
            (webpage_url, title, artist),
        )
        self.conn.execute(
            "INSERT INTO history (song_id) VALUES (?)",
            (webpage_url,),
        )
        self.conn.commit()

    def get_history(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
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
