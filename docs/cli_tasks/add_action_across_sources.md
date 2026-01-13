# Adding a Cross-Source Action

This playbook describes how to add a new CLI action that operates across multiple sources.

## Overview

Cross-source actions are CLI commands that iterate over multiple sources and perform the same operation on each. Examples: `acquire`, `ingest`, `load`, `rebuild`.

## Registry/Interface Pattern

### Source Discovery

Use the source registry to discover eligible sources:

```python
from {{ package_name }}.sources import discover_sources

sources = discover_sources()
# Returns list of SOURCE_KEY values, sorted deterministically
```

### Source Interface

Each source must implement the action method. The interface is defined by the pipeline verb, not by a formal protocol (to keep sources decoupled).

### Action Implementation Pattern

```python
def action_across_sources(only: list[str] | None = None):
    """Perform action across all eligible sources."""
    sources = discover_sources()
    
    if only:
        sources = [s for s in sources if s in only]
    
    if not sources:
        typer.echo("No eligible sources found.")
        return 0  # Exit 0 for "nothing to do"
    
    results = []
    for source_key in sources:
        try:
            source = get_source_by_key(source_key)
            if not hasattr(source, 'action_method'):
                typer.echo(f"⚠ {source_key}: action not supported (skipping)")
                continue  # Skip unsupported sources
            
            result = source.action_method()
            results.append({"source": source_key, "status": "success", "result": result})
        except Exception as e:
            results.append({"source": source_key, "status": "failed", "error": str(e)})
    
    # Determine exit code
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        return 1  # Non-zero exit if any supported source failed
    
    return 0  # Exit 0 if all succeeded or were skipped
```

## Default Behavior for Unsupported Sources

**Policy (LOCKED)**:

- If a source doesn't implement the action (e.g., `hasattr(source, 'action_method')` is False):
  - **Skip** the source
  - **Warn** the user (e.g., `⚠ {source_key}: action not supported (skipping)`)
  - **Do NOT** make the run fail (unsupported is not a failure)

## Exit Code Semantics (LOCKED)

**Policy table**:

| Scenario | Exit Code | Message |
|----------|-----------|---------|
| Unsupported source (doesn't implement action) | 0 | `⚠ {source_key}: action not supported (skipping)` |
| Supported source attempts action and fails | 1 | `✗ {source_key}: {error}` |
| No eligible sources / nothing to do | 0 | `No eligible sources found.` |
| All supported sources succeed | 0 | Summary with success counts |

**Summary**:
- Unsupported source: skip + warn; does NOT make the run fail.
- Any supported source that attempts the action and fails: overall exit code non-zero.
- "No eligible sources / nothing to do": exit 0 with a clear message.

## Compatibility Guidance

### Backward Compatibility

- Existing sources that don't implement a new action should be skipped gracefully.
- New actions should be additive; don't break existing workflows.

### Source Selection

- **Default**: all eligible sources
- **`--only` flag**: restrict to specific sources (e.g., `--only receipts transactions`)
- **Future hook**: `--from-data` (not implemented yet; reserved for future use)

### Ordering

- Sources are processed in deterministic order: sorted by `SOURCE_KEY`.
- This ensures reproducible behavior across runs.

## Policy Table

| Aspect | Policy |
|--------|--------|
| **Selection** | Default: all eligible sources; support `--only` |
| **Unsupported** | Skip + warn; does NOT fail the run |
| **Supported failures** | Non-zero exit; per-source summary |
| **Nothing to do** | Exit 0 + clear message |
| **Ordering** | Stable, sorted by `SOURCE_KEY` |
| **Partial failures** | Non-zero exit if any supported source fails; per-source summary |
| **Idempotency** | Required; define "safe re-run" (no duplicate writes; canonical immutability upheld) |

## Template Evolution Safety

When adding a new cross-source action:

- [ ] Update router in `docs/cli_implementation.md`
- [ ] Update this playbook if patterns change
- [ ] Add tests for exit code semantics
- [ ] Add changelog/migration note (e.g., `docs/template_updates.md`)
- [ ] Include compat notes on what breaks generated repos and what doesn't

## Example: Adding a "rebuild" Action

1. **Define the interface**: Sources implement `rebuild()` method
2. **Implement CLI command**: `rebuild` command that calls `rebuild()` on each source
3. **Handle unsupported**: Skip sources without `rebuild()` method
4. **Exit codes**: Follow the locked policy table above
5. **Document**: Add to router and playbook

## Checklist

- [ ] Action is idempotent (safe to re-run)
- [ ] Unsupported sources are skipped gracefully (not a failure)
- [ ] Exit codes follow the locked policy table
- [ ] Per-source summary is provided
- [ ] Ordering is deterministic (sorted by `SOURCE_KEY`)
- [ ] Tests cover exit code scenarios
- [ ] Documentation is updated

