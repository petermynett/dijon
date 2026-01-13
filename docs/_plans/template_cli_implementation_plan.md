# Template CLI Implementation Plan

## Overview
Write a template-first CLI implementation guide and provide a real working example module (CLI + pipeline) that demonstrates the safe acquire→ingest→load flow while respecting documented architecture and data contracts.

## Todos
- `doc-cli-index`: Create a short, authoritative entrypoint at `template/docs/cli_implementation.md` (architecture + invariants + task router + global checklist).
- `doc-cli-task-add-source`: Create `template/docs/cli_tasks/add_data_source.md` playbook (source registration points, required modules/files, naming, minimal test matrix, done-when checklist).
- `doc-cli-task-add-cross-source-action`: Create `template/docs/cli_tasks/add_action_across_sources.md` playbook (registry/interface pattern, default behavior if a source doesn’t support it, compatibility guidance, policy table, template-evolution/compat checklist).
- `example-pipeline-verbs`: Implement `template/src/{{ package_name }}/pipeline/example/{acquire,ingest,load}.py` as a safe acquire→ingest→load reference using `sources/_manifest.py` and respecting DATA.md.
- `example-cli-module`: Implement `template/src/{{ package_name }}/cli/commands/example.py` as thin Typer wrappers calling pipeline verbs; use `cli/base.py` helpers and `--dry-run` where appropriate.
- `wire-example-cli`: Register the example Typer app in `template/src/{{ package_name }}/cli/main.py` so `tree` shows it.
- `doc-migrate-cli-rules-into-docs`: Fold guidance from soon-to-be-deleted template CLI rules into the new docs; keep `200-cli-implementation.mdc` as the “how to use CLI” guardrail.

## Goals
- Produce a template-first, copy/paste-friendly CLI doc set:
  - Entry point: `template/docs/cli_implementation.md` (short + authoritative)
  - Task playbooks: `template/docs/cli_tasks/*` (procedures)
- Provide a concrete, working example implementation (no placeholders) using the existing CLI framework.

## Authority & Scope
- Follow hierarchy: README → ARCHITECTURE → DATA → AGENTS.
- CLI stays thin; pipeline orchestrates verbs; sources are adapters.
- Respect immutability + manifest rules; avoid destructive/reset behaviors by default.

## Key Decisions
- **Call chain:** CLI → pipeline → sources.
- **Source registry:** scan `template/src/{{ package_name }}/sources/`.
  - Ignore `_manifest.py`, `__pycache__/`, underscore-prefixed entries.
  - Eligibility: exports `SOURCE_KEY: str` and either `SOURCE` or `get_source()`.
  - `SOURCE_KEY` and `DATASET_CODE` live together; both stable once used; not derived at runtime.
  - Deterministic ordering (sorted by `SOURCE_KEY`); never derive registry from `data/`.
- **Fresh-clone / no-data policy:**
  - Supported sources = code-discovered via export contract (even if `data/` is empty).
  - Enumeration lists code-defined sources regardless of `data/`.
  - Data commands must not treat missing `data/` as “no sources”; they either scaffold minimal dirs/manifests safely or fail fast with clear init messaging. Default: scaffold acquisition/raw/overrides dirs and manifest header; never delete/reset.
  - Registry is never derived from `data/`; `data/` may be an optional filter only.
- **Cross-source action policy (to document in playbook + index summary):**
  - Selection: default all eligible sources; support `--only`; define `--from-data` as future hook.
  - Unsupported source: default skip + warn (document choice).
  - Partial failures: non-zero exit if any source fails; per-source summary.
  - Idempotency: required; define “safe re-run” (no duplicate writes; canonical immutability upheld).
  - Ordering: stable, sorted by `SOURCE_KEY`.
- **Template evolution safety:** when adding new CLI actions, also update router, playbook touch list, tests, and changelog/migration note (e.g., `docs/template_updates.md`); include compat notes on what breaks generated repos and what doesn’t.

## What to Implement
1) Docs structure: stable index + playbooks (add data source; add action across sources; router links to future tasks).
2) Example CLI module: acquire/ingest/load commands wrapping pipeline verbs with `cli/base.py` helpers and safe flags.
3) Example pipeline verbs: acquire (only acquisition), ingest (mint file_id, write raw + manifest), load (resolve effective raw, validate; no canonical writes).
4) Wire example into `cli/main.py`.
5) Docs content: architecture/invariants, task router, global checklist, playbook procedures, cross-source policy table, template-evolution safety/compat notes; fold content from deprecated template CLI rules; keep `200-cli-implementation.mdc` as usage guardrail.

