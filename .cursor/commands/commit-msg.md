# /commit-msg — write commit message with embedded file list

## Objective
Generate a single, copy-pasteable commit message that includes:
- a clear 5–20 line commit message, and
- a complete list of files that were added, modified, or removed

This command is read-only.
Do NOT run `git add`, `git commit`, or `git push`.

---

## Step 1 — Inspect changes (terminal, read-only)
Run these commands:

- `git status --porcelain=v1`
- `git diff --stat`
- `git diff --name-status`

Optional (only if needed to understand intent):
- `git diff -U0 --no-color`

---

## Step 2 — Write the commit message (assistant only)

Output ONE single block of plain text that represents the full commit message.
Do NOT split output into multiple sections or UI panels.

### Required structure (all part of the commit message)

1) Title line (1 line)
- ≤ 72 characters
- Prefer Conventional Commit style:
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `data:`

2) Body bullets (3–16 lines)
- Each line starts with `- `
- Describe what changed and why

3) Stats line (1 line)
- Derived from `git diff --stat`
- Format exactly:
  `Stats: <N> files changed (+<adds> / -<dels>)`

4) File list section (embedded, not separate)
- Appears at the END of the commit message
- Group files by change type
- Use these headings exactly:
  - `Files modified:`
  - `Files added:`
  - `Files deleted:`
- Only include sections that have at least one file
- No blank lines between sections or between list items
- Each file path is on its own line, prefixed with `- `