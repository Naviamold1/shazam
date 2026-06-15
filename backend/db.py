import sqlite3
from pathlib import Path
from uuid import uuid4


class DBManager:
    def __init__(self, db_path: str | Path = "data1.db"):
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

        self.conn.commit()
        cursor.close()

    def add_songs(
        self,
        params: list[tuple[str, str | None, str | None] | tuple[str, str, str | None, str | None]],
    ):
        """
        Accepts either:
        [(song_id, song_name, song_author, song_genre), ...]
        [(song_name, song_author, song_genre), ...]
        """
        curr = self.conn.cursor()
        rows: list[tuple[str, str, str | None, str | None]] = []

        for item in params:
            if len(item) == 4:
                song_id, song_name, song_author, song_genre = item
            elif len(item) == 3:
                song_id = uuid4().hex
                song_name, song_author, song_genre = item
            else:
                raise ValueError("Songs must be 3-tuples or 4-tuples")
            rows.append((str(song_id), song_name, song_author, song_genre))

        try:
            curr.executemany(
                """
            INSERT INTO songs (id, song_name, song_author, song_genre) VALUES (
                ?, ?, ?, ?
            )
            """,
                rows,
            )
            self.conn.commit()
        except Exception as e:
            print(e)

        ids = [row[0] for row in rows]
        return ids[0] if len(ids) == 1 else ids

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
