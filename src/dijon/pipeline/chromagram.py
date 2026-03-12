"""Pipeline for computing metric chromagrams from audio and meter maps.

Invariant: meter_map[:, 0] and the waveform passed to metric_chromagram must be
on the same timebase. When meter maps come from marker-trimmed novelty/beats,
chromagram audio must be trimmed to the same marker-defined region.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from ..chromagram import metric_chromagram
from ..global_config import DERIVED_DIR, RAW_AUDIO_DIR
from ..utils.audio_region import resolve_audio_region

METER_DIR = DERIVED_DIR / "meter"
CHROMAGRAM_OUTPUT_DIR = DERIVED_DIR / "chromagram"


def _resolve_audio_files(files: list[Path] | None, raw_audio_dir: Path) -> list[Path]:
    """Return list of audio paths: explicit files if given, else all .wav in raw_audio_dir.

    When files are provided, each item is resolved as follows:
    - Full path (absolute or with directory): used as-is.
    - Basename only (e.g. YTB-014, YTB-014.wav): resolved to raw_audio_dir / <track_id>.wav.
    """
    if not files:
        if not raw_audio_dir.exists():
            return []
        return sorted(raw_audio_dir.glob("*.wav"))

    resolved: list[Path] = []
    for p in files:
        path = Path(p)
        is_shorthand = not path.is_absolute() and len(path.parts) == 1
        if is_shorthand:
            stem = path.stem
            resolved.append((raw_audio_dir / f"{stem}.wav").resolve())
        else:
            resolved.append(path.resolve())
    return list(dict.fromkeys(resolved))


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
    start_marker: str | None = None,
    end_marker: str | None = None,
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
    """Compute metric chromagram for audio file(s) and write .npy to output_dir.

    start_marker, end_marker: When both provided, trim audio to the marker-defined
    region (same as novelty pipeline). Meter maps from novelty/beats are region-relative;
    use the same markers to align timelines. When omitted, use full audio.
    """
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
            region_start_sec: float | None = None
            region_end_sec: float | None = None

            if start_marker is not None and end_marker is not None:
                # Trim waveform so audio and meter_map share the same region-local time origin.
                start_sec, end_sec = resolve_audio_region(
                    audio_path,
                    start_marker=start_marker,
                    end_marker=end_marker,
                )
                start_ix = int(start_sec * sr)
                end_ix = int(end_sec * sr)
                y = y[start_ix:end_ix]
                region_start_sec = start_sec
                region_end_sec = end_sec

            meter_map = np.load(meter_path).astype(np.float64)
            C_metric = metric_chromagram(
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
            item: dict = {
                "file": audio_path.name,
                "meter": meter_path.name,
                "output": out_name,
                "status": "success",
            }
            if region_start_sec is not None and region_end_sec is not None:
                item["region_start_sec"] = region_start_sec
                item["region_end_sec"] = region_end_sec
            items.append(item)
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
