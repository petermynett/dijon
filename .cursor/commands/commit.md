---

## Assess Changes (Always Run)

- `git status`
- `git diff --stat`

If no changes are present (tracked or untracked):
- Fail with:
❌ Nothing to commit (working tree clean).

---

## Warnings (Non-Blocking)

These conditions DO NOT stop the commit. They are reported for visibility.

- File deletions among tracked files
- New directories detected
- Changes under:
- `data/`
- `db/snapshots/`
- `env/`
- `ztemp/`

Warnings are summarized before committing.

---

## Hard Blockers (Secrets + Large Files)

The following conditions STOP execution:

### 1) Secret paths staged (from `.gitignore` Secrets section)

Fail if any staged path matches:
- `.secrets/**`
- `.env`
- `.env.*` (except `.env.example`)

### 2) Any staged file is larger than 2 MB

Fail if any staged file (added/modified) exceeds 2 MB.

Implementation notes (must be performed after staging):
- Enumerate staged paths using `git diff --cached --name-only -z`
- Ignore deleted paths when checking file sizes
- Report the offending paths clearly before failing

---

## Staging Policy

Stage all changes (tracked, untracked, and deletions):
- `git add -A`

If staging fails:
- Hard fail:
❌ git add failed.

After staging:
- Show `git status`
- Run hard-block scans (Secrets + Large Files)

---

## Commit Message Generation

Commit message is always auto-generated.
No prompts. No pauses.

### Change Magnitude

Quick (1–3 files):
- Subject line only

Standard (4–10 files):
- Subject + short bullet list

Significant:
- Triggered by:
- 10+ files changed
- New directories
- Changes to `.cursor/`, `env/`, `pyproject.toml`
- Schema changes (`sql/`, `db/migrations/`)
- Include a concise bullet summary

---

## Commit Message Format

<type>: <subject>

- bullet
- bullet

Files: <comma-separated list or "+N more">

Types:
- `feat`     New feature
- `fix`      Bug fix
- `refactor` Restructure without behavior change
- `docs`     Documentation only
- `config`   Tooling or configuration
- `chore`    Maintenance or cleanup

Rules:
- Use real newlines
- No literal `\n`
- Write message to temp file
- Commit with:
`git commit -F <temp-file>`

---

## Git Operations

Run sequentially, aborting on failure:

1. Commit
- `git commit -F <temp-file>`
- On failure:
  ❌ git commit failed

2. Push
- If upstream exists:
  `git push`
- If no upstream:
  `git push -u origin <branch>`
- On failure:
  ❌ git push failed

---

## Post-Push Verification

1. Fetch:
- `git fetch --quiet origin`
- Warn (do not fail) if fetch fails

2. Verify sync:
- Print refs:
  - `git branch --show-current`
  - `git rev-parse --abbrev-ref @{u}`
- Print SHAs:
  - `git rev-parse HEAD`
  - `git rev-parse @{u}`
- Compare:
  - `git rev-parse HEAD`
  - `git rev-parse @{u}`
- If equal:
  ✅ Push verified
- If not:
  ⚠️ Push completed but SHAs differ. Check manually.

---

## Error Handling

Hard failures only for:
- Detached HEAD
- Merge/rebase/conflicts
- git add / commit / push failures

Warnings never block execution.

---

## Philosophy

- Commit early.
- Commit often.
- Untracked changes are first-class.
- Automation should help you ship, not ask permission.