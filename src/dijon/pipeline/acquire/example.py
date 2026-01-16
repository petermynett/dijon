"""Acquisition verb for example source.

Acquisition fetches upstream data and writes it to the acquisition layer.
This is the first stage of the pipeline: acquire → ingest → load.
"""

from __future__ import annotations

from pathlib import Path

from datetime import UTC, datetime

from ...utils._manifest import compute_file_checksum


def acquire(
    source_key: str,
    acquisition_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, str | int | bool]:
    """Acquire upstream data for the example source.

    This is a reference implementation that demonstrates the acquire verb pattern.
    In a real implementation, this would fetch data from an upstream source
    (API, file system, etc.) and write it to the acquisition directory.

    Args:
        source_key: Source identifier (e.g., "example").
        acquisition_dir: Directory where acquisition files are stored.
        dry_run: If True, simulate the operation without writing files.

    Returns:
        Result dictionary with:
        - success: bool
        - files_acquired: int (number of files acquired)
        - message: str (summary message)
    """
    if dry_run:
        return {
            "success": True,
            "files_acquired": 0,
            "message": f"[DRY RUN] Would acquire data for {source_key}",
        }

    # Ensure acquisition directory exists
    acquisition_dir.mkdir(parents=True, exist_ok=True)

    # Example: Create a minimal acquisition file
    # In a real implementation, this would fetch from upstream
    timestamp = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    example_file = acquisition_dir / f"example_{timestamp.replace(':', '-').replace('T', '_')}.txt"
    example_file.write_text(f"Example acquisition data for {source_key}\nTimestamp: {timestamp}\n")

    # Compute checksum for provenance
    acq_sha256 = compute_file_checksum(example_file)

    return {
        "success": True,
        "files_acquired": 1,
        "message": f"Acquired 1 file for {source_key}",
        "acquisition_file": str(example_file),
        "acq_sha256": acq_sha256,
    }
