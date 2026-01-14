"""Load verb for example source.

Load resolves effective raw files and validates them. This verb does not write
canonical data; it operates on derived/validated representations.
"""

from __future__ import annotations

from pathlib import Path

from ...utils._manifest import (
    get_active_files,
    read_manifest,
    resolve_effective_raw_path,
    verify_manifest_integrity,
)


def load(
    source_key: str,
    raw_dir: Path,
    overrides_dir: Path,
    manifest_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, str | int | bool | list]:
    """Load and validate canonical raw files for the example source.

    This verb:
    - Resolves effective raw files (raw + overrides precedence)
    - Validates manifest integrity
    - Does NOT write canonical data (only validates)

    Args:
        source_key: Source identifier (e.g., "example").
        raw_dir: Directory for raw files (data/raw/<source_key>/).
        overrides_dir: Directory for override files (data/overrides/<source_key>/).
        manifest_path: Path to manifest.csv file.
        dry_run: If True, simulate the operation without reading files.

    Returns:
        Result dictionary with:
        - success: bool
        - files_loaded: int (number of files processed)
        - errors: list[str] (validation errors, if any)
        - message: str (summary message)
    """
    if not manifest_path.exists():
        return {
            "success": False,
            "message": f"Manifest not found: {manifest_path}",
            "files_loaded": 0,
            "errors": [],
        }

    if dry_run:
        manifest_rows = read_manifest(manifest_path, profile="raw")
        active_count = len([r for r in manifest_rows if r.get("status") == "active"])
        return {
            "success": True,
            "files_loaded": active_count,
            "message": f"[DRY RUN] Would load {active_count} active files for {source_key}",
            "errors": [],
        }

    # Verify manifest integrity
    errors = verify_manifest_integrity(manifest_path, raw_dir, overrides_dir, profile="raw")

    # Get active files
    active_files = get_active_files(manifest_path, profile="raw")

    # Resolve effective raw paths for each active file
    resolved_files = []
    for row in active_files:
        file_id = row["file_id"]
        rel_path = row["rel_path"]
        effective_path = resolve_effective_raw_path(raw_dir, overrides_dir, file_id, rel_path)
        if effective_path:
            resolved_files.append({"file_id": file_id, "path": str(effective_path)})
        else:
            errors.append(f"File {file_id} not found at {rel_path} or override")

    success = len(errors) == 0

    return {
        "success": success,
        "files_loaded": len(resolved_files),
        "errors": errors,
        "message": f"Loaded {len(resolved_files)} files for {source_key}" + (
            f" ({len(errors)} errors)" if errors else ""
        ),
    }

