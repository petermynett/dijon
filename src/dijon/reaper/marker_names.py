"""Canonical marker naming conventions.

This module defines the standard names for head markers and lick markers.
"""

from __future__ import annotations

import re

# Canonical marker names
HEAD_IN_START = "HEAD_IN_START"
HEAD_IN_END = "HEAD_IN_END"
HEAD_OUT_START = "HEAD_OUT_START"
HEAD_OUT_END = "HEAD_OUT_END"

# Lick marker pattern: LICK##-START or LICK##-END where ## is exactly two digits
LICK_MARKER_PATTERN = re.compile(r"^LICK(\d{2})-(START|END)$")


def is_head_marker(name: str) -> bool:
    """Check if a marker name is a head marker.

    Args:
        name: The marker name to check.

    Returns:
        True if the name matches a canonical head marker name,
        False otherwise.
    """
    return name in (HEAD_IN_START, HEAD_IN_END, HEAD_OUT_START, HEAD_OUT_END)


def is_lick_marker(name: str) -> bool:
    """Check if a marker name is a lick marker.

    Args:
        name: The marker name to check.

    Returns:
        True if the name matches the pattern LICK##-START or LICK##-END,
        False otherwise.
    """
    return LICK_MARKER_PATTERN.match(name) is not None


def parse_lick_marker(name: str) -> tuple[int, str] | None:
    """Parse a lick marker name to extract lick number and phase.

    Args:
        name: The marker name to parse.

    Returns:
        A tuple (lick_number, phase) where lick_number is an int and phase
        is either "START" or "END", or None if the name is not a lick marker.
    """
    match = LICK_MARKER_PATTERN.match(name)
    if match:
        lick_number = int(match.group(1))
        phase = match.group(2)
        return (lick_number, phase)
    return None
