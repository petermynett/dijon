# DATA

This document defines the **data contract** for this repository: how data is classified, where it lives, how it may change, and what guarantees the system provides about rebuildability and provenance.

This file is authoritative for:
- Canonical vs derived vs ephemeral data
- Data-layer immutability and deletion rules
- Layer semantics and lifecycle
- Manifest-driven canonical data management
- Default safety posture when ambiguity exists

This file does NOT describe system control flow or code structure (see ARCHITECTURE.md), nor agent permissions and approval requirements (see AGENTS.md).


## Scope and authority

DATA.md governs all file-based and database-backed artifacts that represent data, including:
- Files under data/
- Database files under db/
- Schema and validation assets related to data shape
- Any artifacts produced or consumed by pipeline verbs

If a data-related rule appears in multiple places:
- DATA.md is authoritative for meaning and lifecycle
- AGENTS.md is authoritative for enforcement and approval
- Local READMEs may further restrict behavior but may not weaken DATA.md rules


## Core data classification (hard boundary)

Every data artifact MUST belong to exactly one category:

- Canonical
- Derived
- Ephemeral

If an artifact does not explicitly declare its classification: it MUST be treated as Canonical by default.

### Protection and regenerability are orthogonal

- Classification (canonical/derived/ephemeral) is about meaning and rebuild authority.
- Protection (deletion/mutation rules) is about evidence and provenance.
- Regenerability (derived-ness) is about whether something may be safely rebuilt.

Examples:
- Acquisition: non-canonical, non-derived, protected evidence (must not be deleted or edited; not rebuildable).
- Raw / overrides / manifests: canonical **and** protected.
- Normal / optimized / db: derived and rebuildable; safe to delete/regenerate unless local docs say otherwise.


## Canonical data

Canonical data is authoritative source-of-truth input to the system.

Properties:
- Represents original captures, curated corrections, or declared human intent
- Is not reproducible from other artifacts
- Must not be mutated in place
- Serves as the root of rebuildability for downstream layers

Examples:
- Raw source captures
- Manifests that declare canonical files
- Human-authored overrides
- Explicitly curated reference datasets

Rules:
- Canonical data may only change via explicit supersede/archive workflows
- Edits-in-place are forbidden
- Any change must preserve provenance and traceability

If canonical data is wrong:
- The fix is represented as a new canonical artifact (e.g., superseding file, override), not by editing history

Non-canonical does not imply deletable. Protection and canon status are independent.

## Derived data

Derived data is reproducible output generated from canonical inputs plus declared configuration.

Properties:
- Deterministic with respect to inputs
- Safe to delete and regenerate
- Must not introduce new authoritative facts

Examples:
- Normalized tables
- Optimized or aggregated artifacts
- Rebuilt databases
- Exported analysis outputs

Rules:
- Derived data MUST declare (implicitly or explicitly) its upstream dependencies
- Derived data MUST be regenerable without manual intervention
- Long-lived state must not silently accumulate in derived layers

If a derived artifact cannot be regenerated:
- It is misclassified and must be treated as Canonical until fixed


## Ephemeral data

Ephemeral data is temporary, convenience-only output.

Properties:
- Not authoritative
- Not relied upon for rebuilds
- Safe to delete at any time

Examples:
- Caches
- Temporary scratch files
- Debug outputs

Rules:
- Ephemeral data MUST NOT be required for correctness
- Its absence must not change semantic outcomes


## Default safety posture

When in doubt:
- Treat data meaning as Canonical
- Treat protection as strict: do not delete or edit unless a document explicitly says it is safe (e.g., derived/rebuildable layers)
- Do not regenerate blindly

Protected-but-non-canonical evidence (e.g., acquisition) must not be deleted or edited even though it is not a rebuild root.

Explicit permission to delete or regenerate must be stated in:
- DATA.md, or
- A local README.md that this file defers to


## Data workspace (`data/`)

The data workspace is rooted at `data/` and uses a **stage-first directory structure**:
data is organized by **stage** (acquisition, raw, normal, etc.) first, then by **source/dataset** within each stage.

High-level intent:
- data/ contains file-based data artifacts governed by this contract
- data/ is treated as canonical unless explicitly stated otherwise
- Directory structure: `data/<stage>/<source_key>/`

### Directory structure

```
data/
├── acquisition/          # Protected upstream inputs (by source)
│   ├── <source_key>/
│   └── ...
├── raw/                  # Canonical immutable captures (by source)
│   ├── <source_key>/
│   │   ├── manifest.csv  # Metadata tracking raw files
│   │   └── <files>
│   └── ...
├── overrides/            # Canonical human-authored corrections (by source)
│   ├── <source_key>/
│   └── ...
├── normal/               # Derived normalized representations (by source)
│   ├── <source_key>/
│   └── ...
├── optimized/            # Derived aggregated artifacts (by source)
│   ├── <source_key>/
│   └── ...
└── logs/                 # Log files
```

### Stage definitions

- **acquisition** / upstream
  Protected upstream inputs (downloads, exports, API fetch results).
  Not canonical for rebuild semantics and not tracked in manifests.
  Not derived/rebuildable. Protected evidence; must not be deleted or edited.

  Properties:
  - Must not be deleted or edited in place
  - May contain duplicates or superseded captures
  - Serves as evidence and provenance for canonical raw creation
  - Is not relied upon for deterministic rebuilds

  Raw data is derived from acquisition, but acquisition itself is not the rebuild root.

  Location: `data/acquisition/<source_key>/`

- **raw**
  Canonical immutable captures.
  Forms the rebuild contract for the system.
  Tracked via manifests.

  Location: `data/raw/<source_key>/`
  
  Manifests (metadata files tracking raw file identity and provenance) live alongside
  the raw files they track: `data/raw/<source_key>/manifest.csv`

- **overrides**
  Canonical human-authored corrections or interpretations.
  Do not modify raw data; take precedence during downstream resolution.

  Location: `data/overrides/<source_key>/`

- **normal**
  Deterministic normalized representations.
  Derived. Safe to delete/regenerate.

  Location: `data/normal/<source_key>/`

- **optimized**
  Deterministic derived artifacts (aggregations, indices, features).
  Derived. Safe to delete/regenerate.

  Location: `data/optimized/<source_key>/`

Dataset-specific rules and exceptions are documented in local READMEs within each source directory.


## Manifest-driven canonical data

Canonical file-based datasets are tracked via **manifests**.

Manifest intent:
- Declare file identity
- Record provenance and integrity
- Enable reproducible rebuilds
- Support supersede/archive workflows

General principles:
- Manifests are canonical artifacts
- A manifest row represents one canonical file identity
- File identity is stable and content-addressed (e.g., via checksum)
- Canonical files are append-only at the manifest level

Detailed manifest schema, required fields, and lifecycle states are defined here (authoritative):
- file identity (e.g., file_id)
- integrity (e.g., checksum)
- status (e.g., active, archived, superseded)
- provenance metadata

Dataset-specific manifest rules live alongside the dataset.


## Overrides and precedence

Overrides represent explicit human intent to correct or reinterpret canonical inputs.

Rules:
- Overrides do not redefine raw data
- Overrides take precedence during downstream resolution
- Overrides must be explicit and documented
- Overrides are themselves canonical artifacts

The exact resolution logic (e.g., “effective raw”) is defined by the data contract and implemented in code, but the precedence rule is fixed:
- Override > Raw


## Databases (`db/`)

Databases are treated as **derived artifacts** by default.

Rules:
- Databases must be rebuildable from canonical inputs
- Schema is authoritative in src/sql/
- Database files may be deleted and regenerated unless explicitly documented otherwise

If a database (or part of it) is intended to be canonical:
- That fact MUST be explicitly documented locally
- Silent promotion of derived state to canonical is forbidden


## Immutability and deletion rules

Summary table (default posture):

- raw: canonical, immutable, do not delete
- overrides: canonical, immutable, do not delete
- manifests: canonical, immutable, do not delete
- normal: derived, safe to delete
- optimized: derived, safe to delete
- db: derived, safe to delete

Local documentation may further restrict deletion but may not weaken these defaults.


## Determinism and time

Time handling must be explicit and auditable.

Rules:
- Canonical timestamps must use the project's declared standard representation (see `.cursor/rules/050-time-canonical.mdc` for the canonical time format specification)
- Ambiguous or non-existent local times must not be silently guessed or coerced
- Ambiguity is allowed only if explicitly represented or resolved via a documented rule
- Any resolution policy (e.g., earliest, latest, reject, annotate) must be declared and consistent

Downstream derived data must be reproducible given the same inputs and resolution rules.


## Dataset onboarding (data contract)

For any dataset introduced into this system:

- The dataset must declare which artifacts are canonical and which are derived
- Canonical file-based inputs must be tracked via a manifest
- Derived artifacts must be reproducible from canonical inputs and declared rules
- Dataset-specific semantics, quirks, cadence, and exceptions must be documented locally

DATA.md defines the contract.
Dataset-local README.md files define the concrete application of that contract.


## Validation and testing expectations

Changes to:
- data classification
- manifests
- schemas
- canonical/derived boundaries

MUST be accompanied by validation and/or tests that enforce the updated contract.

Silent drift is considered a bug.


## Relationship to other documents

- ARCHITECTURE.md describes system shape and flow; it defers here for data meaning.
- AGENTS.md enforces safety, approvals, and failure modes; it defers here for what is allowed.
- Local READMEs may add constraints but must remain compatible with this contract.


## Final rule

If a data operation would:
- lose information
- obscure provenance
- break rebuildability
- or change meaning without an explicit artifact

it violates this data contract.