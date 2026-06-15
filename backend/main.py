from typing import IO
from optype.io import CanFSPath
import numpy as np
from scipy import signal, ndimage
from scipy.io import wavfile


def load_file(p: str | CanFSPath[str] | IO[bytes]):
    sr, data = wavfile.read(p)

    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), sr


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
    """Return spectrogram peak frequencies and times ordered by time.

    Peaks are local maxima in a log-magnitude STFT. The percentile threshold
    keeps the fingerprint dense enough for matching while discarding background
    energy that would otherwise create many unstable hashes.
    """
    if data.size == 0:
        return np.array([]), np.array([])

    f, t, zxx = signal.stft(
        data,
        fs=sr,
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
    )
    magnitude = np.abs(zxx)
    spectrogram = 20 * np.log10(magnitude + np.finfo(float).eps)

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

    if freq_indexes.size == 0:
        return np.array([]), np.array([])

    peak_strengths = spectrogram[freq_indexes, time_indexes]
    order = np.lexsort((-peak_strengths, f[freq_indexes], t[time_indexes]))

    if max_peaks is not None:
        if max_peaks <= 0:
            return np.array([]), np.array([])
        strongest = np.argsort(peak_strengths)[-max_peaks:]
        order = strongest[
            np.lexsort(
                (
                    -peak_strengths[strongest],
                    f[freq_indexes][strongest],
                    t[time_indexes][strongest],
                )
            )
        ]

    freq_indexes = freq_indexes[order]
    time_indexes = time_indexes[order]
    return f[freq_indexes], t[time_indexes]


def combinatorial_hashing(
    f: np.ndarray,
    t: np.ndarray,
    song_id: str | None = None,
    *,
    min_time_between_peaks: float = 0.05,
    max_time_between_peaks: float = 2.0,
    max_targets: int = 5,
    freq_bin_hz: int = 20,
    time_bin_seconds: float = 0.01,
) -> list[tuple[str, int] | tuple[str, int, str]]:
    """Create landmark hashes from time-ordered spectral peaks.

    Each hash contains an anchor frequency, target frequency, and quantized
    time delta. The returned time is the quantized anchor time, used later for
    offset voting during search.
    """
    if len(f) != len(t):
        raise ValueError("Frequency and time peak arrays must have the same length")

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
    return hashes


def fingerprint_file(path: str | CanFSPath[str] | IO[bytes], song_id: str):
    data, sr = load_file(path)
    peak_frequencies, peak_times = peak_finding(data, sr)
    return combinatorial_hashing(peak_frequencies, peak_times, song_id)


# if __name__ == "__main__":
#     hashes = fingerprint_file("./assets/output.wav")
#     print(f"Generated {len(hashes)} hashes")
