"""Reaper markers session generation and reading."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

from dijon.global_config import AUDIO_MARKERS_DIR, PROJECT_ROOT, RAW_DIR

# Template path
REAPER_DIR = PROJECT_ROOT / "reaper"
DEFAULT_TEMPLATE = REAPER_DIR / "default.RPP"
MARKERS_DIR = REAPER_DIR / "markers"


def _get_audio_duration(audio_file: Path) -> float:
    """Get audio file duration using macOS afinfo.

    Returns duration in seconds, or 0.0 if unavailable.
    """
    try:
        result = subprocess.run(
            ["afinfo", str(audio_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse duration from afinfo output
        # Format: "estimated duration: 61.707 sec"
        match = re.search(r"estimated duration:\s*([\d.]+)\s*sec", result.stdout)
        if match:
            return float(match.group(1))
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    return 0.0


def _get_source_type(audio_file: Path) -> str:
    """Determine Reaper SOURCE type from file extension."""
    ext = audio_file.suffix.lower()
    mapping = {
        ".mp3": "MP3",
        ".wav": "WAVE",
        ".aiff": "WAVE",
        ".aif": "WAVE",
        ".flac": "WAVE",
        ".m4a": "MP3",
    }
    source_type = mapping.get(ext)
    if not source_type:
        raise ValueError(
            f"Unsupported audio format: {ext}. Supported: {', '.join(mapping.keys())}"
        )
    return source_type


def _generate_track_chunk(
    audio_file: Path,
    track_guid: str,
    track_id: str,
    item_guid: str,
    take_guid: str,
    length: float,
) -> str:
    """Generate a TRACK chunk with ITEM and SOURCE for the audio file."""
    source_type = _get_source_type(audio_file)
    audio_path_absolute = str(audio_file.resolve())
    track_name = audio_file.stem
    item_name = audio_file.name

    chunk = f"""  <TRACK {{{track_guid}}}
    NAME {track_name}
    PEAKCOL 16576
    BEAT -1
    AUTOMODE 0
    PANLAWFLAGS 3
    VOLPAN 1 0 -1 -1 1
    MUTESOLO 0 0 0
    IPHASE 0
    PLAYOFFS 0 1
    ISBUS 0 0
    BUSCOMP 0 0 0 0 0
    SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0 0
    FIXEDLANES 9 0 0 0 0
    LANEREC -1 -1 -1 0
    SEL 0
    REC 0 0 1 0 0 0 0 0
    VU 64
    TRACKHEIGHT 0 0 0 0 0 0 0
    INQ 0 0 0 0.5 100 0 0 100
    NCHAN 2
    FX 1
    TRACKID {{{track_id}}}
    PERF 0
    MIDIOUT -1
    MAINSEND 1 0
    <ITEM
      POSITION 0
      SNAPOFFS 0
      LENGTH {length}
      LOOP 1
      ALLTAKES 0
      FADEIN 1 0 0 1 0 0 0
      FADEOUT 1 0 0 1 0 0 0
      MUTE 0 0
      SEL 1
      IGUID {{{item_guid}}}
      IID 1
      NAME {item_name}
      VOLPAN 1 0 1 -1
      SOFFS 0
      PLAYRATE 1 1 0 -1 0 0.0025
      CHANMODE 0
      GUID {{{take_guid}}}
      <SOURCE {source_type}
        FILE "{audio_path_absolute}" 1
      >
    >
  >
"""
    return chunk


def create_markers_session(
    audio_file: Path,
    *,
    dry_run: bool = False,
    open_session: bool = False,
) -> dict:
    """Create a new Reaper markers session from an audio file.

    Args:
        audio_file: Path to source RAW audio file.
        dry_run: If True, simulate without writing files.
        open_session: If True, open the session in REAPER after creation.

    Returns:
        Dictionary with success status and session path.

    Raises:
        FileNotFoundError: If audio_file or template doesn't exist.
        ValueError: If audio format is unsupported.
    """
    audio_file = Path(audio_file)

    # If not absolute, assume it's in data/raw/youtube/
    if not audio_file.is_absolute():
        audio_file = RAW_DIR / "youtube" / audio_file.name

    audio_file = audio_file.resolve()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    if not DEFAULT_TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {DEFAULT_TEMPLATE}")

    # Compute output paths
    session_path = MARKERS_DIR / f"{audio_file.stem}_markers.RPP"

    if session_path.exists():
        raise FileExistsError(
            f"Session file already exists: {session_path}. Refusing to overwrite."
        )

    # Get audio duration
    length = _get_audio_duration(audio_file)
    if length == 0.0:
        # Warning will be logged but we continue
        pass

    # Generate GUIDs
    track_guid = str(uuid.uuid4()).upper()
    track_id = track_guid
    item_guid = str(uuid.uuid4()).upper()
    take_guid = str(uuid.uuid4()).upper()

    # Read template
    template_content = DEFAULT_TEMPLATE.read_text()

    # Generate track chunk
    track_chunk = _generate_track_chunk(
        audio_file=audio_file,
        track_guid=track_guid,
        track_id=track_id,
        item_guid=item_guid,
        take_guid=take_guid,
        length=length,
    )

    # Inject track before final closing >
    # Find the last > that closes the project
    lines = template_content.splitlines()
    last_closing_idx = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped == ">":
            last_closing_idx = i
            break

    if last_closing_idx is None:
        raise ValueError("Template file missing closing >")

    # Insert track chunk before the closing >
    lines.insert(last_closing_idx, track_chunk.rstrip())
    new_content = "\n".join(lines)

    if dry_run:
        return {
            "success": True,
            "message": f"Would create {session_path}",
            "session_path": str(session_path),
            "audio_file": str(audio_file.resolve()),
            "length": length,
        }

    # Create markers directory if needed
    MARKERS_DIR.mkdir(parents=True, exist_ok=True)

    # Write session file
    session_path.write_text(new_content)

    # Open in REAPER if requested
    if open_session:
        try:
            subprocess.run(
                ["open", "-a", "REAPER", str(session_path)],
                check=False,
            )
        except Exception:
            # Don't fail if open fails
            pass

    return {
        "success": True,
        "message": f"Created {session_path}",
        "session_path": str(session_path),
        "audio_file": str(audio_file.resolve()),
        "length": length,
    }


def read_markers(rpp_file: Path) -> dict:
    """Read marker data from a Reaper project file.

    Args:
        rpp_file: Path to Reaper project (.RPP) file.

    Returns:
        Dictionary with markers list, output file path, and metadata.

    Raises:
        FileNotFoundError: If rpp_file doesn't exist.
    """
    rpp_file = Path(rpp_file)
    if not rpp_file.exists():
        raise FileNotFoundError(f"RPP file not found: {rpp_file}")

    content = rpp_file.read_text()

    # Parse MARKER lines
    # Format: MARKER <number> <position> <name> <color> <flags> <locked>
    #         <guid_char> <guid> <unknown>
    # Example: MARKER 1 0.17 1A 8 0 1 B {4B33297A-385B-D84C-8CD4-EB377E55CE19} 0
    pattern = (
        r'MARKER\s+(\d+)\s+([\d.]+)\s+([^\s]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+'
        r'([A-Z])\s+(\{[A-F0-9-]+\})\s+(\d+)'
    )
    marker_pattern = re.compile(pattern)

    markers = []
    for match in marker_pattern.finditer(content):
        markers.append({
            "name": match.group(3),
            "position": float(match.group(2)),
            "number": int(match.group(1)),
            "color": int(match.group(4)),
            "flags": int(match.group(5)),
            "locked": int(match.group(6)),
            "guid": match.group(8),  # GUID is group 8 (after guid_char)
        })

    # Sort markers by number
    markers_sorted = sorted(markers, key=lambda m: m["number"])

    # Create output directory if needed
    AUDIO_MARKERS_DIR.mkdir(parents=True, exist_ok=True)

    # Normalize filename: replace -markers with _markers, ensure _markers suffix
    stem = rpp_file.stem
    # Replace -markers with _markers if present
    if stem.endswith("-markers"):
        stem = stem[:-8] + "_markers"
    elif not stem.endswith("_markers"):
        # If it doesn't end with _markers, add it
        stem = stem + "_markers"
    
    # Write JSON output file (overwrites if exists)
    output_file = AUDIO_MARKERS_DIR / f"{stem}.json"
    
    # Format markers as single-line objects
    marker_lines = []
    for marker in markers_sorted:
        marker_json = json.dumps(marker, separators=(",", ":"))
        marker_lines.append(f"    {marker_json}")
    
    # Build formatted JSON output
    json_output = "{\n"
    json_output += f'  "rpp_file": {json.dumps(str(rpp_file.resolve()))},\n'
    json_output += f'  "count": {len(markers)},\n'
    json_output += "  \"markers\": [\n"
    json_output += ",\n".join(marker_lines)
    json_output += "\n  ]\n"
    json_output += "}"
    
    output_file.write_text(json_output)

    return {
        "success": True,
        "markers": markers_sorted,
        "output_file": str(output_file),
        "count": len(markers),
    }


def read_all_markers() -> dict:
    """Read marker data from all RPP files in the markers directory.

    Searches reaper/markers for *.RPP files, extracts markers from each,
    and writes JSON output files to data/audio-markers (overwriting existing).

    Returns:
        Dictionary with processing results for all files.
    """
    # Find all RPP files in markers directory (excluding backups)
    rpp_files = sorted([
        f for f in MARKERS_DIR.glob("*.RPP")
        if not f.name.startswith(".")
    ])

    if not rpp_files:
        return {
            "success": True,
            "processed": 0,
            "files": [],
            "message": "No RPP files found in markers directory",
        }

    results = []
    for rpp_file in rpp_files:
        try:
            result = read_markers(rpp_file)
            results.append({
                "rpp_file": str(rpp_file),
                "output_file": result["output_file"],
                "count": result["count"],
                "success": True,
            })
        except Exception as e:
            results.append({
                "rpp_file": str(rpp_file),
                "success": False,
                "error": str(e),
            })

    return {
        "success": True,
        "processed": len(rpp_files),
        "files": results,
    }
