"""Canonical marker naming conventions.

This module defines the standard names for head markers and lick markers.
"""

from __future__ import annotations

import re

# Canonical marker names (always use underscores)
HEAD_IN_START = "HEAD_IN_START"
HEAD_IN_END = "HEAD_IN_END"
HEAD_OUT_START = "HEAD_OUT_START"
HEAD_OUT_END = "HEAD_OUT_END"

# Lick marker pattern: LICK##_START or LICK##_END where ## is exactly two digits
# Also matches dash variant (LICK##-START) for detection, but canonical is underscore
LICK_MARKER_PATTERN = re.compile(r"^LICK(\d{2})[_-](START|END)$")

# Pattern for head marker variants (with dashes or underscores)
HEAD_MARKER_PATTERN = re.compile(r"^HEAD[_-](IN|OUT)[_-](START|END)$", re.IGNORECASE)


def normalize_marker_name(name: str) -> str:
    """Normalize a head or lick marker name to use underscores instead of dashes.

    Converts marker names like:
    - HEAD-IN-START -> HEAD_IN_START
    - HEAD-OUT-END -> HEAD_OUT_END
    - LICK01-START -> LICK01_START
    - LICK02-END -> LICK02_END

    Non-head/lick markers are returned unchanged.

    Args:
        name: The marker name to normalize.

    Returns:
        The normalized marker name with underscores instead of dashes for
        head and lick markers, or the original name if not a head/lick marker.
    """
    # Check if it's a head marker variant
    head_match = HEAD_MARKER_PATTERN.match(name)
    if head_match:
        in_out = head_match.group(1).upper()
        start_end = head_match.group(2).upper()
        return f"HEAD_{in_out}_{start_end}"

    # Check if it's a lick marker variant (with dash)
    lick_match = LICK_MARKER_PATTERN.match(name)
    if lick_match:
        lick_number = lick_match.group(1)
        phase = lick_match.group(2).upper()
        return f"LICK{lick_number}_{phase}"

    return name


def is_head_marker(name: str) -> bool:
    """Check if a marker name is a head marker.

    Recognizes both canonical (underscore) and dash variants.

    Args:
        name: The marker name to check.

    Returns:
        True if the name matches a head marker pattern,
        False otherwise.
    """
    return HEAD_MARKER_PATTERN.match(name) is not None


def is_lick_marker(name: str) -> bool:
    """Check if a marker name is a lick marker.

    Recognizes both canonical (underscore) and dash variants.

    Args:
        name: The marker name to check.

    Returns:
        True if the name matches the pattern LICK##_START or LICK##_END
        (or dash variant), False otherwise.
    """
    return LICK_MARKER_PATTERN.match(name) is not None


def parse_lick_marker(name: str) -> tuple[int, str] | None:
    """Parse a lick marker name to extract lick number and phase.

    Recognizes both canonical (underscore) and dash variants.

    Args:
        name: The marker name to parse.

    Returns:
        A tuple (lick_number, phase) where lick_number is an int and phase
        is either "START" or "END", or None if the name is not a lick marker.
    """
    match = LICK_MARKER_PATTERN.match(name)
    if match:
        lick_number = int(match.group(1))
        phase = match.group(2).upper()
        return (lick_number, phase)
    return None
