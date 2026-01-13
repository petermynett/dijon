# /commit-full

Perform a deep, safety-first commit with cross-file dependency tracking,
breaking change detection, and git history context. This command is intended
for large or architectural changes and prioritizes correctness over speed.

This command NEVER auto-includes untracked files.

## Modifiers

Dry Run: `/commit-full --dry-run` or `/commit-full -n`

When dry-run is specified:
1. Run all pre-flight and safety checks
2. Run `git status` and `git diff --stat`
3. Detect and report any danger flags
4. Perform full analysis as normal
5. Generate the full detailed commit message
6. Display:
   - Current branch and upstream
   - All detected danger flags
   - Files that would be staged (if any)
   - Whether auto-staging would occur or be blocked
   - Full proposed commit message
7. DO NOT run `git add`, `git commit`, or `git push`
8. End with: "Run `/commit-full` or say 'commit it' to execute."

## Workflow

### Pre-Flight Checks (Fail Fast)

1. Not detached
   - Run: `git rev-parse --abbrev-ref HEAD`
   - If output is `HEAD`, fail with:
     "❌ Detached HEAD. Checkout a branch first."

2. Origin remote exists
   - Run: `git remote -v`
   - If no `origin` push URL exists, fail with:
     "❌ No remote 'origin' configured. Fix: git remote add origin <url>"

3. Upstream tracking branch exists
   - Run: `git rev-parse --abbrev-ref --symbolic-full-name @{u}`
   - If missing, fail with:
     "❌ No upstream tracking branch set. Fix: git push -u origin <branch>"

4. Not mid-merge / rebase / conflict
   - Run: `git diff --name-only --diff-filter=U`
   - If any output, fail with:
     "❌ Unresolved merge conflicts. Resolve before committing."
   - Check `git status` for merge/rebase indicators (e.g., `.git/MERGE_HEAD`, `.git/REBASE_HEAD`)
   - If merge or rebase in progress, fail with:
     "❌ Merge/rebase in progress. Complete or abort before committing."

5. Echo branch info (print this)
   ```
   Current branch: <branch>
   Upstream:       <upstream>
   Will push to:   <upstream>
   ```

## Assess Changes (Always Run)

Run:
- `git status`
- `git diff --stat`
- `git log -5 --oneline`

## Danger Flags (Auto-Staging Blockers)

If ANY of the following are true, DO NOT auto-stage.

A) Untracked files present
- Run: `git ls-files --others --exclude-standard`
- Policy:
  - Untracked files are NEVER auto-included.
  - User must explicitly decide what to do.

B) File deletions detected
- Run: `git diff --name-status --diff-filter=D`
- Policy:
  - Deletions require explicit confirmation.

C) New top-level directories detected
- Any untracked directory at repo root triggers danger.

D) Risky paths modified
- Any changes under:
  - `data/`
  - `db/snapshots/`
  - `env/`
  - `ztemp/`
  trigger danger.

E) Large untracked files
- Any untracked file exceeding 2 MB triggers danger.
- Check size with: `git ls-files --others --exclude-standard | xargs -I {} sh -c 'test -f {} && test $(stat -f%z {} 2>/dev/null || stat -c%s {} 2>/dev/null || echo 0) -gt 2097152 && echo {}'`

## Staging Policy

If NO danger flags:
- Stage all changes to tracked files (untracked files excluded by danger flag check).
- Run: `git add -A`
- Check exit code: if non-zero, fail immediately with: "❌ git add failed: [stderr]"
- Then show: `git status`

If ANY danger flag:
- STOP. Do NOT auto-stage.
- Explain which danger flags triggered.
- Present options:
  1) Stage specific files explicitly (user chooses exact paths)
  2) Stash: `git stash push -u -m "wip before commit"` then rerun `/commit-full`
  3) Abort (no changes made)

## Analysis Requirements (Mandatory)

The following analyses MUST be performed and reflected explicitly in the commit message.

**Note:** For very large changesets (50+ files), full diff reading may take longer but is required for thorough analysis.

### 1) Read diffs for all changed files
- Read full diffs for all changed files, not just `--stat`.

### 2) Cross-File Dependencies
- Identify imports or references between changed files.
- Note ripple effects.
- If none found, explicitly state: "None (verified)".

### 3) Usage Context
- Search for callers/usages of modified exports (functions, classes, constants).
- List symbols searched and/or files checked.
- If no external callers found, explicitly state: "No external callers found (verified)".

### 4) Breaking Changes
- Explicitly enumerate any of:
  - Renamed symbols
  - Signature changes
  - Deleted exports
  - Data structure changes
- If none, explicitly state: "None (verified)".

### 5) Git History Context
- Review recent commits with `git log -5 --oneline`.
- Reference related work or state "Fresh work".

## Commit Message Format

<type>: <subject>

## Summary
2–3 sentences describing the intent and outcome of this change.

## Changes
- <file or area>: <what changed and why>
- <file or area>: <what changed and why>

## Dependencies
- <cross-file impacts, or "None (verified)">

## Breaking Changes
- <breaking changes, or "None (verified)">

## Context
- <related commits or "Fresh work">

Files: <comma-separated list or "+N more">

Types:
- `feat`     New feature or capability
- `fix`      Bug fix
- `refactor` Code restructuring without behavior change
- `docs`     Documentation only
- `config`   Configuration, environment, tooling
- `chore`    Maintenance, cleanup, formatting

Formatting rules:
- Use REAL newlines.
- Do NOT embed literal `\n`.
- Write the message to a temp file and commit with: `git commit -F <temp-file>`

## Example

```
refactor: restructure transaction parsing into dedicated module

## Summary
Moved transaction parsing logic from monolithic utils.py into a dedicated 
transactions/ package with separate modules for parsing, validation, and types.
This improves maintainability and allows for easier testing.

## Changes
- manchego/sources/transactions/__init__.py: New package with public API exports
- manchego/sources/transactions/core.py: Main parsing logic moved from utils.py
- manchego/sources/transactions/types.py: TransactionRecord dataclass
- manchego/sources/transactions/validation.py: Field validation helpers
- manchego/utils.py: Removed transaction code, kept general utilities

## Dependencies
- manchego/reports/monthly.py imports parse_transactions (updated import path)
- manchego/cli/import_cmd.py imports TransactionRecord (updated import path)

## Breaking Changes
- parse_transactions() moved from manchego.utils to manchego.sources.transactions
- TransactionRecord now requires 'source' field (was optional)

## Context
- Continues modularization started in commit a1b2c3d (split reports module)

Files: transactions/__init__.py, core.py, types.py, validation.py, utils.py, monthly.py, import_cmd.py
```

## Git Operations

Run sequentially, aborting on failure:
1. `git commit -F <temp-file>`
   - Check exit code: if non-zero, fail immediately with: "❌ git commit failed: [stderr]"
2. `git push`
   - Check exit code: if non-zero, fail immediately with: "❌ git push failed: [stderr]"

## Post-Push Verification

1. **Fetch latest refs**: Run `git fetch --quiet origin`
   - Check exit code: if non-zero, fail with:
     "❌ Push may have succeeded but verification failed. Check remote manually."

2. **Verify sync by comparing SHAs**:
   - Local HEAD: `git rev-parse HEAD`
   - Upstream HEAD: `git rev-parse @{u}`
   - If equal:
     - ✅ Pushed to <upstream>. Local and origin are in sync.
   - If not:
     - ❌ Push verification failed. Local and upstream commits differ.

## When to Use

Use `/commit-full` when:
- Making architectural or structural changes
- Refactoring across multiple modules
- Changing public APIs or interfaces
- Deleting or moving files/directories
- Working on large changes (10+ files)
- Long-term documentation value is required

Do NOT use `/commit-full` for:
- Routine formatting
- Trivial fixes
- Pure documentation-only changes
- Small, isolated edits

## Philosophy

- Large commits deserve explicit verification.
- Automation must surface risk, not hide it.
- If something feels surprising, stop and require human confirmation.
