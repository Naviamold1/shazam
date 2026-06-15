import numpy as np

from backend.db import DBManager
from backend.main import combinatorial_hashing, peak_finding


def test_peak_finding_returns_time_ordered_tone_peaks():
    sample_rate = 8_000
    duration = 1.0
    times = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    data = np.sin(2 * np.pi * 440 * times)

    peak_frequencies, peak_times = peak_finding(
        data,
        sample_rate,
        nperseg=512,
        noverlap=256,
        neighborhood_size=7,
        percentile=95,
    )

    assert peak_frequencies.size > 0
    assert np.all(np.diff(peak_times) >= 0)
    assert np.any(np.isclose(peak_frequencies, 440, atol=25))


def test_combinatorial_hashing_quantizes_peaks_and_anchor_time():
    peak_frequencies = np.array([100.0, 200.0, 300.0])
    peak_times = np.array([0.0, 0.1, 0.2])

    hashes = combinatorial_hashing(
        peak_frequencies,
        peak_times,
        min_time_between_peaks=0.05,
        max_time_between_peaks=0.5,
        max_targets=2,
        freq_bin_hz=10,
        time_bin_seconds=0.01,
    )

    assert hashes == [
        ("10:20:10", 0),
        ("10:30:20", 0),
        ("20:30:10", 10),
    ]


def test_find_song_votes_by_consistent_time_offset(tmp_path):
    db = DBManager(tmp_path / "fingerprints.db")
    song_id = db.add_songs([("Synthetic Song", None, None)])
    db.add_hashes(
        [
            ("10:20:10", 100, song_id),
            ("20:30:10", 110, song_id),
            ("30:40:10", 120, song_id),
        ]
    )

    matches = db.find_song(
        [
            ("10:20:10", 40),
            ("20:30:10", 50),
            ("30:40:10", 60),
        ]
    )

    assert matches[0][0] == song_id
    assert matches[0][1] == "Synthetic Song"
    assert matches[0][4] == 60
    assert matches[0][5] == 3
