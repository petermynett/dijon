"""Meter inference and bar/beat labeling from beat times."""

import numpy as np
from scipy.signal import butter, filtfilt


def _band_rms(x, sr, low_hz=None, high_hz=None, order=4):
    """Extract RMS of a band-filtered signal. low_hz/high_hz define passband; None = no limit."""
    nyq = sr / 2
    if low_hz is not None and high_hz is not None:
        b, a = butter(order, [low_hz / nyq, high_hz / nyq], btype="band")
    elif low_hz is not None:
        b, a = butter(order, low_hz / nyq, btype="high")
    elif high_hz is not None:
        b, a = butter(order, high_hz / nyq, btype="low")
    else:
        return np.sqrt(np.mean(x**2))
    x_filt = filtfilt(b, a, x.astype(np.float64))
    return np.sqrt(np.mean(x_filt**2))


def compute_beat_energies(
    beat_times_sec,
    x,
    sr,
    win_half_sec=0.15,
    low_cut_hz=30,
    low_pass_hz=250,
    high_cut_hz=1600,
):
    """Compute low-band (kick/bass) and mid/high-band (hihat/chuck) RMS per beat."""
    n = len(beat_times_sec)
    low_energy = np.zeros(n)
    high_energy = np.zeros(n)
    t = np.arange(len(x)) / sr

    for i in range(n):
        t_center = beat_times_sec[i]
        t_start = max(0, t_center - win_half_sec)
        t_end = min(len(x) / sr, t_center + win_half_sec)
        idx = (t >= t_start) & (t < t_end)
        if not np.any(idx):
            continue
        seg = x[idx]
        low_energy[i] = _band_rms(seg, sr, low_hz=low_cut_hz, high_hz=low_pass_hz)
        high_energy[i] = _band_rms(seg, sr, low_hz=high_cut_hz)

    return low_energy, high_energy


def estimate_beats_per_bar(beat_times_sec, head_in_time_sec, x, sr):
    """Infer beats-per-bar from low-band (strong beats) vs mid/high-band (weak beats) contrast."""
    b = np.asarray(beat_times_sec, dtype=np.float64)
    t0 = head_in_time_sec
    i0 = int(np.argmin(np.abs(b - t0)))

    low_energy, high_energy = compute_beat_energies(b, x, sr)

    # Normalize so scale differences don't dominate
    low_norm = low_energy / (np.std(low_energy) + 1e-10)
    high_norm = high_energy / (np.std(high_energy) + 1e-10)

    candidates = [2, 3, 4]
    best_score = -np.inf
    best_B = 2

    for B in candidates:
        downbeat_low = []
        other_low = []
        downbeat_high = []
        other_high = []
        for i in range(len(b)):
            k = i - i0
            pos = k % B
            if pos == 0:
                downbeat_low.append(low_norm[i])
                downbeat_high.append(high_norm[i])
            else:
                other_low.append(low_norm[i])
                other_high.append(high_norm[i])

        if not downbeat_low or not other_low:
            continue

        # Strong beats (1, 3): more low, less high
        score_low = np.mean(downbeat_low) - np.mean(other_low)
        # Weak beats (2, 4): more high, less low
        score_high = np.mean(other_high) - np.mean(downbeat_high)
        score = score_low + score_high

        if score > best_score:
            best_score = score
            best_B = B

    return best_B, low_energy, high_energy


def label_bars_and_beats(beat_times_sec, head_in_time_sec, beats_per_bar):
    """Map each beat to (time_sec, bar_number, beat_number). Anchor at head_in = bar 1 beat 1."""
    b = np.asarray(beat_times_sec, dtype=np.float64)
    B = int(beats_per_bar)
    i0 = int(np.argmin(np.abs(b - head_in_time_sec)))

    labels = []
    for i in range(len(b)):
        k = i - i0
        bar_number = 1 + (k // B)
        beat_number = 1 + (k % B)
        labels.append((float(b[i]), bar_number, beat_number))

    return np.array(labels)
