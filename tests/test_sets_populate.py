"""Tests for set populate functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dijon.pipeline.sets import populate_set_yaml
from dijon.utils.manifest import write_manifest
from dijon.utils.sets import load_set_yaml, resolve_set_path


class TestResolveSetPath:
    """Tests for resolve_set_path function."""

    def test_resolve_set_name(self, project_root: Path) -> None:
        """Test resolving a set name to SETS_DIR/<name>.yaml."""
        # Create sets directory and file
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text("version: 1\nitems: []\n")

        # Resolve by name
        resolved = resolve_set_path("leading", project_root=project_root)
        assert resolved == set_file
        assert resolved.exists()

    def test_resolve_set_path(self, project_root: Path) -> None:
        """Test resolving a set path relative to project root."""
        # Create sets directory and file
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text("version: 1\nitems: []\n")

        # Resolve by path
        resolved = resolve_set_path("data/sets/leading.yaml", project_root=project_root)
        assert resolved == set_file
        assert resolved.exists()

    def test_resolve_set_path_fails_if_not_exists(self, project_root: Path) -> None:
        """Test that resolving a non-existent set fails."""
        with pytest.raises(FileNotFoundError):
            resolve_set_path("nonexistent", project_root=project_root)

    def test_resolve_set_path_fails_if_outside_project(self, project_root: Path) -> None:
        """Test that resolving a path outside project root fails."""
        with pytest.raises(ValueError, match="outside PROJECT_ROOT"):
            resolve_set_path("../outside.yaml", project_root=project_root)


class TestPopulateSetYaml:
    """Tests for populate_set_yaml function."""

    def test_populate_set_from_manifest(self, project_root: Path) -> None:
        """Test populating set items from manifest data."""
        # Create set YAML
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
kind: audio
items:
  - file_id: YTB-001
    song_name:
    source_name:
    url:
  - file_id: YTB-002
    song_name:
    source_name:
    url:
"""
        )

        # Create manifest
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json_1 = json.dumps(
            {
                "song_name": "I'll fly away",
                "upstream": {"url": "https://www.youtube.com/watch?v=1BPoMIQHwpo"},
            }
        )
        meta_json_2 = json.dumps(
            {
                "song_name": "the blackest crow",
                "upstream": {"url": "https://www.youtube.com/watch?v=NEDHzPnEIZ0"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test1.mp3",
                "schema_version": "1",
                "meta_json": meta_json_1,
            },
            {
                "file_id": "YTB-002",
                "rel_path": "raw/audio/YTB-002.wav",
                "status": "active",
                "sha256": "def456",
                "acq_sha256": "def456",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test2.mp3",
                "schema_version": "1",
                "meta_json": meta_json_2,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate set
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["total"] == 2
        assert result["updated"] == 2
        assert result["skipped"] == 0
        assert result["failed"] == 0

        # Verify set was updated
        set_data = load_set_yaml(set_file)
        items = set_data["items"]

        assert items[0]["file_id"] == "YTB-001"
        assert items[0]["song_name"] == "I'll fly away"
        assert items[0]["source_name"] == "test1.mp3"
        assert items[0]["url"] == "https://www.youtube.com/watch?v=1BPoMIQHwpo"

        assert items[1]["file_id"] == "YTB-002"
        assert items[1]["song_name"] == "the blackest crow"
        assert items[1]["source_name"] == "test2.mp3"
        assert items[1]["url"] == "https://www.youtube.com/watch?v=NEDHzPnEIZ0"

    def test_populate_set_dry_run(self, project_root: Path) -> None:
        """Test that dry_run doesn't write changes."""
        # Create set YAML
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name:
    source_name:
    url:
"""
        )

        # Create manifest
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "Test Song",
                "upstream": {"url": "https://example.com"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate with dry_run
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=True,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["updated"] == 1

        # Verify set was NOT updated
        set_data = load_set_yaml(set_file)
        items = set_data["items"]
        assert items[0]["song_name"] == ""
        assert items[0]["source_name"] == ""
        assert items[0]["url"] == ""

    def test_populate_set_no_overwrite(self, project_root: Path) -> None:
        """Test that existing fields are not overwritten unless overwrite=True."""
        # Create set YAML with existing values
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name: Existing Song
    source_name: existing.mp3
    url: https://existing.com
"""
        )

        # Create manifest with different values
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "New Song",
                "upstream": {"url": "https://new.com"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "new.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate without overwrite
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["updated"] == 0  # No updates because fields already filled

        # Verify existing values preserved
        set_data = load_set_yaml(set_file)
        items = set_data["items"]
        assert items[0]["song_name"] == "Existing Song"
        assert items[0]["source_name"] == "existing.mp3"
        assert items[0]["url"] == "https://existing.com"

    def test_populate_set_with_overwrite(self, project_root: Path) -> None:
        """Test that overwrite=True overwrites existing fields."""
        # Create set YAML with existing values
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name: Existing Song
    source_name: existing.mp3
    url: https://existing.com
"""
        )

        # Create manifest with different values
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "New Song",
                "upstream": {"url": "https://new.com"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "new.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate with overwrite
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=True,
        )

        assert result["success"] is True
        assert result["updated"] == 1

        # Verify values were overwritten
        set_data = load_set_yaml(set_file)
        items = set_data["items"]
        assert items[0]["song_name"] == "New Song"
        assert items[0]["source_name"] == "new.mp3"
        assert items[0]["url"] == "https://new.com"

    def test_populate_set_skips_missing_file_id(self, project_root: Path) -> None:
        """Test that items with missing file_id are skipped."""
        # Create set YAML
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name:
    source_name:
    url:
  - file_id:
    song_name:
    source_name:
    url:
"""
        )

        # Create manifest
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "Test Song",
                "upstream": {"url": "https://example.com"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate set
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["total"] == 2
        assert result["updated"] == 1
        assert result["skipped"] == 1  # One item skipped due to missing file_id

    def test_populate_set_skips_missing_manifest_entry(self, project_root: Path) -> None:
        """Test that items with file_id not in manifest are skipped."""
        # Create set YAML
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name:
    source_name:
    url:
  - file_id: YTB-999
    song_name:
    source_name:
    url:
"""
        )

        # Create manifest with only one entry
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "Test Song",
                "upstream": {"url": "https://example.com"},
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate set
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["total"] == 2
        assert result["updated"] == 1
        assert result["skipped"] == 1  # One item skipped due to missing manifest entry

    def test_populate_set_url_fallback_to_input_url(self, project_root: Path) -> None:
        """Test that url falls back to input_url if upstream.url is missing."""
        # Create set YAML
        sets_dir = project_root / "data" / "sets"
        sets_dir.mkdir(parents=True)
        set_file = sets_dir / "leading.yaml"
        set_file.write_text(
            """version: 1
paths: data/datasets/raw/audio/
items:
  - file_id: YTB-001
    song_name:
    source_name:
    url:
"""
        )

        # Create manifest with input_url but no upstream.url
        manifest_dir = project_root / "data" / "datasets" / "raw" / "audio"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "manifest.csv"

        meta_json = json.dumps(
            {
                "song_name": "Test Song",
                "input_url": "https://fallback.com",
            }
        )

        manifest_rows = [
            {
                "file_id": "YTB-001",
                "rel_path": "raw/audio/YTB-001.wav",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "abc123",
                "ingested_at": "2024-01-01T00:00:00Z",
                "source_name": "test.mp3",
                "schema_version": "1",
                "meta_json": meta_json,
            },
        ]

        write_manifest(manifest_file, manifest_rows, profile="raw")

        # Populate set
        result = populate_set_yaml(
            set_file,
            project_root=project_root,
            dry_run=False,
            overwrite=False,
        )

        assert result["success"] is True
        assert result["updated"] == 1

        # Verify url was populated from input_url
        set_data = load_set_yaml(set_file)
        items = set_data["items"]
        assert items[0]["url"] == "https://fallback.com"
