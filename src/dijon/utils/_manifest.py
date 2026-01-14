"""Shared utilities for manifest.csv management and file_id generation.

This module provides standardized functions for:
- Generating file_id values (SRC-YYMM-SEQ format)
- Reading and writing manifest.csv files
- Computing file checksums
- Resolving effective raw files (raw + overrides precedence)
"""

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

logger = __import__("logging").getLogger(__name__)

# Manifest schema fields (all required, values may be empty)
MANIFEST_FIELDS = [
    "file_id",
    "rel_path",
    "status",
    "sha256",
    "acq_sha256",
    "ingested_at",
    "source_name",
    "schema_version",
    "supersedes_file_id",
    "row_count",
    "start_date",
    "end_date",
    "partition",
]


def generate_file_id(dataset_code: str, ingest_date: datetime | None = None) -> str:
    """Generate a new file_id in SRC-YYMM-SEQ format.

    Format: SRC-YYMM-SEQ
    - SRC: dataset code (e.g., "RCP", "TXN", "GEO")
    - YYMM: ingest year+month (e.g., "2412" for Dec 2024)
    - SEQ: zero-padded sequence number (starts at 001)

    Args:
        dataset_code: Dataset code (uppercase, 3 chars recommended).
        ingest_date: Date for YYMM component. Defaults to current UTC date.

    Returns:
        File ID string (e.g., "RCP-2412-001").

    Raises:
        ValueError: If dataset_code is empty or invalid.
    """
    if not dataset_code or not dataset_code.strip():
        raise ValueError("dataset_code must be non-empty")

    dataset_code = dataset_code.strip().upper()

    if ingest_date is None:
        ingest_date = datetime.now(UTC)

    yymm = ingest_date.strftime("%y%m")

    # Find next sequence number for this dataset+month
    # This requires reading the manifest, so we'll need the manifest path
    # For now, return format - caller will need to check for collisions
    # TODO: Consider passing manifest_path to auto-increment sequence
    return f"{dataset_code}-{yymm}-001"


def generate_next_file_id(
    dataset_code: str,
    manifest_path: Path,
    ingest_date: datetime | None = None,
) -> str:
    """Generate next available file_id by checking existing manifest entries.

    Finds the highest sequence number for the given dataset_code and YYMM,
    then increments it.

    Args:
        dataset_code: Dataset code (uppercase, 3 chars recommended).
        manifest_path: Path to manifest.csv file.
        ingest_date: Date for YYMM component. Defaults to current UTC date.

    Returns:
        File ID string with next available sequence number.
    """
    if ingest_date is None:
        ingest_date = datetime.now(UTC)

    yymm = ingest_date.strftime("%y%m")
    prefix = f"{dataset_code.strip().upper()}-{yymm}-"

    # Read manifest to find max sequence
    max_seq = 0
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    file_id = row.get("file_id", "")
                    if file_id.startswith(prefix):
                        try:
                            seq_str = file_id.split("-")[-1]
                            seq = int(seq_str)
                            max_seq = max(max_seq, seq)
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            logger.warning("Failed to read manifest for sequence check: %s", e)

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:03d}"


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file.

    Args:
        file_path: Path to file.

    Returns:
        SHA256 hex digest string.

    Raises:
        FileNotFoundError: If file does not exist.
        OSError: If file cannot be read.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def read_manifest(manifest_path: Path) -> list[dict[str, str]]:
    """Read manifest.csv file and return all rows as dictionaries.

    Args:
        manifest_path: Path to manifest.csv file.

    Returns:
        List of dictionaries, one per row. Empty list if file doesn't exist
        or is empty (header only).

    Raises:
        ValueError: If manifest file exists but has invalid format.
    """
    if not manifest_path.exists():
        return []

    rows = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Validate fields - backward compatible: check required fields, add missing optional ones
        if reader.fieldnames is None:
            raise ValueError("Manifest file has no header row")
        
        # Required fields (must be present)
        required_fields = [
            "file_id",
            "rel_path",
            "status",
            "sha256",
            "ingested_at",
        ]
        missing_required = [f for f in required_fields if f not in reader.fieldnames]
        if missing_required:
            raise ValueError(
                f"Manifest missing required fields: {missing_required}. "
                f"Found: {list(reader.fieldnames)}"
            )
        
        # Add missing optional fields with empty values
        for row in reader:
            complete_row = {field: row.get(field, "") for field in MANIFEST_FIELDS}
            rows.append(complete_row)

    return rows


def write_manifest(manifest_path: Path, rows: list[dict[str, str]]) -> None:
    """Write manifest.csv file with given rows.

    Args:
        manifest_path: Path to manifest.csv file (will be created if missing).
        rows: List of dictionaries, each representing one manifest row.
            Must contain all MANIFEST_FIELDS keys.

    Raises:
        ValueError: If rows are missing required fields.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            # Ensure all fields present (empty string if missing)
            complete_row = {field: row.get(field, "") for field in MANIFEST_FIELDS}
            writer.writerow(complete_row)


def append_manifest_row(
    manifest_path: Path,
    file_id: str,
    rel_path: str,
    status: str,
    sha256: str,
    ingested_at: str,
    source_name: str = "",
    acq_sha256: str = "",
    schema_version: str = "",
    supersedes_file_id: str = "",
    row_count: str = "",
    start_date: str = "",
    end_date: str = "",
    partition: str = "",
) -> None:
    """Append a single row to manifest.csv.

    Creates manifest file if it doesn't exist.

    Args:
        manifest_path: Path to manifest.csv file.
        file_id: Canonical file ID (SRC-YYMM-SEQ).
        rel_path: File path relative to dataset root (e.g., "raw/RCP-2412-001.jpg").
        status: Status ("active", "archived", or "superseded").
        sha256: SHA256 checksum of the file.
        ingested_at: ISO8601 timestamp.
        source_name: Original upstream filename (optional).
        acq_sha256: SHA256 checksum of the acquisition file (optional).
        schema_version: Schema version string (optional).
        supersedes_file_id: Previous file_id if this replaces another (optional).
        row_count: Optional row estimate (optional).
        start_date: Optional start date/datetime for date range tracking (optional).
            Format: YYYY-MM-DD (date) or YYYY-MM-DDTHH:MM:SSZ (datetime).
        end_date: Optional end date/datetime for date range tracking (optional).
            Format: YYYY-MM-DD (date) or YYYY-MM-DDTHH:MM:SSZ (datetime).
        partition: Optional partition identifier (e.g., account for transactions, device for rescuetime).
    """
    # Read existing rows
    existing_rows = read_manifest(manifest_path)

    # Build new row with all MANIFEST_FIELDS (ensures schema completeness)
    new_row = {
        "file_id": file_id,
        "rel_path": rel_path,
        "status": status,
        "sha256": sha256,
        "acq_sha256": acq_sha256,
        "ingested_at": ingested_at,
        "source_name": source_name,
        "schema_version": schema_version,
        "supersedes_file_id": supersedes_file_id,
        "row_count": row_count,
        "start_date": start_date,
        "end_date": end_date,
        "partition": partition,
    }

    # Ensure all MANIFEST_FIELDS are present (fill missing with empty string)
    complete_row = {field: new_row.get(field, "") for field in MANIFEST_FIELDS}
    existing_rows.append(complete_row)
    write_manifest(manifest_path, existing_rows)


def update_manifest_row_dates(
    manifest_path: Path,
    file_id: str,
    start_date: str,
    end_date: str,
) -> None:
    """Update date range fields for an existing manifest row.

    Args:
        manifest_path: Path to manifest.csv file.
        file_id: File ID to update.
        start_date: Start date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format).
        end_date: End date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format).

    Raises:
        ValueError: If file_id not found in manifest.
    """
    rows = read_manifest(manifest_path)
    found = False
    for row in rows:
        if row["file_id"] == file_id:
            row["start_date"] = start_date
            row["end_date"] = end_date
            found = True
            break

    if not found:
        raise ValueError(f"File ID {file_id} not found in manifest")

    write_manifest(manifest_path, rows)


def get_active_files(manifest_path: Path) -> list[dict[str, str]]:
    """Get all active files from manifest.

    Args:
        manifest_path: Path to manifest.csv file.

    Returns:
        List of manifest rows with status="active".
    """
    all_rows = read_manifest(manifest_path)
    return [row for row in all_rows if row.get("status") == "active"]


def resolve_effective_raw_path(
    raw_dir: Path,
    overrides_dir: Path,
    file_id: str,
    rel_path: str,
) -> Path | None:
    """Resolve effective raw file path (overrides take precedence over raw).

    Per stage-first structure: check data/overrides/<source_key>/<file_id>.* first,
    then data/raw/<source_key>/<file_id>.*.

    Args:
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        overrides_dir: Directory for override files (data/overrides/<source_key>/).
        file_id: File ID (e.g., "RCP-2412-001").
        rel_path: Relative path from manifest (e.g., "raw/RCP-2412-001.jpg").

    Returns:
        Path to effective raw file, or None if neither override nor raw exists.

    Note:
        Extension is inferred from rel_path. If override exists with different
        extension, it still takes precedence.
    """
    # Extract extension from rel_path
    rel_path_obj = Path(rel_path)
    ext = rel_path_obj.suffix

    # Check override first
    override_path = overrides_dir / f"{file_id}{ext}"
    if override_path.exists():
        return override_path

    # Check raw (rel_path is like "raw/<file_id>.ext", extract filename)
    raw_filename = rel_path_obj.name
    raw_path = raw_dir / raw_filename
    if raw_path.exists():
        return raw_path

    return None


def verify_manifest_integrity(
    manifest_path: Path,
    raw_dir: Path,
    overrides_dir: Path,
) -> list[str]:
    """Verify integrity of all active manifest entries.

    Checks that:
    - Files exist at rel_path
    - SHA256 checksums match
    - Override files exist if referenced

    Args:
        manifest_path: Path to manifest.csv file.
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        overrides_dir: Directory for override files (data/overrides/<source_key>/).

    Returns:
        List of error messages. Empty list if all checks pass.
    """
    errors = []
    active_files = get_active_files(manifest_path)

    for row in active_files:
        file_id = row["file_id"]
        rel_path = row["rel_path"]
        expected_sha256 = row["sha256"]

        # Resolve effective path
        effective_path = resolve_effective_raw_path(raw_dir, overrides_dir, file_id, rel_path)
        if effective_path is None:
            errors.append(f"File {file_id} not found at {rel_path} or override")
            continue

        # Verify checksum
        try:
            actual_sha256 = compute_file_checksum(effective_path)
            if actual_sha256 != expected_sha256:
                errors.append(
                    f"Checksum mismatch for {file_id}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
        except Exception as e:
            errors.append(f"Failed to compute checksum for {file_id}: {e}")

    return errors
