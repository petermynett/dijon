"""Shared constants, paths, zoom, and audio/marker loading for temporal widgets."""

from __future__ import annotations

import json
import math
from pathlib import Path

import librosa
import numpy as np

# Project root resolution (works from notebooks/scratch/widget or project root)
_WIDGET_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _WIDGET_DIR
for _ in range(5):
    if (_PROJECT_ROOT / "src" / "dijon").exists():
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent
else:
    raise FileNotFoundError("Could not find project root with src/dijon")

import sys
sys.path.insert(0, str(_PROJECT_ROOT))

from dijon.global_config import AUDIO_MARKERS_DIR, RAW_AUDIO_DIR

FS_NOV = 100
DEFAULT_TEMPO_MIN = 40
DEFAULT_TEMPO_MAX = 320

GAMMA_VALUES = [1.0, 10.0, 50.0, 100.0, 200.0, 500.0, 1000.0]
LOCAL_M_VALUES = [0, 5, 10, 20, 40, 60, 80]
HOP_VALUES = [32, 64, 96, 128, 256, 384, 512, 768]
WINDOW_SEC_VALUES = [2.0, 3.0, 5.0, 7.5, 10.0]
HOP_SEC_VALUES = [0.05, 0.1, 0.15, 0.2, 0.5]

GAMMA_OPTIONS = [(str(g), g) for g in GAMMA_VALUES]
LOCAL_M_OPTIONS = [(str(m), m) for m in LOCAL_M_VALUES]
HOP_OPTIONS = [(str(h), h) for h in HOP_VALUES]
WINDOW_SEC_OPTIONS = [(str(w), w) for w in WINDOW_SEC_VALUES]
HOP_SEC_OPTIONS = [(str(h), h) for h in HOP_SEC_VALUES]

ZOOM_MIN_HALF_SEC = 0.3

NOVELTY_DEFAULTS = {
    "energy": {"N": 2048, "H": 128, "gamma": 10.0, "M": 0},
    "spectral": {"N": 1024, "H": 256, "gamma": 100.0, "M": 10},
    "phase": {"N": 1024, "H": 64, "gamma": None, "M": 40},
    "complex": {"N": 1024, "H": 64, "gamma": 10.0, "M": 40},
}


def zoom_level_to_half_sec(level: int, duration_s: float) -> float:
    """Map zoom level 1-10 to half-window seconds. 1=full duration, 10=min window."""
    level = max(1, min(10, int(level)))
    if level == 1:
        return duration_s
    if level == 10:
        return ZOOM_MIN_HALF_SEC
    log_min = math.log10(ZOOM_MIN_HALF_SEC)
    log_max = math.log10(max(duration_s, ZOOM_MIN_HALF_SEC * 2))
    frac = (10 - level) / 9.0
    return 10 ** (log_min + frac * (log_max - log_min))


def load_audio_and_markers(
    track: str,
    marker: str | None,
) -> tuple[np.ndarray, int, float, float, str]:
    """Load audio segment and resolve marker bounds.

    Returns:
        (x, sr, seg_start_s, seg_end_s, marker_label)
    """
    use_marker = marker and str(marker).strip()
    marker_label = "FULL" if not use_marker else str(marker).upper().replace("-", "_")
    audio_path = RAW_AUDIO_DIR / f"{track}.wav"
    x_full, sr = librosa.load(audio_path, sr=None, mono=True)

    if use_marker:
        markers_path = AUDIO_MARKERS_DIR / f"{track}_markers.json"
        with open(markers_path, encoding="utf-8") as f:
            payload = json.load(f)
        entries = payload.get("entries", [])
        if not entries:
            raise ValueError(f"No entries in {markers_path}")
        marker_list = entries[0].get("markers", [])
        name_to_m = {m["name"]: m for m in marker_list if "name" in m}

        start_key = f"{marker_label}_START"
        end_key = f"{marker_label}_END"
        if start_key not in name_to_m or end_key not in name_to_m:
            raise ValueError(f"Marker {marker} needs {start_key} and {end_key}")
        seg_start = float(name_to_m[start_key]["position"])
        seg_end = float(name_to_m[end_key]["position"])
        start_sample = int(seg_start * sr)
        end_sample = int(seg_end * sr)
        x = x_full[start_sample:end_sample]
    else:
        seg_start = 0.0
        seg_end = len(x_full) / sr
        x = x_full

    return x, sr, seg_start, seg_end, marker_label


def get_head_in_time(track: str) -> float:
    """Get HEAD_IN_START position from markers."""
    path = AUDIO_MARKERS_DIR / f"{track}_markers.json"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    markers = payload["entries"][0]["markers"]
    m = next((x for x in markers if x["name"] == "HEAD_IN_START"), None)
    if m is None:
        raise ValueError(f"HEAD_IN_START not found in {path}")
    return float(m["position"])
