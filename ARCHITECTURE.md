# ARCHITECTURE

This document describes the **system shape**: the major subsystems, their responsibilities, and the direction of dependencies and data flow. It is **descriptive** (what exists and how it fits together), not a how-to guide.

This file is intended to be stable across refactors. Detailed data contracts, schemas, and operational rules live elsewhere.

For navigation and authoritative document routing, see `README.md`.


## Template note

This repository is a **template**. Concrete package names, module paths, and dataset names may differ once instantiated.

This architecture describes responsibilities and boundaries **by role**, not by hard-coded identifiers. Renaming packages or reorganizing modules should not invalidate the concepts here.


## System overview

This is a **CLI-first Python toolkit** for acquiring, canonicalizing, transforming, and analyzing data through a layered pipeline.

The system is designed around:
- **Determinism** for derived outputs
- **Explicit boundaries** between layers and subsystems
- **Reproducibility** via canonical inputs and rebuildable downstream artifacts

The CLI orchestrates work; domain logic lives in pipeline and dataset-specific layers; data contracts are enforced at well-defined boundaries.


## Core goals and non-goals

Goals
- Rebuildability: downstream artifacts can be regenerated from canonical inputs.
- Localized change: modifications in one layer should not ripple unpredictably.
- Extensibility: new datasets and pipeline verbs follow a consistent shape.
- Safety: destructive actions are explicit and reviewable.

Non-goals
- Abstracting over every possible data source or schema.
- Encoding every operational detail in this document.
- Treating generated artifacts as long-lived state.


## Top-level subsystems and responsibilities

### CLI layer

Primary responsibility: **user interface and orchestration**.

- Exposes commands and flags.
- Validates inputs and surfaces results.
- Calls into pipeline/domain functions.
- Does not embed dataset-specific logic or mutate canonical data directly.

The CLI should remain thin: parsing, dispatch, and presentation only.


### Pipeline layer

Primary responsibility: **verb-oriented orchestration**.

- Implements high-level verbs (conceptually: acquire, ingest, load, rebuild, etc.).
- Coordinates transitions between data layers.
- Enforces boundary checks before and after each stage.
- Remains deterministic with respect to canonical inputs and configuration.

Pipeline code may call dataset/source adapters as helpers, but defines the execution flow.


### Sources / dataset adapters

Primary responsibility: **dataset-specific adapters and identity handling**.

- Encapsulates upstream quirks, file formats, naming conventions, and parsing rules.
- Implements helpers for canonical file identity and provenance (e.g., manifest interaction).
- Resolves dataset-local precedence rules (e.g., overrides vs raw), as defined in DATA.md.

This is the only place where source-specific messiness should live.


### Data storage and databases

Primary responsibility: **rebuildable local storage**.

- Canonical files live under the data workspace.
- Generated artifacts (normalized, optimized, databases) are derived.
- Local databases are treated as rebuildable unless explicitly documented otherwise.

Initialization, rebuilds, and destructive resets must be explicit and are governed by AGENTS.md when run by agents.


### Shared configuration

Primary responsibility: **filesystem and environment anchors only**.

- Defines canonical project paths (e.g., data root, database root).
- Contains no business logic or dataset semantics.

This ensures all subsystems agree on where artifacts live.


### Shared utilities

Primary responsibility: **cross-cutting primitives**.

- Time handling, hashing, path helpers, logging primitives, etc.
- Utilities should be dependency-light and reusable.
- Canonical representations (e.g., timestamps) are defined once and reused consistently.


## Dependency direction and boundaries

Allowed dependency flow (high → low):

- CLI → pipeline, sources, database, utilities
- Pipeline → sources, database, utilities
- Sources → utilities (and standard library)
- Database → shared configuration, utilities
- Utilities → standard library only

Hard boundary:
- Sources must not import pipeline logic.

This prevents cyclic coupling and keeps dataset-specific logic from driving orchestration.


## Dataflow model (architectural intent)

This system uses a **layered dataflow** rooted in a single data workspace.

At a conceptual level:
- Upstream intake (acquisition) feeds canonical captures.
- Canonical layers define the rebuild contract.
- Downstream layers are deterministic and regenerable.

Detailed definitions of:
- Canonical vs derived vs ephemeral
- Layer immutability rules
- Manifest schemas and semantics
- Override behavior
- Deletion safety

are authoritative in DATA.md. This file states intent; DATA.md defines contracts.


## Canonical vs derived (high level)

Architectural posture:
- Canonical inputs are authoritative and must not be mutated in place.
- Derived outputs must be reproducible from canonical inputs and declared configuration.
- Manual intent is represented explicitly (e.g., overrides), not by editing canonical files.

If there is ambiguity, the default posture is to treat artifacts as canonical unless explicitly documented otherwise in DATA.md.


## Extension points (system growth)

### Adding a new dataset

At the architectural level, adding a dataset means:
- Introducing a new dataset identity with its own adapters.
- Defining how upstream inputs become canonical.
- Participating in the shared dataflow and contracts defined in DATA.md.
- Documenting dataset-specific rules locally under the data tree.

The exact steps and quirks live with the dataset, not here.


### Adding a new pipeline verb

- Implement orchestration in the pipeline layer.
- Respect dependency direction and data contracts.
- Keep behavior deterministic and boundary-checked.

Pipeline verbs define “what happens,” not dataset specifics.


### Adding new derived artifacts

- Derived artifacts must declare their upstream dependencies.
- They must be safe to delete and regenerate unless explicitly documented otherwise.
- Long-lived state should not accumulate silently in derived layers.


## What does not belong in this file

To keep this document stable, exclude:
- Step-by-step runbooks or command tutorials
- Dataset-specific quirks or one-off rules
- Detailed schemas, manifest fields, or column lists
- Tool- or implementation-specific details likely to churn

If changing something would not alter the system’s mental model or boundaries, it likely belongs elsewhere.