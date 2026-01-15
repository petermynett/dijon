---

## Assess Changes (Always Run)

- `git status`
- `git diff --stat`
- `git log -5 --oneline`

If no changes are present (tracked or untracked):
- Fail with:
❌ Nothing to commit (working tree clean).

---

## Warnings (Reported, Rarely Blocking)

These are surfaced prominently but do NOT stop execution unless noted.

- File deletions among tracked files
- New directories (tracked or untracked)
- Changes under:
- `data/`
- `db/snapshots/`
- `env/`
- `ztemp/`

Warnings are summarized before staging and referenced in the commit message
when relevant.

---

## Hard Blockers (Secrets + Large Files)

The following conditions STOP execution:

- Staging failures
- Commit failures
- Push failures

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

## Mandatory Analysis (Always Performed)

The following analyses MUST be performed and reflected in the commit message.
Unlike `/commit`, this command always reads broadly.

For very large changesets (50+ files), summarize patterns rather than repeating
file-by-file detail.

### 1) Full Diff Review
- Read full diffs for all staged files (not just `--stat`).

### 2) Cross-File Dependencies
- Identify imports, references, or shared contracts between changed files.
- Note ripple effects.
- If none found, explicitly state:
"None (verified)."

### 3) Usage Context
- Search for callers/usages of modified public symbols.
- List symbols checked and files inspected.
- If no external callers found, explicitly state:
"No external callers found (verified)."

### 4) Breaking Changes
- Explicitly enumerate:
- Renamed symbols
- Signature changes
- Deleted exports
- Data structure changes
- If none, explicitly state:
"None (verified)."

### 5) Git History Context
- Review `git log -5 --oneline`.
- Reference related commits or state:
"Fresh work."

---

## Commit Message Format

<type>: <subject>

## Summary
2–3 sentences describing intent, scope, and outcome.

## Changes
- <file or area>: <what changed and why>
- <file or area>: <what changed and why>

## Dependencies
- <cross-file impacts or "None (verified)">

## Breaking Changes
- <breaking changes or "None (verified)">

## Context
- <related commits or "Fresh work">

Files: <comma-separated list or "+N more">

Types:
- `feat`     New feature
- `fix`      Bug fix
- `refactor` Structural change without behavior change
- `docs`     Documentation only
- `config`   Tooling or configuration
- `chore`    Maintenance or cleanup

Rules:
- Use REAL newlines
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
  ⚠️ Push completed but SHAs differ. Verify manually.

---

## When to Use

Use `/commit-full` when:
- Making architectural or cross-module changes
- Refactoring public APIs
- Moving or deleting files/directories
- Working on large or high-impact changes
- Long-term commit history clarity matters

Do NOT use `/commit-full` for:
- Routine edits
- Formatting-only changes
- Small, isolated fixes

---

## Philosophy

- Choosing `/commit-full` is an explicit signal of intent.
- Read widely. Think carefully. Then commit.
- Warnings inform; blockers protect.
- Automation should increase confidence, not slow momentum.