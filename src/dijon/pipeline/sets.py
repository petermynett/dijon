"""Pipeline operations for set management.

This module provides functions for populating set YAML files with data from manifests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dijon.global_config import DATA_DIR, PROJECT_ROOT
from dijon.utils.manifest import read_manifest
from dijon.utils.sets import (
    load_set_yaml,
    normalize_paths_field,
    save_set_yaml,
)

logger = __import__("logging").getLogger(__name__)


def populate_set_yaml(
    set_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Populate set YAML items with metadata from manifests.

    Reads the set YAML file, loads manifests referenced by the `paths` field,
    and populates item fields (song_name, source_name, url) from manifest data.

    Args:
        set_path: Path to the set YAML file.
        project_root: Project root directory. Defaults to PROJECT_ROOT.
        dry_run: If True, don't write changes, just return what would change.
        overwrite: If True, overwrite existing non-empty fields. Defaults to False.

    Returns:
        Dictionary with keys:
        - success: bool
        - total: int (total items processed)
        - updated: int (items that were updated)
        - skipped: int (items skipped due to missing file_id or manifest data)
        - failed: int (items that failed to process)
        - failures: list[dict] (details of failures)

    Raises:
        FileNotFoundError: If set file or manifest files don't exist.
        ValueError: If set YAML structure is invalid.
    """
    # Load set YAML
    set_data = load_set_yaml(set_path)

    if "items" not in set_data:
        raise ValueError(f"Set file {set_path} missing 'items' field")

    items = set_data.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Set file {set_path} has invalid 'items' field (must be a list)")

    # Get paths and normalize to list
    paths = normalize_paths_field(set_data.get("paths"))

    if not paths:
        raise ValueError(f"Set file {set_path} missing or empty 'paths' field")

    # Load all manifests
    manifest_rows_by_file_id: dict[str, dict[str, str]] = {}

    for path_str in paths:
        # Resolve path relative to DATA_DIR
        if path_str.startswith("data/"):
            # Already relative to project root
            dataset_dir = project_root / path_str
        else:
            # Assume relative to DATA_DIR
            dataset_dir = DATA_DIR / path_str

        manifest_path = dataset_dir / "manifest.csv"

        if not manifest_path.exists():
            logger.warning("Manifest not found: %s", manifest_path)
            continue

        # Read manifest
        try:
            rows = read_manifest(manifest_path, profile="raw")
            for row in rows:
                file_id = row.get("file_id", "").strip()
                if file_id:
                    # Store first occurrence (or could merge if needed)
                    if file_id not in manifest_rows_by_file_id:
                        manifest_rows_by_file_id[file_id] = row
        except Exception as e:
            logger.warning("Failed to read manifest %s: %s", manifest_path, e)
            continue

    # Process items
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    failures: list[dict[str, str]] = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            failed_count += 1
            failures.append(
                {
                    "item": f"items[{idx}]",
                    "reason": "Item is not a dictionary",
                }
            )
            continue

        # Get file_id, handling None values from YAML parsing
        file_id_raw = item.get("file_id")
        file_id = str(file_id_raw).strip() if file_id_raw is not None else ""

        if not file_id:
            # Skip items without file_id entirely - don't modify them
            skipped_count += 1
            continue

        # Look up manifest row
        manifest_row = manifest_rows_by_file_id.get(file_id)

        if not manifest_row:
            skipped_count += 1
            continue

        # Extract fields from manifest
        source_name = manifest_row.get("source_name", "").strip()

        # Parse meta_json
        meta_json_str = manifest_row.get("meta_json", "").strip()
        meta_json: dict[str, Any] = {}

        if meta_json_str:
            try:
                meta_json = json.loads(meta_json_str)
                if not isinstance(meta_json, dict):
                    meta_json = {}
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid meta_json for file_id %s", file_id)
                meta_json = {}

        # Extract song_name and url from meta_json
        song_name = meta_json.get("song_name", "").strip() if meta_json else ""

        # Try upstream.url first, fallback to input_url
        url = ""
        if meta_json:
            upstream = meta_json.get("upstream", {})
            if isinstance(upstream, dict):
                url = upstream.get("url", "").strip()
            if not url:
                url = meta_json.get("input_url", "").strip()

        # Update item fields (only if blank or overwrite=True)
        # Only populate fields that have actual values - don't write empty strings
        item_updated = False

        # Helper to safely check if a field is empty (handles None and empty strings)
        def is_empty(value: str | None) -> bool:
            return not value or not str(value).strip()

        # Only populate if we have actual values to write
        if overwrite or is_empty(item.get("song_name")):
            if song_name:
                item["song_name"] = song_name
                item_updated = True

        if overwrite or is_empty(item.get("source_name")):
            if source_name:
                item["source_name"] = source_name
                item_updated = True

        if overwrite or is_empty(item.get("url")):
            if url:
                item["url"] = url
                item_updated = True

        if item_updated:
            updated_count += 1

    # Save if not dry_run
    if not dry_run and updated_count > 0:
        save_set_yaml(set_path, set_data)

    return {
        "success": True,
        "total": len(items),
        "succeeded": updated_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "failures": failures,
    }
