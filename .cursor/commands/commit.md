# /commit

Safely commit tracked changes to git, generate a meaningful commit message,
and push to GitHub. Fast for routine work, intentionally cautious when risk
is detected.

This command NEVER auto-includes untracked files.

## Modifiers

Dry Run: `/commit --dry-run` or `/commit -n`

When dry-run is specified:
1. Run all pre-flight and safety checks
2. Run `git status` and `git diff --stat`
3. Detect and report any danger flags
4. Generate the proposed commit message
5. Display:
   - Current branch and upstream
   - Files that would be staged (if any)
   - Whether auto-staging would occur or be blocked
   - Full proposed commit message
6. DO NOT run `git add`, `git commit`, or `git push`
7. End with: "Run `/commit` or say 'commit it' to execute."

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

## Danger Flags (Auto-Staging Blockers)

If ANY of the following are true, DO NOT run `git add -A`.

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
- Run: `git add -A`
- Check exit code: if non-zero, fail immediately with: "❌ git add failed: [stderr]"
- Then show: `git status`

If ANY danger flag:
- STOP. Do NOT auto-stage.
- Explain which danger flags triggered.
- Present options:
  1) Stage specific files explicitly (user chooses exact paths)
  2) Stash: `git stash push -u -m "wip before commit"` then rerun `/commit`
  3) Abort (no changes made)

## Commit Message Generation

### Change Magnitude

Quick (1–3 files):
- Subject line only

Standard (4–10 files):
- Subject + short bullet list

Significant (read diffs before writing message):
Triggered by any of:
- Deleted files
- New directories
- Changes to `.cursor/`, `env/`, `pyproject.toml`
- Schema changes (`sql/`, `db/migrations/`)
- 10+ files changed

## Commit Message Format

<type>: <subject>

- bullet
- bullet

Files: <comma-separated list or "+N more">

Types:
- `feat`     New feature or capability
- `fix`      Bug fix
- `refactor` Code restructuring without behavior change
- `docs`     Documentation only
- `config`   Configuration, environment, tooling
- `chore`    Maintenance, cleanup, formatting

Formatting rule:
- Use REAL newlines.
- Do NOT embed literal `\n`.
- Write message to a temp file and commit with: `git commit -F <temp-file>`

## Examples

**Quick:**
```
fix: correct import path in transactions module

Files: manchego/sources/transactions/core.py
```

**Standard:**
```
feat: add transaction parsing with validation

- Parse CSV files with header detection
- Validate required fields (date, amount, description)
- Skip malformed rows with warning log

Files: manchego/sources/transactions/core.py, types.py, __init__.py
```

## Git Operations

Run sequentially, aborting on failure:
1. `git commit -F <temp-file>`
   - Check exit code: if non-zero, fail immediately with: "❌ git commit failed: [stderr]"
2. `git push`
   - Check exit code: if non-zero, fail immediately with: "❌ git push failed: [stderr]"

## Post-Push Verification

1. **Fetch latest refs**: Run `git fetch --quiet origin`
   - Check exit code: if non-zero, fail with: "❌ Push may have succeeded but verification failed. Check remote manually."

2. **Verify sync by comparing SHAs**:
   - Local HEAD: `git rev-parse HEAD`
   - Upstream HEAD: `git rev-parse @{u}`
   - If equal:
     - ✅ Pushed to <upstream>. Local and origin are in sync.
   - If not:
     - ❌ Push verification failed. Local and upstream commits differ.

## Error Handling

Pre-Flight Errors:
- Format: `❌ <issue>. Fix: <command>`

Operation Errors:
- Format: `❌ <git command> failed: <stderr>`

Verification Errors:
- Clear statement of mismatch and next step.

## Efficiency Guidelines

- DO rely on `git diff --stat` first
- DO read full diffs only when danger is detected
- DO keep normal commits fast
- DO slow down intentionally when risk appears
- NEVER auto-include untracked files

## Philosophy

- Commits are safety rails.
- Branches are cheap.
- Automation must surface risk, not hide it.
- If something looks surprising, stop and ask the human.
