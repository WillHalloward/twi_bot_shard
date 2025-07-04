#!/usr/bin/env python
"""
Lint script for the Twi Bot Shard project.

This script runs ruff on the project to check for code style issues.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run ruff on the project."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()

    print("Running ruff on the project...")

    # Run ruff check
    result = subprocess.run(
        ["ruff", "check", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    # Print the output
    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Run ruff format (dry run to show what would be changed)
    print("\nChecking formatting issues (dry run)...")
    format_result = subprocess.run(
        ["ruff", "format", ".", "--diff"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    # Print the output
    if format_result.stdout:
        print(format_result.stdout)

    if format_result.stderr:
        print(format_result.stderr, file=sys.stderr)

    # Return the exit code from the check command
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
