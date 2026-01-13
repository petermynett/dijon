# AGENTS.md

This file is the repo-level safety and operations manual for coding agents.  
It defines non-negotiable rules and reasoning model for how to safely change this repository.

AGENTS.md is the primary safety file. If safety rules exist, they live here or in narrowly scoped subfolder AGENTS.md files.

## Purpose

This file governs **how agents operate safely** — the timeless constraints and reasoning model that apply regardless of tooling, workflow, or repo maturity. It does not contain procedures or commands; those belong in procedural overlays (see below).

## Authoritative docs

These CAPS files are authoritative and must be consulted before making changes:

- **README.md** — what the project does and how it is used  
- **ARCHITECTURE.md** — structure, boundaries, and intended extension points  
- **DATA.md** — data layers, schemas, contracts, provenance, regeneration rules

AGENTS.md governs **how changes are made**.  
ARCHITECTURE.md and DATA.md govern **what must remain true**.

## Procedural overlays

Procedural overlays (e.g., `AGENTS_CURSOR.md`) may exist to provide tool- and time-bound execution details. Overlays must not contradict this file's invariants. If they appear to, treat the overlay as wrong and follow this file.

## Explicit approval

**Explicit approval** means a human instruction in the current task/request explicitly authorizing the action. If approval is required and not present, stop and ask.

## Core invariants

If a requested change conflicts with an invariant, stop and explain the conflict.

### Destructive operations

No destructive operations without explicit approval. This includes deletions, resets, rebuilds, migrations, dropping databases, mass renames, and similar operations that cannot be easily reversed.

**Note:** Code formatting (e.g., `ruff format`) and other code-style changes that do not affect data, manifests, or schemas are allowed by default.

Non-canonical does not mean deletable. Protected-but-non-canonical evidence (e.g., acquisition data) must not be deleted or edited without explicit approval.


### Manifests and file identity

Follow all documented manifest rules (see `DATA.md` for authoritative manifest contract). Follow documented file-ID formats and generation rules. Do not invent new ID schemes or manifest fields. Do not retroactively rewrite identifiers.

### Tooling and dependencies

Do not add new tooling, dependencies, or external integrations without explicit approval.

**Package sourcing policy**
- Prefer **conda-forge** for all installable dependencies.
- Use **pip / pipx** only when a dependency is unavailable or unsuitable via conda-forge.
- If proposing a new dependency, explain:
  - why it is needed,
  - whether it is available via conda-forge,
  - and why any non–conda-forge option is justified.

### Environment

Assume one canonical development environment. Activate it before running any repo command. Do not assume the environment is active. If a command fails, first confirm environment activation and that you're using the repo's canonical interpreter before changing code.

### Safe reasoning model

- Prefer the smallest change that satisfies the request.
- Avoid drive-by refactors unless explicitly requested.
- Stop on ambiguity or hidden assumptions; ask rather than guess.
- If behavior or contracts change, update the relevant CAPS docs.

### External communications and secrets

Do not add external communications, telemetry, or handle secrets unsafely without explicit approval.

## Local documentation

Folder-level README.md or AGENTS.md files may define folder-specific rules (e.g., which data files are canonical vs regenerable). They must not contradict root invariants. If a local doc conflicts with this file, treat the local doc as wrong and follow this file.

## When to add nested AGENTS.md

Default: do not create subfolder AGENTS.md files.

Suggest a subfolder AGENTS.md if:
- the folder has specialized invariants or workflows that agents repeatedly violate, and
- a README.md cannot express those constraints clearly enough.
- create a subfolder AGENTS.md only if explicit approval is given.

Otherwise, use README.md files and link back to ARCHITECTURE.md and DATA.md.

