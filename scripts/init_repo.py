from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def ensure_runtime_dirs(root: Path) -> list[str]:
    """Create local runtime directories (idempotent).
    
    Creates: data/, db/, logs/, .secrets/
    
    Args:
        root: Project root directory where directories should be created.
        
    Returns:
        List of directory names that were ensured (always the same set).
    """
    dirs = ["data", "db", "logs", ".secrets"]
    
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    
    return dirs


def maybe_git_init(root: Path, *, push: bool = False) -> None:
    """Initialize git repository if it doesn't exist (stubbed for auth/remote creation).
    
    If .git/ already exists, this is a no-op.
    Otherwise:
    - Runs `git init`
    - Adds all files (`git add -A`)
    - Creates initial commit
    
    Push behavior:
    - If push=True AND a remote origin exists: attempts push (stubbed for now)
    - Otherwise: prints guidance about setting up remote
    
    Args:
        root: Project root directory.
        push: Whether to attempt pushing to remote (only if remote exists).
    """
    git_dir = root / ".git"
    
    if git_dir.exists():
        print("Git repository already exists, skipping git init.")
        return
    
    print("Initializing git repository...")
    subprocess.run(["git", "init"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=root,
        check=True,
    )
    print("Created initial git commit.")
    
    # Check if remote exists
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0 and push:
        # Remote exists and push requested
        # TODO: Implement push logic with proper auth handling
        print("TODO: Push functionality not yet implemented.")
        print("  Remote origin detected:", result.stdout.strip())
        print("  To push manually: git push -u origin main")
    elif result.returncode != 0:
        # No remote configured
        print("No remote origin configured.")
        print("  To set up remote:")
        print("    1. Create repository on GitHub/GitLab/etc.")
        print("    2. git remote add origin <url>")
        print("    3. git push -u origin main")
    else:
        # Remote exists but push not requested
        print("Remote origin exists but --push not specified.")
        print("  To push: git push -u origin main")


def main() -> None:
    """Main entry point for repo initialization script."""
    parser = argparse.ArgumentParser(
        description="Initialize repository directories and optionally git repository."
    )
    parser.add_argument(
        "--git",
        action="store_true",
        help="Initialize git repository if it doesn't exist.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Attempt to push to remote after git init (requires --git and existing remote).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root directory (default: current working directory).",
    )
    
    args = parser.parse_args()
    
    root = args.root if args.root is not None else Path.cwd()
    root = root.resolve()
    
    # Always create runtime directories
    dirs = ensure_runtime_dirs(root)
    print(f"Initialized runtime dirs: {', '.join(dirs)}")
    
    # Optionally initialize git
    if args.git:
        maybe_git_init(root, push=args.push)
    elif args.push:
        print("Warning: --push requires --git. Ignoring --push.", file=sys.stderr)


if __name__ == "__main__":
    main()
