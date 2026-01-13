# DATA.md

This document defines the **data contract** for this repository: how data is classified, where it lives, how it may change, and what guarantees the system provides about rebuildability and provenance.

It is a contract, not a tutorial.  
Operational procedures and enforcement live elsewhere.

---

## Scope and authority

DATA.md is authoritative for:

- data classification and lifecycle
- immutability and deletion rules
- precedence and override semantics
- rebuildability and provenance guarantees

If a rule about data meaning or lifecycle appears elsewhere, **DATA.md wins**.

---

## Data classes (current commitments)

This repository currently commits to the following data classes:

1. **Acquisition** — protected upstream evidence  
2. **Raw** — canonical system of record  
3. **Overrides** — canonical modifier layer applied on top of raw

Additional derived or analytical stages may be introduced later.  
They are intentionally not specified here.

---

## Filesystem authority

**Filesystem location defines data class.**

- Artifacts under `data/acquisition/` are acquisition data
- Artifacts under `data/raw/` are raw data
- Overrides live in their own filesystem locations and are referenced by manifests

Manifests may describe relationships and precedence, but **stage is determined by location**, not metadata alone.

---

## Immutability (hard invariants)

These rules are strict:

- **Acquisition data**
  - append-only
  - never edited or replaced
  - treated as non-replaceable evidence

- **Raw data**
  - append-only
  - never edited or replaced
  - canonical rebuild root

- **Overrides**
  - append-only
  - never edited or replaced
  - express corrections or alternative interpretations

If something is wrong, the fix is expressed by **adding new data**, not modifying history.

---

## Canonical meaning and precedence

- **Raw data is canonical** for system meaning
- **Overrides modify raw** without mutating it
- Overrides may represent corrections, reinterpretations, or precedence rules
- During downstream resolution:  
  **override > raw**

Precedence must be resolvable via data layout and/or manifests.  
Notebooks must not be the only place where “truth” is decided.

---

## Provenance and rebuildability guarantees

The system aims to guarantee:

- **Rebuildability**: downstream artifacts can be regenerated from acquisition + raw + overrides
- **Traceability**: it is possible to determine how an artifact was produced

Minimum guarantee for stable outputs:
- “we can rebuild this”
- “we know exactly how it was produced”

Implementation details may evolve, but these guarantees must hold.

---

## Manual data

Manual data is expected and supported, including:

- annotations
- corrections
- labels
- overrides

Manual inputs may be more authoritative than upstream sources, but they must be represented explicitly as data (typically via overrides), never by mutating acquisition or raw files.

History is not required: only the **latest declared intent** must be available.

---

## Derived data (posture)

Derived or analytical data is not yet formally classified.

Current posture:

- **All data above raw/overrides is considered derived and rebuildable unless explicitly documented otherwise**
- Derived artifacts should be safe to delete and regenerate
- Agents must not delete derived artifacts without explicit approval

The database is treated as derived and rebuildable by default.

---

## Identity (minimal commitment)

Certain entities (e.g. performances, annotations) are expected to have **stable identity** once assigned.

DATA.md does not define identity schemes; it only asserts that identity should not change implicitly across stages.

---

## Deletion and safety

Hard rules:

- **Never delete**:
  - acquisition
  - raw
  - overrides

- **Derived artifacts (including databases)**:
  - rebuildable by default
  - deletable only with explicit approval

When in doubt, treat an artifact as protected and non-deletable.

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

When new data stages are introduced, this contract should be extended by:

- naming the new class
- declaring its mutability rules
- declaring its rebuildability and provenance guarantees
- declaring its precedence relationship (if any)

Until then, the data contract is intentionally small:

**acquisition → raw → overrides → (derived, rebuildable)**