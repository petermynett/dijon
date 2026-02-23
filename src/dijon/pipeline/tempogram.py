"""Pipeline for computing tempograms from novelty .npy and writing to data/derived/tempogram."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..global_config import DERIVED_DIR
from ..tempogram import (
    compute_cyclic_tempogram,
    compute_tempogram_autocorr,
    compute_tempogram_fourier,
)

FS_NOVELTY = 100.0  # Contract: novelty files are at 100 Hz
NOVELTY_DIR = DERIVED_DIR / "novelty"
TEMPOGRAM_OUTPUT_DIR = DERIVED_DIR / "tempogram"

TEMPOGRAM_DEFAULTS: dict[str, tuple[int, int]] = {
    "fourier": (500, 1),
    "autocorr": (500, 1),
    "cyclic": (500, 1),
}
TEMPOGRAM_TYPES = frozenset(TEMPOGRAM_DEFAULTS)
THETA_DEFAULT = (40, 320)


def _resolve_novelty_files(files: list[Path] | None, novelty_dir: Path) -> list[Path]:
    """Return list of novelty paths: explicit if given, else all .npy in novelty_dir."""
    if files:
        return [Path(p).resolve() for p in files]
    if not novelty_dir.exists():
        return []
    return sorted(novelty_dir.glob("*.npy"))


def _track_name_from_novelty_stem(stem: str) -> str:
    """Extract track name from novelty filename stem. E.g. YTB-001_novelty_spectrum_... -> YTB-001."""
    if "_novelty_" in stem:
        return stem.split("_novelty_")[0]
    return stem


def _output_filename(track_name: str, ttype: str, N: int, H: int, theta_min: int, theta_max: int) -> str:
    """Build filename: <track_name>_tempogram_<type>_<N>-<H>-<theta_min>-<theta_max>.npy."""
    return f"{track_name}_tempogram_{ttype}_{N}-{H}-{theta_min}-{theta_max}.npy"


def run_tempogram(
    *,
    novelty_files: list[Path] | None = None,
    output_dir: Path = TEMPOGRAM_OUTPUT_DIR,
    novelty_dir: Path = NOVELTY_DIR,
    ntype: str = "fourier",
    N: int | None = None,
    H: int | None = None,
    theta_min: int | None = None,
    theta_max: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Compute tempogram for novelty file(s) and write .npy to output_dir.

    Input novelty is assumed at 100 Hz. If novelty_files is None/empty, uses all
    .npy in novelty_dir. For type cyclic, computes fourier tempogram then cyclic;
    saves cyclic array. Output: <track_name>_tempogram_<type>_<N>-<H>-<theta_min>-<theta_max>.npy.
    """
    if ntype not in TEMPOGRAM_TYPES:
        return {
            "success": False,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": f"Unknown tempogram type: {ntype}. Use one of: {sorted(TEMPOGRAM_TYPES)}",
            "items": [],
            "failures": [],
        }

    defaults = TEMPOGRAM_DEFAULTS[ntype]
    N = N if N is not None else defaults[0]
    H = H if H is not None else defaults[1]
    theta_min = theta_min if theta_min is not None else THETA_DEFAULT[0]
    theta_max = theta_max if theta_max is not None else THETA_DEFAULT[1]
    Theta = np.arange(theta_min, theta_max + 1, dtype=float)

    paths = _resolve_novelty_files(novelty_files, novelty_dir)
    if not paths:
        return {
            "success": True,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": "No novelty files to process.",
            "items": [],
            "failures": [],
        }

    output_dir = Path(output_dir)
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0
    items: list[dict] = []
    failures: list[dict] = []

    for nov_path in paths:
        track_name = _track_name_from_novelty_stem(nov_path.stem)
        out_name = _output_filename(track_name, ntype, N, H, theta_min, theta_max)
        out_path = output_dir / out_name

        if not nov_path.exists():
            failed += 1
            failures.append({"item": str(nov_path), "reason": "File not found"})
            items.append({"file": nov_path.name, "status": "failed", "detail": "File not found"})
            continue

        try:
            nov = np.load(nov_path).astype(np.float64)
            if nov.ndim != 1:
                raise ValueError(f"Expected 1D novelty, got shape {nov.shape}")

            if ntype == "fourier":
                X, _T, _F = compute_tempogram_fourier(nov, FS_NOVELTY, N, H, Theta)
                out_arr = np.abs(X)
            elif ntype == "autocorr":
                out_arr, _T, _F = compute_tempogram_autocorr(nov, FS_NOVELTY, N, H, Theta=Theta)
            else:  # cyclic: chain from fourier
                X, _T, F_coef_BPM = compute_tempogram_fourier(nov, FS_NOVELTY, N, H, Theta)
                mag = np.abs(X)
                out_arr, _scale = compute_cyclic_tempogram(mag, F_coef_BPM)

            if not dry_run:
                np.save(out_path, out_arr, allow_pickle=False)
            succeeded += 1
            items.append({"file": nov_path.name, "output": out_name, "status": "success"})
        except Exception as e:
            failed += 1
            failures.append({"item": str(nov_path), "reason": str(e)})
            items.append({"file": nov_path.name, "status": "failed", "detail": str(e)})

    return {
        "success": failed == 0,
        "total": len(paths),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": 0,
        "message": f"Processed {len(paths)} file(s). Succeeded: {succeeded}, failed: {failed}."
        + (" [DRY RUN]" if dry_run else ""),
        "items": items,
        "failures": failures,
    }
