"""Canonical marker naming conventions.

This module defines the standard names for head markers.
"""

from __future__ import annotations

# Canonical marker names
HEAD_IN_START = "HEAD_IN_START"
HEAD_IN_END = "HEAD_IN_END"
HEAD_OUT_START = "HEAD_OUT_START"
HEAD_OUT_END = "HEAD_OUT_END"


def is_head_marker(name: str) -> bool:
    """Check if a marker name is a head marker.

    Args:
        name: The marker name to check.

    Returns:
        True if the name matches a canonical head marker name,
        False otherwise.
    """
    return name in (HEAD_IN_START, HEAD_IN_END, HEAD_OUT_START, HEAD_OUT_END)
