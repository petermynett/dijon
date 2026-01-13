from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path.cwd()
ANSWERS_FILE = PROJECT_ROOT / ".copier-answers.yml"
ORIGIN_FILE = PROJECT_ROOT / ".template_origin.yml"


def _today_yyyy_mm_dd() -> str:
    return datetime.now().date().isoformat()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _extract_answer(text: str, key: str) -> str | None:
    """
    Minimal YAML-ish extraction for simple Copier answers.
    Handles:
      key: value
      key: "value"
      key: 'value'
    (Does NOT handle multi-line or nested YAML.)
    
    NOTE: regex only matches one line answers. For full YAML, implement _extract_answer_yaml().
    
    """
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw in ("null", "Null", "NULL", "~"):
        return None
    if raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2:
        raw = raw[1:-1]
    return raw


def _set_yaml_scalar(doc: str, dotted_key: str, value: str) -> str:
    """
    Set a scalar YAML value by dotted path with very simple assumptions:
    - keys exist in the file
    - indentation is 2 spaces
    - target line is like: <key>: <something>
    """
    keys = dotted_key.split(".")
    lines = doc.splitlines(True)

    # Find the line index for the leaf key, under the chain of parents.
    # We do a simple indentation-based descent.
    indent = 0
    start_idx = 0
    for i, k in enumerate(keys):
        pat = re.compile(rf"^({' ' * indent}){re.escape(k)}\s*:\s*(.*)\n?$")
        found = None
        for j in range(start_idx, len(lines)):
            if pat.match(lines[j]):
                found = j
                break
        if found is None:
            raise ValueError(f"Could not find key path: {'.'.join(keys[: i + 1 ])}")
        start_idx = found + 1
        indent += 2

    leaf_idx = found  # type: ignore[name-defined]
    # Replace leaf line
    leaf_key = keys[-1]
    leaf_indent = " " * (indent - 2)
    lines[leaf_idx] = f"{leaf_indent}{leaf_key}: {value}\n"
    return "".join(lines)


def _append_history_entry(doc: str, entry_block: str) -> str:
    """
    Append a history entry to the 'updates.history: []' section.
    Assumes history is present and either:
      history: []
    or
      history:
        - ...
    """
    if re.search(r"(?m)^\s*history:\s*\[\]\s*$", doc):
        # Replace history: [] with history: + entry
        doc = re.sub(r"(?m)^(\s*)history:\s*\[\]\s*$", r"\1history:\n", doc)
        insert_point = re.search(r"(?m)^\s*history:\s*$", doc)
        if not insert_point:
            raise ValueError("history section not found after normalization")
        # Insert right after the history: line
        idx = insert_point.end()
        return doc[:idx] + "\n" + entry_block + doc[idx:]
    else:
        # Find end of history section by appending at end of file (simple + safe enough)
        # Better to keep history near the end; if you want stricter insertion, we can refine later.
        return doc.rstrip() + "\n" + entry_block


def _history_block(version: str | None, commit: str | None, applied_at: str) -> str:
    v = f'"{version}"' if version else "null"
    c = f'"{commit}"' if commit else "null"
    a = f'"{applied_at}"'
    return (
        "  - version: " + v + "\n"
        "    commit: " + c + "\n"
        "    applied_at: " + a + "\n"
    )


def _ensure_origin_file_exists() -> None:
    if ORIGIN_FILE.exists():
        return
    # If the template didn't render it for some reason, create a minimal one.
    _write_text(
        ORIGIN_FILE,
        "template:\n"
        "  name: null\n"
        "  repository: null\n"
        "  version: null\n"
        "  commit: null\n"
        "\n"
        "project:\n"
        "  name: null\n"
        "  package: null\n"
        "  cli: null\n"
        '  created_at: "UNKNOWN"\n'
        '  copier_answers_file: ".copier-answers.yml"\n'
        "\n"
        "updates:\n"
        "  last_applied:\n"
        "    version: null\n"
        "    commit: null\n"
        "    applied_at: null\n"
        "  history: []\n",
    )


def post_copy() -> None:
    """
    Runs after a fresh project is generated.
    - Sets project.created_at if UNKNOWN or empty
    - Sets updates.last_applied.{version,commit,applied_at}
    - Appends a history entry
    """
    _ensure_origin_file_exists()

    origin = _read_text(ORIGIN_FILE)
    answers = _read_text(ANSWERS_FILE)

    # Template version/commit come from answers if you choose to store them there; otherwise remain null.
    template_version = (
        _extract_answer(answers, "_template_version")
        or _extract_answer(answers, "template_version")
        or _extract_answer(answers, "template_ref")
    )
    template_commit = (
        _extract_answer(answers, "_template_commit")
        or _extract_answer(answers, "template_commit")
    )

    applied_at = _today_yyyy_mm_dd()

    # created_at: only set if UNKNOWN or empty
    if re.search(r'(?m)^\s*created_at:\s*(UNKNOWN|""|\'\'|null)\s*$', origin):
        origin = _set_yaml_scalar(origin, "project.created_at", f'"{applied_at}"')

    origin = _set_yaml_scalar(origin, "updates.last_applied.version", f'"{template_version}"' if template_version else "null")
    origin = _set_yaml_scalar(origin, "updates.last_applied.commit", f'"{template_commit}"' if template_commit else "null")
    origin = _set_yaml_scalar(origin, "updates.last_applied.applied_at", f'"{applied_at}"')

    origin = _append_history_entry(origin, _history_block(template_version, template_commit, applied_at))

    _write_text(ORIGIN_FILE, origin)


def post_update() -> None:
    """
    Runs after copier update.
    - Updates updates.last_applied.{version,commit,applied_at}
    - Appends a history entry
    - Does NOT change project.created_at
    """
    _ensure_origin_file_exists()

    origin = _read_text(ORIGIN_FILE)
    answers = _read_text(ANSWERS_FILE)

    template_version = (
        _extract_answer(answers, "_template_version")
        or _extract_answer(answers, "template_version")
        or _extract_answer(answers, "template_ref")
    )
    template_commit = (
        _extract_answer(answers, "_template_commit")
        or _extract_answer(answers, "template_commit")
    )

    applied_at = _today_yyyy_mm_dd()

    origin = _set_yaml_scalar(origin, "updates.last_applied.version", f'"{template_version}"' if template_version else "null")
    origin = _set_yaml_scalar(origin, "updates.last_applied.commit", f'"{template_commit}"' if template_commit else "null")
    origin = _set_yaml_scalar(origin, "updates.last_applied.applied_at", f'"{applied_at}"')

    origin = _append_history_entry(origin, _history_block(template_version, template_commit, applied_at))

    _write_text(ORIGIN_FILE, origin)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("post_copy", "post_update"):
        print("Usage: python scripts/template_hooks.py [post_copy|post_update]")
        raise SystemExit(2)

    mode = sys.argv[1]
    if mode == "post_copy":
        post_copy()
        return
    if mode == "post_update":
        post_update()
        return


if __name__ == "__main__":
    main()