"""Pipeline for computing novelty functions from raw audio and writing .npy outputs."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from ..global_config import DATA_DIR, DERIVED_DIR, RAW_AUDIO_DIR
from ..utils.audio_region import resolve_audio_region_with_names
from ..novelty import (
    compute_novelty_complex,
    compute_novelty_energy,
    compute_novelty_phase,
    compute_novelty_spectrum,
)

NOVELTY_OUTPUT_DIR = DERIVED_DIR / "novelty"

# Type name -> (N, H, gamma, M) defaults for filename and compute
NOVELTY_DEFAULTS: dict[str, tuple[int, int, float, int]] = {
    "spectrum": (1024, 256, 100.0, 10),
    "energy": (2048, 512, 10.0, 0),
    "phase": (1024, 64, 40.0, 10),  # N, H, gamma (unused in phase), M
    "complex": (1024, 64, 10.0, 40),
}

NOVELTY_TYPES = frozenset(NOVELTY_DEFAULTS)


def _resolve_audio_files(files: list[Path] | None, raw_audio_dir: Path) -> list[Path]:
    """Return list of audio paths: explicit files if given, else all .wav in raw_audio_dir."""
    if files:
        return [Path(p).resolve() for p in files]
    if not raw_audio_dir.exists():
        return []
    return sorted(raw_audio_dir.glob("*.wav"))


def _track_name(audio_path: Path) -> str:
    """Stem of the audio file (no extension)."""
    return audio_path.stem


def _output_filename(track_name: str, ntype: str, N: int, H: int, gamma: float, M: int) -> str:
    """Build filename: <track-name>_novelty_<type>_<N>-<H>-<gamma>-<M>.npy."""
    return f"{track_name}_novelty_{ntype}_{N}-{H}-{gamma}-{M}.npy"


def _compute_novelty(
    x: np.ndarray,
    sr: int,
    ntype: str,
    N: int,
    H: int,
    gamma: float,
    M: int,
) -> tuple[np.ndarray, float]:
    """Dispatch to novelty method and return novelty with its feature sample rate."""
    Fs = float(sr)
    if ntype == "spectrum":
        novelty, novelty_fs_hz = compute_novelty_spectrum(
            x, Fs=Fs, N=N, H=H, gamma=gamma, M=M, norm=True, Fs_target=100.0
        )
    elif ntype == "energy":
        novelty, novelty_fs_hz = compute_novelty_energy(
            x, Fs=Fs, N=N, H=H, gamma=gamma, norm=True, Fs_target=100.0
        )
    elif ntype == "phase":
        novelty, novelty_fs_hz = compute_novelty_phase(
            x, Fs=Fs, N=N, H=H, M=M, norm=True, Fs_target=100.0
        )
    elif ntype == "complex":
        novelty, novelty_fs_hz = compute_novelty_complex(
            x, Fs=Fs, N=N, H=H, gamma=gamma, M=M, norm=True, Fs_target=100.0
        )
    else:
        raise ValueError(f"Unknown novelty type: {ntype}")
    return novelty, float(novelty_fs_hz)


def run_novelty(
    *,
    audio_files: list[Path] | None = None,
    output_dir: Path = NOVELTY_OUTPUT_DIR,
    raw_audio_dir: Path = RAW_AUDIO_DIR,
    ntype: str = "spectrum",
    N: int | None = None,
    H: int | None = None,
    gamma: float | None = None,
    M: int | None = None,
    dry_run: bool = False,
    start_marker: str | None = None,
    end_marker: str | None = None,
) -> dict:
    """Compute novelty for audio file(s) and write .npy to output_dir.

    If audio_files is None or empty, uses all .wav files in raw_audio_dir.
    Parameters N, H, gamma, M default from NOVELTY_DEFAULTS for the chosen type.
    Output filename: <track-name>_novelty_<type>_<N>-<H>-<gamma>-<M>.npy.
    Overwrites only when the exact output path already exists (same params).
    Different params produce a different filename, so no overwrite conflict.

    Returns:
        Dict with success, total, succeeded, failed, skipped, message, items, failures.
    """
    if ntype not in NOVELTY_TYPES:
        return {
            "success": False,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": f"Unknown novelty type: {ntype}. Use one of: {sorted(NOVELTY_TYPES)}",
            "items": [],
            "failures": [],
        }

    defaults = NOVELTY_DEFAULTS[ntype]
    N = N if N is not None else defaults[0]
    H = H if H is not None else defaults[1]
    gamma = gamma if gamma is not None else defaults[2]
    M = M if M is not None else defaults[3]

    paths = _resolve_audio_files(audio_files, raw_audio_dir)
    if not paths:
        return {
            "success": True,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "message": "No audio files to process.",
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

    for audio_path in paths:
        track_name = _track_name(audio_path)
        out_name = _output_filename(track_name, ntype, N, H, gamma, M)
        out_path = output_dir / out_name

        if not audio_path.exists():
            failed += 1
            failures.append({"item": str(audio_path), "reason": "File not found"})
            items.append({"file": str(audio_path), "status": "failed", "detail": "File not found"})
            continue

        try:
            start_sec, end_sec, start_name, end_name = resolve_audio_region_with_names(
                audio_path,
                start_marker=start_marker,
                end_marker=end_marker,
            )
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            y = y[int(start_sec * sr) : int(end_sec * sr)]
            novelty, novelty_fs_hz = _compute_novelty(y, sr, ntype, N, H, gamma, M)
            if not dry_run:
                np.save(out_path, novelty, allow_pickle=False)
            succeeded += 1
            items.append({
                "file": audio_path.name,
                "output": out_name,
                "status": "success",
                "start_marker": start_name,
                "end_marker": end_name,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "num_features": int(len(novelty)),
                "novelty_sample_rate_hz": novelty_fs_hz,
            })
        except Exception as e:
            failed += 1
            failures.append({"item": str(audio_path), "reason": str(e)})
            items.append({"file": audio_path.name, "status": "failed", "detail": str(e)})

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
