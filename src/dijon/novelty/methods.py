"""Novelty method implementations."""

import librosa
import numpy as np
from scipy.interpolate import interp1d

from .normalize import compute_local_average

FS_TARGET_DEFAULT = 100.0


def _resample_novelty_to_target(novelty: np.ndarray, Fs_in: float, Fs_target: float) -> np.ndarray:
    """Resample novelty from Fs_in to Fs_target (samples per second). Returns float64 1D."""
    if Fs_in <= 0 or Fs_target <= 0:
        return novelty.astype(np.float64)
    duration_s = len(novelty) / Fs_in
    n_out = max(1, int(round(duration_s * Fs_target)))
    t_in = np.arange(len(novelty), dtype=float) / Fs_in
    t_out = np.linspace(0, duration_s, n_out, endpoint=False)
    interp = interp1d(t_in, novelty, kind="linear", fill_value="extrapolate")
    return interp(t_out).astype(np.float64)


def compute_novelty_energy(x, Fs=1, N=2048, H=128, gamma=10.0, norm=True, Fs_target=FS_TARGET_DEFAULT):
    """Energy-based novelty function.

    Local energy with Hann window, discrete derivative, half-wave rectification.

    Parameters
    ----------
    x : array-like
        Input signal.
    Fs : float
        Sampling rate (default 1).
    N : int
        Window size in samples (default 2048).
    H : int
        Hop size in samples (default 128).
    gamma : float or None
        Log compression factor; None disables (default 10.0).
    norm : bool
        If True, normalize output to [0, 1] (default True).
    Fs_target : float or None
        Target feature rate (Hz). If None, return at native rate Fs/H. If set (default 100),
        resample output to this rate so downstream (tempogram, beats) use a consistent rate.
    """
    w = np.hanning(N) # window size in samples
    Fs_feature = Fs / H # decimation factor
    energy_local = np.convolve(x**2, w**2, "same") # convolve the power to lowpass
    energy_local = energy_local[::H] # decimate by hop size
    if gamma is not None:
        energy_local = np.log(1 + gamma * energy_local) # log compression
    energy_local_diff = np.diff(energy_local) # forward difference (basically discrete derivative)
    energy_local_diff = np.concatenate((energy_local_diff, np.array([0]))) # to maintain length
    novelty_energy = np.copy(energy_local_diff)
    novelty_energy[energy_local_diff < 0] = 0 # half-wave rectify
    if norm:
        max_value = np.max(novelty_energy)
        if max_value > 0:
            novelty_energy = novelty_energy / max_value
    if Fs_target is not None and abs(Fs_feature - Fs_target) > 1e-6:
        novelty_energy = _resample_novelty_to_target(novelty_energy, Fs_feature, Fs_target)
        Fs_feature = Fs_target
    return novelty_energy, Fs_feature


def compute_novelty_spectrum(x, Fs=1, N=1024, H=256, gamma=100.0, M=10, norm=True, Fs_target=FS_TARGET_DEFAULT):
    """Spectral-based novelty / spectral flux.

    STFT -> log compression -> diff -> half-wave rectify -> sum over freq -> optional local norm.

    Parameters
    ----------
    x : array-like
        Input signal.
    Fs : float
        Sampling rate (default 1).
    N : int
        FFT size (default 1024).
    H : int
        Hop size in samples (default 256).
    gamma : float
        Log compression factor (default 100.0).
    M : int
        Local average context in frames; 0 disables (default 10).
    norm : bool
        If True, normalize output to [0, 1] (default True).
    Fs_target : float or None
        Target feature rate (Hz). None = native rate; default 100.
    """
    X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann") # stft
    Fs_feature = Fs / H # decimation factor
    Y = np.log(1 + gamma * np.abs(X)) # log compression
    Y_diff = np.diff(Y, axis=1) # forward difference  in TIME (basically discrete derivative)
    Y_diff[Y_diff < 0] = 0 # half-wave rectify
    novelty_spectrum = np.sum(Y_diff, axis=0) # sum over frequency ie Integrate OVER TIME ACROSS FREQUENCY
    novelty_spectrum = np.concatenate((novelty_spectrum, np.array([0.0]))) # add a zero to maintain length
    if M > 0:
        local_average = compute_local_average(novelty_spectrum, M)
        novelty_spectrum = novelty_spectrum - local_average
        novelty_spectrum[novelty_spectrum < 0] = 0.0
    if norm:
        max_value = np.max(novelty_spectrum)
        if max_value > 0:
            novelty_spectrum = novelty_spectrum / max_value
    if Fs_target is not None and abs(Fs_feature - Fs_target) > 1e-6:
        novelty_spectrum = _resample_novelty_to_target(novelty_spectrum, Fs_feature, Fs_target)
        Fs_feature = Fs_target
    return novelty_spectrum, Fs_feature


def _principal_argument(v):
    """Principal argument: map phase differences to [-0.5, 0.5].

    Parameters
    ----------
    v : array-like
        Phase value(s).
    """
    return np.mod(v + 0.5, 1) - 0.5


def compute_novelty_phase(x, Fs=1, N=1024, H=64, M=40, norm=True, Fs_target=FS_TARGET_DEFAULT):
    """Phase-based novelty.

    Second-order phase difference with principal argument, sum over frequency.

    Parameters
    ----------
    x : array-like
        Input signal.
    Fs : float
        Sampling rate (default 1).
    N : int
        FFT size (default 1024).
    H : int
        Hop size in samples (default 64).
    M : int
        Local average context in frames; 0 disables (default 40).
    norm : bool
        If True, normalize output to [0, 1] (default True).
    Fs_target : float or None
        Target feature rate (Hz). None = native rate; default 100.
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
    if Fs_target is not None and abs(Fs_feature - Fs_target) > 1e-6:
        novelty_phase = _resample_novelty_to_target(novelty_phase, Fs_feature, Fs_target)
        Fs_feature = Fs_target
    return novelty_phase, Fs_feature


def compute_novelty_complex(x, Fs=1, N=1024, H=64, gamma=10.0, M=40, norm=True, Fs_target=FS_TARGET_DEFAULT):
    """Complex-domain novelty (phase-predicted complex residual, onset-only).

    STFT -> (optional) log-magnitude compression -> phase-based prediction of next frame
    -> complex residual -> keep only bins with rising magnitude -> sum over frequency
    -> optional local average subtraction -> optional normalization.

    Parameters
    ----------
    x : array-like
        Input signal.
    Fs : float
        Sampling rate (default 1).
    N : int
        FFT size (default 1024).
    H : int
        Hop size in samples (default 64).
    gamma : float
        Log compression factor; <=0 disables (default 10.0).
    M : int
        Local average context in frames; 0 disables (default 40).
    norm : bool
        If True, normalize output to [0, 1] (default True).
    Fs_target : float or None
        Target feature rate (Hz). None = native rate; default 100.
    """
    def _principal_angle_rad(a):
        # Map to (-pi, pi]
        return (a + np.pi) % (2 * np.pi) - np.pi

    X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann")
    Fs_feature = Fs / H

    mag = np.abs(X)
    if gamma and gamma > 0:
        mag = np.log1p(gamma * mag)

    phase = np.angle(X)  # radians, shape (K, T)
    K, T = phase.shape

    novelty_complex = np.zeros(T, dtype=float)
    if T < 3:
        return novelty_complex, Fs_feature

    # Phase prediction: phi_hat[t] = 2*phi[t-1] - phi[t-2]  (constant instantaneous frequency)
    phi_hat = 2.0 * phase[:, 1:-1] - phase[:, :-2]  # shape (K, T-2)
    phi_hat = _principal_angle_rad(phi_hat)

    # Predicted complex spectrum for frames t=2..T-1 using previous magnitude (steady-state)
    X_hat = mag[:, 1:-1] * np.exp(1j * phi_hat)  # shape (K, T-2)

    # Complex-domain residual for frames t=2..T-1
    R = np.abs(X[:, 2:] - X_hat)  # shape (K, T-2)

    # Onset-only gate: keep only bins whose (compressed) magnitude is non-decreasing
    gate = (mag[:, 2:] >= mag[:, 1:-1])  # shape (K, T-2)
    R_plus = R * gate

    novelty_complex[2:] = np.sum(R_plus, axis=0)

    if M and M > 0:
        local_average = compute_local_average(novelty_complex, M)
        novelty_complex = novelty_complex - local_average
        novelty_complex[novelty_complex < 0] = 0.0

    if norm:
        max_value = float(np.max(novelty_complex))
        if max_value > 0:
            novelty_complex = novelty_complex / max_value

    if Fs_target is not None and abs(Fs_feature - Fs_target) > 1e-6:
        novelty_complex = _resample_novelty_to_target(novelty_complex, Fs_feature, Fs_target)
        Fs_feature = Fs_target
    return novelty_complex, Fs_feature