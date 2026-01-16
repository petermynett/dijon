# src/dijon/sources/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SourceSpec:
    """Specification for a data source.

    Attributes:
        code: Short source code identifier (e.g., "YTB", "IRP", "ABC").
        label: Human-readable label (e.g., "YouTube", "iReal Pro").
        description: Description of the source type.
    """

    code: str
    label: str
    description: str


SOURCES: Final[dict[str, SourceSpec]] = {
    "YTB": SourceSpec(
        code="YTB",
        label="YouTube",
        description="Performance audio acquired from YouTube recordings",
    ),
    "IRP": SourceSpec(
        code="IRP",
        label="iReal Pro",
        description=(
            "Curated play-along lead sheets providing canonical chord changes for tunes"
        ),
    ),
    "ABC": SourceSpec(
        code="ABC",
        label="ABC notation",
        description="Text-based music notation encoding melody, meter, and form",
    ),
}


def validate_source_code(code: str) -> str:
    """Validate and normalize a source code.

    Args:
        code: Source code to validate.

    Returns:
        Normalized uppercase source code.

    Raises:
        ValueError: If code is not registered in SOURCES.
    """
    code = code.strip().upper()
    if code not in SOURCES:
        raise ValueError(
            f"Unknown source code: {code!r}. "
            f"Known sources: {', '.join(sorted(SOURCES))}"
        )
    return code


# Mapping from source name (lowercase) to source code
SOURCE_NAME_TO_CODE: Final[dict[str, str]] = {
    "youtube": "YTB",
    "ireal_pro": "IRP",
    "irealpro": "IRP",
    "abc": "ABC",
    "abc_notation": "ABC",
}


def get_source_code(source_name: str) -> str:
    """Get source code for a given source name.

    Args:
        source_name: Name of the source (e.g., "youtube", "ireal_pro", "abc").

    Returns:
        Source code string (e.g., "YTB", "IRP", "ABC").

    Raises:
        ValueError: If source_name is not registered.
    """
    source_name_lower = source_name.strip().lower()
    code = SOURCE_NAME_TO_CODE.get(source_name_lower)
    if not code:
        raise ValueError(
            f"Unknown source name: {source_name!r}. "
            f"Known source names: {', '.join(sorted(SOURCE_NAME_TO_CODE))}"
        )
    return code
