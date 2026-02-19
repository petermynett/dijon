"""Novelty method implementations (FMP Section 6.1)."""

import librosa
import numpy as np

from .normalize import compute_local_average


def compute_novelty_energy(x, Fs=1, N=2048, H=128, gamma=10.0, norm=True):
    """Energy-based novelty function (FMP Section 6.1.1).

    Local energy with Hann window, discrete derivative, half-wave rectification.
    """
    w = np.hanning(N)
    Fs_feature = Fs / H
    energy_local = np.convolve(x**2, w**2, "same")
    energy_local = energy_local[::H]
    if gamma is not None:
        energy_local = np.log(1 + gamma * energy_local)
    energy_local_diff = np.diff(energy_local)
    energy_local_diff = np.concatenate((energy_local_diff, np.array([0])))
    novelty_energy = np.copy(energy_local_diff)
    novelty_energy[energy_local_diff < 0] = 0
    if norm:
        max_value = np.max(novelty_energy)
        if max_value > 0:
            novelty_energy = novelty_energy / max_value
    return novelty_energy, Fs_feature


def compute_novelty_spectrum(x, Fs=1, N=1024, H=256, gamma=100.0, M=10, norm=True):
    """Spectral-based novelty / spectral flux (FMP Section 6.1.2).

    STFT -> log compression -> diff -> half-wave rectify -> sum over freq -> optional local norm.
    """
    X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann")
    Fs_feature = Fs / H
    Y = np.log(1 + gamma * np.abs(X))
    Y_diff = np.diff(Y, axis=1)
    Y_diff[Y_diff < 0] = 0
    novelty_spectrum = np.sum(Y_diff, axis=0)
    novelty_spectrum = np.concatenate((novelty_spectrum, np.array([0.0])))
    if M > 0:
        local_average = compute_local_average(novelty_spectrum, M)
        novelty_spectrum = novelty_spectrum - local_average
        novelty_spectrum[novelty_spectrum < 0] = 0.0
    if norm:
        max_value = np.max(novelty_spectrum)
        if max_value > 0:
            novelty_spectrum = novelty_spectrum / max_value
    return novelty_spectrum, Fs_feature


def _principal_argument(v):
    """Principal argument: map phase differences to [-0.5, 0.5]."""
    return np.mod(v + 0.5, 1) - 0.5


def compute_novelty_phase(x, Fs=1, N=1024, H=64, M=40, norm=True):
    """Phase-based novelty (FMP Section 6.1.3).

    Second-order phase difference with principal argument, sum over frequency.
    """
    X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann")
    Fs_feature = Fs / H
    phase = np.angle(X) / (2 * np.pi)
    phase_diff = _principal_argument(np.diff(phase, axis=1))
    phase_diff2 = _principal_argument(np.diff(phase_diff, axis=1))
    novelty_phase = np.sum(np.abs(phase_diff2), axis=0)
    novelty_phase = np.concatenate((novelty_phase, np.array([0.0, 0.0])))
    if M > 0:
        local_average = compute_local_average(novelty_phase, M)
        novelty_phase = novelty_phase - local_average
        novelty_phase[novelty_phase < 0] = 0.0
    if norm:
        max_value = np.max(novelty_phase)
        if max_value > 0:
            novelty_phase = novelty_phase / max_value
    return novelty_phase, Fs_feature


def compute_novelty_complex(x, Fs=1, N=1024, H=64, gamma=10.0, M=40, norm=True):
    """Complex-domain novelty (FMP Section 6.1.4).

    Steady-state estimate from phase extrapolation, magnitude difference, onset-only (X+).
    """
    X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann")
    Fs_feature = Fs / H
    mag = np.abs(X)
    if gamma > 0:
        mag = np.log(1 + gamma * mag)
    phase = np.angle(X) / (2 * np.pi)
    phase_diff = np.diff(phase, axis=1)
    phase_diff = np.concatenate((phase_diff, np.zeros((phase.shape[0], 1))), axis=1)
    X_hat = mag * np.exp(2 * np.pi * 1j * (phase + phase_diff))
    X_prime = np.abs(X_hat - X)
    X_plus = np.copy(X_prime)
    for n in range(1, X.shape[1]):
        idx = np.where(mag[:, n] < mag[:, n - 1])
        X_plus[idx, n] = 0
    novelty_complex = np.sum(X_plus, axis=0)
    if M > 0:
        local_average = compute_local_average(novelty_complex, M)
        novelty_complex = novelty_complex - local_average
        novelty_complex[novelty_complex < 0] = 0.0
    if norm:
        max_value = np.max(novelty_complex)
        if max_value > 0:
            novelty_complex = novelty_complex / max_value
    return novelty_complex, Fs_feature
