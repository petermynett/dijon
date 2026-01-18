DATA.md

This document defines the **data contract** for this repository: how data is classified, where it lives, how it may change, and what guarantees the system provides about rebuildability and provenance.

It is a contract, not a tutorial.
Operational procedures and enforcement live elsewhere.

---

## Scope and authority

DATA.md is authoritative for:

- data classification and lifecycle
- immutability and deletion rules
- precedence and annotation semantics
- rebuildability and provenance guarantees

If a rule about data meaning or lifecycle appears elsewhere, **DATA.md wins**.

---

## Repository data root

The repository’s **data root** is `data/`.

Within it, there are two distinct categories:

1. **Datasets** (`data/datasets/`) — canonical lifecycle-governed data classes (acquisition/raw/annotations)
2. **Project data** (`data/sets/`, `data/logs/`) — human workflow and operational artifacts (not dataset lifecycle classes)

Rules differ between these categories. Do not infer dataset lifecycle semantics from the mere fact that something lives under `data/`.

---

## Data classes (current commitments)

This repository currently commits to the following dataset lifecycle classes under `data/datasets/`:

1. **Acquisition** — protected upstream evidence
2. **Raw** — canonical system of record
3. **Annotations** — canonical asserted truth and interpretations

Additional derived or analytical stages may be introduced later.
They are intentionally not specified here.

---

## Filesystem authority

**Filesystem location defines dataset lifecycle class** within `data/datasets/`.

- Artifacts under `data/datasets/acquisition/` are acquisition data
- Artifacts under `data/datasets/raw/` are raw data
- Artifacts under `data/datasets/annotations/` are annotation data

Manifests may describe relationships and precedence, but **stage is determined by location**, not metadata alone.

Artifacts outside `data/datasets/` (e.g. `data/sets/`, `data/logs/`) are not dataset lifecycle classes.

---

## Immutability (hard invariants)

These rules are strict for dataset lifecycle classes.

### Acquisition data (`data/datasets/acquisition/`)
- append-only
- never edited or replaced
- treated as non-replaceable evidence

### Raw data (`data/datasets/raw/`)
- append-only
- never edited or replaced
- canonical rebuild root

### Annotations (`data/datasets/annotations/`)
- append-only
- never edited or replaced
- represent manual judgments, labels, corrections, and alternative readings
- may attach to any stable entity (e.g. performances, tunes, sources, segments, or dataset-level objects)
- not assumed rebuildable and must be treated as protected, non-deletable canonical inputs

If something is wrong, the fix is expressed by **adding new data**, not modifying history.

---

## Human override (explicit approval)

The immutability rules above are **agent guardrails** by default.

**Exception (case-by-case)**: With explicit human approval **and explicit implications stated**, manifest or metadata files may be rewritten during iterative development.

This exception:
- applies case-by-case with explicit approval
- requires explicit implications to be stated
- primarily covers manifests and metadata files, not acquisition or raw artifacts themselves
- does not relax the safety floor defined in `AGENTS.md`

When in doubt, treat artifacts in `data/datasets/` as protected and non-mutable.

---

## Canonical meaning and precedence

- **Raw data is canonical** for system meaning
- **Annotations** accompany canonical artifacts without mutating them

Precedence must be resolvable via filesystem layout and/or manifests.
Notebooks must not be the only place where “truth” is decided.

---

## Provenance and rebuildability guarantees

The system aims to guarantee:

- **Rebuildability**
  - downstream artifacts can be regenerated from raw + annotations
  - raw can be regenerated from acquisitions
- **Traceability**
  - it is possible to determine how an artifact was produced

Minimum guarantee for stable outputs:
- “we can rebuild this”
- “we know exactly how it was produced”

Implementation details may evolve, but these guarantees must hold.

---

## Manual data

Manual data is expected and supported, including:

- annotations (canonical asserted truth and interpretations)
- corrections
- labels
- alternative readings

Manual inputs may be more authoritative than upstream sources, but they must be represented explicitly as annotations, never by mutating acquisition or raw files.

Annotations are append-only and accumulate; multiple annotations may coexist for the same entity without requiring a single “correct” interpretation.

---

## Project data (sets and logs)

The following directories under `data/` support human workflow and operations and are **not** dataset lifecycle classes.

### Sets (`data/sets/`)
- curated, human-maintained selection files used to drive CLI actions (e.g. “gold”, “poc”, “eval”)
- freely editable
- not assumed derivable
- must reference stable identities (e.g. file_id and/or UUID), not filesystem paths
- may be regenerated or rewritten without violating dataset immutability rules

Sets are treated as **project metadata**, not canonical evidence, and do not override raw or annotation truth by themselves.

### Logs (`data/logs/`)
- operational logs and scratch outputs produced during development and runs
- freely editable and deletable unless explicitly documented as retained audit artifacts
- not a source of truth for data meaning

If logs must be preserved for reproducibility, that requirement must be stated explicitly elsewhere.

---

## Derived data (posture)

Derived or analytical data is not yet formally classified.

Current posture:

- all data downstream of raw or annotations is considered derived and rebuildable unless explicitly documented otherwise
- derived artifacts should be safe to delete and regenerate
- agents must not delete derived artifacts without explicit approval

The database is treated as derived and rebuildable by default.

If and when a dedicated derived directory is introduced (e.g. `data/derived/`), it will be governed by explicit rules added to this contract.

---

## Identity (minimal commitment)

Certain entities (e.g. performances, annotations) are expected to have **stable identity** once assigned.

DATA.md does not define identity schemes; it only asserts that identity should not change implicitly across stages.

Sets should reference stable identities rather than transient filesystem paths.

---

## Deletion and safety

Hard rules:

- **Never delete** within `data/datasets/`:
  - acquisition
  - raw
  - annotations

Project data rules:

- **Sets** (`data/sets/`)
  - editable
  - deletable
  - important project artifacts, but not protected canonical inputs

- **Logs** (`data/logs/`)
  - deletable by default

Derived artifacts (including databases) remain:
- rebuildable by default
- deletable only with explicit approval

When in doubt, treat artifacts under `data/datasets/` as protected and non-deletable.

---

## What does not belong in this file

To keep DATA.md stable, it excludes:

- CLI behavior and runbooks
- detailed schemas and column lists
- tool-specific procedures
- notebook workflows

If a change does not affect classification, mutability, precedence, provenance, or rebuild posture, it likely belongs elsewhere.

---

## Expansion seam

When new dataset lifecycle stages are introduced under `data/datasets/`, this contract should be extended by:

- naming the new class
- declaring its mutability rules
- declaring its rebuildability and provenance guarantees
- declaring its precedence relationship (if any)

Until then, the dataset lifecycle contract remains intentionally small:

acquisition + raw + annotations → (derived, rebuildable)