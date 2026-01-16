"""Ingestion verb for YouTube source.

Ingestion copies acquisition MP3s into the raw layer with manifest entries.
This verb is idempotent: re-running with the same acq_sha256 will no-op.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ...global_config import DATA_DIR
from ...sources.registry import get_source_code
from ...utils._manifest import (
    append_manifest_row,
    compute_file_checksum,
    generate_next_file_id,
    read_manifest,
)


def ingest(
    acquisition_dir: Path,
    raw_dir: Path,
    raw_manifest_path: Path,
    acquisition_manifest_path: Path,
    *,
    data_dir: Path = DATA_DIR,
    dry_run: bool = False,
) -> dict[str, str | int | bool | list[str]]:
    """Ingest YouTube acquisition MP3s into the canonical raw layer.

    Scans info_json files in acquisition_dir and ingests all MP3s that are not
    already ingested (based on acq_sha256 check).

    Args:
        acquisition_dir: Directory containing YouTube acquisition files.
        raw_dir: Directory for raw files (data/raw/audio/).
        raw_manifest_path: Path to raw manifest.csv file.
        acquisition_manifest_path: Path to acquisition manifest.csv file.
        data_dir: Data directory root for rel_path normalization. Defaults to DATA_DIR.
        dry_run: If True, simulate the operation without writing files.

    Returns:
        Result dictionary with:
        - success: bool
        - total: int (number of bundles scanned)
        - ingested: int (number of MP3s ingested)
        - skipped: int (number already ingested)
        - failed: int (number that failed)
        - message: str (summary message)
        - failures: list[str] (error messages for failed ingestions)
    """
    if not acquisition_dir.exists():
        return {
            "success": False,
            "total": 0,
            "ingested": 0,
            "skipped": 0,
            "failed": 0,
            "message": f"Acquisition directory not found: {acquisition_dir}",
            "failures": [],
        }

    # Find all info_json files
    info_json_files = sorted(acquisition_dir.glob("*.json"))
    if not info_json_files:
        return {
            "success": True,
            "total": 0,
            "ingested": 0,
            "skipped": 0,
            "failed": 0,
            "message": f"No JSON files found in {acquisition_dir}",
            "failures": [],
        }

    # Read acquisition manifest to get MP3 sha256 values
    acquisition_manifest_rows = (
        read_manifest(acquisition_manifest_path, profile="upstream")
        if acquisition_manifest_path.exists()
        else []
    )
    # Build index: rel_path -> sha256 for audio assets
    acq_audio_sha256: dict[str, str] = {}
    for row in acquisition_manifest_rows:
        meta_json_str = row.get("meta_json", "")
        if meta_json_str:
            try:
                meta_json = json.loads(meta_json_str)
                if meta_json.get("asset_role") == "audio":
                    rel_path = row.get("rel_path", "")
                    sha256 = row.get("sha256", "")
                    if rel_path and sha256:
                        acq_audio_sha256[rel_path] = sha256
            except (json.JSONDecodeError, KeyError):
                continue

    # Read raw manifest for idempotency check
    raw_manifest_rows = (
        read_manifest(raw_manifest_path, profile="raw") if raw_manifest_path.exists() else []
    )
    ingested_acq_sha256: set[str] = set()
    for row in raw_manifest_rows:
        acq_sha256 = row.get("acq_sha256", "").strip()
        status = row.get("status", "").strip()
        if acq_sha256 and status in ("active", "superseded"):
            ingested_acq_sha256.add(acq_sha256)

    ingested_count = 0
    skipped_count = 0
    failed_count = 0
    failures: list[str] = []
    # Track acq_sha256 values processed in this run to avoid duplicates
    processed_acq_sha256 = ingested_acq_sha256.copy()

    for info_json_file in info_json_files:
        try:
            result = _ingest_bundle(
                info_json_file=info_json_file,
                acquisition_dir=acquisition_dir,
                raw_dir=raw_dir,
                raw_manifest_path=raw_manifest_path,
                data_dir=data_dir,
                acq_audio_sha256=acq_audio_sha256,
                ingested_acq_sha256=processed_acq_sha256,
                dry_run=dry_run,
            )
            if result["status"] == "ingested":
                ingested_count += 1
                # Update processed set to avoid duplicates in same run
                if "acq_sha256" in result:
                    processed_acq_sha256.add(result["acq_sha256"])
            elif result["status"] == "skipped":
                skipped_count += 1
            elif result["status"] == "failed":
                failed_count += 1
                failures.append(result["error"])
        except Exception as e:
            failed_count += 1
            failures.append(f"Error processing {info_json_file.name}: {e}")

    success = failed_count == 0
    message = (
        f"Processed {len(info_json_files)} bundles: "
        f"{ingested_count} ingested, {skipped_count} skipped"
    )
    if failed_count > 0:
        message += f", {failed_count} failed"

    return {
        "success": success,
        "total": len(info_json_files),
        "ingested": ingested_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "message": message,
        "failures": failures if failures else [],
    }


def _ingest_bundle(
    info_json_file: Path,
    acquisition_dir: Path,
    raw_dir: Path,
    raw_manifest_path: Path,
    data_dir: Path,
    acq_audio_sha256: dict[str, str],
    ingested_acq_sha256: set[str],
    dry_run: bool,
) -> dict[str, str]:
    """Ingest a single YouTube bundle's MP3 into raw.

    Args:
        info_json_file: Path to the info_json file.
        acquisition_dir: Directory containing acquisition files.
        raw_dir: Directory for raw files.
        raw_manifest_path: Path to raw manifest.csv.
        data_dir: Data directory root for rel_path normalization.
        acq_audio_sha256: Dict mapping acquisition MP3 rel_path -> sha256.
        ingested_acq_sha256: Set of acq_sha256 values already ingested.
        dry_run: If True, simulate without writing.

    Returns:
        Dict with status ("ingested", "skipped", "failed") and optional error.
    """
    # Load info_json
    with open(info_json_file, "r", encoding="utf-8") as f:
        info_data = json.load(f)

    # Extract youtube_id and URL
    youtube_id = _extract_youtube_id(info_data, info_json_file)
    url = _extract_url(info_data)

    if not youtube_id:
        return {
            "status": "failed",
            "error": f"Could not extract youtube_id from {info_json_file.name}",
        }

    # Determine MP3 file path
    base_name = info_json_file.stem
    downloaded = info_data.get("downloaded", {})
    mp3_filename = None
    if isinstance(downloaded, dict):
        mp3_filename = downloaded.get("mp3")
        if mp3_filename == "null" or not mp3_filename:
            mp3_filename = None

    # Fallback: try common extensions
    if not mp3_filename:
        for ext in [".mp3", ".m4a", ".wav", ".flac"]:
            candidate = acquisition_dir / f"{base_name}{ext}"
            if candidate.exists():
                mp3_filename = candidate.name
                break

    if not mp3_filename:
        return {
            "status": "skipped",
            "error": f"No MP3 found for bundle {youtube_id}",
        }

    mp3_path = acquisition_dir / mp3_filename
    if not mp3_path.exists():
        return {
            "status": "skipped",
            "error": f"MP3 file not found: {mp3_filename}",
        }

    # Get acq_sha256 (prefer from manifest, fallback to compute)
    mp3_rel_path = str(mp3_path.relative_to(data_dir))
    acq_sha256 = acq_audio_sha256.get(mp3_rel_path)
    if not acq_sha256:
        # Compute from file
        acq_sha256 = compute_file_checksum(mp3_path)

    # Check if already ingested
    if acq_sha256 in ingested_acq_sha256:
        return {"status": "skipped"}

    if dry_run:
        ingest_date = datetime.now(UTC)
        file_id = generate_next_file_id(get_source_code("youtube"), raw_manifest_path, ingest_date)
        return {
            "status": "ingested",
            "file_id": file_id,
        }

    # Ensure raw directory exists
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Generate file_id
    ingest_date = datetime.now(UTC)
    file_id = generate_next_file_id(get_source_code("youtube"), raw_manifest_path, ingest_date)

    # Copy MP3 to raw layer
    raw_file = raw_dir / f"{file_id}.mp3"
    raw_file.write_bytes(mp3_path.read_bytes())

    # Compute raw file checksum and compare to acquisition
    raw_sha256 = compute_file_checksum(raw_file)
    if raw_sha256 != acq_sha256:
        # Clean up the copied file
        raw_file.unlink(missing_ok=True)
        return {
            "status": "failed",
            "error": (
                f"Checksum mismatch for {mp3_filename}: "
                f"acquisition sha256={acq_sha256[:8]}..., "
                f"raw sha256={raw_sha256[:8]}..."
            ),
        }

    # Build meta_json
    yt_dlp = info_data.get("yt_dlp", {})
    duration_seconds = yt_dlp.get("duration", 0)
    duration_ms = int(duration_seconds * 1000) if duration_seconds else 0
    tags = yt_dlp.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    meta_json_obj = {
        "song_name": info_data.get("song_name", ""),
        "input_url": info_data.get("input_url", url),
        "title": yt_dlp.get("title", ""),
        "description": yt_dlp.get("description", ""),
        "duration_ms": duration_ms,
        "tags": tags,
        "upstream": {
            "kind": "youtube",
            "url": url,
            "youtube_id": youtube_id,
        },
    }
    meta_json = json.dumps(meta_json_obj, sort_keys=True, separators=(",", ":"))

    # Write manifest entry
    ingested_at = ingest_date.isoformat().replace("+00:00", "Z")
    rel_path = str(raw_file.relative_to(data_dir))
    try:
        append_manifest_row(
            manifest_path=raw_manifest_path,
            rel_path=rel_path,
            status="active",
            sha256=raw_sha256,
            source_name=mp3_filename,
            schema_version="1",
            profile="raw",
            validate="row",
            file_id=file_id,
            ingested_at=ingested_at,
            acq_sha256=acq_sha256,
            meta_json=meta_json,
        )
    except Exception as e:
        # Clean up the copied file if manifest write fails
        raw_file.unlink(missing_ok=True)
        return {
            "status": "failed",
            "error": f"Failed to write manifest row: {e}",
        }

    return {
        "status": "ingested",
        "file_id": file_id,
        "acq_sha256": acq_sha256,
    }


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
        import re

        match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", input_url)
        if match:
            return match.group(1)

    # Try parsing from filename (format: Name_YOUTUBE_ID.json)
    filename = info_json_file.stem
    import re

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
