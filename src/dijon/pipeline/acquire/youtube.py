"""Acquisition verb for YouTube source.

Scans already-downloaded YouTube bundles and writes acquisition manifest entries.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ...global_config import DATA_DIR
from ...utils.manifest import (
    append_manifest_row,
    compute_file_checksum,
    normalize_meta_json,
    read_manifest,
)


def acquire(
    acquisition_dir: Path,
    manifest_path: Path,
    *,
    data_dir: Path = DATA_DIR,
    dry_run: bool = False,
) -> dict[str, str | int | bool]:
    """Acquire manifest entries for already-downloaded YouTube bundles.

    Scans info_json files in the acquisition directory and creates manifest rows
    for each asset (mp3, jpg, json, optional mp4) with status="active".

    Args:
        acquisition_dir: Directory containing YouTube acquisition files.
        manifest_path: Path to manifest.csv file to write.
        data_dir: Data directory root for rel_path normalization. Defaults to DATA_DIR.
        dry_run: If True, simulate the operation without writing files.

    Returns:
        Result dictionary with:
        - success: bool
        - files_processed: int (number of bundles processed)
        - rows_added: int (number of manifest rows added)
        - message: str (summary message)
    """
    if not acquisition_dir.exists():
        return {
            "success": False,
            "files_processed": 0,
            "rows_added": 0,
            "message": f"Acquisition directory not found: {acquisition_dir}",
        }

    # Find all info_json files
    info_json_files = sorted(acquisition_dir.glob("*.json"))
    if not info_json_files:
        return {
            "success": True,
            "files_processed": 0,
            "rows_added": 0,
            "message": f"No JSON files found in {acquisition_dir}",
        }

    if dry_run:
        return {
            "success": True,
            "files_processed": len(info_json_files),
            "rows_added": 0,
            "message": f"[DRY RUN] Would process {len(info_json_files)} bundles",
        }

    # Read existing manifest for idempotency checks
    existing_rows = read_manifest(manifest_path, profile="upstream") if manifest_path.exists() else []
    existing_by_rel_path: dict[str, str] = {
        row["rel_path"]: row["sha256"] for row in existing_rows if row.get("rel_path")
    }

    rows_added = 0
    bundles_processed = 0
    errors: list[str] = []

    for info_json_file in info_json_files:
        try:
            bundle_result = _process_bundle(
                info_json_file=info_json_file,
                acquisition_dir=acquisition_dir,
                manifest_path=manifest_path,
                data_dir=data_dir,
                existing_by_rel_path=existing_by_rel_path,
            )
            rows_added += bundle_result["rows_added"]
            bundles_processed += 1
            if bundle_result.get("errors"):
                errors.extend(bundle_result["errors"])
        except Exception as e:
            errors.append(f"Error processing {info_json_file.name}: {e}")

    success = len(errors) == 0
    message = f"Processed {bundles_processed} bundles, added {rows_added} manifest rows"
    if errors:
        message += f" ({len(errors)} errors)"

    return {
        "success": success,
        "files_processed": bundles_processed,
        "rows_added": rows_added,
        "message": message,
        "errors": errors if errors else None,
    }


def _process_bundle(
    info_json_file: Path,
    acquisition_dir: Path,
    manifest_path: Path,
    data_dir: Path,
    existing_by_rel_path: dict[str, str],
) -> dict[str, int | list[str]]:
    """Process a single YouTube bundle (info_json + assets).

    Args:
        info_json_file: Path to the info_json file.
        acquisition_dir: Directory containing acquisition files.
        manifest_path: Path to manifest.csv.
        data_dir: Data directory root for rel_path normalization.
        existing_by_rel_path: Dict mapping rel_path -> sha256 for idempotency.

    Returns:
        Dict with rows_added (int) and optional errors (list[str]).
    """
    # Load info_json
    with open(info_json_file, "r", encoding="utf-8") as f:
        info_data = json.load(f)

    # Extract youtube_id and URL
    youtube_id = _extract_youtube_id(info_data, info_json_file)
    url = _extract_url(info_data)

    if not youtube_id:
        return {
            "rows_added": 0,
            "errors": [f"Could not extract youtube_id from {info_json_file.name}"],
        }

    # Determine asset files (JSON-first approach)
    base_name = info_json_file.stem
    assets = _determine_assets(info_data, base_name, acquisition_dir)

    rows_added = 0
    errors: list[str] = []

    # Process each asset
    for asset_role, asset_file in assets.items():
        if not asset_file.exists():
            continue

        # Compute rel_path relative to data_dir
        rel_path = str(asset_file.relative_to(data_dir))

        # Check idempotency
        existing_sha256 = existing_by_rel_path.get(rel_path)
        if existing_sha256 is not None:
            # Compute current sha256
            current_sha256 = compute_file_checksum(asset_file)
            if current_sha256 == existing_sha256:
                # Already in manifest with same checksum - skip
                continue
            else:
                # Same rel_path but different checksum - error
                errors.append(
                    f"Manifest conflict: {rel_path} exists with different sha256 "
                    f"(existing: {existing_sha256[:8]}..., current: {current_sha256[:8]}...)"
                )
                continue

        # Compute checksum
        sha256 = compute_file_checksum(asset_file)

        # Build meta_json
        meta_json_obj = {
            "upstream": {"kind": "youtube", "url": url, "youtube_id": youtube_id},
            "bundle_id": youtube_id,
            "asset_role": asset_role,
        }
        meta_json = json.dumps(meta_json_obj, sort_keys=True, separators=(",", ":"))

        # Append manifest row
        try:
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path=rel_path,
                status="active",
                sha256=sha256,
                source_name=asset_file.name,
                schema_version="1",
                profile="upstream",
                validate="row",
                meta_json=meta_json,
            )
            rows_added += 1
            # Update existing_by_rel_path for subsequent checks in this run
            existing_by_rel_path[rel_path] = sha256
        except Exception as e:
            errors.append(f"Failed to append manifest row for {asset_file.name}: {e}")

    return {"rows_added": rows_added, "errors": errors if errors else []}


def _extract_youtube_id(info_data: dict, info_json_file: Path) -> str | None:
    """Extract YouTube ID from info_json data or filename.

    Prefers yt_dlp.id, falls back to parsing URL or filename.
    """
    # Try yt_dlp.id first
    if "yt_dlp" in info_data and isinstance(info_data["yt_dlp"], dict):
        yt_id = info_data["yt_dlp"].get("id")
        if yt_id:
            return yt_id

    # Try parsing from input_url
    input_url = info_data.get("input_url", "")
    if input_url:
        match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", input_url)
        if match:
            return match.group(1)

    # Try parsing from filename (format: Name_YOUTUBE_ID.json)
    filename = info_json_file.stem
    # Look for 11-character YouTube ID pattern at end of filename
    match = re.search(r"_([a-zA-Z0-9_-]{11})$", filename)
    if match:
        return match.group(1)

    return None


def _extract_url(info_data: dict) -> str:
    """Extract YouTube URL from info_json data.

    Prefers yt_dlp.webpage_url, falls back to input_url.
    """
    if "yt_dlp" in info_data and isinstance(info_data["yt_dlp"], dict):
        url = info_data["yt_dlp"].get("webpage_url")
        if url:
            return url

    return info_data.get("input_url", "")


def _determine_assets(
    info_data: dict, base_name: str, acquisition_dir: Path
) -> dict[str, Path]:
    """Determine asset file paths for a bundle.

    Uses JSON-first approach: prefers downloaded.* fields, falls back to filename patterns.

    Returns:
        Dict mapping asset_role -> Path. Keys: "audio", "thumb", "info_json", optionally "video".
    """
    assets: dict[str, Path] = {}

    # Always include the info_json file itself
    info_json_path = acquisition_dir / f"{base_name}.json"
    if info_json_path.exists():
        assets["info_json"] = info_json_path

    # JSON-first: check downloaded block
    downloaded = info_data.get("downloaded", {})
    if isinstance(downloaded, dict):
        # Audio (mp3)
        mp3_name = downloaded.get("mp3")
        if mp3_name and mp3_name != "null":
            mp3_path = acquisition_dir / mp3_name
            if mp3_path.exists():
                assets["audio"] = mp3_path

        # Thumbnail
        thumb_name = downloaded.get("thumbnail")
        if thumb_name and thumb_name != "null":
            thumb_path = acquisition_dir / thumb_name
            if thumb_path.exists():
                assets["thumb"] = thumb_path

        # Video (optional)
        mp4_name = downloaded.get("mp4")
        if mp4_name and mp4_name != "null":
            mp4_path = acquisition_dir / mp4_name
            if mp4_path.exists():
                assets["video"] = mp4_path

    # Fallback: infer from base_name and extensions
    if "audio" not in assets:
        for ext in [".mp3", ".m4a", ".wav", ".flac"]:
            audio_path = acquisition_dir / f"{base_name}{ext}"
            if audio_path.exists():
                assets["audio"] = audio_path
                break

    if "thumb" not in assets:
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            thumb_path = acquisition_dir / f"{base_name}{ext}"
            if thumb_path.exists():
                assets["thumb"] = thumb_path
                break

    if "video" not in assets:
        video_path = acquisition_dir / f"{base_name}.mp4"
        if video_path.exists():
            assets["video"] = video_path

    return assets
