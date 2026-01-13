"""Pipeline orchestration layer.

Import policy:
- CLI imports only from `pipeline.*` for orchestration (verbs).
- `pipeline.*` may call `sources.*` as helpers/adapters.
- `sources.*` must not call `pipeline.*`.

See `pipeline/readme.md` for universal pipeline checklist and verb-specific checklists in rules 410/420/430.
"""


