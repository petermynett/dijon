"""Cleaning operations for the pipeline.

Provides utilities for cleaning up generated artifacts like Python cache files.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..global_config import PROJECT_ROOT


def clean_pyc(directories: list[Path] | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Remove all __pycache__ directories and *.pyc files from specified directories.

    Recursively finds and deletes Python cache artifacts (__pycache__ directories
    and *.pyc files) from the specified directories.

    Args:
        directories: List of directory paths to clean.
            Defaults to [PROJECT_ROOT / "src"].
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        Result dictionary with:
        - success: bool (True if operation completed without errors)
        - total: int (total number of items deleted or would be deleted)
        - directories_deleted: int (number of __pycache__ directories removed or would be removed)
        - files_deleted: int (number of *.pyc files removed or would be removed)
        - failures: list[dict] (list of failures with item and reason, if any)
        - dry_run: bool (indicates if this was a dry run)
        - items_to_delete: list[str] (list of items that would be deleted, only in dry_run mode)
    """
    if directories is None:
        directories = [PROJECT_ROOT / "src"]

    directories_deleted = 0
    files_deleted = 0
    failures: list[dict[str, str]] = []
    pycache_dirs: list[Path] = []
    standalone_pyc_files: list[Path] = []
    items_to_delete: list[str] = []

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
                        if dry_run:
                            base_dir = next(
                                (d for d in directories if pyc_file.is_relative_to(d)), None
                            )
                            rel_path = (
                                pyc_file.relative_to(base_dir)
                                if base_dir
                                else pyc_file.name
                            )
                            items_to_delete.append(f"FILE: {rel_path}")

        # Find standalone *.pyc files outside __pycache__ directories BEFORE deleting
        for pyc_file in target_dir.rglob("*.pyc"):
            if pyc_file.is_file() and "__pycache__" not in pyc_file.parts:
                standalone_pyc_files.append(pyc_file)
                files_deleted += 1
                if dry_run:
                    base_dir = next(
                        (d for d in directories if pyc_file.is_relative_to(d)), None
                    )
                    rel_path = (
                        pyc_file.relative_to(base_dir) if base_dir else pyc_file.name
                    )
                    items_to_delete.append(f"FILE: {rel_path}")

    # Collect directory paths for dry-run output
    if dry_run:
        for pycache_dir in pycache_dirs:
            base_dir = next(
                (d for d in directories if pycache_dir.is_relative_to(d)), None
            )
            rel_path = (
                pycache_dir.relative_to(base_dir)
                if base_dir
                else pycache_dir.name
            )
            items_to_delete.append(f"DIR:  {rel_path}/")

    # Delete all __pycache__ directories (this removes files inside them)
    if not dry_run:
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
    else:
        directories_deleted = len(pycache_dirs)

    # Delete standalone *.pyc files
    if not dry_run:
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
        "dry_run": dry_run,
    }

    if failures:
        result["failures"] = failures

    if dry_run and items_to_delete:
        result["items_to_delete"] = items_to_delete

    if total > 0:
        if dry_run:
            result["message"] = (
                f"Would clean {directories_deleted} directories and {files_deleted} files"
            )
        else:
            result["message"] = (
                f"Cleaned {directories_deleted} directories and {files_deleted} files"
            )
    else:
        result["message"] = "No Python cache files found"

    return result


def clean_reaper(dry_run: bool = False) -> dict[str, Any]:
    """Remove Reaper-generated artifacts and temporary files.

    Removes:
    - All *reapeaks files recursively in reaper/
    - Folders named "peaks" that contain reapeaks files
    - Backups/ and Media/ directories in reaper/examples/, reaper/markers/, and reaper/heads/
    - *.rpp files in reaper/ (root), reaper/markers/, and reaper/heads/ but NOT in reaper/examples/

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        Result dictionary with:
        - success: bool (True if operation completed without errors)
        - total: int (total number of items deleted or would be deleted)
        - directories_deleted: int (number of directories removed or would be removed)
        - files_deleted: int (number of files removed or would be removed)
        - failures: list[dict] (list of failures with item and reason, if any)
        - message: str (summary message)
        - dry_run: bool (indicates if this was a dry run)
        - items_to_delete: list[str] (list of items that would be deleted, only in dry_run mode)
    """
    reaper_dir = PROJECT_ROOT / "reaper"

    if not reaper_dir.exists():
        return {
            "success": True,
            "total": 0,
            "directories_deleted": 0,
            "files_deleted": 0,
            "message": "Reaper directory does not exist",
        }

    directories_deleted = 0
    files_deleted = 0
    failures: list[dict[str, str]] = []
    items_to_delete: list[str] = []

    # Collect items to delete
    reapeaks_files: list[Path] = []
    peaks_dirs: list[Path] = []
    backups_media_dirs: list[Path] = []
    rpp_files: list[Path] = []

    examples_dir = reaper_dir / "examples"
    markers_dir = reaper_dir / "markers"
    heads_dir = reaper_dir / "heads"

    # Find all *reapeaks files
    for reapeaks_file in reaper_dir.rglob("*reapeaks"):
        if reapeaks_file.is_file():
            reapeaks_files.append(reapeaks_file)

    # Find peaks folders that contain reapeaks files
    # We need to check if a peaks folder contains any reapeaks files
    for peaks_dir in reaper_dir.rglob("peaks"):
        if peaks_dir.is_dir():
            # Check if this peaks directory contains any reapeaks files
            has_reapeaks = any(
                reapeaks_file.is_relative_to(peaks_dir)
                for reapeaks_file in reapeaks_files
            )
            if has_reapeaks:
                peaks_dirs.append(peaks_dir)

    # Find Backups/ and Media/ directories in examples/, markers/, and heads/
    for subdir_name in ["examples", "markers", "heads"]:
        subdir = reaper_dir / subdir_name
        if subdir.exists():
            for target_dir_name in ["Backups", "Media"]:
                target_dir = subdir / target_dir_name
                if target_dir.exists() and target_dir.is_dir():
                    backups_media_dirs.append(target_dir)

    # Find *.rpp files in reaper/ root and reaper/markers/ but NOT in reaper/examples/
    # Find .rpp files in root (reaper/)
    for rpp_file in reaper_dir.glob("*.rpp"):
        if rpp_file.is_file():
            rpp_files.append(rpp_file)
    for rpp_file in reaper_dir.glob("*.RPP"):
        if rpp_file.is_file():
            rpp_files.append(rpp_file)

    # Find .rpp files in markers/ (but not examples/)
    if markers_dir.exists():
        for rpp_file in markers_dir.rglob("*.rpp"):
            if rpp_file.is_file():
                rpp_files.append(rpp_file)
        for rpp_file in markers_dir.rglob("*.RPP"):
            if rpp_file.is_file():
                rpp_files.append(rpp_file)

    # Find .rpp files in heads/ (but not examples/)
    if heads_dir.exists():
        for rpp_file in heads_dir.rglob("*.rpp"):
            if rpp_file.is_file():
                rpp_files.append(rpp_file)
        for rpp_file in heads_dir.rglob("*.RPP"):
            if rpp_file.is_file():
                rpp_files.append(rpp_file)

    # Filter out .rpp files in examples/ directory
    rpp_files = [
        rpp_file
        for rpp_file in rpp_files
        if not (examples_dir.exists() and rpp_file.is_relative_to(examples_dir))
    ]

    # Collect items for dry-run output
    if dry_run:
        for reapeaks_file in reapeaks_files:
            rel_path = reapeaks_file.relative_to(reaper_dir)
            items_to_delete.append(f"FILE: {rel_path}")
        for peaks_dir in peaks_dirs:
            rel_path = peaks_dir.relative_to(reaper_dir)
            items_to_delete.append(f"DIR:  {rel_path}/")
        for target_dir in backups_media_dirs:
            rel_path = target_dir.relative_to(reaper_dir)
            items_to_delete.append(f"DIR:  {rel_path}/")
        for rpp_file in rpp_files:
            rel_path = rpp_file.relative_to(reaper_dir)
            items_to_delete.append(f"FILE: {rel_path}")

    # Delete reapeaks files
    if not dry_run:
        for reapeaks_file in reapeaks_files:
            try:
                if reapeaks_file.exists():
                    reapeaks_file.unlink()
                    files_deleted += 1
            except Exception as exc:  # noqa: BLE001
                rel_path = reapeaks_file.relative_to(reaper_dir)
                failures.append(
                    {
                        "item": str(rel_path),
                        "reason": f"Failed to delete file: {exc}",
                    }
                )
    else:
        files_deleted = len(reapeaks_files)

    # Delete peaks directories
    if not dry_run:
        for peaks_dir in peaks_dirs:
            try:
                if peaks_dir.exists():
                    shutil.rmtree(peaks_dir)
                    directories_deleted += 1
            except Exception as exc:  # noqa: BLE001
                rel_path = peaks_dir.relative_to(reaper_dir)
                failures.append(
                    {
                        "item": str(rel_path),
                        "reason": f"Failed to delete directory: {exc}",
                    }
                )
    else:
        directories_deleted += len(peaks_dirs)

    # Delete Backups/ and Media/ directories
    if not dry_run:
        for target_dir in backups_media_dirs:
            try:
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                    directories_deleted += 1
            except Exception as exc:  # noqa: BLE001
                rel_path = target_dir.relative_to(reaper_dir)
                failures.append(
                    {
                        "item": str(rel_path),
                        "reason": f"Failed to delete directory: {exc}",
                    }
                )
    else:
        directories_deleted += len(backups_media_dirs)

    # Delete .rpp files
    if not dry_run:
        for rpp_file in rpp_files:
            try:
                if rpp_file.exists():
                    rpp_file.unlink()
                    files_deleted += 1
            except Exception as exc:  # noqa: BLE001
                rel_path = rpp_file.relative_to(reaper_dir)
                failures.append(
                    {
                        "item": str(rel_path),
                        "reason": f"Failed to delete file: {exc}",
                    }
                )
    else:
        files_deleted += len(rpp_files)

    total = directories_deleted + files_deleted
    success = len(failures) == 0

    result: dict[str, Any] = {
        "success": success,
        "total": total,
        "directories_deleted": directories_deleted,
        "files_deleted": files_deleted,
        "dry_run": dry_run,
    }

    if failures:
        result["failures"] = failures

    if dry_run and items_to_delete:
        result["items_to_delete"] = items_to_delete

    if total > 0:
        if dry_run:
            result["message"] = (
                f"Would clean {directories_deleted} directories and {files_deleted} files"
            )
        else:
            result["message"] = (
                f"Cleaned {directories_deleted} directories and {files_deleted} files"
            )
    else:
        result["message"] = "No Reaper artifacts found"

    return result
