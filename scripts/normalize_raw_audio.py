#!/usr/bin/env python3
"""One-time migration script to normalize existing MP3 files to canonical WAV format.

Converts all MP3 files in data/datasets/raw/audio/ to mono 48kHz PCM WAV format
and updates manifest.csv entries accordingly. Preserves audio duration so markers
remain valid.

This script is idempotent: re-running will skip already-converted files.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add src to path so we can import dijon modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dijon.global_config import DATA_DIR, RAW_AUDIO_DIR
from dijon.pipeline.ingest.youtube import _convert_to_canonical_wav
from dijon.utils.manifest import compute_file_checksum, read_manifest, write_manifest


def normalize_raw_audio(*, dry_run: bool = False, no_backup: bool = False) -> dict:
    """Normalize all MP3 files in raw audio directory to canonical WAV format.

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
            "converted": 0,
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
            "converted": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [f"Failed to read manifest: {e}"],
        }

    # Filter to active rows only
    active_rows = [row for row in rows if row.get("status", "").strip() == "active"]

    converted_count = 0
    skipped_count = 0
    failed_count = 0
    errors: list[str] = []
    updated_rows = []

    # Process each active row
    for row in rows:
        rel_path = row.get("rel_path", "").strip()
        file_id = row.get("file_id", "").strip()

        # Skip if not active
        if row.get("status", "").strip() != "active":
            updated_rows.append(row)
            continue

        # Skip if already WAV (idempotency)
        if rel_path.endswith(".wav"):
            skipped_count += 1
            updated_rows.append(row)
            continue

        # Skip if not MP3
        if not rel_path.endswith(".mp3"):
            updated_rows.append(row)
            continue

        # Resolve absolute path
        # Try multiple possible locations (handle legacy rel_path formats)
        mp3_path = None
        for base_dir in [RAW_AUDIO_DIR, DATA_DIR / rel_path, DATA_DIR / "datasets" / rel_path]:
            candidate = base_dir / Path(rel_path).name if base_dir == RAW_AUDIO_DIR else base_dir
            if candidate.exists():
                mp3_path = candidate
                break
        
        if mp3_path is None or not mp3_path.exists():
            failed_count += 1
            errors.append(f"{file_id}: MP3 file not found for rel_path: {rel_path}")
            updated_rows.append(row)  # Keep original row
            continue

        # Determine WAV path (same directory as MP3)
        wav_path = mp3_path.with_suffix(".wav")
        # Update rel_path to match the actual location relative to DATA_DIR
        wav_rel_path = str(wav_path.relative_to(DATA_DIR))

        if dry_run:
            print(f"[DRY RUN] Would convert: {mp3_path.name} → {wav_path.name}")
            converted_count += 1
            # Create updated row for dry-run preview
            updated_row = row.copy()
            updated_row["rel_path"] = wav_rel_path
            updated_row["sha256"] = "[would be computed]"
            updated_rows.append(updated_row)
            continue

        # Convert MP3 → WAV
        try:
            _convert_to_canonical_wav(mp3_path, wav_path)
        except Exception as e:
            failed_count += 1
            errors.append(f"{file_id}: Conversion failed: {e}")
            updated_rows.append(row)  # Keep original row
            continue

        # Compute new SHA256 for WAV file
        try:
            wav_sha256 = compute_file_checksum(wav_path)
        except Exception as e:
            failed_count += 1
            errors.append(f"{file_id}: Failed to compute WAV checksum: {e}")
            # Clean up WAV file if checksum failed
            wav_path.unlink(missing_ok=True)
            updated_rows.append(row)  # Keep original row
            continue

        # Update row
        updated_row = row.copy()
        updated_row["rel_path"] = wav_rel_path
        updated_row["sha256"] = wav_sha256
        # Preserve all other fields (acq_sha256, ingested_at, source_name, meta_json, etc.)

        # Delete old MP3 file
        try:
            mp3_path.unlink()
        except Exception as e:
            # Log warning but don't fail - WAV conversion succeeded
            errors.append(f"{file_id}: Warning - failed to delete MP3: {e}")

        updated_rows.append(updated_row)
        converted_count += 1
        print(f"Converted: {mp3_path.name} → {wav_path.name}")

    # Write updated manifest (unless dry-run)
    if not dry_run and converted_count > 0:
        # Create backup
        if not no_backup:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = manifest_path.with_suffix(f".csv.backup-{timestamp}")
            try:
                shutil.copy2(manifest_path, backup_path)
                print(f"Created backup: {backup_path}")
            except Exception as e:
                return {
                    "success": False,
                    "converted": converted_count,
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
                "converted": converted_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "errors": errors + [f"Failed to write manifest: {e}"],
            }

    success = failed_count == 0
    return {
        "success": success,
        "converted": converted_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "errors": errors,
    }


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Normalize existing MP3 files in raw audio directory to canonical WAV format."
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

    print("Normalizing raw audio files...")
    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]")

    result = normalize_raw_audio(dry_run=args.dry_run, no_backup=args.no_backup)

    print(f"\nResults:")
    print(f"  Converted: {result['converted']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Failed: {result['failed']}")

    if result["errors"]:
        print(f"\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
