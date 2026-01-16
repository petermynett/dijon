"""Cleaning operations for the pipeline.

Provides utilities for cleaning up generated artifacts like Python cache files.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..global_config import PROJECT_ROOT


def clean_pyc(directories: list[Path] | None = None) -> dict[str, Any]:
    """Remove all __pycache__ directories and *.pyc files from specified directories.

    Recursively finds and deletes Python cache artifacts (__pycache__ directories
    and *.pyc files) from the specified directories.

    Args:
        directories: List of directory paths to clean. Defaults to [PROJECT_ROOT / "src"].

    Returns:
        Result dictionary with:
        - success: bool (True if operation completed without errors)
        - total: int (total number of items deleted)
        - directories_deleted: int (number of __pycache__ directories removed)
        - files_deleted: int (number of *.pyc files removed)
        - failures: list[dict] (list of failures with item and reason, if any)
    """
    if directories is None:
        directories = [PROJECT_ROOT / "src"]

    directories_deleted = 0
    files_deleted = 0
    failures: list[dict[str, str]] = []
    pycache_dirs: list[Path] = []
    standalone_pyc_files: list[Path] = []

    # First, find all __pycache__ directories and count files inside them
    for target_dir in directories:
        if not target_dir.exists():
            failures.append(
                {
                    "item": str(target_dir),
                    "reason": f"Directory does not exist: {target_dir}",
                }
            )
            continue

        for pycache_dir in target_dir.rglob("__pycache__"):
            if pycache_dir.is_dir():
                pycache_dirs.append(pycache_dir)
                # Count .pyc files inside this directory before deleting
                for pyc_file in pycache_dir.rglob("*.pyc"):
                    if pyc_file.is_file():
                        files_deleted += 1

        # Find standalone *.pyc files outside __pycache__ directories BEFORE deleting
        for pyc_file in target_dir.rglob("*.pyc"):
            if pyc_file.is_file() and "__pycache__" not in pyc_file.parts:
                standalone_pyc_files.append(pyc_file)
                files_deleted += 1

    # Delete all __pycache__ directories (this removes files inside them)
    for pycache_dir in pycache_dirs:
        try:
            if pycache_dir.exists():  # Check it still exists before deleting
                shutil.rmtree(pycache_dir)
                directories_deleted += 1
        except Exception as exc:  # noqa: BLE001
            # Find which target directory this belongs to for relative path
            base_dir = next(
                (d for d in directories if pycache_dir.is_relative_to(d)), None
            )
            rel_path = (
                pycache_dir.relative_to(base_dir)
                if base_dir
                else pycache_dir.name
            )
            failures.append(
                {
                    "item": str(rel_path),
                    "reason": f"Failed to delete directory: {exc}",
                }
            )

    # Delete standalone *.pyc files
    for pyc_file in standalone_pyc_files:
        try:
            if pyc_file.exists():  # Check it still exists before deleting
                pyc_file.unlink()
        except Exception as exc:  # noqa: BLE001
            # Find which target directory this belongs to for relative path
            base_dir = next(
                (d for d in directories if pyc_file.is_relative_to(d)), None
            )
            rel_path = (
                pyc_file.relative_to(base_dir) if base_dir else pyc_file.name
            )
            failures.append(
                {
                    "item": str(rel_path),
                    "reason": f"Failed to delete file: {exc}",
                }
            )

    total = directories_deleted + files_deleted
    success = len(failures) == 0

    result: dict[str, Any] = {
        "success": success,
        "total": total,
        "directories_deleted": directories_deleted,
        "files_deleted": files_deleted,
    }

    if failures:
        result["failures"] = failures

    if total > 0:
        result["message"] = (
            f"Cleaned {directories_deleted} directories and {files_deleted} files"
        )
    else:
        result["message"] = "No Python cache files found"

    return result
