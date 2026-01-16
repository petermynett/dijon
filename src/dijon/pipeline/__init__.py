"""Pipeline orchestration layer.

Pipeline modules are organized by verb (acquire, ingest, load, reset), with datasource-specific
implementations as modules within each verb package:
- `pipeline/acquire/youtube.py` - YouTube acquisition
- `pipeline/ingest/youtube.py` - YouTube ingestion
- `pipeline/acquire/example.py` - Example acquisition
- etc.

Import policy:
- CLI imports only from `pipeline.*` for orchestration (verbs).
- `pipeline.*` may call `sources.*` as helpers/adapters.
- `sources.*` must not call `pipeline.*`.
"""


