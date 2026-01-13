# Adding a New Data Source

This playbook describes how to add a new data source to the CLI system.

## Overview

Adding a data source involves:
1. Creating a source adapter module
2. Registering it via the discovery contract
3. Implementing required pipeline verbs
4. Testing the integration

## Source Registration Points

### Module Location

Create a new directory under `src/{{ package_name }}/sources/<source_name>/`:

```
sources/
  <source_name>/
    __init__.py    # Required: exports discovery symbols
    # Optional: other modules for source-specific logic
```

### Discovery Contract (CRITICAL)

The `sources/<name>/__init__.py` file **must** export:

- `SOURCE_KEY: str` - Stable identifier for this source (e.g., "receipts", "transactions")
- `DATASET_CODE: str` - Dataset code used in file_id generation (e.g., "RCP", "TXN")
- Optional: `CAPABILITIES: dict` - Action support matrix
- Either `SOURCE` (a source instance) or `get_source()` (a factory function)

**Discovery import constraints (LOCKED)**:

- Discovery imports **only** `sources.<name>` (i.e., `sources/<name>/__init__.py`) **or** a dedicated `sources/<name>/meta.py`.
- `__init__.py` (or `meta.py`) **must not import any other internal modules by default**.
- Rationale: prevents "SOURCE_KEY buried in a deeper module" from pulling in heavy code during discovery.

**Side-effect-free imports (LOCKED)**:

- Importing `sources/<name>/__init__.py` **MUST be side-effect-free**:
  - No filesystem writes (including `mkdir()`)
  - No reading secrets/config files (e.g., `read_text()` for config/credentials)
  - No network calls
  - No global config reads with side effects
- Any expensive setup (paths creation, secrets reads, API clients) must occur **only inside** `get_source()` and/or action methods, not at import time.

### Example `__init__.py`

```python
"""Source adapter for <source_name>."""

# Discovery symbols (must be at module level, no I/O)
SOURCE_KEY = "receipts"
DATASET_CODE = "RCP"

# Optional capabilities
CAPABILITIES = {
    "acquire": True,
    "ingest": True,
    "load": True,
}

def get_source():
    """Factory function that returns a configured source instance.
    
    This function may perform I/O (read config, create paths, etc.).
    Called only when the source is actually used, not during discovery.
    """
    from .adapter import ReceiptSource  # Import here, not at module level
    return ReceiptSource()
```

## Required Modules/Files

### Minimum Structure

```
sources/<source_name>/
  __init__.py          # Discovery contract (required)
  adapter.py           # Source adapter implementation (recommended)
```

### Optional Files

- `acquire.py` - Source-specific acquisition logic
- `ingest.py` - Source-specific ingestion logic
- `load.py` - Source-specific load logic
- `README.md` - Source-specific documentation

## Naming Conventions

- **SOURCE_KEY**: lowercase, plural (e.g., "receipts", "transactions")
- **DATASET_CODE**: uppercase, 3-4 characters (e.g., "RCP", "TXN")
- **Directory name**: matches `SOURCE_KEY` (lowercase, plural)
- **Module names**: lowercase, underscore-separated (e.g., `adapter.py`)

## Pipeline Verb Implementation

Each source should implement pipeline verbs as needed:

- **acquire**: Fetch/download upstream data
- **ingest**: Canonicalize and write to raw + manifest
- **load**: Transform raw data into derived formats

See `src/{{ package_name }}/pipeline/example/` for reference implementations.

## Minimal Test Matrix

At minimum, test:

- [ ] Source discovery: `SOURCE_KEY` and `DATASET_CODE` are exported correctly
- [ ] Import safety: importing `__init__.py` is side-effect-free
- [ ] Factory function: `get_source()` returns a valid source instance
- [ ] Pipeline verbs: each implemented verb works end-to-end
- [ ] Idempotency: ingest is idempotent w.r.t. `acq_sha256`

## Done-When Checklist

- [ ] `sources/<name>/__init__.py` exports `SOURCE_KEY`, `DATASET_CODE`, and `get_source()` (or `SOURCE`)
- [ ] `__init__.py` does not import internal modules by default
- [ ] `__init__.py` is side-effect-free (no I/O at import time)
- [ ] `get_source()` performs any expensive setup (paths, config, clients)
- [ ] Source appears in `tree` command output
- [ ] Pipeline verbs are implemented and tested
- [ ] Ingest idempotency is implemented and tested
- [ ] Source-specific documentation is added (if needed)

## Common Pitfalls

1. **Import-time I/O**: Putting `mkdir()` or `read_text()` at module level in `__init__.py`
   - Fix: Move I/O into `get_source()` or action methods

2. **Heavy imports**: Importing large modules or dependencies at module level
   - Fix: Use lazy imports inside `get_source()` or action methods

3. **Missing discovery symbols**: Forgetting to export `SOURCE_KEY` or `DATASET_CODE`
   - Fix: Ensure all required symbols are exported at module level

4. **Non-idempotent ingest**: Creating duplicate manifest entries for the same `acq_sha256`
   - Fix: Check manifest for existing `acq_sha256` before minting new `file_id`

