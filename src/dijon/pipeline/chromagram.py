"""Pipeline for computing metric chromagrams from audio and meter maps."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from ..chromagram import metric_chromagram_mvp
from ..global_config import DERIVED_DIR, RAW_AUDIO_DIR

METER_DIR = DERIVED_DIR / "meter"
CHROMAGRAM_OUTPUT_DIR = DERIVED_DIR / "chromagram"


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


def _meter_path_for_track(track_name: str, meter_dir: Path) -> Path:
    """Return expected meter path for track."""
    return meter_dir / f"{track_name}_meter.npy"


def _output_filename(
    track_name: str,
    *,
    chroma_type: str,
    hop_length: int,
    bpm_threshold: float,
    aggregate: str,
    accent_mode: str,
    weight_source: str,
    weight_power: float,
    min_frames_per_bin: int,
) -> str:
    """Build output filename encoding key metric-chromagram parameters."""
    return (
        f"{track_name}_chromagram_metric_{chroma_type}_"
        f"{hop_length}-{bpm_threshold}-{aggregate}-{accent_mode}-{weight_source}-{weight_power}-{min_frames_per_bin}.npy"
    )


def run_chromagram(
    *,
    audio_files: list[Path] | None = None,
    output_dir: Path = CHROMAGRAM_OUTPUT_DIR,
    raw_audio_dir: Path = RAW_AUDIO_DIR,
    meter_dir: Path = METER_DIR,
    hop_length: int = 256,
    bpm_threshold: float = 180.0,
    chroma_type: str = "cqt",
    aggregate: str = "mean",
    accent_mode: str = "preserve",
    weight_source: str = "rms",
    weight_power: float = 1.0,
    min_frames_per_bin: int = 2,
    dry_run: bool = False,
) -> dict:
    """Compute metric chromagram for audio file(s) and write .npy to output_dir."""
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
    skipped = 0
    items: list[dict] = []
    failures: list[dict] = []

    for audio_path in paths:
        track_name = _track_name(audio_path)
        meter_path = _meter_path_for_track(track_name, meter_dir)

        if not meter_path.exists():
            skipped += 1
            items.append({
                "file": audio_path.name,
                "status": "skipped",
                "detail": f"Missing meter map: {meter_path.name}",
            })
            continue

        out_name = _output_filename(
            track_name,
            chroma_type=chroma_type,
            hop_length=hop_length,
            bpm_threshold=bpm_threshold,
            aggregate=aggregate,
            accent_mode=accent_mode,
            weight_source=weight_source,
            weight_power=weight_power,
            min_frames_per_bin=min_frames_per_bin,
        )
        out_path = output_dir / out_name

        if not audio_path.exists():
            failed += 1
            failures.append({"item": str(audio_path), "reason": "File not found"})
            items.append({"file": audio_path.name, "status": "failed", "detail": "Audio file not found"})
            continue

        try:
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            meter_map = np.load(meter_path).astype(np.float64)
            C_metric = metric_chromagram_mvp(
                y,
                sr=sr,
                meter_map=meter_map,
                hop_length=hop_length,
                bpm_threshold=bpm_threshold,
                chroma_type=chroma_type,
                aggregate=aggregate,
                accent_mode=accent_mode,
                weight_source=weight_source,
                weight_power=weight_power,
                min_frames_per_bin=min_frames_per_bin,
            )
            if not dry_run:
                np.save(out_path, C_metric, allow_pickle=False)

            succeeded += 1
            items.append({
                "file": audio_path.name,
                "meter": meter_path.name,
                "output": out_name,
                "status": "success",
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
        "skipped": skipped,
        "message": f"Processed {len(paths)} file(s). Succeeded: {succeeded}, failed: {failed}, skipped: {skipped}."
        + (" [DRY RUN]" if dry_run else ""),
        "items": items,
        "failures": failures,
    }
