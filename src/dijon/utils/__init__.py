"""Utility modules.

This package provides shared utilities used across the codebase.
"""

from .time import (
    DEFAULT_TZ_EVENT,
    AmbiguousLocalTimeError,
    NonexistentLocalTimeError,
    assert_civil_date,
    assert_iana_zone,
    assert_ts_utc_z,
    civil_today,
    civil_yesterday,
    compare_date_or_datetime,
    format_ts_for_display,
    format_ts_utc_z,
    local_naive_to_utc,
    normalize_instant,
    now_ts_utc_z,
    parse_date_or_datetime,
    parse_ts_utc,
    utc_now,
)

__all__ = [
    # Time utilities (canonical time handling)
    "DEFAULT_TZ_EVENT",
    "AmbiguousLocalTimeError",
    "NonexistentLocalTimeError",
    "assert_civil_date",
    "assert_iana_zone",
    "assert_ts_utc_z",
    "civil_today",
    "civil_yesterday",
    "compare_date_or_datetime",
    "format_ts_for_display",
    "format_ts_utc_z",
    "local_naive_to_utc",
    "normalize_instant",
    "now_ts_utc_z",
    "parse_date_or_datetime",
    "parse_ts_utc",
    "utc_now",
]

