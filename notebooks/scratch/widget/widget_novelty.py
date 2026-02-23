"""Novelty computation and caching for temporal widgets."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import librosa
import numpy as np
from scipy.interpolate import interp1d

from widget_common import (
    FS_NOV,
    GAMMA_VALUES,
    HOP_VALUES,
    LOCAL_M_VALUES,
    NOVELTY_DEFAULTS,
)

if TYPE_CHECKING:
    pass

# Ensure project root on path (widget_common already does this)
from dijon.novelty import (
    compute_novelty_complex,
    compute_novelty_energy,
    compute_novelty_phase,
    compute_novelty_spectrum,
)


def compute_novelty(
    x: np.ndarray,
    sr: int,
    method: str,
    *,
    N: int | None = None,
    H: int | None = None,
    gamma: float | None = None,
    M: int | None = None,
    norm: bool = True,
) -> tuple[np.ndarray, float]:
    """Compute novelty function for given method and params."""
    defaults = NOVELTY_DEFAULTS.get(method, NOVELTY_DEFAULTS["spectral"])
    N = N if N is not None else defaults["N"]
    H = H if H is not None else defaults["H"]
    gamma = gamma if gamma is not None else defaults.get("gamma")
    M = M if M is not None else defaults.get("M", 0)

    if method == "energy":
        nov, Fs = compute_novelty_energy(x, Fs=sr, N=N, H=H, gamma=gamma if gamma is not None else 10.0, norm=norm)
    elif method == "spectral":
        nov, Fs = compute_novelty_spectrum(x, Fs=sr, N=N, H=H, gamma=gamma if gamma is not None else 100.0, M=M, norm=norm)
    elif method == "phase":
        nov, Fs = compute_novelty_phase(x, Fs=sr, N=N, H=H, M=M, norm=norm)
    elif method == "complex":
        nov, Fs = compute_novelty_complex(x, Fs=sr, N=N, H=H, gamma=gamma if gamma is not None else 10.0, M=M, norm=norm)
    else:
        raise ValueError(f"Unknown novelty method: {method}")
    return nov, Fs


def resample_novelty_to_100hz(novelty: np.ndarray, Fs_in: float) -> np.ndarray:
    """Resample novelty to FS_NOV (100 Hz)."""
    duration_s = len(novelty) / Fs_in
    n_out = int(duration_s * FS_NOV)
    t_in = np.arange(len(novelty)) / Fs_in
    t_out = np.linspace(0, duration_s, n_out, endpoint=False)
    interp = interp1d(t_in, novelty, kind="linear", fill_value="extrapolate")
    return interp(t_out).astype(np.float64)


def novelty_params_key(method: str, N: int, H: int, gamma: float | None, M: int) -> tuple:
    """Build cache key for novelty. Exported for callers that need to pass to get_tempogram_for_methods."""
    return (method, N, H, gamma, M)


def _novelty_params_key(method: str, N: int, H: int, gamma: float | None, M: int) -> tuple:
    return novelty_params_key(method, N, H, gamma, M)


def _novelty_grid_keys() -> list[tuple]:
    """Build list of (method, N, H, gamma, M) keys for full precompute grid (896 variants)."""
    keys: list[tuple] = []
    for method in ("energy", "spectral", "phase", "complex"):
        d = NOVELTY_DEFAULTS[method]
        N = d["N"]
        for H in HOP_VALUES:
            if method == "energy":
                for gamma in GAMMA_VALUES:
                    keys.append((method, N, H, gamma, 0))
            elif method == "spectral":
                for gamma in GAMMA_VALUES:
                    for M in LOCAL_M_VALUES:
                        keys.append((method, N, H, gamma, M))
            elif method == "phase":
                for M in LOCAL_M_VALUES:
                    keys.append((method, N, H, None, M))
            else:  # complex
                for gamma in GAMMA_VALUES:
                    for M in LOCAL_M_VALUES:
                        keys.append((method, N, H, gamma, M))
    return keys


def _compute_novelty_batch_shared_stft(
    x: np.ndarray,
    sr: int,
    novelty_cache: dict,
) -> None:
    """Compute novelty variants with shared STFT where possible (spectral, phase, complex)."""
    from dijon.novelty.normalize import compute_local_average

    def _principal_argument(v):
        return np.mod(v + 0.5, 1) - 0.5

    for method in ("spectral", "phase", "complex"):
        d = NOVELTY_DEFAULTS[method]
        N = d["N"]
        for H in HOP_VALUES:
            X = librosa.stft(x, n_fft=N, hop_length=H, win_length=N, window="hann")
            Fs_feature = sr / H

            if method == "spectral":
                for gamma in GAMMA_VALUES:
                    Y = np.log(1 + gamma * np.abs(X))
                    Y_diff = np.diff(Y, axis=1)
                    Y_diff[Y_diff < 0] = 0
                    nov_base = np.sum(Y_diff, axis=0)
                    nov_base = np.concatenate((nov_base, np.array([0.0])))
                    for M in LOCAL_M_VALUES:
                        nov = nov_base.copy()
                        if M > 0:
                            local_avg = compute_local_average(nov, M)
                            nov = nov - local_avg
                            nov[nov < 0] = 0.0
                        max_val = np.max(nov)
                        if max_val > 0:
                            nov = nov / max_val
                        nov_100 = resample_novelty_to_100hz(nov, Fs_feature)
                        novelty_cache[(method, N, H, gamma, M)] = (nov, nov_100)

            elif method == "phase":
                phase = np.angle(X) / (2 * np.pi)
                phase_diff = _principal_argument(np.diff(phase, axis=1))
                phase_diff2 = _principal_argument(np.diff(phase_diff, axis=1))
                nov_base = np.sum(np.abs(phase_diff2), axis=0)
                nov_base = np.concatenate((nov_base, np.array([0.0, 0.0])))
                for M in LOCAL_M_VALUES:
                    nov = nov_base.copy()
                    if M > 0:
                        local_avg = compute_local_average(nov, M)
                        nov = nov - local_avg
                        nov[nov < 0] = 0.0
                    max_val = np.max(nov)
                    if max_val > 0:
                        nov = nov / max_val
                    nov_100 = resample_novelty_to_100hz(nov, Fs_feature)
                    novelty_cache[(method, N, H, None, M)] = (nov, nov_100)

            else:  # complex
                phase = np.angle(X) / (2 * np.pi)
                phase_diff = np.diff(phase, axis=1)
                phase_diff = np.concatenate((phase_diff, np.zeros((X.shape[0], 1))), axis=1)
                for gamma in GAMMA_VALUES:
                    mag = np.log(1 + gamma * np.abs(X)) if gamma > 0 else np.abs(X)
                    X_hat = mag * np.exp(2 * np.pi * 1j * (phase + phase_diff))
                    X_prime = np.abs(X_hat - X)
                    X_plus = np.copy(X_prime)
                    for n in range(1, X.shape[1]):
                        idx = np.where(mag[:, n] < mag[:, n - 1])
                        X_plus[idx, n] = 0
                    nov_base = np.sum(X_plus, axis=0)
                    for M in LOCAL_M_VALUES:
                        nov = nov_base.copy()
                        if M > 0:
                            local_avg = compute_local_average(nov, M)
                            nov = nov - local_avg
                            nov[nov < 0] = 0.0
                        max_val = np.max(nov)
                        if max_val > 0:
                            nov = nov / max_val
                        nov_100 = resample_novelty_to_100hz(nov, Fs_feature)
                        novelty_cache[(method, N, H, gamma, M)] = (nov, nov_100)

    d = NOVELTY_DEFAULTS["energy"]
    N = d["N"]
    for H in HOP_VALUES:
        for gamma in GAMMA_VALUES:
            nov, Fs = compute_novelty_energy(
                x, Fs=sr, N=N, H=H, gamma=gamma, norm=True
            )
            nov_100 = resample_novelty_to_100hz(nov, Fs)
            novelty_cache[("energy", N, H, gamma, 0)] = (nov, nov_100)


def eager_compute_novelty(
    x: np.ndarray,
    sr: int,
) -> tuple[dict[tuple, tuple[np.ndarray, np.ndarray]], float, dict[str, float]]:
    """Eagerly compute novelty only (full grid, shared-STFT).

    Returns (novelty_cache, total_time_s, timings).
    novelty_cache: (method, N, H, gamma, M) -> (nov, nov_100)  # 896 variants.
    """
    t0 = time.perf_counter()
    novelty_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
    timings: dict[str, float] = {}
    t_nov_start = time.perf_counter()
    _compute_novelty_batch_shared_stft(x, sr, novelty_cache)
    timings["novelty_all"] = time.perf_counter() - t_nov_start
    timings["total"] = time.perf_counter() - t0
    return novelty_cache, timings["total"], timings


def eager_compute_all(
    x: np.ndarray,
    sr: int,
) -> tuple[dict, dict, float, dict[str, float]]:
    """Eagerly compute novelty; return empty tempogram_cache for backward compatibility.

    Returns (novelty_cache, tempogram_cache, total_time_s, timings).
    tempogram_cache is {} and is populated by get_tempogram_for_methods on demand.
    """
    novelty_cache, total_time_s, timings = eager_compute_novelty(x, sr)
    return novelty_cache, {}, total_time_s, timings


def get_novelty_for_method(
    novelty_cache: dict,
    x: np.ndarray,
    sr: int,
    method: str,
    N: int,
    H: int,
    gamma: float | None,
    M: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Get (nov, nov_100) from cache or compute and cache."""
    key = _novelty_params_key(method, N, H, gamma, M)
    if key in novelty_cache:
        return novelty_cache[key]
    kwargs = {"N": N, "H": H, "M": M}
    if method != "phase":
        kwargs["gamma"] = gamma
    nov, Fs = compute_novelty(x, sr, method, **kwargs)
    nov_100 = resample_novelty_to_100hz(nov, Fs)
    novelty_cache[key] = (nov, nov_100)
    return nov, nov_100
