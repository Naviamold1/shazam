from typing import IO
from optype.io import CanFSPath
import numpy as np
from scipy import signal, ndimage
from scipy.io import wavfile


def load_file(p: str | CanFSPath[str] | IO[bytes]):
    sr, data = wavfile.read(p)

    if data.ndim > 1:
        data = data.mean(axis=1)

    downsample_factor = 4
    new_sr = int(sr / downsample_factor)
    downsampled_data = signal.decimate(data, downsample_factor, axis=0)

    return downsampled_data.astype(np.float32), new_sr


def peak_finding(
    data: np.ndarray,
    sr: int,
    *,
    nperseg: int = 2048,
    noverlap: int = 1024,
    neighborhood_size: int = 15,
    amp_min_db: float | None = None,
    percentile: float = 92.0,
    max_peaks: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if data.size == 0 or sr <= 0:
        return np.array([]), np.array([])

    nperseg = min(int(nperseg), data.size)
    if nperseg < 2:
        return np.array([]), np.array([])

    noverlap = min(int(noverlap), nperseg - 1)
    neighborhood_size = max(1, int(neighborhood_size))

    f, t, zxx = signal.stft(
        data,
        fs=sr,
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    spectrogram = np.abs(zxx)

    if amp_min_db is None:
        amp_min_db = float(np.percentile(spectrogram, percentile))

    local_max = ndimage.maximum_filter(
        spectrogram,
        size=neighborhood_size,
        mode="constant",
        cval=spectrogram.min(),
    )
    peak_mask = (spectrogram == local_max) & (spectrogram >= amp_min_db)
    freq_indexes, time_indexes = np.nonzero(peak_mask)

    if freq_indexes.size == 0 or max_peaks == 0:
        return np.array([]), np.array([])

    peak_strengths = spectrogram[freq_indexes, time_indexes]
    if max_peaks is not None:
        if max_peaks < 0:
            return np.array([]), np.array([])
        if freq_indexes.size > max_peaks:
            strongest = np.argpartition(peak_strengths, -max_peaks)[-max_peaks:]
            freq_indexes = freq_indexes[strongest]
            time_indexes = time_indexes[strongest]
            peak_strengths = peak_strengths[strongest]

    peak_frequencies = f[freq_indexes]
    peak_times = t[time_indexes]
    order = np.lexsort((-peak_strengths, peak_frequencies, peak_times))
    return peak_frequencies[order], peak_times[order]


def extract_peaks(data, sr):
    f, t, zxx = signal.stft(data, sr, nperseg=1022)
    spectrogram = np.abs(zxx)

    bands = [(0, 10), (10, 20), (20, 40), (40, 80), (80, 160), (160, 512)]
    peaks = []

    local_max = ndimage.maximum_filter(spectrogram, size=15)

    threshold = np.percentile(spectrogram, 75)

    freq_idx, times_idx = np.where(
        (spectrogram == local_max) & (spectrogram > threshold)
    )
    order = np.argsort(times_idx)

    freq_idx = freq_idx[order]
    time_idx = times_idx[order]

    peak_frequencies = f[freq_idx]
    peak_times = t[times_idx]
    return peak_frequencies, peak_times


def combinatorial_hashing(
    f: np.ndarray,
    t: np.ndarray,
    song_id: str | None = None,
    min_time_between_peaks: float = 0.05,
    max_time_between_peaks: float = 2.0,
    max_targets: int = 5,
    freq_bin_hz: int = 20,
    time_bin_seconds: float = 0.01,
):
    order = np.lexsort((f, t))
    frequencies = f[order]
    times = t[order]

    hashes: list[tuple[str, int] | tuple[str, int, str]] = []
    for i in range(len(t)):
        peak_time = times[i]
        peak_freq = frequencies[i]

        targets_count = 0
        for j in range(i + 1, len(t)):
            if targets_count >= max_targets:
                break

            peak_time2 = times[j]
            peak_freq2 = frequencies[j]

            delta_t = peak_time2 - peak_time

            if delta_t < min_time_between_peaks:
                continue

            if delta_t > max_time_between_peaks:
                break

            targets_count += 1
            anchor_bin = int(round(peak_freq / freq_bin_hz))
            target_bin = int(round(peak_freq2 / freq_bin_hz))
            delta_bin = int(round(delta_t / time_bin_seconds))
            anchor_time_bin = int(round(peak_time / time_bin_seconds))
            hash_value = f"{anchor_bin}:{target_bin}:{delta_bin}"
            if song_id is None:
                hashes.append((hash_value, anchor_time_bin))
            else:
                hashes.append((hash_value, anchor_time_bin, song_id))
    print(hashes)
    return hashes


def fingerprint_file(path: str | CanFSPath[str] | IO[bytes], song_id: str | None = None):
    data, sr = load_file(path)
    peak_frequencies, peak_times = peak_finding(data, sr)
    return combinatorial_hashing(peak_frequencies, peak_times, song_id)


# if __name__ == "__main__":
#     hashes = fingerprint_file("./assets/output.wav")
#     print(f"Generated {len(hashes)} hashes")
