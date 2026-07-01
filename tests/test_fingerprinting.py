import numpy as np
from scipy.io import wavfile

from backend.main import (
    combinatorial_hashing,
    create_address,
    fingerprint_file,
    load_file,
    peak_finding,
)


def test_load_file_converts_stereo_and_resamples(tmp_path):
    source_rate = 22_050
    duration = 0.2
    times = np.arange(int(source_rate * duration)) / source_rate
    mono = np.sin(2 * np.pi * 440 * times)
    stereo = np.column_stack((mono, mono * 0.5)).astype(np.float32)
    path = tmp_path / "stereo.wav"
    wavfile.write(path, source_rate, stereo)

    data, sample_rate = load_file(path)

    assert sample_rate == 11_025
    assert data.dtype == np.float32
    assert data.ndim == 1
    assert data.size == int(sample_rate * duration)


def test_peak_finding_handles_short_or_invalid_audio():
    for data, sample_rate in (
        (np.ones(1_023), 11_025),
        (np.ones(1_024), 0),
    ):
        frequencies, times = peak_finding(data, sample_rate)

        assert frequencies.size == 0
        assert times.size == 0


def test_peak_finding_returns_time_ordered_tone_peaks():
    sample_rate = 11_025
    times = np.arange(sample_rate) / sample_rate
    data = np.sin(2 * np.pi * 440 * times)

    frequencies, peak_times = peak_finding(data, sample_rate)

    assert frequencies.size > 0
    assert frequencies.shape == peak_times.shape
    assert np.all(np.diff(peak_times) >= 0)
    assert np.any(np.isclose(frequencies, 440, atol=15))


def test_create_address_packs_quantized_values():
    address = create_address(1_000, 2_000, 0.125)

    assert address == (100 << 23) | (200 << 14) | 125


def test_combinatorial_hashing_sorts_peaks_and_pairs_targets():
    frequencies = np.array([300.0, 100.0, 200.0])
    times = np.array([0.2, 0.0, 0.1])

    hashes = combinatorial_hashing(frequencies, times)

    assert hashes == [
        (str(create_address(100, 200, 0.1)), 0),
        (str(create_address(100, 300, 0.2)), 0),
        (str(create_address(200, 300, 0.1)), 100),
    ]


def test_combinatorial_hashing_includes_song_id():
    hashes = combinatorial_hashing(
        np.array([100.0, 200.0]),
        np.array([0.25, 0.5]),
        song_id="song-1",
    )

    assert hashes == [(str(create_address(100, 200, 0.25)), 250, "song-1")]


def test_fingerprint_file_composes_pipeline(monkeypatch):
    expected_data = np.array([1.0, 2.0])
    expected_frequencies = np.array([100.0, 200.0])
    expected_times = np.array([0.0, 0.1])

    monkeypatch.setattr(
        "backend.main.load_file",
        lambda path: (expected_data, 11_025),
    )
    monkeypatch.setattr(
        "backend.main.peak_finding",
        lambda data, sample_rate: (expected_frequencies, expected_times),
    )

    result = fingerprint_file("recording.wav", "song-1")

    assert result == [
        (str(create_address(100, 200, 0.1)), 0, "song-1"),
    ]
