from typing import IO

import numpy as np
from optype.io import CanFSPath
from scipy import signal
from scipy.io import wavfile


TARGET_SAMPLE_RATE = 11025
WINDOW_SIZE = 1024
HOP_SIZE = WINDOW_SIZE // 2
TARGET_ZONE_SIZE = 5
MAX_FREQ_BITS = 9
MAX_DELTA_BITS = 14
FREQUENCY_BANDS = ((0, 10), (10, 20), (20, 40), (40, 80), (80, 160), (160, 512))


def load_file(p: str | CanFSPath[str] | IO[bytes]):
    sr, data = wavfile.read(p)

    if data.ndim > 1:
        data = data.mean(axis=1)

    if sr != TARGET_SAMPLE_RATE:
        divisor = np.gcd(sr, TARGET_SAMPLE_RATE)
        data = signal.resample_poly(
            data,
            TARGET_SAMPLE_RATE // divisor,
            sr // divisor,
        )

    return data.astype(np.float32), TARGET_SAMPLE_RATE


def peak_finding(
    data: np.ndarray,
    sample_rate: int,
    nperseg: int = WINDOW_SIZE,
    noverlap: int = HOP_SIZE,
) -> tuple[np.ndarray, np.ndarray]:
    """Pick strong frequency-band peaks from every STFT frame."""
    if data.size < nperseg or sample_rate <= 0:
        return np.array([]), np.array([])

    noverlap = min(noverlap, nperseg - 1)
    window = signal.windows.hann(nperseg, sym=True)
    frequencies, _, zxx = signal.stft(
        data,
        fs=sample_rate,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    magnitudes = np.abs(zxx)
    if magnitudes.shape[1] == 0:
        return np.array([]), np.array([])

    frame_duration = (data.size / sample_rate) / magnitudes.shape[1]
    peaks = []

    for frame_index, frame in enumerate(magnitudes.T):
        band_maxima = []
        for start, end in FREQUENCY_BANDS:
            end = min(end, frame.size)
            if start >= end:
                continue
            frequency_index = start + int(np.argmax(frame[start:end]))
            band_maxima.append((float(frame[frequency_index]), frequency_index))

        average = np.mean([magnitude for magnitude, _ in band_maxima])
        for magnitude, frequency_index in band_maxima:
            if magnitude > average:
                peaks.append(
                    (
                        frame_index * frame_duration,
                        frequencies[frequency_index],
                        magnitude,
                    )
                )

    peaks.sort(key=lambda peak: (peak[0], peak[1]))
    peak_times = np.array([time for time, _, _ in peaks])
    peak_frequencies = np.array([frequency for _, frequency, _ in peaks])
    return peak_frequencies, peak_times


def create_address(anchor_frequency, target_frequency, delta_seconds):
    anchor_bits = int(anchor_frequency / 10) & ((1 << MAX_FREQ_BITS) - 1)
    target_bits = int(target_frequency / 10) & ((1 << MAX_FREQ_BITS) - 1)
    delta_bits = int(delta_seconds * 1000) & ((1 << MAX_DELTA_BITS) - 1)
    return (anchor_bits << 23) | (target_bits << 14) | delta_bits


def combinatorial_hashing(
    frequencies: np.ndarray,
    times: np.ndarray,
    song_id: str | None = None,
    max_targets: int = TARGET_ZONE_SIZE,
):
    """Pair each peak with the next five peaks, as the Go implementation does."""
    order = np.lexsort((frequencies, times))
    frequencies = frequencies[order]
    times = times[order]
    hashes = {}

    for index, (anchor_frequency, anchor_time) in enumerate(zip(frequencies, times)):
        end = min(index + max_targets + 1, len(times))
        for target_index in range(index + 1, end):
            address = create_address(
                anchor_frequency,
                frequencies[target_index],
                times[target_index] - anchor_time,
            )
            hashes[str(address)] = int(anchor_time * 1000)

    if song_id is None:
        return [(address, anchor_time) for address, anchor_time in hashes.items()]
    return [(address, anchor_time, song_id) for address, anchor_time in hashes.items()]


def fingerprint_file(
    path: str | CanFSPath[str] | IO[bytes], song_id: str | None = None
):
    data, sample_rate = load_file(path)
    peak_frequencies, peak_times = peak_finding(data, sample_rate)
    return combinatorial_hashing(peak_frequencies, peak_times, song_id)
