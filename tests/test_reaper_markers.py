"""Tests for Reaper markers session generation and reading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dijon.reaper.markers_session import (
    create_markers_session,
    read_markers,
)


@pytest.fixture
def template_file(project_root: Path) -> Path:
    """Create a minimal Reaper template file for testing."""
    template = project_root / "reaper" / "default.RPP"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(
        """<REAPER_PROJECT 0.1 "7.59/macOS-arm64" 1768512459 0
  <NOTES 0 2
  >
  RIPPLE 0 0
  <PROJBAY
  >
>
"""
    )
    return template


@pytest.fixture
def test_audio_file(project_root: Path) -> Path:
    """Create a test audio file."""
    audio_file = project_root / "data" / "datasets" / "raw" / "audio" / "test-audio.wav"
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    # Create a minimal valid WAV file header (44 bytes)
    wav_header = (
        b"RIFF"
        + (36).to_bytes(4, "little")  # file size - 8
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")  # fmt chunk size
        + (1).to_bytes(2, "little")  # audio format (PCM)
        + (1).to_bytes(2, "little")  # num channels (mono)
        + (48000).to_bytes(4, "little")  # sample rate
        + (96000).to_bytes(4, "little")  # byte rate
        + (2).to_bytes(2, "little")  # block align
        + (16).to_bytes(2, "little")  # bits per sample
        + b"data"
        + (0).to_bytes(4, "little")  # data chunk size
    )
    audio_file.write_bytes(wav_header)
    return audio_file


@pytest.fixture
def markers_dir(project_root: Path) -> Path:
    """Create markers directory."""
    markers = project_root / "markers"
    markers.mkdir(parents=True, exist_ok=True)
    return markers


def test_create_markers_session_dry_run(
    project_root: Path,
    template_file: Path,
    test_audio_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that dry-run doesn't create files."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    result = create_markers_session(
        audio_file=test_audio_file,
        dry_run=True,
        open_session=False,
    )

    assert result["success"] is True
    assert "Would create" in result["message"]
    assert result["session_path"].endswith("test-audio_markers.RPP")
    assert result["audio_file"] == str(test_audio_file.resolve())

    # Session file should not exist
    session_path = Path(result["session_path"])
    assert not session_path.exists()


def test_create_markers_session_creates_file(
    project_root: Path,
    template_file: Path,
    test_audio_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that create_markers_session creates the RPP file."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    result = create_markers_session(
        audio_file=test_audio_file,
        dry_run=False,
        open_session=False,
    )

    assert result["success"] is True
    session_path = Path(result["session_path"])
    assert session_path.exists()

    # Verify content
    content = session_path.read_text()
    assert "<TRACK {" in content
    assert "<ITEM" in content
    assert "<SOURCE WAVE" in content
    assert str(test_audio_file.resolve()) in content
    assert "test-audio.wav" in content


def test_create_markers_session_uses_absolute_paths(
    project_root: Path,
    template_file: Path,
    test_audio_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that FILE paths are absolute, not relative Media/ paths."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    result = create_markers_session(
        audio_file=test_audio_file,
        dry_run=False,
        open_session=False,
    )

    session_path = Path(result["session_path"])
    content = session_path.read_text()

    # Should use absolute path, not Media/ relative path
    assert str(test_audio_file.resolve()) in content
    assert 'FILE "Media/' not in content
    assert 'FILE "/' in content or 'FILE "' + str(test_audio_file.resolve()) in content


def test_create_markers_session_refuses_overwrite(
    project_root: Path,
    template_file: Path,
    test_audio_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that create_markers_session refuses to overwrite existing file."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    # Create existing session file
    existing_session = markers_dir / "test-audio-markers.RPP"
    existing_session.write_text("existing content")

    with pytest.raises(FileExistsError, match="already exists"):
        create_markers_session(
            audio_file=test_audio_file,
            dry_run=False,
            open_session=False,
        )

    # Original content should be unchanged
    assert existing_session.read_text() == "existing content"


def test_create_markers_session_unsupported_format(
    project_root: Path,
    template_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that unsupported audio formats raise ValueError."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    unsupported_file = project_root / "test.xyz"
    unsupported_file.write_bytes(b"fake content")

    with pytest.raises(ValueError, match="Unsupported audio format"):
        create_markers_session(
            audio_file=unsupported_file,
            dry_run=False,
            open_session=False,
        )


def test_read_markers_parses_correctly(
    project_root: Path,
) -> None:
    """Test that read_markers parses marker data correctly."""
    rpp_content = """<REAPER_PROJECT 0.1 "7.59/macOS-arm64" 1768498733 0
  <NOTES 0 2
  >
  MARKER 1 0.17 1A 8 0 1 B {4B33297A-385B-D84C-8CD4-EB377E55CE19} 0
  MARKER 2 8.48 1A2 8 0 1 B {8CB6F37A-4D25-CF46-8F8A-8750ED0D3D7A} 0
  MARKER 3 16.04113527826887 1B1 8 0 1 B {7971FA09-9ED7-FB49-8148-15909D311ACA} 0
  <PROJBAY
  >
>
"""
    rpp_file = project_root / "test-markers.RPP"
    rpp_file.write_text(rpp_content)

    result = read_markers(rpp_file=rpp_file)

    assert result["success"] is True
    assert result["count"] == 3
    assert len(result["markers"]) == 3

    # Check first marker
    marker1 = result["markers"][0]
    assert marker1["number"] == 1
    assert marker1["position"] == pytest.approx(0.17)
    assert marker1["name"] == "1A"
    assert marker1["guid"] == "{4B33297A-385B-D84C-8CD4-EB377E55CE19}"

    # Check output file was created
    output_file = Path(result["output_file"])
    assert output_file.exists()
    assert output_file.name == "test-markers.json"

    # Check JSON content
    json_data = json.loads(output_file.read_text())
    assert json_data["count"] == 3
    assert len(json_data["markers"]) == 3
    assert json_data["rpp_file"] == str(rpp_file.resolve())
    assert json_data["markers"][0]["name"] == "1A"


def test_read_markers_no_markers(
    project_root: Path,
) -> None:
    """Test that read_markers handles files with no markers."""
    rpp_content = """<REAPER_PROJECT 0.1 "7.59/macOS-arm64" 1768498733 0
  <NOTES 0 2
  >
  <PROJBAY
  >
>
"""
    rpp_file = project_root / "test-no-markers.RPP"
    rpp_file.write_text(rpp_content)

    result = read_markers(rpp_file=rpp_file)

    assert result["success"] is True
    assert result["count"] == 0
    assert len(result["markers"]) == 0

    # Check output file was created
    output_file = Path(result["output_file"])
    assert output_file.exists()

    # Check JSON content
    json_data = json.loads(output_file.read_text())
    assert json_data["count"] == 0
    assert len(json_data["markers"]) == 0


def test_read_markers_file_not_found() -> None:
    """Test that read_markers raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        read_markers(rpp_file=Path("/nonexistent/file.RPP"))


def test_create_markers_session_file_not_found(
    project_root: Path,
    template_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that create_markers_session raises FileNotFoundError for missing audio."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.DEFAULT_TEMPLATE", template_file
    )
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    with pytest.raises(FileNotFoundError):
        create_markers_session(
            audio_file=Path("/nonexistent/audio.wav"),
            dry_run=False,
            open_session=False,
        )


def test_create_markers_session_template_not_found(
    project_root: Path,
    test_audio_file: Path,
    markers_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that create_markers_session raises FileNotFoundError for missing template."""
    monkeypatch.setattr(
        "dijon.reaper.markers_session.MARKERS_DIR", markers_dir
    )

    with pytest.raises(FileNotFoundError):
        create_markers_session(
            audio_file=test_audio_file,
            dry_run=False,
            open_session=False,
        )
