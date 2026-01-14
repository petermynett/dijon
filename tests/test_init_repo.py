from __future__ import annotations

import shutil
from pathlib import Path

import pytest

# Import the script module directly (not as a subprocess)
import sys
from importlib.util import spec_from_file_location, module_from_spec

# Load init_repo.py as a module
INIT_REPO_PATH = Path(__file__).parent.parent / "scripts" / "init_repo.py"
spec = spec_from_file_location("init_repo", INIT_REPO_PATH)
init_repo = module_from_spec(spec)
spec.loader.exec_module(init_repo)  # type: ignore[union-attr]


@pytest.mark.integration
def test_ensure_runtime_dirs_creates_all_directories(project_root: Path) -> None:
    """Test that ensure_runtime_dirs creates all required directories."""
    expected_dirs = ["data", "db", "logs", ".secrets"]
    
    # Ensure directories don't exist initially
    for d in expected_dirs:
        dir_path = project_root / d
        if dir_path.exists():
            shutil.rmtree(dir_path)
    
    # Run the function
    created = init_repo.ensure_runtime_dirs(project_root)
    
    # Verify all directories were created
    assert set(created) == set(expected_dirs)
    for d in expected_dirs:
        dir_path = project_root / d
        assert dir_path.exists(), f"Directory {d} should exist"
        assert dir_path.is_dir(), f"{d} should be a directory"


@pytest.mark.integration
def test_ensure_runtime_dirs_is_idempotent(project_root: Path) -> None:
    """Test that ensure_runtime_dirs can be called multiple times safely."""
    # First call
    dirs1 = init_repo.ensure_runtime_dirs(project_root)
    
    # Second call
    dirs2 = init_repo.ensure_runtime_dirs(project_root)
    
    # Should return the same directories
    assert set(dirs1) == set(dirs2)
    
    # All directories should still exist
    for d in dirs1:
        assert (project_root / d).exists()
