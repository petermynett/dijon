"""Reaper markers session generation and reading."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from dijon.global_config import AUDIO_MARKERS_DIR, PROJECT_ROOT, RAW_AUDIO_DIR
from dijon.reaper.marker_names import (
    HEAD_IN_END,
    HEAD_IN_START,
    HEAD_OUT_END,
    HEAD_OUT_START,
    is_head_marker,
    is_lick_marker,
    normalize_marker_name,
    parse_lick_marker,
)

# Template path
REAPER_DIR = PROJECT_ROOT / "reaper"
DEFAULT_TEMPLATE = REAPER_DIR / "examples" / "default.RPP"
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


def _generate_marker_lines(markers: list[dict]) -> list[str]:
    """Generate RPP MARKER lines from marker JSON data.

    Args:
        markers: List of marker dictionaries with keys: number, position, name,
                 color, flags, locked, guid

    Returns:
        List of MARKER lines in RPP format.
    """
    # Sort markers by number to ensure correct order
    sorted_markers = sorted(markers, key=lambda m: m.get("number", 0))
    
    marker_lines = []
    for marker in sorted_markers:
        number = marker.get("number", 0)
        position = marker.get("position", 0.0)
        name = marker.get("name", "")
        color = marker.get("color", 0)
        flags = marker.get("flags", 0)
        locked = marker.get("locked", 1)
        guid = marker.get("guid", "")
        guid_char = "B"  # Default guid_char
        unknown = 0  # Default unknown value
        
        # Format: MARKER <number> <position> <name> <color> <flags> <locked> <guid_char> <guid> <unknown>
        marker_line = f"  MARKER {number} {position} {name} {color} {flags} {locked} {guid_char} {guid} {unknown}"
        marker_lines.append(marker_line)
    
    return marker_lines


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
    TRACKHEIGHT 385 0 0 0 0 0 0
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

    If a session file already exists, it will be deleted and replaced.

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

    # If not absolute, assume it's in data/datasets/raw/audio/
    if not audio_file.is_absolute():
        audio_file = RAW_AUDIO_DIR / audio_file.name

    # If no extension, presume it's .wav
    if not audio_file.suffix:
        audio_file = audio_file.with_suffix(".wav")

    audio_file = audio_file.resolve()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    if not DEFAULT_TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {DEFAULT_TEMPLATE}")

    # Compute output paths
    session_path = MARKERS_DIR / f"{audio_file.stem}_markers.RPP"

    # Delete existing session file if it exists (overwrite behavior)
    if session_path.exists():
        session_path.unlink()

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

    # Check for existing marker annotation file
    annotation_file = AUDIO_MARKERS_DIR / f"{audio_file.stem}_markers.json"
    markers_data = None
    
    if annotation_file.exists():
        try:
            annotation_json = json.loads(annotation_file.read_text())
            
            # Handle backward compatibility: old format without entries array
            if "entries" not in annotation_json:
                # Old format: convert to new format structure
                old_markers = annotation_json.get("markers", [])
                markers_data = {
                    "markers": old_markers,
                }
            else:
                # New format: use newest entry (first in entries array)
                entries = annotation_json.get("entries", [])
                if entries:
                    markers_data = entries[0]
        except (json.JSONDecodeError, KeyError) as e:
            # If we can't parse, continue without markers
            pass

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

    # Parse template into lines
    lines = template_content.splitlines()
    
    # Find insertion points
    # 1. Find TEMPOENVEX closing tag (for marker insertion)
    tempoenv_closing_idx = None
    for i, line in enumerate(lines):
        if "<TEMPOENVEX" in line:
            # Find the matching closing > (should be within next 10 lines)
            for j in range(i + 1, min(len(lines), i + 10)):
                if lines[j].strip() == ">":
                    tempoenv_closing_idx = j
                    break
            break
    
    # 2. Find PROJBAY line (markers go before this)
    projbay_idx = None
    for i, line in enumerate(lines):
        if "<PROJBAY" in line:
            projbay_idx = i
            break
    
    # 3. Find final closing > (for track insertion)
    last_closing_idx = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped == ">":
            last_closing_idx = i
            break

    if last_closing_idx is None:
        raise ValueError("Template file missing closing >")
    
    # Insert markers if we have marker data
    if markers_data and markers_data.get("markers"):
        marker_lines = _generate_marker_lines(markers_data["markers"])
        
        if projbay_idx is not None:
            # Insert markers before PROJBAY (preferred location)
            lines[projbay_idx:projbay_idx] = marker_lines
            # Update last_closing_idx since we added lines
            last_closing_idx += len(marker_lines)
        elif tempoenv_closing_idx is not None:
            # Insert markers after TEMPOENVEX closing (fallback)
            lines[tempoenv_closing_idx + 1:tempoenv_closing_idx + 1] = marker_lines
            # Update last_closing_idx since we added lines
            last_closing_idx += len(marker_lines)
        # If neither found, skip marker insertion (shouldn't happen with valid template)

    # Insert track chunk before the final closing >
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


def _order_markers_in_entry(entry: dict) -> dict:
    """Order markers by position and renumber them sequentially.
    
    Takes an entry dict with a markers list, sorts regular markers by position
    (ascending), then appends head markers (HEAD_IN_START, HEAD_IN_END,
    HEAD_OUT_START, HEAD_OUT_END) in that specific order, then appends lick
    markers (LICK##_START, LICK##_END) grouped by lick number ascending with
    START before END for each lick number. Renumbers all markers sequentially
    starting from 1. Updates the count field to match the number of markers.
    
    Also normalizes head and lick marker names to use underscores instead of
    dashes (e.g., HEAD-IN-START -> HEAD_IN_START, LICK01-START -> LICK01_START).
    
    Handles any subset of marker types safely (form/head/lick/none).
    
    Args:
        entry: Dictionary with 'markers' list and optionally 'count' field.
    
    Returns:
        Modified entry dict with ordered and renumbered markers.
    """
    markers = entry.get("markers", [])
    
    # Normalize marker names (replace dashes with underscores for head/lick markers)
    for marker in markers:
        marker["name"] = normalize_marker_name(marker.get("name", ""))
    
    # Separate regular markers, head markers, and lick markers
    regular_markers = []
    head_markers = []
    lick_markers = []
    
    for marker in markers:
        marker_name = marker.get("name", "")
        if is_head_marker(marker_name):
            head_markers.append(marker)
        elif is_lick_marker(marker_name):
            lick_markers.append(marker)
        else:
            regular_markers.append(marker)
    
    # Sort regular markers by position (ascending)
    sorted_regular = sorted(regular_markers, key=lambda m: m.get("position", 0.0))
    
    # Define the order for head markers
    head_marker_order = (HEAD_IN_START, HEAD_IN_END, HEAD_OUT_START, HEAD_OUT_END)
    
    # Create a mapping from marker name to order index
    order_map = {name: idx for idx, name in enumerate(head_marker_order)}
    
    # Sort head markers by their position in the defined order
    sorted_head = sorted(
        head_markers,
        key=lambda m: order_map.get(m.get("name", ""), len(head_marker_order)),
    )
    
    # Sort lick markers: by lick number ascending, then START before END
    def lick_sort_key(marker: dict) -> tuple[int, int]:
        """Sort key for lick markers: (lick_number, phase_order).
        
        phase_order: 0 for START, 1 for END
        """
        parsed = parse_lick_marker(marker.get("name", ""))
        if parsed:
            lick_number, phase = parsed
            phase_order = 0 if phase == "START" else 1
            return (lick_number, phase_order)
        # Fallback: should not happen if is_lick_marker was used correctly
        return (999999, 1)
    
    sorted_lick = sorted(lick_markers, key=lick_sort_key)
    
    # Combine: regular markers first, then head markers, then lick markers
    sorted_markers = sorted_regular + sorted_head + sorted_lick
    
    # Renumber markers sequentially starting from 1
    for i, marker in enumerate(sorted_markers, start=1):
        marker["number"] = i
    
    # Create new entry with ordered markers
    ordered_entry = entry.copy()
    ordered_entry["markers"] = sorted_markers
    ordered_entry["count"] = len(sorted_markers)
    
    return ordered_entry


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
    # Example with spaces (quoted): MARKER 1 0.17 "head in start" 8 0 1 B {4B33297A-385B-D84C-8CD4-EB377E55CE19} 0
    # Marker names with spaces may be quoted in RPP files
    # Match quoted names first, then unquoted names
    pattern_quoted = (
        r'MARKER\s+(\d+)\s+([\d.]+)\s+"([^"]+)"\s+(\d+)\s+(\d+)\s+(\d+)\s+'
        r'([A-Z])\s+(\{[A-F0-9-]+\})\s+(\d+)'
    )
    pattern_unquoted = (
        r'MARKER\s+(\d+)\s+([\d.]+)\s+([^\s]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+'
        r'([A-Z])\s+(\{[A-F0-9-]+\})\s+(\d+)'
    )
    marker_pattern_quoted = re.compile(pattern_quoted)
    marker_pattern_unquoted = re.compile(pattern_unquoted)

    markers = []
    # Track positions we've already matched to avoid duplicates
    matched_positions = set()
    
    # First, try to match quoted marker names
    for match in marker_pattern_quoted.finditer(content):
        pos = match.start()
        matched_positions.add(pos)
        raw_name = match.group(3)
        markers.append({
            "name": raw_name,
            "position": float(match.group(2)),
            "number": int(match.group(1)),
            "color": int(match.group(4)),
            "flags": int(match.group(5)),
            "locked": int(match.group(6)),
            "guid": match.group(8),  # GUID is group 8 (after guid_char)
        })
    
    # Then, match unquoted marker names (excluding already matched)
    for match in marker_pattern_unquoted.finditer(content):
        pos = match.start()
        if pos not in matched_positions:
            raw_name = match.group(3)
            markers.append({
                "name": raw_name,
                "position": float(match.group(2)),
                "number": int(match.group(1)),
                "color": int(match.group(4)),
                "flags": int(match.group(5)),
                "locked": int(match.group(6)),
                "guid": match.group(8),  # GUID is group 8 (after guid_char)
            })

    # Sort markers by number (for initial parsing)
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
    
    output_file = AUDIO_MARKERS_DIR / f"{stem}.json"
    
    # Generate timestamp
    timestamp = datetime.now().isoformat()
    rpp_file_path = str(rpp_file.resolve())

    # Order markers by position and renumber sequentially
    ordered_entry = _order_markers_in_entry({
        "timestamp": timestamp,
        "count": len(markers),
        "markers": markers_sorted,
    })

    # Build flat output and always overwrite
    marker_lines = []
    for marker in ordered_entry["markers"]:
        marker_json = json.dumps(marker, separators=(",", ":"))
        marker_lines.append(f"    {marker_json}")

    json_output = "{\n"
    json_output += f'  "rpp_file": {json.dumps(rpp_file_path)},\n'
    json_output += f'  "timestamp": {json.dumps(timestamp)},\n'
    json_output += f'  "count": {ordered_entry["count"]},\n'
    json_output += '  "markers": [\n'
    json_output += ",\n".join(marker_lines)
    json_output += "\n  ]\n"
    json_output += "}"

    output_file.write_text(json_output)

    # Delete the source RPP file after successful write
    try:
        rpp_file.unlink()
    except OSError:
        pass

    return {
        "success": True,
        "markers": ordered_entry["markers"],
        "output_file": str(output_file),
        "count": ordered_entry["count"],
    }


def order_markers_in_file(file_path: Path) -> dict:
    """Order markers in a single JSON file by position and renumber sequentially.

    Reads a marker JSON file (flat format: rpp_file, timestamp, count, markers),
    orders markers by position and renumbers them, then writes the file back.

    Args:
        file_path: Path to the marker JSON file to process.

    Returns:
        Dictionary with success status, file path, and counts.

    Raises:
        FileNotFoundError: If file_path doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Marker file not found: {file_path}")

    try:
        data = json.loads(file_path.read_text())
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos)

    # Support flat format; migrate legacy entries format by using first entry
    if "markers" in data:
        markers = data["markers"]
    elif "entries" in data and data["entries"]:
        markers = data["entries"][0].get("markers", [])
    else:
        return {
            "success": True,
            "file": str(file_path),
            "entries_processed": 0,
            "total_markers": 0,
            "message": "No markers found in file",
        }

    entry = {"timestamp": data.get("timestamp", ""), "count": len(markers), "markers": markers}
    ordered_entry = _order_markers_in_entry(entry)

    marker_lines = []
    for marker in ordered_entry["markers"]:
        marker_json = json.dumps(marker, separators=(",", ":"))
        marker_lines.append(f"    {marker_json}")

    json_output = "{\n"
    json_output += f'  "rpp_file": {json.dumps(data["rpp_file"])},\n'
    json_output += f'  "timestamp": {json.dumps(ordered_entry["timestamp"])},\n'
    json_output += f'  "count": {ordered_entry["count"]},\n'
    json_output += '  "markers": [\n'
    json_output += ",\n".join(marker_lines)
    json_output += "\n  ]\n"
    json_output += "}"

    file_path.write_text(json_output)

    return {
        "success": True,
        "file": str(file_path),
        "entries_processed": 1,
        "total_markers": ordered_entry["count"],
    }


def order_all_marker_files() -> dict:
    """Order markers in all JSON files in the audio-markers directory.
    
    Finds all *_markers.json files in AUDIO_MARKERS_DIR, processes each file
    to order markers by position and renumber them sequentially.
    
    Returns:
        Dictionary with success status and processing results for all files.
    """
    # Find all marker JSON files
    marker_files = sorted([
        f for f in AUDIO_MARKERS_DIR.glob("*_markers.json")
        if f.is_file()
    ])
    
    if not marker_files:
        return {
            "success": True,
            "processed": 0,
            "files": [],
            "message": "No marker files found in audio-markers directory",
        }
    
    results = []
    for marker_file in marker_files:
        try:
            result = order_markers_in_file(marker_file)
            results.append({
                "file": result["file"],
                "entries_processed": result["entries_processed"],
                "total_markers": result.get("total_markers", 0),
                "success": True,
            })
        except Exception as e:
            results.append({
                "file": str(marker_file),
                "success": False,
                "error": str(e),
            })
    
    return {
        "success": True,
        "processed": len(marker_files),
        "files": results,
    }


def read_all_markers() -> dict:
    """Read marker data from all RPP files in the markers directory.

    Searches reaper/markers for *.RPP files, extracts markers from each,
    and writes JSON output files to data/annotations/audio-markers (overwrites
    existing files with current markers).

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
