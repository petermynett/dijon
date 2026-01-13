# <project_name>

This repository is a **Python CLI-first data/pipeline toolkit template** optimized for solo, agent-assisted development.

This README is a **contract and navigation index**, not a tutorial.
It defines what this repository is, how to orient yourself, and which documents are authoritative for specific kinds of decisions.

## Purpose


Project context (agents): see **PROJECT.md**.

## What this repository is

- A scaffold for building deterministic, reproducible data pipelines
- A CLI-first system with explicit boundaries and contracts
- A repo designed to be safely modified by coding agents
- A template: concrete names, datasets, and domains are plugged in later

Primary languages: Python, SQL  
Primary artifact types: CSV, JSON, SQLite, Markdown


## How to read this repo (important)

This project is governed by a small set of **authoritative CAPS files**.
Before making changes, read the relevant one:

- **README.md** (this file)  
  What the project is, how to navigate it, and which doc governs what.

- **ARCHITECTURE.md**  
  System shape, subsystems, boundaries, dependency direction, and extension points.

- **DATA.md**  
  Data contracts: canonical vs derived, immutability, manifests, provenance, deletion rules.

- **AGENTS.md**  
  Safety model and invariants for how changes may be made.

- **AGENTS_CURSOR.md** (if present)  
  Tool- and time-specific commands and workflows. Subordinate to AGENTS.md.

If instructions conflict:
- The most specific and most authoritative document wins.
- AGENTS.md governs safety.
- DATA.md governs data meaning and lifecycle.
- ARCHITECTURE.md governs system shape.


## Repository structure (high level)

This is a summary only. Detailed rules live in the documents above.

- src/  
  Application code (Python, src-layout).

- data/  
  Data workspace. Canonical, derived, and protected upstream data live here.  
  Rules are defined in DATA.md and local READMEs.

- db/  
  Local databases (derived by default).

- src/sql/  
  Authoritative database schema and seed SQL.

- tests/  
  Automated tests.

- docs/  
  Durable documentation (specs, ADRs, notes).

If you are working inside a subdirectory:
- Read that directory’s README.md first.
- Fall back to this file and the CAPS docs.


## Entry points

Primary execution is via the CLI.

Typical patterns (exact names vary by instantiation):
- In-repo: `python -m <package>.cli.main --help`
- Installed entry point: `<cli_name> --help`

CLI usage details belong in procedural docs, not here. Keep the CLI thin (parse/dispatch/present) and put logic in domain modules.

## Environment & install (brief)

- Env: `mamba env create -n template -f env/environment.yml` then `mamba activate dijon`.
- Install protocol: dry-run first (`mamba install -c conda-forge --dry-run ...`), install only if clean.
- Adding any dependencies or new tooling requires explicit approval.
- Always activate the env before running repo commands.

## Quickstart (minimal)

1) `mamba activate dijon`
2) `python -m <package>.cli.main --help` (or `<cli_name> --help` if installed)
3) Run or add a sample CLI command (keep CLI thin; logic in domain modules)
4) Optional checks: `pytest -q path` and `ruff check path`

## Best-effort checks

Before concluding work (scope as appropriate):
- `ruff check path`
- `ruff format path`
- `pytest -q path`
If skipped or failing, note why in your change description.


## Safety and defaults (high level)

Authoritative safety rules live in AGENTS.md and DATA.md.

In brief:
- Meaning vs protection are separate: treating meaning as canonical does **not** imply it is safe to delete. Acquisition data is non-canonical but protected evidence; do not delete or edit it.
- Treat data meaning as canonical unless documented otherwise
- No destructive operations without explicit approval
- Do not edit raw/canonical files in place


## Testing

Testing protocol and agent instructions live in `docs/testing.md`.

Quick run:
- `pytest -q`


## How to extend the system (navigation only)

If you want to:

- Change system structure or add new subsystems  
  → see ARCHITECTURE.md

- Add or modify datasets, data layers, manifests, or schemas  
  → see DATA.md and data/<dataset>/README.md

- Run commands, install dependencies, or follow workflows  
  → see AGENTS_CURSOR.md (if present)

- Understand what you are allowed to do as an agent  
  → see AGENTS.md


## What this README intentionally excludes

This file does NOT contain:
- Installation guides
- Step-by-step tutorials
- Command runbooks
- Dataset-specific rules
- Data schemas or manifest formats

Those belong in more specific documents.


## Change discipline

Any change that affects:
- data meaning or lifecycle
- system boundaries or flow
- safety, permissions, or destructive behavior

must be reflected in the appropriate CAPS file:
- ARCHITECTURE.md
- DATA.md
- AGENTS.md

Unreflected changes are considered incomplete.


## Final note

This repository is designed to be reasoned about, not explored blindly.

If you are unsure where a rule belongs:
- Meaning → DATA.md
- Shape → ARCHITECTURE.md
- Permission → AGENTS.md
- Procedure → AGENTS_CURSOR.md