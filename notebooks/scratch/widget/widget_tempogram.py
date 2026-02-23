"""Tempogram computation and caching for temporal widgets."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from widget_common import DEFAULT_TEMPO_MAX, DEFAULT_TEMPO_MIN, FS_NOV

from dijon.tempogram import (
    compute_cyclic_tempogram,
    compute_tempogram_autocorr,
    compute_tempogram_fourier,
)


def compute_tempogram(
    nov_100: np.ndarray,
    method: str,
    *,
    window_sec: float = 5.0,
    hop_sec: float = 0.1,
    tempo_min: int = DEFAULT_TEMPO_MIN,
    tempo_max: int = DEFAULT_TEMPO_MAX,
    norm_sum: bool = False,
    tempo_ref: float = 40,
    octave_bin: int = 40,
    octave_num: int = 4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Compute tempogram. Returns (tempogram, T_coef, F_coef, aux).

    For fourier/autocorr: F_coef is BPM. For cyclic: F_coef is scale [1,2).
    aux contains method-specific data (e.g. F_coef_BPM for cyclic tempo extraction).
    """
    N = int(window_sec * FS_NOV)
    H = int(hop_sec * FS_NOV)
    Theta = np.arange(tempo_min, tempo_max + 1, dtype=np.float64)

    if method == "fourier":
        X, T_coef, F_coef_BPM = compute_tempogram_fourier(nov_100, FS_NOV, N=N, H=H, Theta=Theta)
        tempogram = np.abs(X)
        return tempogram, T_coef, F_coef_BPM, {"F_coef_BPM": F_coef_BPM}

    if method == "autocorr":
        tempogram, T_coef, F_coef_BPM = compute_tempogram_autocorr(
            nov_100, FS_NOV, N=N, H=H, norm_sum=norm_sum, Theta=Theta
        )
        return tempogram, T_coef, F_coef_BPM, {"F_coef_BPM": F_coef_BPM}

    if method == "cyclic":
        X, T_coef, F_coef_BPM = compute_tempogram_fourier(nov_100, FS_NOV, N=N, H=H, Theta=Theta)
        tempogram_fourier = np.abs(X)
        tempogram_cyclic, F_coef_scale = compute_cyclic_tempogram(
            tempogram_fourier, F_coef_BPM, tempo_ref=tempo_ref, octave_bin=octave_bin, octave_num=octave_num
        )
        return tempogram_cyclic, T_coef, F_coef_scale, {
            "F_coef_BPM": F_coef_BPM,
            "tempogram_fourier": tempogram_fourier,
            "tempo_ref": tempo_ref,
        }

    raise ValueError(f"Unknown tempogram method: {method}")


def tempo_from_tempogram(
    tempogram: np.ndarray,
    F_coef_BPM: np.ndarray,
    method: str,
    *,
    aux: dict | None = None,
) -> float:
    """Extract dominant tempo (BPM) from tempogram for beat tracking.

    For cyclic, uses the underlying Fourier tempogram in aux for tempo extraction.
    """
    if method in ("fourier", "autocorr"):
        profile = np.mean(tempogram, axis=1)
        idx = int(np.argmax(profile))
        return float(F_coef_BPM[idx])

    if method == "cyclic" and aux:
        t_fourier = aux.get("tempogram_fourier")
        f_bpm = aux.get("F_coef_BPM")
        if t_fourier is not None and f_bpm is not None:
            profile = np.mean(t_fourier, axis=1)
            idx = int(np.argmax(profile))
            return float(f_bpm[idx])

    raise ValueError(f"Cannot extract tempo for method: {method}")


def _tempogram_cache_key(
    novelty_key: tuple,
    tempogram_method: str,
    window_sec: float,
    hop_sec: float,
    tempo_min: int,
    tempo_max: int,
) -> tuple:
    """Cache key for tempogram. novelty_key must identify the nov_100 source."""
    return (novelty_key, tempogram_method, window_sec, hop_sec, tempo_min, tempo_max)


def get_tempogram_for_methods(
    tempogram_cache: dict,
    nov_100: np.ndarray,
    novelty_key: tuple,
    tempogram_method: str,
    window_sec: float = 5.0,
    hop_sec: float = 0.1,
    tempo_min: int = DEFAULT_TEMPO_MIN,
    tempo_max: int = DEFAULT_TEMPO_MAX,
    norm_sum: bool = False,
) -> tuple:
    """Get tempogram from cache or compute. novelty_key identifies nov_100 source."""
    key = _tempogram_cache_key(novelty_key, tempogram_method, window_sec, hop_sec, tempo_min, tempo_max)
    if key in tempogram_cache:
        return tempogram_cache[key]
    out = compute_tempogram(
        nov_100, tempogram_method,
        window_sec=window_sec, hop_sec=hop_sec,
        tempo_min=tempo_min, tempo_max=tempo_max, norm_sum=norm_sum,
    )
    tempogram_cache[key] = out
    return out


def eager_compute_tempogram(
    nov_100: np.ndarray,
    novelty_key: tuple,
    *,
    tempogram_method: str = "fourier",
    window_sec: float = 5.0,
    hop_sec: float = 0.1,
    tempo_min: int = DEFAULT_TEMPO_MIN,
    tempo_max: int = DEFAULT_TEMPO_MAX,
    norm_sum: bool = False,
) -> tuple[dict[str, Any], dict[tuple, tuple], float, dict[str, float]]:
    """Eagerly compute tempogram default state for one novelty input.

    Returns (tempogram_state, tempogram_cache, total_time_s, timings).
    tempogram_cache is keyed exactly as get_tempogram_for_methods so widget recomputes
    can reuse the cache without recomputing the same configuration.
    """
    t0 = time.perf_counter()
    tempogram_cache: dict[tuple, tuple] = {}
    tempogram, T_coef, F_coef, aux = get_tempogram_for_methods(
        tempogram_cache,
        nov_100,
        novelty_key,
        tempogram_method,
        window_sec=window_sec,
        hop_sec=hop_sec,
        tempo_min=tempo_min,
        tempo_max=tempo_max,
        norm_sum=norm_sum,
    )
    tempo_bpm = tempo_from_tempogram(tempogram, aux["F_coef_BPM"], tempogram_method, aux=aux)
    elapsed = time.perf_counter() - t0
    state = {
        "tempogram": tempogram,
        "T_coef": T_coef,
        "F_coef": F_coef,
        "aux": aux,
        "tm": tempogram_method,
        "tempo_bpm": tempo_bpm,
    }
    timings = {"tempogram_default": elapsed, "total": elapsed}
    return state, tempogram_cache, elapsed, timings
