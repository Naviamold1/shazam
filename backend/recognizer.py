from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from backend.db import DBManager
from backend.main import fingerprint_file


@dataclass
class SongCandidate:
    song_id: str
    title: str
    votes: int
    confidence: float


class SongRecognizer:
    def __init__(self, db_path: str | Path = "data.db"):
        self.db = DBManager(db_path)

    def recognize_file(self, path: str | Path, limit: int = 5) -> list[SongCandidate]:
        hashes = fingerprint_file(path)
        if not hashes:
            return []

        matches = defaultdict(list)
        titles = {}

        for address, recording_time in hashes:
            for song_id, title, db_time in self.db.get_hashes(address):
                titles[song_id] = title
                matches[song_id].append((recording_time, db_time))

        candidates = []
        for song_id, pairs in matches.items():
            buckets = defaultdict(int)
            for recording_time, db_time in pairs:
                bucket = int((db_time - recording_time) / 100)
                buckets[bucket] += 1

            candidates.append(
                SongCandidate(
                    song_id=song_id,
                    title=titles[song_id],
                    votes=max(buckets.values()),
                    confidence=0,
                )
            )

        candidates = sorted(
            candidates,
            key=lambda candidate: candidate.votes,
            reverse=True,
        )[:limit]

        if not candidates:
            return []

        best_votes = candidates[0].votes
        for candidate in candidates:
            candidate.confidence = candidate.votes / best_votes * 100

        return candidates
