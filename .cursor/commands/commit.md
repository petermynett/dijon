---

## Assess Changes (Always Run)

- `git status`
- `git diff --stat`

If no tracked changes are present:
- Fail with:
❌ Nothing to commit (no tracked changes).

---

## Warnings (Non-Blocking)

These conditions DO NOT stop the commit. They are reported for visibility.

- Untracked files present
- File deletions among tracked files
- New directories detected
- Changes under:
- `data/`
- `db/snapshots/`
- `env/`
- `ztemp/`
- Large untracked files (>2 MB)

Warnings are summarized before committing.

Untracked files are excluded unless `--include-new` is specified.

---

## Staging Policy

Default behavior:
- Stage tracked changes only:
- `git add -u`

If `--include-new` is specified:
- Stage all changes:
- `git add -A`
- Exclude untracked files larger than 2 MB and warn.

If staging fails:
- Hard fail:
❌ git add failed.

After staging:
- Show `git status`

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
- Tracked changes are safe.
- Untracked changes are opt-in.
- Automation should help you ship, not ask permission.