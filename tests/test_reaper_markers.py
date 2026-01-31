"""Tests for Reaper markers session generation and reading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dijon.reaper.marker_names import (
    HEAD_IN_END,
    HEAD_IN_START,
    HEAD_OUT_END,
    HEAD_OUT_START,
    is_lick_marker,
    parse_lick_marker,
)
from dijon.reaper.markers_session import (
    _order_markers_in_entry,
    create_markers_session,
    order_markers_in_file,
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


def test_is_head_marker() -> None:
    """Test that is_head_marker correctly identifies head markers."""
    from dijon.reaper.marker_names import is_head_marker
    
    # Test canonical head marker names
    assert is_head_marker(HEAD_IN_START) is True
    assert is_head_marker(HEAD_IN_END) is True
    assert is_head_marker(HEAD_OUT_START) is True
    assert is_head_marker(HEAD_OUT_END) is True
    
    # Test non-head markers
    assert is_head_marker("1A") is False
    assert is_head_marker("F1.A1") is False
    assert is_head_marker("") is False


def test_read_markers_with_head_markers(
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that read_markers handles head marker names from RPP files."""
    from dijon.global_config import AUDIO_MARKERS_DIR
    
    # Patch AUDIO_MARKERS_DIR to use tmp_path
    markers_output_dir = tmp_path / "audio-markers"
    markers_output_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "dijon.reaper.markers_session.AUDIO_MARKERS_DIR", markers_output_dir
    )
    
    rpp_content = """<REAPER_PROJECT 0.1 "7.59/macOS-arm64" 1768498733 0
  <NOTES 0 2
  >
  MARKER 1 0.17 HEAD_IN_START 8 0 1 B {4B33297A-385B-D84C-8CD4-EB377E55CE19} 0
  MARKER 2 5.5 HEAD_IN_END 8 0 1 B {8CB6F37A-4D25-CF46-8F8A-8750ED0D3D7A} 0
  MARKER 3 10.0 HEAD_OUT_START 8 0 1 B {7971FA09-9ED7-FB49-8148-15909D311ACA} 0
  MARKER 4 15.0 HEAD_OUT_END 8 0 1 B {A1B2C3D4-E5F6-7890-ABCD-EF1234567890} 0
  MARKER 5 20.0 1A 8 0 1 B {B2C3D4E5-F6A7-8901-BCDE-F23456789012} 0
  <PROJBAY
  >
>
"""
    rpp_file = project_root / "test-head-markers.RPP"
    rpp_file.write_text(rpp_content)

    result = read_markers(rpp_file=rpp_file)

    assert result["success"] is True
    assert result["count"] == 5
    assert len(result["markers"]) == 5

    # Check that head markers are present
    marker_names = [m["name"] for m in result["markers"]]
    assert HEAD_IN_START in marker_names
    assert HEAD_IN_END in marker_names
    assert HEAD_OUT_START in marker_names
    assert HEAD_OUT_END in marker_names
    assert "1A" in marker_names
    
    # Verify output JSON contains head marker names
    output_file = Path(result["output_file"])
    assert output_file.exists()
    json_data = json.loads(output_file.read_text())
    json_marker_names = [m["name"] for m in json_data["entries"][0]["markers"]]
    assert HEAD_IN_START in json_marker_names
    assert HEAD_IN_END in json_marker_names
    assert HEAD_OUT_START in json_marker_names
    assert HEAD_OUT_END in json_marker_names


def test_unified_output_location(
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that all markers (form + head) are written to audio-markers/ JSON."""
    from dijon.global_config import AUDIO_MARKERS_DIR
    
    # Patch AUDIO_MARKERS_DIR to use tmp_path
    markers_output_dir = tmp_path / "audio-markers"
    markers_output_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "dijon.reaper.markers_session.AUDIO_MARKERS_DIR", markers_output_dir
    )
    
    rpp_content = """<REAPER_PROJECT 0.1 "7.59/macOS-arm64" 1768498733 0
  <NOTES 0 2
  >
  MARKER 1 0.17 HEAD_IN_START 8 0 1 B {4B33297A-385B-D84C-8CD4-EB377E55CE19} 0
  MARKER 2 5.5 1A 8 0 1 B {8CB6F37A-4D25-CF46-8F8A-8750ED0D3D7A} 0
  MARKER 3 10.0 F1.A1 8 0 1 B {7971FA09-9ED7-FB49-8148-15909D311ACA} 0
  <PROJBAY
  >
>
"""
    rpp_file = project_root / "test-unified-output.RPP"
    rpp_file.write_text(rpp_content)

    result = read_markers(rpp_file=rpp_file)

    assert result["success"] is True
    
    # Verify output is in audio-markers directory
    output_file = Path(result["output_file"])
    assert output_file.exists()
    assert "audio-markers" in str(output_file)
    assert output_file.parent == markers_output_dir
    
    # Verify all markers are in the same JSON file
    json_data = json.loads(output_file.read_text())
    markers = json_data["entries"][0]["markers"]
    marker_names = [m["name"] for m in markers]
    assert HEAD_IN_START in marker_names
    assert "1A" in marker_names
    assert "F1.A1" in marker_names


def test_order_markers_head_markers_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that head markers are ordered after regular markers."""
    from dijon.global_config import AUDIO_MARKERS_DIR
    
    # Patch AUDIO_MARKERS_DIR to use tmp_path
    markers_output_dir = tmp_path / "audio-markers"
    markers_output_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "dijon.reaper.markers_session.AUDIO_MARKERS_DIR", markers_output_dir
    )
    
    # Create a test marker file with mixed regular and head markers
    test_file = markers_output_dir / "test_order_markers.json"
    test_data = {
        "rpp_file": "/test/test.RPP",
        "entries": [
            {
                "timestamp": "2026-01-30T00:00:00",
                "count": 6,
                "markers": [
                    {"name": "A", "position": 5.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{A}"},
                    {"name": HEAD_IN_START, "position": 2.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{B}"},
                    {"name": "B", "position": 10.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{C}"},
                    {"name": HEAD_IN_END, "position": 8.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{D}"},
                    {"name": HEAD_OUT_START, "position": 1.0, "number": 5, "color": 0, "flags": 0, "locked": 1, "guid": "{E}"},
                    {"name": HEAD_OUT_END, "position": 15.0, "number": 6, "color": 0, "flags": 0, "locked": 1, "guid": "{F}"},
                ],
            }
        ],
    }
    test_file.write_text(json.dumps(test_data, indent=2))
    
    # Order the markers
    result = order_markers_in_file(test_file)
    
    assert result["success"] is True
    assert result["entries_processed"] == 1
    
    # Read back the ordered file
    ordered_data = json.loads(test_file.read_text())
    ordered_markers = ordered_data["entries"][0]["markers"]
    
    # Verify order: regular markers first (by position), then head markers (in specific order)
    marker_names = [m["name"] for m in ordered_markers]
    marker_numbers = [m["number"] for m in ordered_markers]
    
    # Regular markers should come first, sorted by position
    assert marker_names[0] == "A"  # position 5.0
    assert marker_numbers[0] == 1
    assert marker_names[1] == "B"  # position 10.0
    assert marker_numbers[1] == 2
    
    # Head markers should come after, in specific order
    assert marker_names[2] == HEAD_IN_START
    assert marker_numbers[2] == 3
    assert marker_names[3] == HEAD_IN_END
    assert marker_numbers[3] == 4
    assert marker_names[4] == HEAD_OUT_START
    assert marker_numbers[4] == 5
    assert marker_names[5] == HEAD_OUT_END
    assert marker_numbers[5] == 6
    
    # Verify all markers are numbered sequentially
    assert marker_numbers == [1, 2, 3, 4, 5, 6]


def test_order_markers_entry_direct() -> None:
    """Test _order_markers_in_entry directly with head markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 4,
        "markers": [
            {"name": "Regular1", "position": 10.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{1}"},
            {"name": HEAD_IN_START, "position": 2.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{2}"},
            {"name": "Regular2", "position": 5.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{3}"},
            {"name": HEAD_IN_END, "position": 8.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{4}"},
        ],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    marker_numbers = [m["number"] for m in ordered_entry["markers"]]
    
    # Regular markers should be first, sorted by position
    assert marker_names[0] == "Regular2"  # position 5.0
    assert marker_numbers[0] == 1
    assert marker_names[1] == "Regular1"  # position 10.0
    assert marker_numbers[1] == 2
    
    # Head markers should follow in specific order
    assert marker_names[2] == HEAD_IN_START
    assert marker_numbers[2] == 3
    assert marker_names[3] == HEAD_IN_END
    assert marker_numbers[3] == 4
    
    # Verify count is updated
    assert ordered_entry["count"] == 4


def test_is_lick_marker() -> None:
    """Test that is_lick_marker correctly identifies lick markers."""
    # Test valid lick marker patterns
    assert is_lick_marker("LICK01-START") is True
    assert is_lick_marker("LICK01-END") is True
    assert is_lick_marker("LICK02-START") is True
    assert is_lick_marker("LICK02-END") is True
    assert is_lick_marker("LICK10-START") is True
    assert is_lick_marker("LICK99-END") is True
    
    # Test invalid patterns
    assert is_lick_marker("LICK01") is False
    assert is_lick_marker("LICK-START") is False
    assert is_lick_marker("LICK1-START") is False  # needs two digits
    assert is_lick_marker("lick01-START") is False  # case sensitive
    assert is_lick_marker("HEAD_IN_START") is False
    assert is_lick_marker("1A") is False
    assert is_lick_marker("") is False


def test_parse_lick_marker() -> None:
    """Test that parse_lick_marker correctly extracts lick number and phase."""
    # Test valid markers
    assert parse_lick_marker("LICK01-START") == (1, "START")
    assert parse_lick_marker("LICK01-END") == (1, "END")
    assert parse_lick_marker("LICK02-START") == (2, "START")
    assert parse_lick_marker("LICK10-END") == (10, "END")
    assert parse_lick_marker("LICK99-START") == (99, "START")
    
    # Test invalid markers
    assert parse_lick_marker("LICK01") is None
    assert parse_lick_marker("HEAD_IN_START") is None
    assert parse_lick_marker("1A") is None
    assert parse_lick_marker("") is None


def test_order_markers_with_lick_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that lick markers are ordered after head markers."""
    from dijon.global_config import AUDIO_MARKERS_DIR
    
    # Patch AUDIO_MARKERS_DIR to use tmp_path
    markers_output_dir = tmp_path / "audio-markers"
    markers_output_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "dijon.reaper.markers_session.AUDIO_MARKERS_DIR", markers_output_dir
    )
    
    # Create a test marker file with regular, head, and lick markers
    test_file = markers_output_dir / "test_lick_markers.json"
    test_data = {
        "rpp_file": "/test/test.RPP",
        "entries": [
            {
                "timestamp": "2026-01-30T00:00:00",
                "count": 8,
                "markers": [
                    {"name": "A", "position": 5.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{A}"},
                    {"name": "LICK02-END", "position": 20.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{B}"},
                    {"name": HEAD_IN_START, "position": 2.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{C}"},
                    {"name": "LICK01-START", "position": 15.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{D}"},
                    {"name": "B", "position": 10.0, "number": 5, "color": 0, "flags": 0, "locked": 1, "guid": "{E}"},
                    {"name": HEAD_IN_END, "position": 8.0, "number": 6, "color": 0, "flags": 0, "locked": 1, "guid": "{F}"},
                    {"name": "LICK01-END", "position": 18.0, "number": 7, "color": 0, "flags": 0, "locked": 1, "guid": "{G}"},
                    {"name": "LICK02-START", "position": 19.0, "number": 8, "color": 0, "flags": 0, "locked": 1, "guid": "{H}"},
                ],
            }
        ],
    }
    test_file.write_text(json.dumps(test_data, indent=2))
    
    # Order the markers
    result = order_markers_in_file(test_file)
    
    assert result["success"] is True
    assert result["entries_processed"] == 1
    
    # Read back the ordered file
    ordered_data = json.loads(test_file.read_text())
    ordered_markers = ordered_data["entries"][0]["markers"]
    
    marker_names = [m["name"] for m in ordered_markers]
    marker_numbers = [m["number"] for m in ordered_markers]
    
    # Regular markers should come first, sorted by position
    assert marker_names[0] == "A"  # position 5.0
    assert marker_numbers[0] == 1
    assert marker_names[1] == "B"  # position 10.0
    assert marker_numbers[1] == 2
    
    # Head markers should come after regular markers
    assert marker_names[2] == HEAD_IN_START
    assert marker_numbers[2] == 3
    assert marker_names[3] == HEAD_IN_END
    assert marker_numbers[3] == 4
    
    # Lick markers should come last, grouped by lick number (01 before 02), START before END
    assert marker_names[4] == "LICK01-START"
    assert marker_numbers[4] == 5
    assert marker_names[5] == "LICK01-END"
    assert marker_numbers[5] == 6
    assert marker_names[6] == "LICK02-START"
    assert marker_numbers[6] == 7
    assert marker_names[7] == "LICK02-END"
    assert marker_numbers[7] == 8
    
    # Verify all markers are numbered sequentially
    assert marker_numbers == [1, 2, 3, 4, 5, 6, 7, 8]


def test_order_markers_entry_with_all_types() -> None:
    """Test _order_markers_in_entry with regular, head, and lick markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 7,
        "markers": [
            {"name": "Regular1", "position": 10.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{1}"},
            {"name": "LICK02-END", "position": 25.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{2}"},
            {"name": HEAD_IN_START, "position": 2.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{3}"},
            {"name": "Regular2", "position": 5.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{4}"},
            {"name": "LICK01-START", "position": 15.0, "number": 5, "color": 0, "flags": 0, "locked": 1, "guid": "{5}"},
            {"name": HEAD_IN_END, "position": 8.0, "number": 6, "color": 0, "flags": 0, "locked": 1, "guid": "{6}"},
            {"name": "LICK01-END", "position": 18.0, "number": 7, "color": 0, "flags": 0, "locked": 1, "guid": "{7}"},
        ],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    marker_numbers = [m["number"] for m in ordered_entry["markers"]]
    
    # Regular markers should be first, sorted by position
    assert marker_names[0] == "Regular2"  # position 5.0
    assert marker_numbers[0] == 1
    assert marker_names[1] == "Regular1"  # position 10.0
    assert marker_numbers[1] == 2
    
    # Head markers should follow
    assert marker_names[2] == HEAD_IN_START
    assert marker_numbers[2] == 3
    assert marker_names[3] == HEAD_IN_END
    assert marker_numbers[3] == 4
    
    # Lick markers should come last, grouped by lick number
    assert marker_names[4] == "LICK01-START"
    assert marker_numbers[4] == 5
    assert marker_names[5] == "LICK01-END"
    assert marker_numbers[5] == 6
    assert marker_names[6] == "LICK02-END"
    assert marker_numbers[6] == 7
    
    # Verify count is updated
    assert ordered_entry["count"] == 7


def test_order_markers_only_regular() -> None:
    """Test ordering with only regular markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 3,
        "markers": [
            {"name": "C", "position": 10.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{1}"},
            {"name": "A", "position": 5.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{2}"},
            {"name": "B", "position": 8.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{3}"},
        ],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    marker_numbers = [m["number"] for m in ordered_entry["markers"]]
    
    assert marker_names == ["A", "B", "C"]
    assert marker_numbers == [1, 2, 3]
    assert ordered_entry["count"] == 3


def test_order_markers_only_head() -> None:
    """Test ordering with only head markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 4,
        "markers": [
            {"name": HEAD_OUT_END, "position": 15.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{1}"},
            {"name": HEAD_IN_START, "position": 2.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{2}"},
            {"name": HEAD_IN_END, "position": 8.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{3}"},
            {"name": HEAD_OUT_START, "position": 1.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{4}"},
        ],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    marker_numbers = [m["number"] for m in ordered_entry["markers"]]
    
    assert marker_names == [HEAD_IN_START, HEAD_IN_END, HEAD_OUT_START, HEAD_OUT_END]
    assert marker_numbers == [1, 2, 3, 4]
    assert ordered_entry["count"] == 4


def test_order_markers_only_lick() -> None:
    """Test ordering with only lick markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 4,
        "markers": [
            {"name": "LICK02-END", "position": 20.0, "number": 1, "color": 0, "flags": 0, "locked": 1, "guid": "{1}"},
            {"name": "LICK01-START", "position": 15.0, "number": 2, "color": 0, "flags": 0, "locked": 1, "guid": "{2}"},
            {"name": "LICK02-START", "position": 19.0, "number": 3, "color": 0, "flags": 0, "locked": 1, "guid": "{3}"},
            {"name": "LICK01-END", "position": 18.0, "number": 4, "color": 0, "flags": 0, "locked": 1, "guid": "{4}"},
        ],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    marker_numbers = [m["number"] for m in ordered_entry["markers"]]
    
    assert marker_names == ["LICK01-START", "LICK01-END", "LICK02-START", "LICK02-END"]
    assert marker_numbers == [1, 2, 3, 4]
    assert ordered_entry["count"] == 4


def test_order_markers_empty() -> None:
    """Test ordering with no markers."""
    entry = {
        "timestamp": "2026-01-30T00:00:00",
        "count": 0,
        "markers": [],
    }
    
    ordered_entry = _order_markers_in_entry(entry)
    marker_names = [m["name"] for m in ordered_entry["markers"]]
    
    assert marker_names == []
    assert ordered_entry["count"] == 0
