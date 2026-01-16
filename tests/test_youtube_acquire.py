"""Tests for YouTube acquisition manifest generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dijon.pipeline.acquire.youtube import acquire
from dijon.utils._manifest import read_manifest


@pytest.mark.integration
def test_acquire_creates_manifest_with_three_assets(project_root: Path) -> None:
    """Test that acquire creates manifest entries for mp3, jpg, and json."""
    # Setup: create acquisition directory with test files
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    # Create test info_json
    youtube_id = "TEST1234567"
    base_name = f"Test-Song_{youtube_id}"
    info_json_data = {
        "song_name": "Test Song",
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "mp4": None,
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    # Create asset files (minimal content)
    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"fake mp3 content")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg content")

    # Run acquire
    result = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Assertions
    assert result["success"] is True
    assert result["rows_added"] == 3  # mp3, jpg, json
    assert result["files_processed"] == 1

    # Verify manifest content
    rows = read_manifest(manifest_path, profile="upstream")
    assert len(rows) == 3

    # Check that all three asset roles are present
    asset_roles = set()
    bundle_ids = set()
    for row in rows:
        meta_json = json.loads(row["meta_json"])
        asset_roles.add(meta_json["asset_role"])
        bundle_ids.add(meta_json["bundle_id"])
        assert row["status"] == "active"
        assert row["sha256"]  # Should have checksum
        assert row["rel_path"]  # Should have rel_path

    assert asset_roles == {"audio", "thumb", "info_json"}
    assert bundle_ids == {youtube_id}


@pytest.mark.integration
def test_acquire_includes_optional_mp4(project_root: Path) -> None:
    """Test that acquire includes mp4 video if present."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    youtube_id = "VIDEO123456"
    base_name = f"Test-Video_{youtube_id}"
    info_json_data = {
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "mp4": f"{base_name}.mp4",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    # Create all asset files
    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"fake mp3")
    (acquisition_dir / f"{base_name}.mp4").write_bytes(b"fake mp4")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg")

    result = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["rows_added"] == 4  # mp3, mp4, jpg, json

    rows = read_manifest(manifest_path, profile="upstream")
    asset_roles = {json.loads(row["meta_json"])["asset_role"] for row in rows}
    assert asset_roles == {"audio", "video", "thumb", "info_json"}


@pytest.mark.integration
def test_acquire_is_idempotent(project_root: Path) -> None:
    """Test that re-running acquire doesn't create duplicate rows."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    youtube_id = "IDEMP12345"
    base_name = f"Idempotent_{youtube_id}"
    info_json_data = {
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": f"https://www.youtube.com/watch?v={youtube_id}",
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"fake mp3")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg")

    # First run
    result1 = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )
    assert result1["success"] is True
    assert result1["rows_added"] == 3

    # Second run (should be idempotent)
    result2 = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )
    assert result2["success"] is True
    assert result2["rows_added"] == 0  # No new rows

    # Verify manifest still has exactly 3 rows
    rows = read_manifest(manifest_path, profile="upstream")
    assert len(rows) == 3


@pytest.mark.integration
def test_acquire_dry_run(project_root: Path) -> None:
    """Test that dry_run doesn't write manifest."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    youtube_id = "DRYRUN1234"
    base_name = f"DryRun_{youtube_id}"
    info_json_data = {
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {"id": youtube_id},
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"fake mp3")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg")

    result = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=True,
    )

    assert result["success"] is True
    assert result["rows_added"] == 0
    assert result["files_processed"] == 1
    assert "[DRY RUN]" in result["message"]

    # Manifest should not exist
    assert not manifest_path.exists()


@pytest.mark.integration
def test_acquire_handles_missing_assets_gracefully(project_root: Path) -> None:
    """Test that acquire handles missing asset files gracefully."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    youtube_id = "MISSING123"
    base_name = f"Missing_{youtube_id}"
    info_json_data = {
        "input_url": f"https://www.youtube.com/watch?v={youtube_id}",
        "downloaded": {
            "mp3": f"{base_name}.mp3",  # File doesn't exist
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",  # File doesn't exist
        },
        "yt_dlp": {"id": youtube_id},
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    # Only create the json file
    # mp3 and jpg are missing

    result = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    # Should succeed but only add info_json row
    assert result["success"] is True
    assert result["rows_added"] == 1  # Only info_json

    rows = read_manifest(manifest_path, profile="upstream")
    assert len(rows) == 1
    meta_json = json.loads(rows[0]["meta_json"])
    assert meta_json["asset_role"] == "info_json"


@pytest.mark.integration
def test_acquire_meta_json_structure(project_root: Path) -> None:
    """Test that meta_json has correct structure."""
    acquisition_dir = project_root / "data" / "acquisition" / "youtube"
    acquisition_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = acquisition_dir / "manifest.csv"

    youtube_id = "META1234567"
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    base_name = f"MetaTest_{youtube_id}"
    info_json_data = {
        "input_url": url,
        "downloaded": {
            "mp3": f"{base_name}.mp3",
            "json": f"{base_name}.json",
            "thumbnail": f"{base_name}.jpg",
        },
        "yt_dlp": {
            "id": youtube_id,
            "webpage_url": url,
        },
    }
    info_json_file = acquisition_dir / f"{base_name}.json"
    info_json_file.write_text(json.dumps(info_json_data, indent=2))

    (acquisition_dir / f"{base_name}.mp3").write_bytes(b"fake mp3")
    (acquisition_dir / f"{base_name}.jpg").write_bytes(b"fake jpg")

    result = acquire(
        acquisition_dir=acquisition_dir,
        manifest_path=manifest_path,
        data_dir=project_root / "data",
        dry_run=False,
    )

    assert result["success"] is True

    rows = read_manifest(manifest_path, profile="upstream")
    for row in rows:
        meta_json = json.loads(row["meta_json"])
        assert "upstream" in meta_json
        assert meta_json["upstream"]["kind"] == "youtube"
        assert meta_json["upstream"]["youtube_id"] == youtube_id
        assert meta_json["upstream"]["url"] == url
        assert meta_json["bundle_id"] == youtube_id
        assert meta_json["asset_role"] in ["audio", "thumb", "info_json"]
