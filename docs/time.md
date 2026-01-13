# Time Handling

This document provides implementation guidance for adding time fields to data files (raw files, manifests, normalized layers). For the canonical time contract, see Rule 050.

**Reference hierarchy:**
- **Rule 050**: Usage contract (what must be true)
- **This doc**: Implementation guidance (how to add time fields)
- **`src/<pkg>/utils/time.py`**: Utility functions (use these)

## Goals

- Every instant is stored canonically as RFC 3339 UTC with trailing `Z`, seconds-only.
- Local times are treated as input/display only and are never persisted as authoritative.
- DST ambiguity is never guessed.

## Canonical Formats

### Instants (canonical)
- Format: `YYYY-MM-DDTHH:MM:SSZ` (exactly 20 characters)
- Example: `2025-12-25T18:03:12Z`
- No fractional seconds, no `+00:00` suffix

### Civil dates
- Format: `YYYY-MM-DD` (exactly 10 characters)
- These are not instants and must not be UTC-shifted
- Interpreted in `tz_event` (or `DEFAULT_TZ_EVENT` if missing)

## Field Semantics

When adding time fields to data files, use these standard field names:

### Required Fields

**`ts_utc`** (required for instants)
- Canonical UTC instant string: `YYYY-MM-DDTHH:MM:SSZ`
- Always use `format_ts_utc_z()` or `now_ts_utc_z()` to generate
- Never store naive times, offsets, or `+00:00` format

### Optional Fields

**`tz_event`** (recommended)
- IANA timezone identifier (e.g., `America/Vancouver`)
- Never use `PST/PDT` or fixed offsets as zones
- Required for interpreting civil dates
- If missing, defaults to `DEFAULT_TZ_EVENT` for civil date interpretation

**`tz_offset_minutes`** (optional metadata)
- Integer offset in minutes (e.g., `-420` for `-07:00`)
- Only include if source explicitly provided an offset
- Never infer or recompute offsets
- This is metadata, not authority (`ts_utc` is canonical)

**`ts_src`** (optional provenance)
- Verbatim timestamp string from source (diagnostic only)
- Never use `ts_src` for computation
- Useful for debugging and audit trails

### Forbidden Fields

**`ts_local`** (never persist)
- Must not be stored in data files, manifests, or databases
- May exist only in queries, views, or UI output
- Always derive from `ts_utc` + `tz_event` at display time using `format_ts_for_display()`

## Implementation Patterns

### Ingest Layer (Normalization)

During ingest (acquisition → raw), normalize all timestamps:

```python
from src.<pkg>.utils.time import normalize_instant, DEFAULT_TZ_EVENT

def ingest_record(source_data: dict) -> dict:
    """Normalize timestamp during ingest."""
    raw_ts = source_data.get("timestamp")  # Raw string from source
    
    # Normalize using utility function
    ts_utc, tz_event, tz_source, tz_offset_minutes, ts_src = normalize_instant(
        raw=raw_ts,
        tz_event=source_data.get("timezone"),  # IANA zone if known, else None
        tz_source="source" if source_data.get("timezone") else "assumed",
        tz_assumed=DEFAULT_TZ_EVENT,
        datasource="my_datasource",
        field="timestamp"
    )
    
    return {
        "ts_utc": ts_utc,  # Canonical: YYYY-MM-DDTHH:MM:SSZ
        "tz_event": tz_event,  # IANA zone
        "tz_offset_minutes": tz_offset_minutes,  # Only if source provided
        "ts_src": ts_src,  # Original for provenance
        # ... other fields
    }
```

**Key points:**
- Use `normalize_instant()` for all timestamp normalization
- Always provide `datasource` and `field` parameters for error messages
- Handle DST errors explicitly (see below)

### Load Layer (Validation Only)

During load (raw → database), validate format but do not normalize:

```python
from src.<pkg>.utils.time import assert_ts_utc_z, assert_civil_date, assert_iana_zone

def load_record(raw_data: dict) -> dict:
    """Validate timestamp format during load."""
    # Validate canonical format
    assert_ts_utc_z(raw_data["ts_utc"])
    
    # Validate optional fields if present
    if "tz_event" in raw_data:
        assert_iana_zone(raw_data["tz_event"])
    
    if "start_date" in raw_data:
        assert_civil_date(raw_data["start_date"])
    
    # Insert into database (no normalization)
    return raw_data
```

**Key points:**
- Use `assert_ts_utc_z()` to validate canonical format
- Use `assert_iana_zone()` for timezone validation
- Use `assert_civil_date()` for date-only fields
- Never normalize or convert timezones in load layer

### Current Timestamps

For metadata timestamps (e.g., `ingested_at`, `created_at`):

```python
from src.<pkg>.utils.time import now_ts_utc_z

manifest_row = {
    "file_id": "SRC-2512-001",
    "ingested_at": now_ts_utc_z(),  # Current UTC time
    # ... other fields
}
```

## DST Edge Cases

When converting naive local times to UTC, DST ambiguity must be handled explicitly:

### Ambiguous Time (DST Fall-Back)

Occurs when clocks "fall back" and the same local time occurs twice:

```python
from src.<pkg>.utils.time import local_naive_to_utc, AmbiguousLocalTimeError
from datetime import datetime

try:
    # Naive datetime in ambiguous hour
    naive_dt = datetime(2025, 11, 2, 1, 30, 0)  # 1:30 AM on DST fall-back day
    utc_dt = local_naive_to_utc(
        naive_dt,
        tz="America/Vancouver",
        datasource="my_source",
        field="event_time"
    )
except AmbiguousLocalTimeError as e:
    # Must handle explicitly - cannot guess
    # Error message: "Ambiguous local time: 2025-11-02T01:30:00 in America/Vancouver (datasource=my_source, field=event_time)"
    raise ValueError("Cannot process ambiguous time - source must provide offset") from e
```

### Non-Existent Time (DST Spring-Forward)

Occurs when clocks "spring forward" and skip an hour:

```python
from src.<pkg>.utils.time import local_naive_to_utc, NonexistentLocalTimeError

try:
    # Naive datetime in non-existent hour
    naive_dt = datetime(2025, 3, 9, 2, 30, 0)  # 2:30 AM on DST spring-forward day
    utc_dt = local_naive_to_utc(
        naive_dt,
        tz="America/Vancouver",
        datasource="my_source",
        field="event_time"
    )
except NonexistentLocalTimeError as e:
    # Must handle explicitly - cannot invent time
    # Error message: "Nonexistent local time: 2025-03-09T02:30:00 in America/Vancouver (datasource=my_source, field=event_time)"
    raise ValueError("Time does not exist - source data may be invalid") from e
```

**Key points:**
- Never silently guess or fold ambiguous/non-existent times
- Always catch and handle DST errors explicitly
- Provide `datasource` and `field` parameters for clear error messages

## Civil Date Handling

Civil dates (`YYYY-MM-DD`) are not instants and must not be UTC-shifted:

```python
from src.<pkg>.utils.time import assert_civil_date, DEFAULT_TZ_EVENT

# Validate format
assert_civil_date("2025-12-25")  # OK
assert_civil_date("2025-12-25T18:03:12Z")  # Raises ValueError

# Interpretation: civil dates are interpreted in tz_event (or DEFAULT_TZ_EVENT)
record = {
    "start_date": "2025-12-25",  # Civil date
    "tz_event": "America/Vancouver",  # Interpret start_date in this zone
    # If tz_event missing, interpret in DEFAULT_TZ_EVENT
}
```

**Key points:**
- Never convert civil dates to UTC or shift them
- Interpret civil dates in `tz_event` when present
- Use `DEFAULT_TZ_EVENT` if `tz_event` is missing

## Display (Never Persist)

For displaying timestamps to users, derive local time from `ts_utc`:

```python
from src.<pkg>.utils.time import format_ts_for_display, DEFAULT_TZ_EVENT

# Display UTC timestamp in local timezone
ts_utc = "2025-12-25T18:03:12Z"
display_str = format_ts_for_display(ts_utc, tz=DEFAULT_TZ_EVENT)
# Returns: "2025-12-25 10:03:12" (local time, for display only)

# Never persist display_str - always derive from ts_utc
```

## Default Timezone

**`DEFAULT_TZ_EVENT`** is defined in `src/<pkg>/utils/time.py` (currently `America/Vancouver`).

- Used only when source does not provide a zone for civil-date interpretation
- Used as default display zone
- Treat changes as breaking (document in release notes)

## Complete Example: Adding Time Fields to a New Dataset

```python
from src.<pkg>.utils.time import (
    normalize_instant,
    assert_ts_utc_z,
    assert_civil_date,
    assert_iana_zone,
    now_ts_utc_z,
    DEFAULT_TZ_EVENT,
    AmbiguousLocalTimeError,
    NonexistentLocalTimeError,
)

def ingest_my_dataset(source_record: dict) -> dict:
    """Ingest example showing complete time field handling."""
    # 1. Normalize event timestamp
    raw_ts = source_record.get("event_time")
    ts_utc, tz_event, _, tz_offset_minutes, ts_src = normalize_instant(
        raw=raw_ts,
        tz_event=source_record.get("timezone"),  # IANA zone if known
        tz_source="source" if source_record.get("timezone") else "assumed",
        tz_assumed=DEFAULT_TZ_EVENT,
        datasource="my_dataset",
        field="event_time"
    )
    
    # 2. Handle civil date (if present)
    start_date = source_record.get("start_date")  # YYYY-MM-DD
    # No normalization needed - civil dates stay as-is
    
    # 3. Add metadata timestamp
    ingested_at = now_ts_utc_z()
    
    return {
        "ts_utc": ts_utc,  # Required: canonical UTC instant
        "tz_event": tz_event,  # Recommended: IANA zone
        "tz_offset_minutes": tz_offset_minutes,  # Optional: only if source provided
        "ts_src": ts_src,  # Optional: provenance
        "start_date": start_date,  # Civil date (no UTC conversion)
        "ingested_at": ingested_at,  # Metadata timestamp
    }

def load_my_dataset(raw_record: dict) -> dict:
    """Load example showing validation only."""
    # Validate canonical format
    assert_ts_utc_z(raw_record["ts_utc"])
    
    # Validate optional fields
    if "tz_event" in raw_record:
        assert_iana_zone(raw_record["tz_event"])
    
    if "start_date" in raw_record:
        assert_civil_date(raw_record["start_date"])
    
    # Insert into database (no normalization)
    return raw_record
```

## Do's and Don'ts

### ✅ Do

- Use `format_ts_utc_z()` or `now_ts_utc_z()` for all canonical timestamps
- Use `normalize_instant()` during ingest for all timestamp normalization
- Use `assert_ts_utc_z()` during load for validation
- Store `tz_event` as IANA zones (`America/Vancouver`, not `PST`)
- Handle DST errors explicitly with try/except
- Include `datasource` and `field` parameters in DST error calls
- Derive `ts_local` at display time only, never persist it

### ❌ Don't

- Never store naive times or times without `Z` suffix
- Never use `PST/PDT` or fixed offsets as timezone identifiers
- Never persist `ts_local` in data files
- Never normalize or convert timezones in load layer
- Never silently guess or fold ambiguous/non-existent DST times
- Never convert civil dates to UTC or shift them
- Never use `ts_src` for computation (diagnostic only)

## Utility Functions Reference

All time utilities are in `src/<pkg>/utils/time.py`:

**Formatting:**
- `now_ts_utc_z()` - Current UTC time as canonical string
- `format_ts_utc_z(dt)` - Format datetime to canonical string
- `format_ts_for_display(ts_utc, tz)` - Display-only formatting (never persist)

**Parsing:**
- `parse_ts_utc(s)` - Parse canonical string to UTC datetime
- `normalize_instant(...)` - Normalize raw timestamps during ingest

**Validation (load layer):**
- `assert_ts_utc_z(s)` - Validate canonical format
- `assert_civil_date(s)` - Validate date format
- `assert_iana_zone(s)` - Validate IANA timezone

**DST handling:**
- `local_naive_to_utc(naive_dt, tz, *, datasource, field)` - Convert with DST checks
- `AmbiguousLocalTimeError` - Raised for ambiguous times
- `NonexistentLocalTimeError` - Raised for non-existent times

**Constants:**
- `DEFAULT_TZ_EVENT` - Default timezone (`America/Vancouver`)

## See Also

- **Rule 050**: Canonical time contract (usage rules)
- **Rule 420**: Ingest Contract (uses time utilities for manifest timestamps)
- **Rule 430**: Load Contract (uses time validation utilities)