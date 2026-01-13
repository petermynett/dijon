# CLI Implementation Guide

This document is the authoritative entry point for implementing and extending the CLI. It defines architecture, invariants, task routing, and a global checklist.

## Authority & Scope

Follow the document hierarchy: `README.md` → `ARCHITECTURE.md` → `DATA.md` → `AGENTS.md`.

- **CLI stays thin**: parse/dispatch/present only; logic lives in pipeline and sources.
- **Pipeline orchestrates verbs**: acquire, ingest, load, etc.
- **Sources are adapters**: dataset-specific logic only.

## Architecture

### Call Chain

```
CLI → pipeline → sources
```

The CLI layer is a thin wrapper around pipeline verbs. Pipeline verbs coordinate data layer transitions. Sources provide dataset-specific adapters.

### Source Registry

Sources are discovered by scanning `src/{{ package_name }}/sources/`:

- **Ignore**: `_manifest.py`, `__pycache__/`, underscore-prefixed entries.
- **Eligibility**: exports `SOURCE_KEY: str` and either `SOURCE` or `get_source()`.
- **Discovery imports constraint (CRITICAL)**: Registry enumeration imports **only** `sources.<name>` (i.e., `sources/<name>/__init__.py`) **or** a dedicated `sources/<name>/meta.py`.
  - Discovery reads only: `SOURCE_KEY`, `DATASET_CODE`, optional `CAPABILITIES`, and checks for existence of `get_source` (or `SOURCE`) symbol.
  - **No internal imports by default**: `sources/<name>/__init__.py` (or `meta.py`) **must not import any other internal modules by default**.
  - Rationale: prevents "SOURCE_KEY buried in a deeper module" from pulling in heavy code during discovery.
- **Side-effect-free imports (CRITICAL)**: Importing any module used for source discovery **MUST be side-effect-free**:
  - No filesystem writes (including `mkdir()`)
  - No reading secrets/config files
  - No network calls
  - No global config reads with side effects
  - Any expensive setup (paths creation, secrets reads, API clients) must occur **only inside** `get_source()` and/or action methods, not at import time.
- **Deterministic ordering**: sorted by `SOURCE_KEY`; never derive registry from `data/`.
- **Fresh-clone policy**: Supported sources = code-discovered via export contract (even if `data/` is empty). Enumeration lists code-defined sources regardless of `data/`.

## Key Invariants

### Ingest Idempotency

**Idempotency key (locked)**: `acq_sha256` is the primary stable input identity for ingest idempotency.

- Optional: `partition` may be used as an additional discriminator if the dataset uses partitions.
- Optional (diagnostics only): `source_name` or `rel_path` may be logged/emitted for clarity, but does not change the idempotency key.
- **Manifest columns used**: manifest lookup is by `acq_sha256` (and `partition` if used).
- **Status scope**: The "already ingested?" check treats an input as already ingested if a manifest row exists with matching `acq_sha256` and `status` in `{active, superseded}`.
- **Behavior**: If an input identity is already ingested, `ingest` must **NO-OP (preferred)** or **FAIL-FAST** with a clear message; it must **NOT** mint a new `file_id` for the same input.

**No-op definition (locked)**: When `acq_sha256` is already present (per status scope above), ingest must:
- not write a raw file
- not append a manifest row
- exit **0**
- emit a clear message like: `already ingested: <file_id>`

### Cross-Source Action Policy

**Exit code semantics (locked)**:

- **Unsupported source** (doesn't implement the action) ⇒ skip + warn; **does NOT** make the run fail.
- **Any supported source** that attempts the action and fails ⇒ overall **exit code non-zero**.
- **"No eligible sources / nothing to do"** ⇒ **exit 0** with a clear message.

**Selection**:
- Default: all eligible sources
- Support `--only` flag
- Define `--from-data` as future hook

**Ordering**: stable, sorted by `SOURCE_KEY`.

**Partial failures**: non-zero exit if any supported source fails; per-source summary.

**Idempotency**: required; define "safe re-run" (no duplicate writes; canonical immutability upheld).

## Task Router

### Adding a New Data Source

See: [`docs/cli_tasks/add_data_source.md`](cli_tasks/add_data_source.md)

### Adding a Cross-Source Action

See: [`docs/cli_tasks/add_action_across_sources.md`](cli_tasks/add_action_across_sources.md)

## Global Checklist

Before implementing any CLI command or pipeline verb:

- [ ] Consult `ARCHITECTURE.md` for boundary and dependency rules
- [ ] Consult `DATA.md` for data contracts and immutability rules
- [ ] Consult `AGENTS.md` for safety and approval requirements
- [ ] Ensure source discovery imports are side-effect-free
- [ ] Lock idempotency key and behavior for any ingest operations
- [ ] Define exit code semantics for cross-source actions
- [ ] Add `--dry-run` support for mutating operations
- [ ] Update this document if adding new patterns or invariants

## Template Evolution Safety

When adding new CLI actions:

- Update router (this document)
- Update relevant playbook touch list
- Add tests
- Add changelog/migration note (e.g., `docs/template_updates.md`)
- Include compat notes on what breaks generated repos and what doesn't

## Safety Guardrails

This implementation guide is complemented by `.cursor/rules/200-cli-implementation.mdc`, which provides usage guardrails for agents working with the CLI.

Key safety rules (from the guardrail):
- **Entrypoint**: The CLI entrypoint is `src/<pkg>/cli/main.py:main`; do not introduce additional entrypoints without approval.
- **Mutating actions**: Commands that write files, modify data, or touch the database MUST provide `--dry-run` mode and clearly log intent before performing the action.
- **Forbidden without approval**: Do not add CLI commands that perform destructive operations by default, modify schemas/manifests, write to disk without confirmation, make network calls, or install dependencies.
- **Output & exit codes**: Use stdout for normal output, stderr for warnings/errors, exit with non-zero on failure, do not swallow exceptions.
- **Scope control**: Avoid new global options unless required; prefer extending existing commands; consult authoritative docs before major refactors.

For complete guardrail details, see `.cursor/rules/200-cli-implementation.mdc`.

## Reference Implementation

See `src/{{ package_name }}/cli/commands/example.py` and `src/{{ package_name }}/pipeline/example/` for a working reference implementation.

