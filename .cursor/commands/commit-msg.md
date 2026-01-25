# /commit-msg — write commit message with embedded file list

## Objective
Generate a single, copy-pasteable commit message that includes:
- a clear 5–20 line commit message, and
- a complete list of files that were added, modified, or removed.

This command is read-only.
Do NOT run `git add`, `git commit`, or `git push`.

The output is only the commit message text, not a shell command.

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

Output the commit message INSIDE ONE markdown fenced code block (triple backticks),
so the UI shows a copy button.

- Output EXACTLY one fenced code block containing the full commit message text
- Do NOT put any text before or after the code block
- Do NOT split output into multiple sections or UI panels

### CRITICAL: QUOTING & SAFETY RULES (MANDATORY)

The commit message MUST NOT cause failure when used with `git commit -m "<message>"`.

To guarantee this:

1) DO NOT include any unescaped double quotes (")
- Either remove them entirely, or replace them with:
  - nothing
  - parentheses
  - backticks (`), or
  - typographic double quotes (“ and ”)
- Fidelity does not matter. Safety matters.

2) DO NOT include any single quotes (')
- Either remove them, or replace them with:
  - nothing
  - backticks (`), or
  - typographic apostrophes (’)
- Never output a literal ASCII single quote (').

3) DO NOT use shell escaping patterns
- Do NOT output sequences like: \", \', or '\''
- The output must be safe without requiring the user to think about escaping.

4) Filenames that contain quotes
- If a file path contains ' or ", sanitize the rendered path by removing or replacing those characters.
- Exact filename fidelity is NOT required; stability is.

5) If in doubt
- Delete the problematic character.

If any of the above rules are violated, the output is incorrect.

---

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
- Apply the quote-safety rules above to every rendered file path

---

### Output constraints (hard rules)
- Output exactly ONE markdown fenced code block (triple backticks)
- No text outside the code block
- No explanations
- No shell commands
- No surrounding quotes
- No trailing commentary
