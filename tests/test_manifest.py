"""Tests for manifest utilities."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from dijon.utils.manifest import (
    append_manifest_row,
    build_manifest_index,
    normalize_meta_json,
    normalize_rel_path,
    read_manifest,
    validate_manifest,
    write_manifest,
)


class TestNormalizeRelPath:
    """Tests for rel_path normalization and validation."""

    def test_relative_path_under_data_dir(self, tmp_path: Path) -> None:
        """Test that relative paths under DATA_DIR are accepted."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "raw").mkdir()

        # Relative path should normalize correctly
        result = normalize_rel_path("raw/test.txt", data_dir=data_dir)
        assert result == "raw/test.txt"

    def test_absolute_path_under_data_dir(self, tmp_path: Path) -> None:
        """Test that absolute paths under DATA_DIR are accepted and converted."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "raw").mkdir()
        abs_path = data_dir / "raw" / "test.txt"

        result = normalize_rel_path(str(abs_path), data_dir=data_dir)
        assert result == "raw/test.txt"

    def test_rejects_path_with_dotdot(self, tmp_path: Path) -> None:
        """Test that paths with '..' are rejected."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with pytest.raises(ValueError, match="must not contain"):
            normalize_rel_path("../outside.txt", data_dir=data_dir)

    def test_rejects_absolute_path_outside_data_dir(self, tmp_path: Path) -> None:
        """Test that absolute paths outside DATA_DIR are rejected."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        outside_path = tmp_path / "outside.txt"

        with pytest.raises(ValueError, match="outside DATA_DIR"):
            normalize_rel_path(str(outside_path), data_dir=data_dir)

    def test_rejects_relative_path_escaping_data_dir(self, tmp_path: Path) -> None:
        """Test that relative paths that escape DATA_DIR are rejected."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Use a symlink escape to hit the "escapes DATA_DIR" branch without using ".."
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        try:
            (data_dir / "link").symlink_to(outside_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform/filesystem")

        with pytest.raises(ValueError, match="escapes DATA_DIR"):
            normalize_rel_path("link/outside.txt", data_dir=data_dir)

    def test_rejects_empty_path(self, tmp_path: Path) -> None:
        """Test that empty paths are rejected."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with pytest.raises(ValueError, match="must be non-empty"):
            normalize_rel_path("", data_dir=data_dir)


class TestNormalizeMetaJson:
    """Tests for meta_json normalization."""

    def test_empty_string_returns_empty(self) -> None:
        """Test that empty string returns empty string."""
        assert normalize_meta_json("") == ""
        assert normalize_meta_json("   ") == ""

    def test_valid_json_object_canonicalized(self) -> None:
        """Test that valid JSON objects are canonicalized."""
        input_json = '{"b":2,"a":1}'
        result = normalize_meta_json(input_json)
        # Should be sorted and minified
        assert result == '{"a":1,"b":2}'
        # Should parse back to same dict
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_rejects_json_array(self) -> None:
        """Test that JSON arrays are rejected."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            normalize_meta_json('[1,2,3]')

    def test_rejects_json_string(self) -> None:
        """Test that JSON strings are rejected."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            normalize_meta_json('"just a string"')

    def test_rejects_invalid_json(self) -> None:
        """Test that invalid JSON is rejected."""
        with pytest.raises(ValueError, match="must be valid JSON"):
            normalize_meta_json("{invalid}")


class TestManifestProfiles:
    """Tests for manifest profile validation."""

    def test_raw_profile_requires_all_fields(self, tmp_path: Path) -> None:
        """Test that raw profile enforces all required fields."""
        manifest_path = tmp_path / "manifest.csv"

        # Missing required fields should raise
        with pytest.raises(ValueError, match="requires fields"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="raw/test.txt",
                status="active",
                sha256="abc123",
                source_name="test.txt",
                schema_version="1",
                profile="raw",
                # Missing file_id, ingested_at, acq_sha256
            )

    def test_raw_profile_enforces_uniqueness(self, tmp_path: Path) -> None:
        """Test that raw profile enforces uniqueness on file_id, sha256, rel_path."""
        manifest_path = tmp_path / "manifest.csv"

        # Add first row
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="raw/test1.txt",
            status="active",
            sha256="abc123",
            source_name="test1.txt",
            schema_version="1",
            profile="raw",
            file_id="TEST-2412-001",
            ingested_at="2024-12-01T00:00:00Z",
            acq_sha256="def456",
        )

        # Duplicate file_id should fail
        with pytest.raises(ValueError, match="Uniqueness constraint violated.*file_id"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="raw/test2.txt",
                status="active",
                sha256="xyz789",
                source_name="test2.txt",
                schema_version="1",
                profile="raw",
                file_id="TEST-2412-001",  # Duplicate
                ingested_at="2024-12-01T00:00:00Z",
                acq_sha256="def456",
            )

        # Duplicate sha256 should fail
        with pytest.raises(ValueError, match="Uniqueness constraint violated.*sha256"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="raw/test2.txt",
                status="active",
                sha256="abc123",  # Duplicate
                source_name="test2.txt",
                schema_version="1",
                profile="raw",
                file_id="TEST-2412-002",
                ingested_at="2024-12-01T00:00:00Z",
                acq_sha256="def456",
            )

        # Duplicate rel_path should fail
        with pytest.raises(ValueError, match="Uniqueness constraint violated.*rel_path"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="raw/test1.txt",  # Duplicate
                status="active",
                sha256="xyz789",
                source_name="test2.txt",
                schema_version="1",
                profile="raw",
                file_id="TEST-2412-002",
                ingested_at="2024-12-01T00:00:00Z",
                acq_sha256="def456",
            )

    def test_upstream_profile_minimal_fields(self, tmp_path: Path) -> None:
        """Test that upstream profile only requires minimal fields."""
        manifest_path = tmp_path / "manifest.csv"

        # Should succeed with only required fields
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="",  # Optional for upstream
            status="active",
            sha256="abc123",
            source_name="test.txt",
            schema_version="1",
            profile="upstream",
        )

        rows = read_manifest(manifest_path, profile="upstream")
        assert len(rows) == 1
        assert rows[0]["sha256"] == "abc123"
        assert rows[0]["rel_path"] == ""  # Empty is allowed

    def test_upstream_profile_no_uniqueness(self, tmp_path: Path) -> None:
        """Test that upstream profile does not enforce uniqueness."""
        manifest_path = tmp_path / "manifest.csv"

        # Add first row
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="",
            status="active",
            sha256="abc123",
            source_name="test.txt",
            schema_version="1",
            profile="upstream",
        )

        # Duplicate sha256 should be allowed for upstream
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="",
            status="active",
            sha256="abc123",  # Duplicate allowed
            source_name="test2.txt",
            schema_version="1",
            profile="upstream",
        )

        rows = read_manifest(manifest_path, profile="upstream")
        assert len(rows) == 2

    def test_derived_profile_requires_rel_path(self, tmp_path: Path) -> None:
        """Test that derived profile requires rel_path."""
        manifest_path = tmp_path / "manifest.csv"

        # Missing rel_path should fail
        with pytest.raises(ValueError, match="requires fields"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="",  # Required for derived
                status="active",
                sha256="abc123",
                source_name="test.txt",
                schema_version="1",
                profile="derived",
            )

    def test_derived_profile_enforces_rel_path_uniqueness(self, tmp_path: Path) -> None:
        """Test that derived profile enforces rel_path uniqueness."""
        manifest_path = tmp_path / "manifest.csv"

        # Add first row
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="derived/test1.txt",
            status="active",
            sha256="abc123",
            source_name="test1.txt",
            schema_version="1",
            profile="derived",
        )

        # Duplicate rel_path should fail
        with pytest.raises(ValueError, match="Uniqueness constraint violated.*rel_path"):
            append_manifest_row(
                manifest_path=manifest_path,
                rel_path="derived/test1.txt",  # Duplicate
                status="active",
                sha256="xyz789",  # Different sha256 OK
                source_name="test2.txt",
                schema_version="1",
                profile="derived",
            )


class TestAppendManifestRow:
    """Tests for append_manifest_row with different validation modes."""

    def test_row_validation_mode(self, tmp_path: Path) -> None:
        """Test that validate='row' only validates the new row."""
        manifest_path = tmp_path / "manifest.csv"

        # Should succeed with row validation (default)
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="raw/test.txt",
            status="active",
            sha256="abc123",
            source_name="test.txt",
            schema_version="1",
            profile="raw",
            validate="row",
            file_id="TEST-2412-001",
            ingested_at="2024-12-01T00:00:00Z",
            acq_sha256="def456",
        )

        rows = read_manifest(manifest_path, profile="raw")
        assert len(rows) == 1

    def test_full_validation_mode(self, tmp_path: Path) -> None:
        """Test that validate='full' validates entire manifest."""
        manifest_path = tmp_path / "manifest.csv"

        # Add valid row
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="raw/test1.txt",
            status="active",
            sha256="abc123",
            source_name="test1.txt",
            schema_version="1",
            profile="raw",
            validate="full",
            file_id="TEST-2412-001",
            ingested_at="2024-12-01T00:00:00Z",
            acq_sha256="def456",
        )

        # Add another valid row with full validation
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="raw/test2.txt",
            status="active",
            sha256="xyz789",
            source_name="test2.txt",
            schema_version="1",
            profile="raw",
            validate="full",
            file_id="TEST-2412-002",
            ingested_at="2024-12-01T00:00:00Z",
            acq_sha256="def456",
        )

        rows = read_manifest(manifest_path, profile="raw")
        assert len(rows) == 2


class TestValidateManifest:
    """Tests for validate_manifest function."""

    def test_valid_manifest_returns_empty_errors(self, tmp_path: Path) -> None:
        """Test that valid manifest returns empty error list."""
        manifest_path = tmp_path / "manifest.csv"

        # Create valid manifest
        append_manifest_row(
            manifest_path=manifest_path,
            rel_path="raw/test.txt",
            status="active",
            sha256="abc123",
            source_name="test.txt",
            schema_version="1",
            profile="raw",
            file_id="TEST-2412-001",
            ingested_at="2024-12-01T00:00:00Z",
            acq_sha256="def456",
        )

        errors = validate_manifest(manifest_path, profile="raw")
        assert errors == []

    def test_validate_manifest_detects_missing_fields(self, tmp_path: Path) -> None:
        """Test that validate_manifest detects missing required fields."""
        manifest_path = tmp_path / "manifest.csv"

        # Header must include required fields for the profile, but values may be missing.
        # (If the header is missing required fields, read_manifest() raises.)
        rows = [
            {
                "file_id": "TEST-2412-001",
                "rel_path": "raw/test.txt",
                "status": "active",
                "sha256": "",
                "acq_sha256": "",
                "ingested_at": "",
                "source_name": "",
                "schema_version": "",
            }
        ]
        write_manifest(manifest_path, rows, profile="raw")

        errors = validate_manifest(manifest_path, profile="raw")
        assert len(errors) > 0
        assert any("Missing required fields" in err for err in errors)

    def test_validate_manifest_detects_duplicates(self, tmp_path: Path) -> None:
        """Test that validate_manifest detects duplicate unique values."""
        manifest_path = tmp_path / "manifest.csv"

        # Write manifest with duplicates manually
        rows = [
            {
                "file_id": "TEST-2412-001",
                "rel_path": "raw/test1.txt",
                "status": "active",
                "sha256": "abc123",
                "acq_sha256": "def456",
                "ingested_at": "2024-12-01T00:00:00Z",
                "source_name": "test1.txt",
                "schema_version": "1",
            },
            {
                "file_id": "TEST-2412-001",  # Duplicate file_id
                "rel_path": "raw/test2.txt",
                "status": "active",
                "sha256": "xyz789",
                "acq_sha256": "def456",
                "ingested_at": "2024-12-01T00:00:00Z",
                "source_name": "test2.txt",
                "schema_version": "1",
            },
        ]
        write_manifest(manifest_path, rows, profile="raw")

        errors = validate_manifest(manifest_path, profile="raw")
        assert len(errors) > 0
        assert any("Duplicate" in err and "file_id" in err for err in errors)


class TestBuildManifestIndex:
    """Tests for build_manifest_index function."""

    def test_index_builds_correctly(self) -> None:
        """Test that index is built correctly for uniqueness fields."""
        rows = [
            {
                "file_id": "TEST-2412-001",
                "rel_path": "raw/test1.txt",
                "sha256": "abc123",
            },
            {
                "file_id": "TEST-2412-002",
                "rel_path": "raw/test2.txt",
                "sha256": "xyz789",
            },
        ]

        index = build_manifest_index(rows, profile="raw")
        assert "file_id" in index
        assert "sha256" in index
        assert "rel_path" in index

        assert "TEST-2412-001" in index["file_id"]
        assert "TEST-2412-002" in index["file_id"]
        assert "abc123" in index["sha256"]
        assert "xyz789" in index["sha256"]

    def test_index_ignores_empty_values(self) -> None:
        """Test that index ignores empty values."""
        rows = [
            {
                "file_id": "TEST-2412-001",
                "rel_path": "",  # Empty
                "sha256": "abc123",
            },
        ]

        index = build_manifest_index(rows, profile="raw")
        assert "rel_path" in index
        assert len(index["rel_path"]) == 0  # Empty values not indexed
