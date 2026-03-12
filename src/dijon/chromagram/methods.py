# src/dijon/chromagram/methods.py
"""Chromagram method implementations."""

from __future__ import annotations

import re
from pathlib import Path

import librosa
import numpy as np


def _parse_novelty_log_region(log_path: Path, base: str) -> tuple[float, float, str, str]:
    """Parse novelty log and extract analysis region for one base filename.

    Expected log pattern:
    - item line containing "• {base}.wav:" and "success"
    - following line containing "region: Xs -> Ys"
    - optional "markers: A -> B"
    """
    # NOTE FOR AGENTS: If novelty log formatting changes, update regex + line-walk
    # logic here and the notebook import sites that rely on this parser.
    text = log_path.read_text()
    wav_name = f"{base}.wav"
    if wav_name not in text:
        raise ValueError(f"Base '{base}' not found in novelty log {log_path}")

    lines = text.splitlines()
    region_re = re.compile(r"region:\s*([\d.]+)s\s*->\s*([\d.]+)s")
    markers_re = re.compile(r"markers:\s*(\S+)\s*->\s*(\S+)")
    for i, line in enumerate(lines):
        if f"• {wav_name}:" in line and "success" in line:
            if i + 1 >= len(lines):
                raise ValueError(f"Incomplete entry for {wav_name} in {log_path}")
            details = lines[i + 1]
            m_region = region_re.search(details)
            m_markers = markers_re.search(details)
            if not m_region:
                raise ValueError(f"No region found for {wav_name} in {log_path}")
            start_sec = float(m_region.group(1))
            end_sec = float(m_region.group(2))
            start_name = m_markers.group(1) if m_markers else ""
            end_name = m_markers.group(2) if m_markers else ""
            return (start_sec, end_sec, start_name, end_name)

    raise ValueError(f"Could not parse region for {wav_name} in {log_path}")


def cents_to_cqt_tuning(cents: float, bins_per_octave: int = 36) -> float:
    """Convert cents offset to librosa CQT tuning offset (fractional bins)."""
    return cents * (bins_per_octave / 1200.0)


def safe_l1_normalize_columns(C: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """L1-normalize columns with safe handling of near-zero columns."""
    C = np.asarray(C, dtype=np.float64)
    sums = C.sum(axis=0, keepdims=True)
    out = np.zeros_like(C)
    mask = sums > eps
    out[:, mask[0]] = C[:, mask[0]] / sums[:, mask[0]]
    return out


def score_metric_chromagram(
    C_metric: np.ndarray,
    k: int = 4,
    lambda_jitter: float = 0.5,
) -> tuple[float, float, float]:
    """Score metric chroma by concentration minus temporal jitter penalty."""
    strengths = np.sum(C_metric, axis=0)
    C_norm = safe_l1_normalize_columns(C_metric)
    sorted_desc = np.sort(C_norm, axis=0)[::-1]
    topk = np.sum(sorted_desc[:k], axis=0)
    conc = (
        np.sum(topk * strengths) / np.sum(strengths)
        if np.sum(strengths) > 0
        else np.nan
    )
    jitter = (
        np.sum(np.abs(np.diff(C_norm, axis=1)), axis=0)
        if C_norm.shape[1] >= 2
        else np.zeros(0)
    )
    jw = np.minimum(strengths[:-1], strengths[1:])
    jit = np.sum(jitter * jw) / np.sum(jw) if len(jitter) and np.sum(jw) > 0 else 0.0
    return float(conc - lambda_jitter * jit), float(conc), float(jit)


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


def _preprocess_audio_for_chroma(
    y: np.ndarray,
    *,
    preprocess: str,
) -> np.ndarray:
    """Preprocess audio for chroma extraction."""
    if preprocess == "none":
        return y
    if preprocess == "harmonic":
        return librosa.effects.harmonic(y)
    raise ValueError('preprocess must be "none" or "harmonic"')


def _extract_beat_times_from_meter_map(
    meter_map: np.ndarray,
    *,
    duration: float,
    tol: float = 1e-6,
) -> np.ndarray:
    """Validate meter map and return beat boundary times in seconds.

    Returns validated beat boundaries verbatim. Does not clip, prepend 0.0,
    or append duration. Requires at least two rows. Assumes the audio passed
    to metric_chromagram is on the same timebase as meter_map[:, 0].
    """
    if not isinstance(meter_map, np.ndarray):
        raise TypeError("meter_map must be a NumPy array")
    if meter_map.ndim != 2:
        raise ValueError(f"meter_map must be 2-D, got shape {meter_map.shape}")
    if meter_map.shape[1] != 3:
        raise ValueError(f"meter_map must have shape (N, 3), got {meter_map.shape}")
    if meter_map.shape[0] < 2:
        raise ValueError("meter_map must contain at least two rows")

    if meter_map.dtype.kind != "f":
        raise TypeError(f"meter_map must be float dtype, got {meter_map.dtype}")
    if not np.all(np.isfinite(meter_map)):
        raise ValueError("meter_map contains non-finite values")

    beat_times = meter_map[:, 0].astype(np.float64, copy=False)
    if beat_times.size < 1:
        raise ValueError("meter_map time column is empty")
    if not np.all(np.diff(beat_times) > 0):
        raise ValueError("meter_map[:, 0] (time_sec) must be strictly increasing")

    # Do not repair out-of-range or missing endpoints; upstream meter generation owns boundary definition.
    if beat_times[0] < -tol or beat_times[-1] > duration + tol:
        raise ValueError(
            f"meter_map time_sec must lie within [0, duration]. "
            f"Got [{beat_times[0]:.3f}, {beat_times[-1]:.3f}] for duration={duration:.3f}s"
        )

    return beat_times


def _compute_frame_chroma(
    y: np.ndarray,
    *,
    sr: int,
    hop_length: int,
    chroma_type: str,
    tuning: float | None = None,
) -> np.ndarray:
    """Compute frame-level chroma features."""
    if hop_length <= 0:
        raise ValueError(f"hop_length must be positive, got {hop_length}")
    if chroma_type == "cqt":
        C = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=hop_length,
            tuning=tuning,
        )
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
        weights = librosa.feature.rms(
            y=y,
            frame_length=2048,
            hop_length=hop_length,
            center=True,
        )[0]
    elif weight_source == "onset":
        weights = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    else:
        raise ValueError('weight_source must be "rms" or "onset"')

    weights = librosa.util.fix_length(weights, size=n_frames)
    weights = np.maximum(weights.astype(np.float64, copy=False), 1e-10) ** float(
        weight_power
    )
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


def metric_chromagram(
    y: np.ndarray,
    *,
    sr: int,
    meter_map: np.ndarray,
    hop_length: int = 256,
    bpm_threshold: float = 180.0,
    chroma_type: str = "cqt",
    preprocess: str = "harmonic",
    tuning: float | None = None,
    aggregate: str = "mean",
    accent_mode: str = "preserve",
    weight_source: str = "rms",
    weight_power: float = 1.0,
    min_frames_per_bin: int = 2,
) -> np.ndarray:
    """Metric-aligned chromagram using an external meter map.

    Parameters
    ----------
    y : np.ndarray
        Mono audio signal.
    sr : int
        Sampling rate (Hz).
    meter_map : np.ndarray
        Shape (N, 3) with columns [time_sec, bar_number, beat_number].
        Only time_sec is used for boundaries; bar/beat columns are metadata.
        time_sec must be on the same timeline as y; if y is region-trimmed,
        meter_map must be region-relative.
    hop_length : int
        Feature hop length in samples.
    bpm_threshold : float
        Local BPM threshold for subdivision selection.
        <= threshold uses 4 bins/beat; > threshold uses 2 bins/beat.
    chroma_type : str
        "cqt" or "stft".
    preprocess : str
        Audio preprocessing applied before chroma extraction.
        "none" uses the raw signal.
        "harmonic" extracts the harmonic component using
        librosa.effects.harmonic.
    tuning : float | None
        Tuning offset in fractional chroma bins passed to
        librosa.feature.chroma_cqt. None uses librosa's default behavior.
    aggregate : str
        "mean" or "median".
    accent_mode : str
        "preserve", "normalize", or "weighted".
    weight_source : str
        For accent_mode="weighted": "rms" or "onset".
    weight_power : float
        Exponent applied to positive frame weights.
    min_frames_per_bin : int
        Minimum chroma frames per subdivision bin after time-to-frame quantization.

    Returns
    -------
    np.ndarray
        `C_metric` with shape (12, M), aligned to adaptive metric subdivisions.

    Notes
    -----
    Preprocessing affects only the signal used for chroma estimation.
    Frame weighting, when enabled, is still computed from the original waveform.
    """
    if min_frames_per_bin < 1:
        raise ValueError(f"min_frames_per_bin must be >= 1, got {min_frames_per_bin}")

    # --- setup: validate audio, preprocess for chroma, extract beat times ---
    y, sr = _validate_audio(y, sr)
    y_chroma = _preprocess_audio_for_chroma(y, preprocess=preprocess)
    duration = len(y) / float(sr)
    beat_times = _extract_beat_times_from_meter_map(meter_map, duration=duration)

    C = _compute_frame_chroma(
        y_chroma,
        sr=sr,
        hop_length=hop_length,
        chroma_type=chroma_type,
        tuning=tuning,
    )

    # --- accent handling: optionally normalise or pre-compute frame weights ---
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

    # --- build adaptive subdivision grid (tempo-aware) and convert to frame indices ---
    boundary_times = _build_subdivision_boundaries(
        beat_times,
        bpm_threshold=bpm_threshold,
    )
    boundary_frames = librosa.time_to_frames(boundary_times, sr=sr, hop_length=hop_length)

    # --- guard: boundaries must be strictly increasing after quantisation to frames ---
    if not np.all(np.diff(boundary_frames) > 0):
        raise ValueError(
            "Subdivision boundaries collapsed to non-increasing frame indices. "
            "Try smaller hop_length or lower min_frames_per_bin."
        )

    T = C.shape[1]
    if boundary_frames[-1] > T:
        raise ValueError(
            f"Meter map extends beyond chroma frames (last_frame={boundary_frames[-1]}, T={T})"
        )

    # --- guard: every bin must have enough frames for a meaningful aggregate ---
    # Very short metric subdivisions can collapse after time-to-frame quantization;
    # treat as an input/configuration issue, not something to auto-correct.
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

    # --- aggregate chroma frames into metric bins ---
    M = len(boundary_frames) - 1
    C_metric = np.zeros((12, M), dtype=np.float32)

    # fast path: unweighted mean/median per bin
    if accent_mode != "weighted":
        agg_fn = np.mean if aggregate == "mean" else np.median
        for j in range(M):
            s = int(boundary_frames[j])
            t = int(boundary_frames[j + 1])
            C_metric[:, j] = agg_fn(C[:, s:t], axis=1).astype(np.float32, copy=False)
        return C_metric

    # weighted path: weighted mean per bin (median not supported here)
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
        C_metric[:, j] = ((C[:, s:t] * w[None, :]).sum(axis=1) / W).astype(
            np.float32,
            copy=False,
        )

    return C_metric