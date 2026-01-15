"""Global, project-wide configuration constants.

This module intentionally contains **no business logic** – only simple,
shared filesystem anchors and cross-cutting constants that many modules
can import.

Larger or more specialized modules should define their own `config.py`
files that build on top of these anchors. Smaller modules can import
directly from global_config.
"""

from pathlib import Path

# Core roots
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
# PROJECT_ROOT is the repo root (where pyproject.toml and data/ live)
# From src/dijon/global_config.py, go up two levels: src/dijon -> src -> repo root
PROJECT_ROOT: Path = PACKAGE_ROOT.parent.parent

# Core Names
PROJECT_NAME = "dijon"
PACKAGE_NAME = "dijon"


# Data directories
DATA_DIR: Path = PROJECT_ROOT / "data"
ACQUISITION_DIR: Path = DATA_DIR / "acquisition"
RAW_DIR: Path = DATA_DIR / "raw"
NORMAL_DIR: Path = DATA_DIR / "normal"
OPTIMIZED_DIR: Path = DATA_DIR / "optimized"
ANNOTATIONS_DIR: Path = DATA_DIR / "annotations"
# Legacy: kept for backward compatibility, but deprecated
OVERRIDES_DIR: Path = DATA_DIR / "overrides"

# Logs directories
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# Database directories
DB_DIR: Path = PROJECT_ROOT / "db"
DB_MIGRATIONS_DIR: Path = DB_DIR / "migrations"
DB_SNAPSHOTS_DIR: Path = DB_DIR / "snapshots"
DB_SNAPSHOTS_DEV_DIR: Path = DB_SNAPSHOTS_DIR / "dev"
DB_SNAPSHOTS_PROD_DIR: Path = DB_SNAPSHOTS_DIR / "prod"

# SQL directory
SQL_DIR: Path = PROJECT_ROOT / "sql"

# Analytics database directories
ANALYTICS_DB_DIR: Path = DB_DIR / "analytics"
ANALYTICS_MIGRATIONS_DIR: Path = DB_MIGRATIONS_DIR / "analytics"

# Placeholders for future internal Python-package modules
SOURCES_DIR: Path = PACKAGE_ROOT / "sources"
PIPELINES_DIR: Path = PACKAGE_ROOT / "pipelines"
EXPERIMENTS_DIR: Path = PACKAGE_ROOT / "experiments"


