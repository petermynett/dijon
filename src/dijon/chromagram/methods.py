"""Chromagram method implementations."""

from __future__ import annotations

import librosa
import numpy as np


def _validate_audio(y: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
    """Validate and normalize audio input."""
    if sr <= 0:
        raise ValueError(f"sr must be positive, got {sr}")
    if not isinstance(y, np.ndarray):
        raise TypeError("y must be a NumPy array")
    if y.ndim != 1:
        raise ValueError(f"y must be 1-D, got shape {y.shape}")
    if y.size == 0:
        raise ValueError("y must not be empty")
    if not np.all(np.isfinite(y)):
        raise ValueError("y contains non-finite values")
    return y.astype(np.float64, copy=False), int(sr)


def _extract_beat_times_from_meter_map(
    meter_map: np.ndarray,
    *,
    duration: float,
    tol: float = 1e-6,
) -> np.ndarray:
    """Validate meter map and return beat times in seconds with optional auto-padding."""
    if not isinstance(meter_map, np.ndarray):
        raise TypeError("meter_map must be a NumPy array")
    if meter_map.ndim != 2:
        raise ValueError(f"meter_map must be 2-D, got shape {meter_map.shape}")
    if meter_map.shape[1] != 3:
        raise ValueError(f"meter_map must have shape (N, 3), got {meter_map.shape}")
    if meter_map.shape[0] < 1:
        raise ValueError("meter_map must contain at least one row")
    if meter_map.dtype.kind != "f":
        raise TypeError(f"meter_map must be float dtype, got {meter_map.dtype}")
    if not np.all(np.isfinite(meter_map)):
        raise ValueError("meter_map contains non-finite values")

    beat_times = meter_map[:, 0].astype(np.float64, copy=False)
    if beat_times.size < 1:
        raise ValueError("meter_map time column is empty")
    if not np.all(np.diff(beat_times) > 0):
        raise ValueError("meter_map[:, 0] (time_sec) must be strictly increasing")

    if beat_times[0] < -tol or beat_times[-1] > duration + tol:
        raise ValueError(
            f"meter_map time_sec must lie within [0, duration]. "
            f"Got [{beat_times[0]:.3f}, {beat_times[-1]:.3f}] for duration={duration:.3f}s"
        )

    beat_times = np.clip(beat_times, 0.0, duration)
    if beat_times[0] > tol:
        beat_times = np.concatenate(([0.0], beat_times))
    if beat_times[-1] < duration - tol:
        beat_times = np.concatenate((beat_times, [duration]))
    if beat_times.size < 2:
        raise ValueError("Need at least two beat boundaries after auto-padding")
    if not np.all(np.diff(beat_times) > 0):
        raise ValueError("Beat boundaries must be strictly increasing after auto-padding")
    return beat_times


def _compute_frame_chroma(
    y: np.ndarray,
    *,
    sr: int,
    hop_length: int,
    chroma_type: str,
) -> np.ndarray:
    """Compute frame-level chroma features."""
    if hop_length <= 0:
        raise ValueError(f"hop_length must be positive, got {hop_length}")
    if chroma_type == "cqt":
        C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    elif chroma_type == "stft":
        C = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop_length)
    else:
        raise ValueError('chroma_type must be "cqt" or "stft"')
    if C.ndim != 2 or C.shape[0] != 12:
        raise ValueError(f"Unexpected chroma shape {C.shape}, expected (12, T)")
    return C.astype(np.float64, copy=False)


def _compute_frame_weights(
    y: np.ndarray,
    *,
    sr: int,
    hop_length: int,
    weight_source: str,
    weight_power: float,
    n_frames: int,
) -> np.ndarray:
    """Compute per-frame weights for weighted aggregation."""
    if weight_source == "rms":
        weights = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length, center=True)[0]
    elif weight_source == "onset":
        weights = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    else:
        raise ValueError('weight_source must be "rms" or "onset"')

    weights = librosa.util.fix_length(weights, size=n_frames)
    weights = np.maximum(weights.astype(np.float64, copy=False), 1e-10) ** float(weight_power)
    return weights


def _build_subdivision_boundaries(
    beat_times: np.ndarray,
    *,
    bpm_threshold: float,
) -> np.ndarray:
    """Build adaptive subdivision boundaries from beat boundaries."""
    if bpm_threshold <= 0:
        raise ValueError(f"bpm_threshold must be positive, got {bpm_threshold}")
    beat_durs = np.diff(beat_times)
    if not np.all(beat_durs > 0):
        raise ValueError("beat_times must be strictly increasing")
    local_bpm = 60.0 / beat_durs

    boundary_times: list[float] = [float(beat_times[0])]
    for i, dur in enumerate(beat_durs):
        start = float(beat_times[i])
        end = float(beat_times[i + 1])
        subdiv = 4 if local_bpm[i] <= bpm_threshold else 2
        for k in range(1, subdiv):
            boundary_times.append(start + (k / subdiv) * dur)
        boundary_times.append(end)
    return np.asarray(boundary_times, dtype=np.float64)


def metric_chromagram_mvp(
    y: np.ndarray,
    *,
    sr: int,
    meter_map: np.ndarray,
    hop_length: int = 256,
    bpm_threshold: float = 180.0,
    chroma_type: str = "cqt",
    aggregate: str = "mean",
    accent_mode: str = "preserve",
    weight_source: str = "rms",
    weight_power: float = 1.0,
    min_frames_per_bin: int = 2,
) -> np.ndarray:
    """MVP metric-aligned chromagram using an external meter map.

    Parameters
    ----------
    y : np.ndarray
        Mono audio signal.
    sr : int
        Sampling rate (Hz).
    meter_map : np.ndarray
        Shape (N, 3) with columns [time_sec, bar_number, beat_number].
        Only time_sec is used for boundaries; bar/beat columns are metadata.
    hop_length : int
        Feature hop length in samples.
    bpm_threshold : float
        Local BPM threshold for subdivision selection.
        <= threshold uses 4 bins/beat; > threshold uses 2 bins/beat.
    chroma_type : str
        "cqt" or "stft".
    aggregate : str
        "mean" or "median".
    accent_mode : str
        "preserve", "normalize", or "weighted".
    weight_source : str
        For accent_mode="weighted": "rms" or "onset".
    weight_power : float
        Exponent applied to positive frame weights.
    min_frames_per_bin : int
        Minimum number of chroma frames required per subdivision bin.

    Returns
    -------
    np.ndarray
        `C_metric` with shape (12, M), aligned to adaptive metric subdivisions.
    """
    if min_frames_per_bin < 1:
        raise ValueError(f"min_frames_per_bin must be >= 1, got {min_frames_per_bin}")

    y, sr = _validate_audio(y, sr)
    duration = len(y) / float(sr)
    beat_times = _extract_beat_times_from_meter_map(meter_map, duration=duration)

    C = _compute_frame_chroma(y, sr=sr, hop_length=hop_length, chroma_type=chroma_type)

    frame_weights: np.ndarray | None = None
    if accent_mode == "normalize":
        C = librosa.util.normalize(C, norm=1, axis=0)
    elif accent_mode == "preserve":
        pass
    elif accent_mode == "weighted":
        frame_weights = _compute_frame_weights(
            y,
            sr=sr,
            hop_length=hop_length,
            weight_source=weight_source,
            weight_power=weight_power,
            n_frames=C.shape[1],
        )
    else:
        raise ValueError('accent_mode must be "preserve", "normalize", or "weighted"')

    boundary_times = _build_subdivision_boundaries(beat_times, bpm_threshold=bpm_threshold)
    boundary_frames = librosa.time_to_frames(boundary_times, sr=sr, hop_length=hop_length)

    if not np.all(np.diff(boundary_frames) > 0):
        raise ValueError(
            "Subdivision boundaries collapsed to non-increasing frame indices. "
            "Try smaller hop_length or lower min_frames_per_bin."
        )

    T = C.shape[1]
    if boundary_frames[-1] > T:
        raise ValueError(f"Meter map extends beyond chroma frames (last_frame={boundary_frames[-1]}, T={T})")

    bin_lengths = np.diff(boundary_frames)
    if np.any(bin_lengths < min_frames_per_bin):
        bad = int(np.where(bin_lengths < min_frames_per_bin)[0][0])
        raise ValueError(
            f"Subdivision bin too short: bin={bad}, frames={bin_lengths[bad]}, "
            f"min_frames_per_bin={min_frames_per_bin}. "
            "(Consider smaller hop_length.)"
        )

    if aggregate not in {"mean", "median"}:
        raise ValueError('aggregate must be "mean" or "median"')

    M = len(boundary_frames) - 1
    C_metric = np.zeros((12, M), dtype=np.float32)

    if accent_mode != "weighted":
        agg_fn = np.mean if aggregate == "mean" else np.median
        for j in range(M):
            s = int(boundary_frames[j])
            t = int(boundary_frames[j + 1])
            C_metric[:, j] = agg_fn(C[:, s:t], axis=1).astype(np.float32, copy=False)
        return C_metric

    if aggregate != "mean":
        raise ValueError('aggregate must be "mean" when accent_mode="weighted"')
    assert frame_weights is not None

    for j in range(M):
        s = int(boundary_frames[j])
        t = int(boundary_frames[j + 1])
        w = frame_weights[s:t]
        W = float(np.sum(w))
        if W <= 0:
            raise ValueError(f"Zero weight in bin {j} (frames {s}:{t})")
        C_metric[:, j] = ((C[:, s:t] * w[None, :]).sum(axis=1) / W).astype(np.float32, copy=False)

    return C_metric
