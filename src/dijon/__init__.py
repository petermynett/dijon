"""
dijon core package.

This rebooted version currently provides:
- A minimal Typer-based CLI (`dijon.cli`)
- Database and schema scaffolding (`db/`, `sql/`)
- Source data layout under `dijon.sources`

Higher-level pipelines and integrations (Google, time tracking, etc.)
will be reintroduced incrementally.

Configuration:
- Shared, project-wide filesystem anchors live in `dijon.global_config`.
- Larger modules that need extra, domain-specific settings should define
  their own `config.py` and build on top of `dijon.global_config`.
"""
