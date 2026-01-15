# /commit — fast non-interactive commit + push

## Objective
Commit all current changes and push to GitHub with a short, meaningful message.
Fail loudly if:
- Any untracked file larger than 2MB would be added.
- Any staged content looks like it contains secrets (common token/key patterns) or forbidden secret-ish filenames.

## Important (no prompts)
This command is designed to run without human confirmation.
In Cursor, make sure Agent terminal execution is allowed to auto-run tools/commands (e.g. "Run Everything"), otherwise Cursor may still prompt before running terminal commands.  [oai_citation:1‡Cursor](https://cursor.com/docs/agent/terminal?utm_source=chatgpt.com)

## Step 1 — Inspect changes (so you can write a good message)
Run these and read the output:
- `git status --porcelain`
- `git diff --stat`
- `git diff --name-status`

Then write a commit message:
- One line, <= 72 chars.
- Prefer Conventional Commit style: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`
- Mention the primary “why/what” based on the diff summary (not every file).

## Step 2 — Preflight + stage + secret scan + commit + push (single terminal run)
When you have the message, run the block below by substituting the message after `MSG=`.

```bash
bash -lc '
set -euo pipefail

MAX_UNTRACKED=$((2*1024*1024))

die(){ echo "ERROR: $*" >&2; exit 1; }

# --- 1) Block large untracked files (>2MB) ---
# List untracked (excluding ignored) and check sizes (mac+linux)
mapfile -t UNTRACKED < <(git ls-files --others --exclude-standard || true)

too_big=0
for f in "${UNTRACKED[@]:-}"; do
  [ -f "$f" ] || continue
  if stat -f%z "$f" >/dev/null 2>&1; then sz=$(stat -f%z "$f"); else sz=$(stat -c%s "$f"); fi
  if [ "$sz" -gt "$MAX_UNTRACKED" ]; then
    echo "Untracked file too large (>2MB): $f (${sz} bytes)" >&2
    too_big=1
  fi
done
[ "$too_big" -eq 0 ] || die "Aborting: large untracked file(s) detected."

# --- 2) Stage everything ---
git add -A

# Nothing to commit?
git diff --cached --quiet && die "Nothing staged to commit."

# --- 3) Block forbidden filenames (common secret containers) ---
DENY_NAME_REGEX='"'"'(^|/)(\.env(\..*)?|id_rsa|id_ed25519|.*\.pem|.*\.p12|.*\.key|.*credentials(\.json)?|.*secret.*|.*\.kdbx)$'"'"'
bad_names=$(git diff --cached --name-only | grep -E "$DENY_NAME_REGEX" || true)
[ -z "$bad_names" ] || die "Aborting: forbidden filename(s) staged:\n$bad_names"

# --- 4) Secret pattern scan in staged diff ---
DIFF="$(git diff --cached -U0 --no-color || true)"

# A small but useful set of high-signal patterns (tune later if needed)
PATTERNS=(
  "AKIA[0-9A-Z]{16}"                 # AWS access key id
  "ASIA[0-9A-Z]{16}"                 # AWS temp access key id
  "ghp_[A-Za-z0-9]{30,}"             # GitHub classic token
  "github_pat_[A-Za-z0-9_]{20,}"     # GitHub fine-grained token
  "sk-[A-Za-z0-9]{20,}"              # OpenAI-ish key prefix
  "-----BEGIN (RSA|EC|OPENSSH|PGP|PRIVATE) KEY-----"  # private key blocks
  "xox[baprs]-[A-Za-z0-9-]{10,}"     # Slack token-ish
)

for re in "${PATTERNS[@]}"; do
  if echo "$DIFF" | grep -E -n "$re" >/dev/null 2>&1; then
    echo "$DIFF" | grep -E -n "$re" | head -n 20 >&2
    die "Aborting: potential secret matched pattern: $re"
  fi
done

# --- 5) Commit + push ---
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
MSG='"'"'__REPLACE_ME__'"'"'

# Guard: message must not be empty
[ -n "$MSG" ] || die "Commit message is empty."

git commit -m "$MSG"
git push origin "$BRANCH"
echo "OK: pushed to origin/$BRANCH"
'