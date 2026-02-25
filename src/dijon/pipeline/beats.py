"""Pipeline for computing beat times from tempogram and novelty .npy files."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..beats import compute_beat_sequence
from ..global_config import DERIVED_DIR

FS_NOV = 100.0
TEMPOGRAM_DIR = DERIVED_DIR / "tempogram"
NOVELTY_DIR = DERIVED_DIR / "novelty"
BEATS_OUTPUT_DIR = DERIVED_DIR / "beats"

THETA_DEFAULT = (40, 320)


def _resolve_tempogram_files(files: list[Path] | None, tempogram_dir: Path) -> list[Path]:
    """Return list of tempogram paths: explicit if given, else all .npy in tempogram_dir."""
    if files:
        return [Path(p).resolve() for p in files]
    if not tempogram_dir.exists():
        return []
    return sorted(tempogram_dir.glob("*.npy"))


def _track_name_from_tempogram_stem(stem: str) -> str:
    """Extract track name from tempogram filename stem."""
    if "_tempogram_" in stem:
        return stem.split("_tempogram_")[0]
    return stem


def _find_novelty_for_track(track_name: str, novelty_dir: Path) -> Path | None:
    """Find first matching novelty file for a track."""
    prefix = f"{track_name}_novelty_"
    matches = sorted(novelty_dir.glob(f"{prefix}*.npy"))
    return matches[0] if matches else None


def run_beats(
    *,
    tempogram_files: list[Path] | None = None,
    output_dir: Path = BEATS_OUTPUT_DIR,
    tempogram_dir: Path = TEMPOGRAM_DIR,
    novelty_dir: Path = NOVELTY_DIR,
    factor: float = 1.0,
    theta_min: int | None = None,
    theta_max: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Compute beat times from tempogram and novelty files and write .npy to output_dir.

    If tempogram_files is None or empty, uses all .npy in tempogram_dir.
    For each tempogram, finds matching novelty (first match by track name prefix).
    Output filename: <track_name>_beats.npy

    Returns:
        Dict with success, total, succeeded, failed, skipped, message, items, failures.
    """
    theta_min = theta_min if theta_min is not None else THETA_DEFAULT[0]
    theta_max = theta_max if theta_max is not None else THETA_DEFAULT[1]
    theta = np.arange(theta_min, theta_max + 1, dtype=np.float64)

    paths = _resolve_tempogram_files(tempogram_files, tempogram_dir)
    if not paths:
        return {
            "success": True,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": "No tempogram files to process.",
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

    for tempo_path in paths:
        track_name = _track_name_from_tempogram_stem(tempo_path.stem)
        nov_path = _find_novelty_for_track(track_name, novelty_dir)

        if nov_path is None:
            skipped += 1
            items.append({
                "file": tempo_path.name,
                "status": "skipped",
                "detail": f"No matching novelty in {novelty_dir}",
            })
            continue

        out_name = f"{track_name}_beats.npy"
        out_path = output_dir / out_name

        if not tempo_path.exists():
            failed += 1
            failures.append({"item": str(tempo_path), "reason": "File not found"})
            items.append({"file": tempo_path.name, "status": "failed", "detail": "File not found"})
            continue

        if not nov_path.exists():
            failed += 1
            failures.append({"item": str(nov_path), "reason": "Novelty file not found"})
            items.append({"file": tempo_path.name, "status": "failed", "detail": "Novelty file not found"})
            continue

        try:
            novelty = np.load(nov_path).astype(np.float64)
            tempogram_arr = np.load(tempo_path)

            if tempogram_arr.ndim != 2:
                raise ValueError(f"Expected 2D tempogram, got shape {tempogram_arr.shape}")

            K, _M = tempogram_arr.shape
            F_coef_BPM = theta if K == len(theta) else np.arange(40, 40 + K, dtype=np.float64)
            tempo_profile = np.mean(np.abs(tempogram_arr), axis=1)
            tempo_bpm = float(F_coef_BPM[int(np.argmax(tempo_profile))])
            beat_ref = int(np.round(FS_NOV * 60.0 / tempo_bpm))

            B = compute_beat_sequence(novelty, beat_ref=beat_ref, factor=factor)
            beat_times = B / FS_NOV

            if not dry_run:
                np.save(out_path, beat_times, allow_pickle=False)

            succeeded += 1
            items.append({
                "file": tempo_path.name,
                "output": out_name,
                "status": "success",
            })
        except Exception as e:
            failed += 1
            failures.append({"item": str(tempo_path), "reason": str(e)})
            items.append({"file": tempo_path.name, "status": "failed", "detail": str(e)})

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
