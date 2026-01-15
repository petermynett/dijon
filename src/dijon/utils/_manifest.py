"""Shared utilities for manifest.csv management and file_id generation.

This module provides standardized functions for:
- Generating file_id values (SRC-YYMM-SEQ format)
- Reading and writing manifest.csv files
- Computing file checksums
- Resolving effective raw files (raw + annotations precedence)
- Supporting multiple manifest types (raw, upstream, derived) with type-specific schemas
"""

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..global_config import DATA_DIR

logger = __import__("logging").getLogger(__name__)

# Manifest type definitions
ManifestType = Literal["raw", "upstream", "derived"]

# Profile definitions (Python constants, no runtime schema-file IO)
PROFILES: dict[str, dict] = {
    "raw": {
        "required_fields": ["file_id", "rel_path", "status", "sha256", "acq_sha256", "ingested_at", "source_name", "schema_version"],
        "unique_fields": ["file_id", "sha256", "rel_path"],
        "status_enum_mode": "strict",
    },
    "upstream": {
        "required_fields": ["sha256", "source_name", "schema_version"],  # status is optional
        "unique_fields": [],
        "status_enum_mode": "if_present",
    },
    "derived": {
        "required_fields": ["rel_path", "status", "sha256", "source_name", "schema_version"],
        "unique_fields": ["rel_path"],
        "status_enum_mode": "if_present",
    },
}

# Manifest schema fields (all fields that may appear)
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
    "meta_json",
]

# Valid status values
VALID_STATUSES = ["active", "superseded", "archived"]


def normalize_rel_path(rel_path: str, data_dir: Path = DATA_DIR) -> str:
    """Normalize and validate rel_path under DATA_DIR.

    Accepts:
    - Absolute paths that normalize under DATA_DIR
    - Relative paths that normalize under DATA_DIR

    Rejects:
    - Absolute paths outside DATA_DIR
    - Any paths containing '..'
    - Paths that escape DATA_DIR after normalization

    Args:
        rel_path: Path to normalize (may be absolute or relative).
        data_dir: Data directory root (defaults to DATA_DIR).

    Returns:
        Normalized relative path (relative to data_dir).

    Raises:
        ValueError: If path is invalid or escapes data_dir.
    """
    if not rel_path or not rel_path.strip():
        raise ValueError("rel_path must be non-empty")

    rel_path = rel_path.strip()

    # Check for '..' in the path
    if ".." in rel_path:
        raise ValueError(f"rel_path must not contain '..': {rel_path}")

    # Convert to Path and resolve
    path_obj = Path(rel_path)

    # If absolute, check it's under data_dir
    if path_obj.is_absolute():
        try:
            resolved = path_obj.resolve()
            data_dir_resolved = data_dir.resolve()
            # Check if resolved path is under data_dir
            try:
                resolved.relative_to(data_dir_resolved)
            except ValueError:
                raise ValueError(
                    f"Absolute path {rel_path} resolves to {resolved} "
                    f"which is outside DATA_DIR {data_dir_resolved}"
                )
            # Convert to relative path
            return str(resolved.relative_to(data_dir_resolved))
        except Exception as e:
            raise ValueError(f"Failed to normalize absolute path {rel_path}: {e}")

    # If relative, normalize it and ensure it stays under data_dir
    try:
        # Resolve relative to data_dir
        resolved = (data_dir / path_obj).resolve()
        data_dir_resolved = data_dir.resolve()
        # Ensure it's still under data_dir
        try:
            relative = resolved.relative_to(data_dir_resolved)
            return str(relative)
        except ValueError:
            raise ValueError(
                f"Relative path {rel_path} resolves to {resolved} "
                f"which escapes DATA_DIR {data_dir_resolved}"
            )
    except Exception as e:
        raise ValueError(f"Failed to normalize relative path {rel_path}: {e}")


def normalize_meta_json(meta_json: str) -> str:
    """Normalize meta_json field to canonical JSON object format.

    - Empty string treated as absent (returns empty string)
    - Must parse as JSON object (not array, string, etc.)
    - Re-serialized canonically with sort_keys=True and minified separators

    Args:
        meta_json: JSON string to normalize.

    Returns:
        Canonical JSON string, or empty string if input is empty.

    Raises:
        ValueError: If meta_json is not empty and not a valid JSON object.
    """
    if not meta_json or not meta_json.strip():
        return ""

    try:
        parsed = json.loads(meta_json)
        if not isinstance(parsed, dict):
            raise ValueError(f"meta_json must be a JSON object, got {type(parsed).__name__}")
        # Re-serialize canonically
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    except json.JSONDecodeError as e:
        raise ValueError(f"meta_json must be valid JSON: {e}")


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


def read_manifest(
    manifest_path: Path,
    profile: ManifestType = "raw",
) -> list[dict[str, str]]:
    """Read manifest.csv file and return all rows as dictionaries.

    Args:
        manifest_path: Path to manifest.csv file.
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Returns:
        List of dictionaries, one per row. Empty list if file doesn't exist
        or is empty (header only).

    Raises:
        ValueError: If manifest file exists but has invalid format or missing required fields.
    """
    if not manifest_path.exists():
        return []

    # Handle empty file (0 bytes) - treat as if it doesn't exist
    if manifest_path.stat().st_size == 0:
        return []

    profile_config = PROFILES.get(profile)
    if not profile_config:
        raise ValueError(f"Unknown manifest profile: {profile}")

    required_fields = profile_config["required_fields"]

    rows = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Manifest file has no header row")

        # Validate required fields are present
        missing_required = [f for f in required_fields if f not in reader.fieldnames]
        if missing_required:
            raise ValueError(
                f"Manifest profile '{profile}' missing required fields: {missing_required}. "
                f"Found: {list(reader.fieldnames)}"
            )

        # Add missing optional fields with empty values
        for row in reader:
            complete_row = {field: row.get(field, "") for field in MANIFEST_FIELDS}
            rows.append(complete_row)

    return rows


def write_manifest(
    manifest_path: Path,
    rows: list[dict[str, str]],
    profile: ManifestType = "raw",
) -> None:
    """Write manifest.csv file with given rows.

    Args:
        manifest_path: Path to manifest.csv file (will be created if missing).
        rows: List of dictionaries, each representing one manifest row.
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Raises:
        ValueError: If rows are missing required fields for the specified profile.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    profile_config = PROFILES.get(profile)
    if not profile_config:
        raise ValueError(f"Unknown manifest profile: {profile}")

    required_fields = profile_config["required_fields"]

    # Determine which fields to write: required fields plus any optional fields present in rows
    all_fields_in_rows = set()
    for row in rows:
        all_fields_in_rows.update(row.keys())

    # Use required fields plus any optional fields from MANIFEST_FIELDS that appear in rows
    fields_to_write = [
        field for field in MANIFEST_FIELDS
        if field in required_fields or field in all_fields_in_rows
    ]

    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields_to_write)
        writer.writeheader()
        for row in rows:
            # Ensure all fields present (empty string if missing)
            complete_row = {field: row.get(field, "") for field in fields_to_write}
            writer.writerow(complete_row)


def build_manifest_index(
    rows: list[dict[str, str]],
    profile: ManifestType,
) -> dict[str, set[str]]:
    """Build index of unique field values for fast uniqueness checking.

    Args:
        rows: Existing manifest rows.
        profile: Manifest profile type.

    Returns:
        Dictionary mapping field names to sets of existing values.
    """
    profile_config = PROFILES.get(profile)
    if not profile_config:
        raise ValueError(f"Unknown manifest profile: {profile}")

    unique_fields = profile_config["unique_fields"]
    index: dict[str, set[str]] = {field: set() for field in unique_fields}

    for row in rows:
        for field in unique_fields:
            value = row.get(field, "").strip()
            if value:  # Only index non-empty values
                index[field].add(value)

    return index


def validate_manifest(
    manifest_path: Path,
    profile: ManifestType = "raw",
) -> list[str]:
    """Validate entire manifest for required fields and uniqueness constraints.

    Args:
        manifest_path: Path to manifest.csv file.
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Returns:
        List of error messages. Empty list if all checks pass.
    """
    errors = []
    rows = read_manifest(manifest_path, profile=profile)

    profile_config = PROFILES.get(profile)
    if not profile_config:
        return [f"Unknown manifest profile: {profile}"]

    required_fields = profile_config["required_fields"]
    unique_fields = profile_config["unique_fields"]
    status_enum_mode = profile_config["status_enum_mode"]

    # Validate each row
    for idx, row in enumerate(rows, start=2):  # Start at 2 (row 1 is header)
        # Check required fields
        missing_required = [
            field for field in required_fields
            if not row.get(field, "").strip()
        ]
        if missing_required:
            errors.append(
                f"Row {idx}: Missing required fields: {missing_required}"
            )

        # Validate status enum if present
        status = row.get("status", "").strip()
        if status:
            if status not in VALID_STATUSES:
                errors.append(
                    f"Row {idx}: Invalid status '{status}'. Must be one of {VALID_STATUSES}"
                )
        elif status_enum_mode == "strict":
            errors.append(f"Row {idx}: status is required for profile '{profile}'")

        # Validate rel_path if present
        rel_path = row.get("rel_path", "").strip()
        if rel_path:
            try:
                normalize_rel_path(rel_path)
            except ValueError as e:
                errors.append(f"Row {idx}: Invalid rel_path: {e}")

        # Validate meta_json if present
        meta_json = row.get("meta_json", "").strip()
        if meta_json:
            try:
                normalize_meta_json(meta_json)
            except ValueError as e:
                errors.append(f"Row {idx}: Invalid meta_json: {e}")

    # Validate uniqueness constraints
    if unique_fields:
        index = build_manifest_index(rows, profile)
        # Check for duplicates
        seen: dict[str, dict[str, int]] = {field: {} for field in unique_fields}
        for idx, row in enumerate(rows, start=2):
            for field in unique_fields:
                value = row.get(field, "").strip()
                if value:
                    if value in seen[field]:
                        errors.append(
                            f"Row {idx}: Duplicate {field} '{value}' "
                            f"(also appears in row {seen[field][value]})"
                        )
                    else:
                        seen[field][value] = idx

    return errors


def append_manifest_row(
    manifest_path: Path,
    rel_path: str,
    status: str,
    sha256: str,
    source_name: str,
    schema_version: str,
    *,
    profile: ManifestType = "raw",
    validate: Literal["row", "full"] = "row",
    file_id: str = "",
    ingested_at: str = "",
    acq_sha256: str = "",
    supersedes_file_id: str = "",
    row_count: str = "",
    start_date: str = "",
    end_date: str = "",
    partition: str = "",
    meta_json: str = "",
) -> None:
    """Append a single row to manifest.csv with fast validation.

    Creates manifest file if it doesn't exist. Validates required fields and
    uniqueness constraints based on profile.

    Args:
        manifest_path: Path to manifest.csv file.
        rel_path: File path relative to DATA_DIR.
        status: Status ("active", "archived", or "superseded").
        sha256: SHA256 checksum of the file.
        source_name: Original upstream filename.
        schema_version: Schema version string.
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".
        validate: Validation mode. "row" (default) validates only the new row.
            "full" also validates the entire manifest before writing.
        file_id: Canonical file ID (SRC-YYMM-SEQ). Required for "raw" profile.
        ingested_at: ISO8601 timestamp. Required for "raw" profile.
        acq_sha256: SHA256 checksum of the acquisition file. Required for "raw" profile.
        supersedes_file_id: Previous file_id if this replaces another (optional).
        row_count: Optional row estimate (optional).
        start_date: Optional start date/datetime for date range tracking (optional).
            Format: YYYY-MM-DD (date) or YYYY-MM-DDTHH:MM:SSZ (datetime).
        end_date: Optional end date/datetime for date range tracking (optional).
            Format: YYYY-MM-DD (date) or YYYY-MM-DDTHH:MM:SSZ (datetime).
        partition: Optional partition identifier (optional).
        meta_json: Optional JSON object string (optional).

    Raises:
        ValueError: If required fields are missing, uniqueness constraints are violated,
            or validation fails.
    """
    profile_config = PROFILES.get(profile)
    if not profile_config:
        raise ValueError(f"Unknown manifest profile: {profile}")

    required_fields = profile_config["required_fields"]
    unique_fields = profile_config["unique_fields"]
    status_enum_mode = profile_config["status_enum_mode"]

    # Read existing rows once (O(n))
    existing_rows = read_manifest(manifest_path, profile=profile)

    # Build index once (O(n))
    index = build_manifest_index(existing_rows, profile)

    # Normalize rel_path if present
    normalized_rel_path = ""
    if rel_path:
        normalized_rel_path = normalize_rel_path(rel_path)

    # Normalize meta_json if present
    normalized_meta_json = ""
    if meta_json:
        normalized_meta_json = normalize_meta_json(meta_json)

    # Build new row
    new_row = {
        "file_id": file_id,
        "rel_path": normalized_rel_path,
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
        "meta_json": normalized_meta_json,
    }

    # Validate required fields
    missing_required = [
        field for field in required_fields
        if not new_row.get(field, "").strip()
    ]
    if missing_required:
        raise ValueError(
            f"Manifest profile '{profile}' requires fields: {missing_required}. "
            f"Missing values for: {missing_required}"
        )

    # Validate status enum (only if status is provided)
    if status:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of {VALID_STATUSES}"
            )
    elif status_enum_mode == "strict":
        raise ValueError(f"status is required for profile '{profile}'")

    # Check uniqueness constraints via index (O(1))
    for field in unique_fields:
        value = new_row.get(field, "").strip()
        if value:
            if value in index[field]:
                raise ValueError(
                    f"Uniqueness constraint violated: field '{field}' with value '{value}' "
                    f"already exists in manifest (profile: {profile})"
                )

    # If full validation requested, validate entire manifest
    if validate == "full":
        # Temporarily add new row for full validation
        temp_rows = existing_rows + [new_row]
        temp_manifest_path = manifest_path.parent / f".temp_{manifest_path.name}"
        try:
            write_manifest(temp_manifest_path, temp_rows, profile=profile)
            validation_errors = validate_manifest(temp_manifest_path, profile=profile)
            if validation_errors:
                temp_manifest_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Full manifest validation failed:\n" + "\n".join(validation_errors)
                )
            temp_manifest_path.unlink(missing_ok=True)
        except Exception as e:
            temp_manifest_path.unlink(missing_ok=True)
            raise

    # Ensure all MANIFEST_FIELDS are present (fill missing with empty string)
    complete_row = {field: new_row.get(field, "") for field in MANIFEST_FIELDS}
    existing_rows.append(complete_row)
    write_manifest(manifest_path, existing_rows, profile=profile)


def update_manifest_row_dates(
    manifest_path: Path,
    file_id: str,
    start_date: str,
    end_date: str,
    profile: ManifestType = "raw",
) -> None:
    """Update date range fields for an existing manifest row.

    Args:
        manifest_path: Path to manifest.csv file.
        file_id: File ID to update.
        start_date: Start date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format).
        end_date: End date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format).
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Raises:
        ValueError: If file_id not found in manifest.
    """
    rows = read_manifest(manifest_path, profile=profile)
    found = False
    for row in rows:
        if row["file_id"] == file_id:
            row["start_date"] = start_date
            row["end_date"] = end_date
            found = True
            break

    if not found:
        raise ValueError(f"File ID {file_id} not found in manifest")

    write_manifest(manifest_path, rows, profile=profile)


def get_active_files(
    manifest_path: Path,
    profile: ManifestType = "raw",
) -> list[dict[str, str]]:
    """Get all active files from manifest.

    Args:
        manifest_path: Path to manifest.csv file.
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Returns:
        List of manifest rows with status="active".
    """
    all_rows = read_manifest(manifest_path, profile=profile)
    return [row for row in all_rows if row.get("status") == "active"]


def resolve_effective_raw_path(
    raw_dir: Path,
    annotations_dir: Path,
    file_id: str,
    rel_path: str,
) -> Path | None:
    """Resolve effective raw file path (overriding annotations take precedence over raw).

    Per stage-first structure: check data/annotations/<source_key>/<file_id>.* first
    for overriding annotations, then data/raw/<source_key>/<file_id>.*.

    Args:
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        annotations_dir: Directory for annotation files (data/annotations/<source_key>/).
        file_id: File ID (e.g., "RCP-2412-001").
        rel_path: Relative path from manifest (e.g., "raw/RCP-2412-001.jpg").

    Returns:
        Path to effective raw file, or None if neither overriding annotation nor raw exists.

    Note:
        Extension is inferred from rel_path. If overriding annotation exists with different
        extension, it still takes precedence. Multiple overriding annotations for the same
        file_id result in ambiguity (caller must handle this case).
    """
    # Extract extension from rel_path
    rel_path_obj = Path(rel_path)
    ext = rel_path_obj.suffix

    # Check for overriding annotations first
    # TODO: Implement proper annotation schema and filtering for "overriding" flag
    # For now, check if annotation file exists (simple file-based check)
    annotation_path = annotations_dir / f"{file_id}{ext}"
    if annotation_path.exists():
        return annotation_path

    # Check raw (rel_path is like "raw/<file_id>.ext", extract filename)
    raw_filename = rel_path_obj.name
    raw_path = raw_dir / raw_filename
    if raw_path.exists():
        return raw_path

    return None


def verify_manifest_integrity(
    manifest_path: Path,
    raw_dir: Path,
    annotations_dir: Path,
    profile: ManifestType = "raw",
) -> list[str]:
    """Verify integrity of all active manifest entries.

    Checks that:
    - Files exist at rel_path
    - SHA256 checksums match
    - Overriding annotation files exist if referenced

    Args:
        manifest_path: Path to manifest.csv file.
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        annotations_dir: Directory for annotation files (data/annotations/<source_key>/).
        profile: Manifest profile type ("raw", "upstream", or "derived"). Defaults to "raw".

    Returns:
        List of error messages. Empty list if all checks pass.
    """
    errors = []
    active_files = get_active_files(manifest_path, profile=profile)

    for row in active_files:
        file_id = row.get("file_id", "")
        rel_path = row.get("rel_path", "")
        expected_sha256 = row.get("sha256", "")

        if not rel_path:
            errors.append(f"Row missing rel_path (file_id: {file_id})")
            continue

        # Resolve effective path
        effective_path = resolve_effective_raw_path(raw_dir, annotations_dir, file_id, rel_path)
        if effective_path is None:
            errors.append(f"File {file_id} not found at {rel_path} or overriding annotation")
            continue

        # Verify checksum
        if expected_sha256:
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
