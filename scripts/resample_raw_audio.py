#!/usr/bin/env python3
"""One-time script to resample existing WAV files in raw audio directory to 22050 Hz.

Converts all WAV files in data/datasets/raw/audio/ to 22050 Hz sample rate
and updates manifest.csv entries accordingly. Preserves audio duration so markers
remain valid.

This script is idempotent: re-running will skip already-resampled files.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add src to path so we can import dijon modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dijon.global_config import DATA_DIR, RAW_AUDIO_DIR
from dijon.utils.manifest import compute_file_checksum, read_manifest, write_manifest


def resample_wav_to_22050(input_path: Path, output_path: Path) -> None:
    """Resample WAV file to 22050 Hz sample rate.

    Args:
        input_path: Path to input WAV file.
        output_path: Path where resampled WAV will be written.

    Raises:
        subprocess.CalledProcessError: If ffmpeg conversion fails.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-i", str(input_path),
            "-ac", "1",  # mono
            "-ar", "22050",  # 22.05kHz sample rate
            "-c:a", "pcm_s16le",  # PCM 16-bit little-endian
            "-f", "wav",  # explicitly specify WAV format
            "-y",  # overwrite output file
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def resample_raw_audio(*, dry_run: bool = False, no_backup: bool = False) -> dict:
    """Resample all WAV files in raw audio directory to 22050 Hz.

    Args:
        dry_run: If True, simulate without making changes.
        no_backup: If True, skip creating manifest backup (not recommended).

    Returns:
        Dictionary with success status and conversion statistics.
    """
    manifest_path = RAW_AUDIO_DIR / "manifest.csv"

    if not manifest_path.exists():
        return {
            "success": False,
            "resampled": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [f"Manifest not found: {manifest_path}"],
        }

    # Read manifest
    try:
        rows = read_manifest(manifest_path, profile="raw")
    except Exception as e:
        return {
            "success": False,
            "resampled": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [f"Failed to read manifest: {e}"],
        }

    # Filter to active rows only
    active_rows = [row for row in rows if row.get("status", "").strip() == "active"]

    resampled_count = 0
    skipped_count = 0
    failed_count = 0
    errors: list[str] = []
    updated_rows = []

    # Process each row
    for row in rows:
        rel_path = row.get("rel_path", "").strip()
        file_id = row.get("file_id", "").strip()

        # Skip if not active
        if row.get("status", "").strip() != "active":
            updated_rows.append(row)
            continue

        # Skip if not WAV
        if not rel_path.endswith(".wav"):
            updated_rows.append(row)
            continue

        # Resolve absolute path
        wav_path = DATA_DIR / rel_path
        if not wav_path.exists():
            failed_count += 1
            errors.append(f"{file_id}: WAV file not found at {rel_path}")
            updated_rows.append(row)  # Keep original row
            continue

        # Check current sample rate (skip if already 22050)
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=sample_rate",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(wav_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            current_sr = int(result.stdout.strip())
            if current_sr == 22050:
                skipped_count += 1
                updated_rows.append(row)
                continue
        except (subprocess.CalledProcessError, ValueError) as e:
            # If we can't check sample rate, proceed with conversion
            pass

        if dry_run:
            print(f"[DRY RUN] Would resample: {wav_path.name} to 22050 Hz")
            resampled_count += 1
            # Create updated row for dry-run preview
            updated_row = row.copy()
            updated_row["sha256"] = "[would be computed]"
            updated_rows.append(updated_row)
            continue

        # Create temporary output file (use .tmp.wav so ffmpeg recognizes format)
        temp_wav_path = wav_path.with_suffix(".tmp.wav")

        # Resample WAV → 22050 Hz
        try:
            resample_wav_to_22050(wav_path, temp_wav_path)
        except Exception as e:
            failed_count += 1
            errors.append(f"{file_id}: Resampling failed: {e}")
            temp_wav_path.unlink(missing_ok=True)
            updated_rows.append(row)  # Keep original row
            continue

        # Compute new SHA256 for resampled file
        try:
            new_sha256 = compute_file_checksum(temp_wav_path)
        except Exception as e:
            failed_count += 1
            errors.append(f"{file_id}: Failed to compute checksum: {e}")
            temp_wav_path.unlink(missing_ok=True)
            updated_rows.append(row)  # Keep original row
            continue

        # Replace original with resampled file
        try:
            # Backup original (optional, but safe)
            backup_path = wav_path.with_suffix(".wav.backup")
            shutil.copy2(wav_path, backup_path)
            # Replace original with resampled
            temp_wav_path.replace(wav_path)
            # Remove backup after successful replacement
            backup_path.unlink()
        except Exception as e:
            failed_count += 1
            errors.append(f"{file_id}: Failed to replace file: {e}")
            temp_wav_path.unlink(missing_ok=True)
            backup_path.unlink(missing_ok=True)
            updated_rows.append(row)  # Keep original row
            continue

        # Update row
        updated_row = row.copy()
        updated_row["sha256"] = new_sha256
        # Preserve all other fields (acq_sha256, ingested_at, source_name, meta_json, etc.)

        updated_rows.append(updated_row)
        resampled_count += 1
        print(f"Resampled: {wav_path.name} to 22050 Hz")

    # Write updated manifest (unless dry-run)
    if not dry_run and resampled_count > 0:
        # Create backup
        if not no_backup:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = manifest_path.with_suffix(f".csv.backup-{timestamp}")
            try:
                shutil.copy2(manifest_path, backup_path)
                print(f"Created manifest backup: {backup_path}")
            except Exception as e:
                return {
                    "success": False,
                    "resampled": resampled_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                    "errors": errors + [f"Failed to create backup: {e}"],
                }

        # Write updated manifest
        try:
            write_manifest(manifest_path, updated_rows, profile="raw")
        except Exception as e:
            # Restore from backup if write failed
            if not no_backup and backup_path.exists():
                try:
                    shutil.copy2(backup_path, manifest_path)
                    print(f"Restored manifest from backup due to write failure")
                except Exception as restore_error:
                    errors.append(f"Failed to restore backup: {restore_error}")
            return {
                "success": False,
                "resampled": resampled_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "errors": errors + [f"Failed to write manifest: {e}"],
            }

    success = failed_count == 0
    return {
        "success": success,
        "resampled": resampled_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "errors": errors,
    }


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Resample existing WAV files in raw audio directory to 22050 Hz."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate conversion without making changes",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating manifest backup (not recommended)",
    )

    args = parser.parse_args()

    print("Resampling raw audio files to 22050 Hz...")
    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    result = resample_raw_audio(dry_run=args.dry_run, no_backup=args.no_backup)

    print(f"\nResults:")
    print(f"  Resampled: {result['resampled']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Failed: {result['failed']}")

    if result["errors"]:
        print(f"\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
