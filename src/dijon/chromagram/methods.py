"""Chromagram computation (STFT + pitch-class folding)."""

import numpy as np


def compute_chromagram(
    x,
    Fs,
    N_fft=2048,
    H=512,
    f_min=None,
    f_max=None,
    A4=440.0,
    eps=1e-10,
):
    """Basic chromagram: STFT + pitch-class folding.

    Parameters
    ----------
    x : array-like
        Audio signal (float array).
    Fs : float
        Sample rate (Hz).
    N_fft : int
        FFT size (default 2048).
    H : int
        Hop size in samples (default 512).
    f_min, f_max : float or None
        Frequency range to include (Hz). None means no limit.
    A4 : float
        Reference tuning frequency (Hz), default 440.
    eps : float
        Small constant for stability (default 1e-10).

    Returns
    -------
    C : np.ndarray
        Chromagram, shape (12, T), pitch classes C=0..B=11.
    times : np.ndarray
        Frame times in seconds, length T.
    """
    x = np.asarray(x, dtype=float)
    window = np.hanning(N_fft)
    T = 1 + int(np.floor((len(x) - N_fft) / H))
    T = max(0, T)
    C = np.zeros((12, T), dtype=float)

    for t in range(T):
        start = t * H
        frame = x[start : start + N_fft].copy()
        if len(frame) < N_fft:
            frame = np.pad(frame, (0, N_fft - len(frame)), mode="constant")
        frame = frame * window

        X = np.fft.fft(frame)
        n_half = N_fft // 2 + 1
        P = np.abs(X[:n_half]) ** 2

        for bin_idx in range(n_half):
            f = bin_idx * Fs / N_fft
            if f == 0:
                continue
            if f_min is not None and f < f_min:
                continue
            if f_max is not None and f > f_max:
                continue

            midi = 69 + 12 * np.log2(f / A4)
            pc = int(round(midi)) % 12

            C[pc, t] += P[bin_idx]

        norm = np.sqrt(np.sum(C[:, t] ** 2)) + eps
        C[:, t] /= norm

    times = np.arange(T, dtype=float) * H / Fs
    return C, times
