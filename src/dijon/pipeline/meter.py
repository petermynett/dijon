"""Pipeline for computing meter labels from beat times and writing to data/derived/meter."""

from __future__ import annotations

import json
from pathlib import Path

import librosa
import numpy as np

from ..beats import estimate_beats_per_bar, label_bars_and_beats
from ..global_config import AUDIO_MARKERS_DIR, DERIVED_DIR, RAW_AUDIO_DIR

BEATS_DIR = DERIVED_DIR / "beats"
METER_OUTPUT_DIR = DERIVED_DIR / "meter"


def _resolve_beats_files(files: list[Path] | None, beats_dir: Path) -> list[Path]:
    """Return list of beats paths: explicit if given, else all .npy in beats_dir."""
    if files:
        return [Path(p).resolve() for p in files]
    if not beats_dir.exists():
        return []
    return sorted(beats_dir.glob("*.npy"))


def _track_name_from_beats_stem(stem: str) -> str:
    """Extract track name from beats filename stem. E.g. YTB-001_beats -> YTB-001."""
    if "_beats" in stem:
        return stem.split("_beats")[0]
    return stem


def _get_head_in_time_sec(track_name: str, markers_dir: Path) -> float | None:
    """Load HEAD_IN_START position from marker JSON. Returns None if missing."""
    marker_path = markers_dir / f"{track_name}_markers.json"
    if not marker_path.exists():
        return None
    try:
        with open(marker_path, encoding="utf-8") as f:
            payload = json.load(f)
        markers = payload.get("markers", [])
        if not markers:
            return None
        for m in markers:
            if isinstance(m, dict) and m.get("name") == "HEAD_IN_START" and "position" in m:
                return float(m["position"])
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def run_meter(
    *,
    beats_files: list[Path] | None = None,
    output_dir: Path = METER_OUTPUT_DIR,
    beats_dir: Path = BEATS_DIR,
    raw_audio_dir: Path = RAW_AUDIO_DIR,
    markers_dir: Path = AUDIO_MARKERS_DIR,
    dry_run: bool = False,
) -> dict:
    """Compute meter labels for beat files and write .npy to output_dir.

    If beats_files is None or empty, uses all .npy in beats_dir.
    Tracks without HEAD_IN_START marker are skipped.
    Output filename: <track_name>_meter.npy

    Returns:
        Dict with success, total, succeeded, failed, skipped, message, items, failures.
    """
    paths = _resolve_beats_files(beats_files, beats_dir)
    if not paths:
        return {
            "success": True,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": "No beats files to process.",
            "items": [],
            "failures": [],
        }

    output_dir = Path(output_dir)
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0
    skipped = 0
    items: list[dict] = []
    failures: list[dict] = []

    for beats_path in paths:
        track_name = _track_name_from_beats_stem(beats_path.stem)
        out_name = f"{track_name}_meter.npy"
        out_path = output_dir / out_name

        head_in = _get_head_in_time_sec(track_name, markers_dir)
        if head_in is None:
            skipped += 1
            items.append({
                "file": beats_path.name,
                "status": "skipped",
                "detail": "No HEAD_IN_START marker",
            })
            continue

        audio_path = raw_audio_dir / f"{track_name}.wav"
        if not audio_path.exists():
            failed += 1
            failures.append({"item": str(beats_path), "reason": f"Audio not found: {audio_path}"})
            items.append({"file": beats_path.name, "status": "failed", "detail": "Audio file not found"})
            continue

        if not beats_path.exists():
            failed += 1
            failures.append({"item": str(beats_path), "reason": "File not found"})
            items.append({"file": beats_path.name, "status": "failed", "detail": "File not found"})
            continue

        try:
            beat_times = np.load(beats_path).astype(np.float64)
            if beat_times.ndim != 1:
                raise ValueError(f"Expected 1D beat times, got shape {beat_times.shape}")

            x, sr = librosa.load(audio_path, sr=None, mono=True)
            beats_per_bar, _low_energy, _high_energy = estimate_beats_per_bar(
                beat_times, head_in, x, sr
            )
            labels = label_bars_and_beats(beat_times, head_in, beats_per_bar)

            if not dry_run:
                np.save(out_path, labels, allow_pickle=False)

            succeeded += 1
            items.append({
                "file": beats_path.name,
                "output": out_name,
                "status": "success",
            })
        except Exception as e:
            failed += 1
            failures.append({"item": str(beats_path), "reason": str(e)})
            items.append({"file": beats_path.name, "status": "failed", "detail": str(e)})

    return {
        "success": failed == 0,
        "total": len(paths),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "message": f"Processed {len(paths)} file(s). Succeeded: {succeeded}, failed: {failed}, skipped: {skipped}."
        + (" [DRY RUN]" if dry_run else ""),
        "items": items,
        "failures": failures,
    }
