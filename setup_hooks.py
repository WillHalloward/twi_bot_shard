#!/usr/bin/env python
"""Setup script for pre-commit hooks.

This script installs pre-commit and sets up the git hooks for the project.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Install pre-commit and set up git hooks."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()

    print("Setting up pre-commit hooks for the project...")

    # Check if pre-commit is installed
    try:
        subprocess.run(
            ["pre-commit", "--version"],
            check=True,
            capture_output=True,
        )
        print("pre-commit is already installed.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing pre-commit...")
        try:
            # Try to use uv first
            subprocess.run(
                ["uv", "pip", "install", "pre-commit"],
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to pip
            subprocess.run(
                ["pip", "install", "pre-commit"],
                check=True,
            )

    # Install the git hooks
    print("Installing git hooks...")
    result = subprocess.run(
        ["pre-commit", "install"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("Git hooks installed successfully.")
        print(result.stdout)
    else:
        print("Failed to install git hooks:")
        print(result.stderr)
        return result.returncode

    # Run pre-commit on all files
    print("\nRunning pre-commit on all files to verify setup...")
    verify_result = subprocess.run(
        ["pre-commit", "run", "--all-files"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if verify_result.stdout:
        print(verify_result.stdout)

    if verify_result.stderr:
        print(verify_result.stderr, file=sys.stderr)

    if verify_result.returncode == 0:
        print("\nPre-commit hooks are set up and working correctly.")
    else:
        print(
            "\nPre-commit found issues that need to be fixed. Please review the output above."
        )

    return verify_result.returncode


if __name__ == "__main__":
    sys.exit(main())
