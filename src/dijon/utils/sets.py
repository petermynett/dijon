"""Utilities for managing set YAML files.

This module provides functions for:
- Loading and saving set YAML files
- Resolving set file paths (name-based or path-based)
- Working with set data structures
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..global_config import PROJECT_ROOT, SETS_DIR

logger = __import__("logging").getLogger(__name__)


def resolve_set_path(
    set_ref: str, project_root: Path = PROJECT_ROOT
) -> Path:
    """Resolve a set reference to a file path.

    If set_ref is a single word (no path separators), resolve to
    SETS_DIR/<set_ref>.yaml. Otherwise, treat it as a path relative to
    project_root.

    Args:
        set_ref: Set reference (name like "leading" or path like
            "data/sets/leading.yaml").
        project_root: Project root directory. Defaults to PROJECT_ROOT.

    Returns:
        Resolved Path to the set YAML file.

    Raises:
        ValueError: If set_ref is empty or resolution fails.
        FileNotFoundError: If the resolved file doesn't exist.
    """
    if not set_ref or not set_ref.strip():
        raise ValueError("set_ref must be non-empty")

    set_ref = set_ref.strip()

    # Check if it's a single word (no path separators)
    if "/" not in set_ref and "\\" not in set_ref:
        # Single word: resolve via SETS_DIR
        set_path = SETS_DIR / f"{set_ref}.yaml"
    else:
        # Path: resolve relative to project_root
        set_path = (project_root / set_ref).resolve()
        # Ensure it's under project_root for safety
        try:
            set_path.relative_to(project_root.resolve())
        except ValueError as err:
            raise ValueError(
                f"Set path {set_ref} resolves to {set_path} "
                f"which is outside PROJECT_ROOT {project_root}"
            ) from err

    if not set_path.exists():
        raise FileNotFoundError(f"Set file not found: {set_path}")

    return set_path


def load_set_yaml(set_path: Path) -> dict[str, Any]:
    """Load a set YAML file.

    Args:
        set_path: Path to the set YAML file.

    Returns:
        Dictionary containing the set data.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        yaml.YAMLError: If the YAML is invalid.
    """
    if not set_path.exists():
        raise FileNotFoundError(f"Set file not found: {set_path}")

    with open(set_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}

    return data


def save_set_yaml(set_path: Path, data: dict[str, Any]) -> None:
    """Save a set YAML file.

    Args:
        set_path: Path to save the set YAML file.
        data: Dictionary containing the set data.

    Side Effects:
        - Creates parent directories if they don't exist.
        - Writes the YAML file.
    """
    set_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean up None values to avoid writing nulls in YAML
    cleaned_data = _clean_none_values(data)

    with open(set_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            cleaned_data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def _clean_none_values(obj: Any) -> Any:
    """Recursively remove None values from data structure.

    Args:
        obj: Object to clean (dict, list, or other).

    Returns:
        Cleaned object with None values removed or converted to empty strings.
    """
    if isinstance(obj, dict):
        return {
            k: _clean_none_values(v) if v is not None else ""
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_clean_none_values(item) for item in obj]
    return obj


def normalize_paths_field(
    paths: str | list[str] | None,
) -> list[str]:
    """Normalize the paths field from a set YAML to a list of strings.

    Args:
        paths: Paths field value (string, list of strings, or None).

    Returns:
        List of path strings. Empty list if paths is None or empty.
    """
    if paths is None:
        return []

    if isinstance(paths, str):
        return [paths] if paths.strip() else []

    if isinstance(paths, list):
        return [p.strip() for p in paths if p and p.strip()]

    return []
