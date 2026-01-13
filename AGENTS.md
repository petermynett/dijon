# AGENTS.md

This file defines the **safety model and reasoning constraints** for coding agents operating in this repository.

It specifies **non-negotiable invariants** about how changes may be made.  
It does not define procedures, commands, or workflows.

AGENTS.md is the primary safety authority.

---

## Purpose

This document governs **how agents operate safely**, independent of tooling, workflow, or project maturity.

It exists to:
- prevent irreversible mistakes
- avoid silent drift in data meaning or system shape
- enforce explicit human intent for risky actions

If a requested action conflicts with this file, the agent must stop and explain why.

---

## Relationship to other CAPS docs

The following documents are authoritative and must be consulted as relevant:

- **README.md** — project intent and navigation
- **ARCHITECTURE.md** — system shape, boundaries, dependency direction
- **DATA.md** — data meaning, lifecycle, immutability, rebuildability

**Rule of precedence:**
- AGENTS.md governs **whether** a change may proceed
- DATA.md and ARCHITECTURE.md govern **what must remain true**

If an action satisfies DATA.md but violates AGENTS.md, **stop**.

---

## Procedural overlays

Tool- or time-specific instructions (e.g. `AGENTS_CURSOR.md`) may exist.

Overlays:
- may add detail
- must not weaken or contradict this file
- are subordinate to AGENTS.md

If an overlay conflicts with this file, treat the overlay as wrong.

---

## Explicit approval

**Explicit approval** means a clear human instruction in the current task authorizing the action.

If explicit approval is required and not present:
- stop
- explain what approval is needed
- do not proceed

---

## Core invariants

If a requested change violates any invariant below, stop and explain the conflict.

### Destructive operations

No destructive operations without explicit approval.

This includes (but is not limited to):
- deleting data or code
- rebuilding or resetting databases
- migrations
- dropping tables
- mass renames or rewrites

**Important:**  
Derived or rebuildable artifacts (including databases) are *still* considered destructive to rebuild by default and require explicit approval.

Formatting-only code changes (e.g. `ruff format`) are allowed if they do not affect data, manifests, schemas, or contracts.

Non-canonical does **not** mean deletable.  
Protected evidence (e.g. acquisition data) must never be deleted or edited.

---

### Data contracts and manifests

- Follow all data rules defined in **DATA.md**
- Do not edit acquisition, raw, or override data in place
- Do not invent new manifest fields, schemas, or ID formats
- Do not retroactively rewrite file identifiers

If data meaning or lifecycle changes, **DATA.md must be updated**.

---

### Tooling and dependencies

Do not add:
- new dependencies
- new tools
- new external integrations

without explicit approval.

**Package sourcing posture**
- Prefer **conda-forge**
- Use pip/pipx only if conda-forge is unsuitable
- Any proposal must explain why the dependency is needed and how it fits the system

---

### Environment assumptions

Assume one canonical environment: **dijon**.

Agents must:
- not assume the environment is active
- confirm environment activation before diagnosing failures
- avoid changing code to compensate for a misconfigured environment

---

## Safe reasoning model

Agents must:

- prefer the **smallest change** that satisfies the request
- avoid drive-by refactors
- stop on ambiguity or hidden assumptions
- ask rather than guess

If a change affects:
- data meaning or lifecycle
- system boundaries or dependencies
- safety posture

the relevant CAPS document **must** be updated.

---

## Structural code changes

Structural refactors (renames, moves, re-organization) are allowed **without explicit approval** *only if*:

- data meaning is unchanged
- manifests and schemas are untouched
- contracts in DATA.md and ARCHITECTURE.md remain true

If unsure, stop and ask.

---

## Local documentation

Folder-level README.md files may further restrict behavior.

They must not weaken root invariants.

If a local rule conflicts with this file, follow **AGENTS.md**.

---

## When to add nested AGENTS.md

Default: do not.

Suggest a subfolder AGENTS.md only if:
- repeated agent failures indicate missing invariants, and
- a README.md cannot express the constraint clearly

Creating a nested AGENTS.md requires explicit approval.

---

## Final rule

If an action would:
- lose information
- obscure provenance
- break rebuildability
- or change meaning without an explicit artifact

it violates this safety model.

Stop and ask.