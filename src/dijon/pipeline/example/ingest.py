"""Ingestion verb for example source.

Ingestion canonicalizes acquisition data and writes it to the raw layer with manifest entries.
This verb is idempotent: re-running with the same acq_sha256 will no-op.
"""

from __future__ import annotations

from pathlib import Path

from datetime import UTC, datetime

from ...utils._manifest import (
    append_manifest_row,
    compute_file_checksum,
    generate_next_file_id,
    read_manifest,
)


def ingest(
    source_key: str,
    dataset_code: str,
    acquisition_file: Path,
    raw_dir: Path,
    manifest_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, str | int | bool]:
    """Ingest an acquisition file into the canonical raw layer.

    This is a reference implementation that demonstrates:
    - Idempotency via acq_sha256 check
    - Manifest-driven canonical file management
    - Safe no-op behavior when already ingested

    Args:
        source_key: Source identifier (e.g., "example").
        dataset_code: Dataset code for file_id generation (e.g., "EXM").
        acquisition_file: Path to the acquisition file to ingest.
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        manifest_path: Path to manifest.csv file.
        dry_run: If True, simulate the operation without writing files.

    Returns:
        Result dictionary with:
        - success: bool
        - file_id: str (if ingested) or None (if no-op)
        - message: str (summary message)
        - already_ingested: bool (True if no-op due to existing entry)
    """
    if not acquisition_file.exists():
        return {
            "success": False,
            "message": f"Acquisition file not found: {acquisition_file}",
        }

    # Compute acquisition checksum (idempotency key)
    acq_sha256 = compute_file_checksum(acquisition_file)

    # Check if already ingested (idempotency check)
    # Status scope: active or superseded entries are considered "already ingested"
    manifest_rows = read_manifest(manifest_path, profile="raw") if manifest_path.exists() else []
    for row in manifest_rows:
        if row.get("acq_sha256") == acq_sha256:
            status = row.get("status", "").strip()
            if status in ("active", "superseded"):
                # Already ingested - no-op
                existing_file_id = row.get("file_id", "unknown")
                return {
                    "success": True,
                    "file_id": existing_file_id,
                    "message": f"already ingested: {existing_file_id}",
                    "already_ingested": True,
                }

    if dry_run:
        # Generate a file_id for dry-run display
        ingest_date = datetime.now(UTC)
        file_id = generate_next_file_id(dataset_code, manifest_path, ingest_date)
        return {
            "success": True,
            "file_id": file_id,
            "message": f"[DRY RUN] Would ingest {acquisition_file.name} as {file_id}",
            "already_ingested": False,
        }

    # Ensure raw directory exists
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Generate file_id
    ingest_date = datetime.now(UTC)
    file_id = generate_next_file_id(dataset_code, manifest_path, ingest_date)

    # Copy acquisition file to raw layer (canonical copy)
    raw_file = raw_dir / f"{file_id}{acquisition_file.suffix}"
    raw_file.write_bytes(acquisition_file.read_bytes())

    # Compute raw file checksum
    sha256 = compute_file_checksum(raw_file)

    # Write manifest entry
    # rel_path must be relative to DATA_DIR
    ingested_at = ingest_date.isoformat().replace('+00:00', 'Z')
    # Construct rel_path relative to DATA_DIR (raw_dir is data/raw/<source_key>/)
    from ...global_config import DATA_DIR
    rel_path = str(raw_file.relative_to(DATA_DIR))
    append_manifest_row(
        manifest_path=manifest_path,
        rel_path=rel_path,
        status="active",
        sha256=sha256,
        source_name=acquisition_file.name,
        schema_version="1",
        profile="raw",
        validate="row",
        file_id=file_id,
        ingested_at=ingested_at,
        acq_sha256=acq_sha256,
    )

    return {
        "success": True,
        "file_id": file_id,
        "message": f"Ingested {acquisition_file.name} as {file_id}",
        "already_ingested": False,
    }

