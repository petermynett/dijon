"""Resolve audio regions from Reaper marker JSONs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import librosa

from ..global_config import AUDIO_MARKERS_DIR


def _validate_markers(markers: list, marker_path: Path) -> None:
    """Validate marker structure; raise ValueError with clear message on bad entries."""
    for i, m in enumerate(markers):
        if not isinstance(m, dict):
            raise ValueError(
                f"Marker entry {i} in {marker_path} is not a dict: {type(m).__name__}"
            )
        if "name" not in m or "position" not in m:
            missing = [k for k in ("name", "position") if k not in m]
            raise ValueError(
                f"Marker entry {i} in {marker_path} missing required keys: {missing}"
            )
        pos = m["position"]
        if not isinstance(pos, (int, float)):
            raise ValueError(
                f"Marker entry {i} in {marker_path} has invalid position type: "
                f"{type(pos).__name__} (expected int or float)"
            )


def resolve_audio_region(
    audio_path: Path,
    *,
    start_marker: str | None = None,
    end_marker: str | None = None,
) -> tuple[float, float]:
    """Resolve (start_sec, end_sec) from marker JSON and audio duration.

    Marker file: AUDIO_MARKERS_DIR / f"{track_name}_markers.json" where
    track_name = audio_path.stem.

    Raises:
        FileNotFoundError: Marker file missing.
        ValueError: Zero markers, marker not found, or bounds invalid.
    """
    start_sec, end_sec, _, _ = resolve_audio_region_with_names(
        audio_path,
        start_marker=start_marker,
        end_marker=end_marker,
    )
    return (start_sec, end_sec)


def resolve_audio_region_with_names(
    audio_path: Path,
    *,
    start_marker: str | None = None,
    end_marker: str | None = None,
) -> tuple[float, float, str, str]:
    """Resolve region and marker names as (start_sec, end_sec, start_name, end_name)."""
    track_name = audio_path.stem
    marker_path = AUDIO_MARKERS_DIR / f"{track_name}_markers.json"

    if not marker_path.exists():
        raise FileNotFoundError(f"Marker file not found: {marker_path}")

    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    markers = data.get("markers", [])
    if not markers:
        raise ValueError(f"Marker file has zero markers: {marker_path}")

    _validate_markers(markers, marker_path)

    # Sort by position for deterministic "first match" behavior
    markers_sorted = sorted(markers, key=lambda m: m["position"])

    start_sec, start_name = _resolve_marker_time_with_name(
        markers_sorted,
        query=start_marker,
        fallback_earliest=start_marker is None,
        fallback_end_exact=False,
    )
    end_sec, end_name = _resolve_marker_time_with_name(
        markers_sorted,
        query=end_marker,
        fallback_earliest=False,
        fallback_end_exact=end_marker is None,
    )

    duration = librosa.get_duration(path=str(audio_path))
    if not (0 <= start_sec < end_sec <= duration):
        raise ValueError(
            f"Invalid region: start={start_sec}, end={end_sec}, duration={duration}; "
            "expected 0 <= start < end <= duration"
        )

    return (start_sec, end_sec, start_name, end_name)


def _resolve_marker_time(
    markers: list[dict],
    *,
    query: str | None,
    fallback_earliest: bool,
    fallback_end_exact: bool,
) -> float:
    """Resolve a single marker time from sorted markers list."""
    if fallback_earliest:
        return markers[0]["position"]

    if fallback_end_exact:
        # end_marker is None: exact match "END" only
        for m in markers:
            if m["name"].lower() == "end":
                return m["position"]
        raise ValueError('No marker named "END" (case-insensitive) found')

    assert query is not None
    matches = _find_matching_markers(markers, query)
    if not matches:
        raise ValueError(f'No marker matching "{query}" found')
    return matches[0]["position"]


def _resolve_marker_time_with_name(
    markers: list[dict],
    *,
    query: str | None,
    fallback_earliest: bool,
    fallback_end_exact: bool,
) -> tuple[float, str]:
    """Resolve a single marker as (position, name) from sorted markers list."""
    if fallback_earliest:
        marker = markers[0]
        return (marker["position"], marker["name"])

    if fallback_end_exact:
        # end_marker is None: exact match "END" only
        for marker in markers:
            if marker["name"].lower() == "end":
                return (marker["position"], marker["name"])
        raise ValueError('No marker named "END" (case-insensitive) found')

    assert query is not None
    matches = _find_matching_markers(markers, query)
    if not matches:
        raise ValueError(f'No marker matching "{query}" found')
    marker = matches[0]
    return (marker["position"], marker["name"])


def _find_matching_markers(markers: list[dict], query: str) -> list[dict]:
    """Find markers matching query: exact (case-insensitive) first, else prefix with boundary."""
    exact = []
    prefix = []
    pattern = r"^" + re.escape(query) + r"(?=[^A-Za-z0-9]|$)"
    query_lower = query.lower()

    for m in markers:
        name = m["name"]
        if name.lower() == query_lower:
            exact.append(m)
        elif re.match(pattern, name, re.IGNORECASE):
            prefix.append(m)

    # Exact first, else prefix; already sorted by position
    return exact if exact else prefix
