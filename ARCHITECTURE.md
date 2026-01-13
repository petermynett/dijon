# ARCHITECTURE.md

This document describes the **system shape** of the project:  
the major subsystems, their responsibilities, and the direction of dependencies and data flow.

It is **descriptive**, not procedural.  
It explains what exists, how it fits together, and which constraints are intentional.

This file is intended to remain stable across refactors.  
Detailed contracts, schemas, and safety rules live elsewhere.

For document authority and navigation, see `README.md`.

---

## Architectural stance

This system is designed as a **stable ingestion and storage core** with **experimental research layers above it**.

It combines two modes:

- a **deterministic, rebuildable pipeline** for bringing external material into structured form
- a **notebook-driven research layer** where plural interpretations and visualizations are explored

Key principles:

- Lower layers are **stable, deterministic, and rebuildable**
- Upper layers are **exploratory and allowed to change**
- The **filesystem is the system of record**
- The **database is derived, disposable, and accelerative**
- No subsystem enforces a single “correct” interpretation

The architecture intentionally favors **under-restriction early**.

---

## System overview

At a high level, this is a **CLI-orchestrated Python system** for:

- acquiring external artifacts
- staging them into structured datasets
- indexing them for efficient access
- supporting comparative analysis in notebooks

The CLI coordinates work.  
Core logic lives in library modules.  
Research happens primarily above the stable core.

---

## Core goals and non-goals

### Goals
- **Rebuildability**: derived artifacts can be regenerated from canonical inputs
- **Explicit boundaries** between subsystems
- **Localized change**: research should not destabilize ingestion or storage
- **Safety by default** for destructive actions

### Non-goals
- Fully specifying research workflows up front
- Treating derived artifacts as long-lived state
- Forcing canonical analytical interpretations

---

## Core subsystems (authoritative)

### Sources
- Acquire external artifacts and normalize inputs
- Pure adapters: no database access, no orchestration, no analysis
- The only place upstream messiness should live

### Pipeline
- Orchestrates movement between dataset stages
- Deterministic, idempotent, re-runnable
- The only subsystem allowed to mutate structured data
- Defines *when* transitions occur, not *how* data is interpreted

### Dataset stages
- Filesystem-backed representations of data lifecycle
- Encode *where* data is in the system, not *what it means*
- Meaning and mutability rules are defined in DATA.md

### Database
- Query accelerator over filesystem-backed data
- Fully rebuildable and safe to delete
- Never a source of truth

### CLI implementation
- Thin orchestration and interface layer
- No domain logic or data meaning
- Delegates all substantive work to library modules

### Notebooks
- Exploratory research, comparison, and visualization
- Explicitly experimental and pluralistic
- Must never be depended on by core library code

---

## Dependency direction and boundaries

Allowed dependency flow (high → low):

- CLI → pipeline, database
- Pipeline → sources, dataset stages, database
- Database → dataset stages
- Notebooks → core library, database, dataset stages

Hard boundaries:

- Core library must not depend on notebooks
- Sources must not import pipeline logic
- Database must not be required for data safety

---

## Dataflow model (intent)

Conceptually:

1. External artifacts enter via **sources**
2. **Pipeline** stages structure and normalize data
3. Structured outputs live in **dataset stages (filesystem)**
4. The **database** indexes and accelerates access
5. **Notebooks** perform comparison and interpretation

This flow defines a **spine**, not a prison.

---

## Canonical vs derived (posture)

- The filesystem is the ultimate system of record
- Canonical artifacts are not edited in place
- Derived artifacts must be reproducible
- Manual intent is represented explicitly, not by mutation

Detailed rules are defined in DATA.md.

---

## Manual truth, comparison, and uncertainty

- Manual annotations live in the filesystem
- They are treated as **labeled interpretations**
- Automated outputs may coexist alongside manual truth
- Automated processes must never overwrite manual truth
- Parallel hypotheses and partial results are valid outcomes

Comparison across performances is expected to occur primarily in notebooks.  
Tune identity is explicit, filesystem-backed, and may be indexed by the database.

---

## Extension philosophy

This architecture supports:
- new MIR techniques
- new repertoires and representations
- new comparative and visual questions

It avoids early commitment to fixed analysis pipelines or evaluation schemes.

---

## Final note

This architecture is designed to support **thinking**, not just execution.

If a future constraint conflicts with exploratory research,  
the architecture should bend before the research does.