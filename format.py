#!/usr/bin/env python
"""
Format script for the Twi Bot Shard project.

This script runs Black on the project to format code according to the project's style guidelines.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run Black on the project."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()

    print("Running Black on the project...")

    # Run Black in check mode first to see what would be changed
    check_result = subprocess.run(
        ["black", "--check", "--diff", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    # Print the output
    if check_result.stdout:
        print(check_result.stdout)

    if check_result.stderr:
        print(check_result.stderr, file=sys.stderr)

    # Automatically apply the changes if needed
    if check_result.returncode != 0:
        print("\nApplying changes...")
        format_result = subprocess.run(
            ["black", "."],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # Print the output
        if format_result.stdout:
            print(format_result.stdout)

        if format_result.stderr:
            print(format_result.stderr, file=sys.stderr)

        return format_result.returncode
    else:
        print("\nAll files are already formatted correctly.")

    return check_result.returncode


if __name__ == "__main__":
    sys.exit(main())
