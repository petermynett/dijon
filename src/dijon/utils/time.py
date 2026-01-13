"""Canonical time and date utilities.

This module provides a single source of truth for all time/date operations:
- Canonical instant strings: YYYY-MM-DDTHH:MM:SSZ (seconds-only, UTC)
- Civil date helpers (YYYY-MM-DD interpreted in declared zones)
- DST-safe naive timestamp conversion with explicit error handling
- Validation helpers for load-layer safety gates

All timestamps at rest (raw files, manifests, DB) must be strings in ...Z format.
Internal operations may use tz-aware datetime objects, but boundaries serialize to strings.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

# Default timezone for assumed zones, civil date calculations, and display
DEFAULT_TZ_EVENT = "America/Vancouver"

# Canonical ts_utc format: exactly 20 characters, YYYY-MM-DDTHH:MM:SSZ
TS_UTC_LENGTH = 20
TS_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class AmbiguousLocalTimeError(ValueError):
    """Raised when a naive local time is ambiguous due to DST fall-back.

    This occurs when a clock "falls back" and the same local time occurs twice.
    The pipeline must not guess which occurrence was intended.
    """


class NonexistentLocalTimeError(ValueError):
    """Raised when a naive local time does not exist due to DST spring-forward.

    This occurs when clocks "spring forward" and skip an hour.
    The pipeline must not invent a time that never occurred.
    """


def utc_now() -> datetime:
    """Return current UTC time as tz-aware datetime.

    Returns:
        Current UTC datetime with timezone.utc.
    """
    return datetime.now(UTC)


def format_ts_utc_z(dt: datetime, *, timespec: str = "seconds") -> str:
    """Format a datetime as canonical UTC instant string (YYYY-MM-DDTHH:MM:SSZ).

    Converts any aware datetime to UTC before formatting. For naive datetimes,
    raises ValueError (caller must provide timezone context).

    Args:
        dt: Datetime to format. Must be timezone-aware. If not UTC, converts to UTC.
        timespec: Precision specifier. Must be "seconds" for canonical format.

    Returns:
        Canonical instant string: YYYY-MM-DDTHH:MM:SSZ (exactly 20 characters).

    Raises:
        ValueError: If dt is naive (no timezone) or timespec is not "seconds".
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"Cannot format naive datetime {dt}. "
            "Provide timezone context or use local_naive_to_utc() first."
        )

    if timespec != "seconds":
        raise ValueError(
            f"Canonical format requires timespec='seconds', got {timespec}"
        )

    # Convert to UTC if not already
    if dt.tzinfo != UTC:
        dt = dt.astimezone(UTC)

    # Format as YYYY-MM-DDTHH:MM:SSZ (isoformat with Z suffix, no microseconds)
    iso_str = dt.isoformat(timespec="seconds")
    # Replace +00:00 with Z, or ensure Z suffix
    if iso_str.endswith("+00:00"):
        return iso_str[:-6] + "Z"
    if iso_str.endswith("Z"):
        return iso_str
    # Should not happen for UTC, but handle gracefully
    return iso_str + "Z"


def now_ts_utc_z(*, timespec: str = "seconds") -> str:
    """Return current UTC time as canonical instant string.

    Args:
        timespec: Must be "seconds" for canonical format.

    Returns:
        Canonical instant string: YYYY-MM-DDTHH:MM:SSZ.
    """
    return format_ts_utc_z(utc_now(), timespec=timespec)


def parse_ts_utc(s: str) -> datetime:
    """Parse a canonical UTC instant string to tz-aware UTC datetime.

    Accepts both ...Z and ...+00:00 formats, but normalizes to UTC-aware datetime.

    Args:
        s: Timestamp string in RFC3339 UTC format (YYYY-MM-DDTHH:MM:SSZ or
            YYYY-MM-DDTHH:MM:SS+00:00).

    Returns:
        Tz-aware UTC datetime object.

    Raises:
        ValueError: If string format is invalid or not UTC.
    """
    # Try parsing with Z suffix first
    if s.endswith("Z"):
        # Remove Z and parse as UTC
        dt_str = s[:-1]
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                # Naive datetime from isoformat, attach UTC
                return dt.replace(tzinfo=UTC)
            # Already aware, ensure UTC
            return dt.astimezone(UTC)
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {s}") from e

    # Try parsing with +00:00 offset
    if s.endswith("+00:00"):
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                raise ValueError(f"Timestamp {s} parsed as naive")
            return dt.astimezone(UTC)
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {s}") from e

    # Try general fromisoformat (may have other offsets)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise ValueError(
                f"Timestamp {s} is naive. Provide UTC timestamp with Z or +00:00."
            )
        # Convert to UTC
        return dt.astimezone(UTC)
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: {s}") from e


def assert_ts_utc_z(s: str) -> None:
    """Used by load layer to reject malformed raw data.

    Args:
        s: String to validate.

    Raises:
        ValueError: If string is not exactly YYYY-MM-DDTHH:MM:SSZ format.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected string, got {type(s).__name__}: {s}")

    # If the string has an explicit offset suffix (e.g., +00:00), raise a clear
    # canonical-format error (even though length would also fail). This matches
    # the intended guidance: must be ...Z.
    if re.search(r"[+-]\d{2}:\d{2}$", s):
        raise ValueError("ts_utc must match YYYY-MM-DDTHH:MM:SSZ")

    if len(s) != TS_UTC_LENGTH:
        raise ValueError(
            f"ts_utc must be exactly {TS_UTC_LENGTH} characters, "
            f"got {len(s)}: {s}"
        )

    if not TS_UTC_PATTERN.match(s):
        raise ValueError("ts_utc must match YYYY-MM-DDTHH:MM:SSZ")


def assert_civil_date(s: str) -> None:
    """Validate that a string is a civil date (YYYY-MM-DD).

    Args:
        s: String to validate.

    Raises:
        ValueError: If string is not YYYY-MM-DD format.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected string, got {type(s).__name__}: {s}")

    if len(s) != 10:
        raise ValueError(
            f"Civil date must be exactly 10 characters (YYYY-MM-DD), got {len(s)}: {s}"
        )

    try:
        date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Invalid civil date format (expected YYYY-MM-DD): {s}") from e


def assert_iana_zone(s: str) -> None:
    """Validate that a string is a valid IANA timezone identifier.

    Args:
        s: String to validate.

    Raises:
        ValueError: If string is not a valid IANA zone.
    """
    if not isinstance(s, str):
        raise ValueError(f"Expected string, got {type(s).__name__}: {s}")

    try:
        ZoneInfo(s)
    except Exception as e:
        raise ValueError(f"Invalid IANA timezone: {s}") from e


def local_naive_to_utc(
    dt_naive: datetime,
    *,
    tz: str,
    datasource: str | None = None,
    field: str | None = None,
) -> datetime:
    """Convert a naive local datetime to UTC, with DST ambiguity checks.

    Interprets the naive datetime in the given IANA zone and converts to UTC.
    Raises explicit errors for DST ambiguous/non-existent times.

    Args:
        dt_naive: Naive datetime (no timezone info).
        tz: IANA timezone identifier (e.g., "America/Vancouver").
        datasource: Optional datasource name for error messages.
        field: Optional field name for error messages.

    Returns:
        Tz-aware UTC datetime.

    Raises:
        AmbiguousLocalTimeError: If local time is ambiguous (DST fall-back).
        NonexistentLocalTimeError: If local time does not exist (DST spring-forward).
        ValueError: If tz is not a valid IANA zone.
    """
    if dt_naive.tzinfo is not None:
        raise ValueError(
            f"Expected naive datetime, got timezone-aware: {dt_naive}"
        )

    try:
        zone = ZoneInfo(tz)
    except Exception as e:
        raise ValueError(f"Invalid IANA timezone: {tz}") from e

    # Check for ambiguous/non-existent time by trying both fold values
    dt_fold0 = dt_naive.replace(tzinfo=zone, fold=0)
    dt_fold1 = dt_naive.replace(tzinfo=zone, fold=1)
    utc_fold0 = dt_fold0.astimezone(UTC)
    utc_fold1 = dt_fold1.astimezone(UTC)

    # Check if converting UTC back to local matches original
    def matches_original(utc_dt: datetime) -> bool:
        """Check if UTC datetime converts back to original naive datetime."""
        dt_back = utc_dt.astimezone(zone)
        dt_back_naive = dt_back.replace(tzinfo=None)
        return (
            dt_back_naive.year == dt_naive.year
            and dt_back_naive.month == dt_naive.month
            and dt_back_naive.day == dt_naive.day
            and dt_back_naive.hour == dt_naive.hour
            and dt_back_naive.minute == dt_naive.minute
            and dt_back_naive.second == dt_naive.second
        )

    matches_fold0 = matches_original(utc_fold0)
    matches_fold1 = matches_original(utc_fold1)

    iso_str = dt_naive.isoformat()
    datasource_str = (
        f"datasource={datasource}" if datasource else "datasource=unknown"
    )
    field_str = f"field={field}" if field else "field=unknown"

    if utc_fold0 != utc_fold1:
        # Different UTC times - could be ambiguous or non-existent
        if matches_fold0 or matches_fold1:
            # At least one fold converts back to original -> ambiguous
            raise AmbiguousLocalTimeError(
                f"Ambiguous local time: {iso_str} in {tz} ({datasource_str}, {field_str})"
            )
        # Neither fold converts back -> non-existent
        raise NonexistentLocalTimeError(
            f"Nonexistent local time: {iso_str} in {tz} ({datasource_str}, {field_str})"
        )

    # Same UTC times - check if it converts back correctly
    if not matches_fold0:
        # Doesn't convert back -> non-existent
        raise NonexistentLocalTimeError(
            f"Nonexistent local time: {iso_str} in {tz} ({datasource_str}, {field_str})"
        )

    # Time is valid, return UTC
    return utc_fold0


def normalize_instant(
    raw: str,
    *,
    tz_event: str | None,
    tz_source: str,
    tz_assumed: str = DEFAULT_TZ_EVENT,
    datasource: str | None = None,
    field: str | None = None,
) -> tuple[str, str, str, int | None, str]:
    """Normalize a raw timestamp string to canonical format with metadata.

    Centralizes ingest policy for timestamp parsing and normalization.
    Handles naive timestamps, offset-bearing timestamps, and already-UTC strings.

    Args:
        raw: Raw timestamp string from source.
        tz_event: IANA zone if known from source, None if unknown/assumed.
        tz_source: One of "source", "assumed", or "unknown".
        tz_assumed: IANA zone to assume if tz_event is None. Defaults to DEFAULT_TZ_EVENT.
        datasource: Optional datasource name for error messages.
        field: Optional field name for error messages.

    Returns:
        Tuple of:
        - ts_utc_str: Canonical UTC instant string (YYYY-MM-DDTHH:MM:SSZ)
        - tz_event_out: IANA zone (from tz_event if provided, else tz_assumed)
        - tz_source_out: Provenance ("source" if tz_event provided, else tz_source)
        - tz_offset_minutes: Offset in minutes if source provided explicit offset, else None
        - ts_src: Original raw string for provenance

    Raises:
        AmbiguousLocalTimeError: If naive timestamp is ambiguous in assumed zone.
        NonexistentLocalTimeError: If naive timestamp does not exist in assumed zone.
        ValueError: If raw string cannot be parsed or tz_source is invalid.
    """
    if tz_source not in ("source", "assumed", "unknown"):
        raise ValueError(
            f"tz_source must be one of 'source', 'assumed', 'unknown', got: {tz_source}"
        )

    ts_src = raw  # Preserve original

    # Try parsing as ISO format first (may have offset)
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            # Has timezone info
            if dt.tzinfo == UTC or dt.tzinfo.utcoffset(dt) == timedelta(0):
                # Already UTC
                ts_utc_str = format_ts_utc_z(dt)
                tz_event_out = tz_event or tz_assumed
                tz_source_out = "source" if tz_event else tz_source
                tz_offset_minutes = None  # UTC, no offset to record
                return ts_utc_str, tz_event_out, tz_source_out, tz_offset_minutes, ts_src

            # Has non-UTC offset
            offset = dt.tzinfo.utcoffset(dt)
            if offset is not None:
                tz_offset_minutes = int(offset.total_seconds() / 60)
            else:
                tz_offset_minutes = None

            # Convert to UTC
            dt_utc = dt.astimezone(UTC)
            ts_utc_str = format_ts_utc_z(dt_utc)

            # tz_event is optional when we only have offset
            tz_event_out = tz_event or tz_assumed
            tz_source_out = "source" if tz_event else tz_source
            return ts_utc_str, tz_event_out, tz_source_out, tz_offset_minutes, ts_src

    except ValueError:
        # Not ISO format, try other patterns or treat as naive
        pass

    # Try parsing as naive datetime (common case)
    # Attempt common formats
    naive_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",  # With microseconds
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    dt_naive = None
    for fmt in naive_formats:
        try:
            dt_naive = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue

    if dt_naive is None:
        raise ValueError(
            f"Cannot parse timestamp: {raw} "
            f"(datasource={datasource or 'unknown'}, field={field or 'unknown'})"
        )

    # Interpret naive datetime in assumed zone
    zone_to_use = tz_event or tz_assumed
    dt_utc = local_naive_to_utc(
        dt_naive, tz=zone_to_use, datasource=datasource, field=field
    )
    ts_utc_str = format_ts_utc_z(dt_utc)

    tz_event_out = zone_to_use
    tz_source_out = tz_source
    tz_offset_minutes = None  # No explicit offset from source

    return ts_utc_str, tz_event_out, tz_source_out, tz_offset_minutes, ts_src


def civil_today(*, tz: str = DEFAULT_TZ_EVENT) -> str:
    """Return today's civil date (YYYY-MM-DD) in the given timezone.

    Args:
        tz: IANA timezone identifier. Defaults to DEFAULT_TZ_EVENT.

    Returns:
        Civil date string: YYYY-MM-DD.
    """
    zone = ZoneInfo(tz)
    now_local = datetime.now(zone)
    return now_local.date().isoformat()


def civil_yesterday(*, tz: str = DEFAULT_TZ_EVENT) -> str:
    """Return yesterday's civil date (YYYY-MM-DD) in the given timezone.

    Args:
        tz: IANA timezone identifier. Defaults to DEFAULT_TZ_EVENT.

    Returns:
        Civil date string: YYYY-MM-DD.
    """
    zone = ZoneInfo(tz)
    now_local = datetime.now(zone)
    yesterday = now_local.date() - timedelta(days=1)
    return yesterday.isoformat()


def format_ts_for_display(
    ts_utc: str | datetime, *, tz: str = DEFAULT_TZ_EVENT
) -> str:
    """Format a UTC timestamp for human-readable display in local timezone.

    This is a view-only operation; never persist the result.

    Args:
        ts_utc: UTC timestamp (string YYYY-MM-DDTHH:MM:SSZ or datetime).
        tz: IANA timezone for display. Defaults to DEFAULT_TZ_EVENT.

    Returns:
        Formatted string in local timezone (for display only).
    """
    if isinstance(ts_utc, str):
        dt_utc = parse_ts_utc(ts_utc)
    else:
        if ts_utc.tzinfo is None:
            raise ValueError("Cannot display naive datetime")
        dt_utc = ts_utc.astimezone(UTC) if ts_utc.tzinfo != UTC else ts_utc

    zone = ZoneInfo(tz)
    dt_local = dt_utc.astimezone(zone)
    return dt_local.isoformat(sep=" ", timespec="seconds")


def parse_date_or_datetime(s: str) -> datetime:
    """Parse a string that may be either a date (YYYY-MM-DD) or datetime (YYYY-MM-DDTHH:MM:SSZ).

    For date-only strings, interprets as midnight UTC on that date.
    For datetime strings, parses as UTC timestamp.

    Args:
        s: String in either YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format.

    Returns:
        Tz-aware UTC datetime object.

    Raises:
        ValueError: If string format is invalid.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError(f"Expected non-empty string, got: {s}")

    s = s.strip()

    # Try parsing as datetime first (YYYY-MM-DDTHH:MM:SSZ)
    if len(s) == TS_UTC_LENGTH and s.endswith("Z"):
        return parse_ts_utc(s)

    # Try parsing as date (YYYY-MM-DD)
    if len(s) == 10:
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # Naive date, interpret as midnight UTC
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            pass

    # Try general datetime parsing (may have other formats)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # If no timezone, assume UTC
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError as e:
        raise ValueError(
            f"Invalid date/datetime format: {s}. "
            "Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
        ) from e


def compare_date_or_datetime(date1: str, date2: str) -> int:
    """Compare two date/datetime strings.

    Args:
        date1: First date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ).
        date2: Second date/datetime string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ).

    Returns:
        -1 if date1 < date2, 0 if date1 == date2, 1 if date1 > date2.

    Raises:
        ValueError: If either string format is invalid.
    """
    dt1 = parse_date_or_datetime(date1)
    dt2 = parse_date_or_datetime(date2)

    if dt1 < dt2:
        return -1
    if dt1 > dt2:
        return 1
    return 0

