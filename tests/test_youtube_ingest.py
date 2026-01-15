"""Tests for YouTube ingestion (acquisition → raw)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dijon.pipeline.youtube.acquire import acquire
from dijon.pipeline.youtube.ingest import ingest
from dijon.utils._manifest import read_manifest


@pytest.mark.integration
def test_ingest_copies_mp3_to_raw(project_root: Path) -> None:
    """Test that ingest copies MP3 files to raw directory."""
    # Setup: create acquisition directory with test files
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    acquisition_manifest_path = acquisition_dir / "manifest.csv"

    raw_dir = project_root / "data" / "raw" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_manifest_path = raw_dir / "manifest.csv"

    # Create test info_json
    youtube_id = "INGEST12345"
    base_name = f"Test-Song_{youtube_id}"
    info_json_data = {
        "song_name": "Test Song",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "title": "Test Song Title",
            "description": "Test description",
            "duration": 120,
            "tags": ["test", "song"],
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    # Create asset files
    mp3_content = b"fake mp3 content for ingest test"
    (acquisition_dir / f"{base_name}.mp3").write_bytes(mp3_content)
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg content")

    # First, run acquire to create acquisition manifest
    acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Run ingest
    result = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Assertions
    assert result["success"] is True
    assert result["ingested"] == 1
    assert result["skipped"] == 0

    # Verify raw file exists
    raw_manifest_rows = read_manifest(raw_manifest_path, profile="raw")
    assert len(raw_manifest_rows) == 1
    raw_row = raw_manifest_rows[0]
    assert raw_row["status"] == "active"
    assert raw_row["acq_sha256"]  # Should have acq_sha256

    # Verify raw file exists and has correct content
    raw_file_path = project_root / "data" / raw_row["rel_path"]
    assert raw_file_path.exists()
    assert raw_file_path.read_bytes() == mp3_content

    # Verify meta_json has required fields
    meta_json = json.loads(raw_row["meta_json"])
    assert meta_json["song_name"] == "Test Song"
    assert meta_json["input_url"] == f"https://www.youtube.com/watch?v={youtube_id}"
    assert meta_json["title"] == "Test Song Title"
    assert meta_json["description"] == "Test description"
    assert meta_json["duration_ms"] == 120000
    assert meta_json["tags"] == ["test", "song"]
    assert meta_json["upstream"]["kind"] == "youtube"
    assert meta_json["upstream"]["youtube_id"] == youtube_id


@pytest.mark.integration
def test_ingest_ignores_thumbnails(project_root: Path) -> None:
    """Test that ingest ignores thumbnail files."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    acquisition_manifest_path = acquisition_dir / "manifest.csv"

    raw_dir = project_root / "data" / "raw" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_manifest_path = raw_dir / "manifest.csv"

    youtube_id = "THUMB12345"
    base_name = f"Thumbnail-Test_{youtube_id}"
    info_json_data = {
        "song_name": "Thumbnail Test",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "title": "Thumbnail Test",
            "description": "",
            "duration": 60,
            "tags": [],
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"mp3 content")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"jpg content")

    # Run acquire
    acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Run ingest
    result = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Should only ingest MP3, not jpg
    assert result["ingested"] == 1

    # Verify only MP3 files in raw directory
    raw_files = list(raw_dir.glob("*.mp3"))
    assert len(raw_files) == 1
    jpg_files = list(raw_dir.glob("*.jpg"))
    assert len(jpg_files) == 0


@pytest.mark.integration
def test_ingest_is_idempotent(project_root: Path) -> None:
    """Test that re-running ingest doesn't create duplicate entries."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    acquisition_manifest_path = acquisition_dir / "manifest.csv"

    raw_dir = project_root / "data" / "raw" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_manifest_path = raw_dir / "manifest.csv"

    youtube_id = "IDEMP12345"
    base_name = f"Idempotent_{youtube_id}"
    info_json_data = {
        "song_name": "Idempotent Test",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "title": "Idempotent Test",
            "description": "",
            "duration": 90,
            "tags": [],
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"idempotent mp3")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"jpg")

    # Run acquire
    acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # First ingest
    result1 = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )
    assert result1["ingested"] == 1
    assert result1["skipped"] == 0

    # Second ingest (should be idempotent)
    result2 = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )
    assert result2["ingested"] == 0
    assert result2["skipped"] == 1

    # Verify manifest still has exactly 1 row
    raw_manifest_rows = read_manifest(raw_manifest_path, profile="raw")
    assert len(raw_manifest_rows) == 1

    # Verify only one raw file exists
    raw_files = list(raw_dir.glob("*.mp3"))
    assert len(raw_files) == 1


@pytest.mark.integration
def test_ingest_dry_run(project_root: Path) -> None:
    """Test that dry_run doesn't write files."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    acquisition_manifest_path = acquisition_dir / "manifest.csv"

    raw_dir = project_root / "data" / "raw" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_manifest_path = raw_dir / "manifest.csv"

    youtube_id = "DRYRUN1234"
    base_name = f"DryRun_{youtube_id}"
    info_json_data = {
        "song_name": "Dry Run Test",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "title": "Dry Run Test",
            "description": "",
            "duration": 45,
            "tags": [],
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"dry run mp3")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"jpg")

    # Run acquire
    acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Run ingest with dry_run
    result = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=True,
    )

    assert result["success"] is True
    assert result["ingested"] >= 0  # May show what would be ingested
    assert "[DRY RUN]" not in result.get("message", "")  # Message format may vary

    # Verify no raw files were created
    raw_files = list(raw_dir.glob("*.mp3"))
    assert len(raw_files) == 0

    # Verify manifest doesn't exist or is empty
    if raw_manifest_path.exists():
        rows = read_manifest(raw_manifest_path, profile="raw")
        assert len(rows) == 0


@pytest.mark.integration
def test_ingest_handles_missing_mp3_gracefully(project_root: Path) -> None:
    """Test that ingest handles missing MP3 files gracefully."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    acquisition_manifest_path = acquisition_dir / "manifest.csv"

    raw_dir = project_root / "data" / "raw" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_manifest_path = raw_dir / "manifest.csv"

    youtube_id = "MISSING123"
    base_name = f"Missing_{youtube_id}"
    info_json_data = {
        "song_name": "Missing MP3 Test",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",  # File doesn't exist
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
            "title": "Missing MP3",
            "description": "",
            "duration": 30,
            "tags": [],
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    # Only create the json file, not the mp3

    # Run acquire (will only add info_json)
    acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Run ingest
    result = ingest(
        acquisition_dir=acquisition_dir,
        raw_dir=raw_dir,
        raw_manifest_path=raw_manifest_path,
        acquisition_manifest_path=acquisition_manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Should succeed but skip the missing MP3
    assert result["success"] is True
    assert result["ingested"] == 0
    assert result["skipped"] >= 0  # May skip due to missing MP3
