# AGENTS_CURSOR.md

**Procedural overlay** — current, tool-specific execution details for this repository.

This file provides *how-to* guidance for agents using the repository **today**.  
It is intentionally volatile.

It must not contradict **AGENTS.md**.  
If it appears to, **AGENTS.md wins**.

---

## Purpose

This overlay exists to capture **current tooling, commands, and best-effort workflows** for agent work (e.g. Cursor, mamba, ruff, pytest).

It is not a safety contract.  
It is not a policy file.  
It is not authoritative for meaning or permissions.

Those live in:
- **AGENTS.md** — safety model and invariants
- **DATA.md** — data meaning and lifecycle
- **ARCHITECTURE.md** — system shape and boundaries
- **README.md** — project intent and navigation

---

## Environment

This repository uses a single canonical environment.

Activate before running any repo command:
```zsh
mamba activate dijon