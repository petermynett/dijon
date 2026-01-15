---

## Execution Model

**CRITICAL: All operations must run in a single tool call batch. No pauses. No approval prompts.**
- Batch: status check, staging, commit message generation, commit, push
- Use `required_permissions: ['all']` for all git operations
- Do not wait for user approval between steps

---

## Assess Changes (Always Run)

- `git status --short` (single command, no separate diff)

If no changes are present (tracked or untracked):
- Fail with:
❌ Nothing to commit (working tree clean).

---

## Warnings (REMOVED)

No warnings. Commit proceeds immediately.

---

## Hard Blockers (REMOVED)

No blocking checks. Commit proceeds immediately after staging.

---

## Staging Policy

Stage all changes (tracked, untracked, and deletions):
- `git add -A`

If staging fails:
- Hard fail:
❌ git add failed.

After staging:
- Proceed directly to commit message generation

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
- Write message to temp file in workspace (e.g., `.git/COMMIT_MSG` or use `mktemp` in workspace)
- Commit with:
`git commit -F <temp-file>`
- If temp file creation fails, hard fail before attempting commit

---

## Git Operations

Run as single atomic operation:

1. Commit and push in one batch:
- Create commit message file
- `git commit -F <temp-file> && git push` (or `git push -u origin <branch>` if no upstream)
- On failure: ❌ git operation failed

---

## Post-Push Verification (REMOVED)

No verification. Push completes the command.

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