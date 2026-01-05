#!/usr/bin/env python3
"""Restore script for SQL dump files (from gcloud export) to Railway.

This script restores a plain SQL dump (not pg_dump custom format) to Railway.
Works with SQL files exported from Cloud SQL using gcloud.

Usage:
    railway run python scripts/migration/restore_railway_sql.py --input backups/cognita_backup.sql
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def run_command_with_input(
    cmd: list[str], input_file: Path, description: str, env: dict | None = None
) -> bool:
    """Run a command with file input.

    Args:
        cmd: Command and arguments as list
        input_file: File to pipe as input
        description: Description of what the command does
        env: Optional environment variables

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'=' * 60}")
    print(f"📋 {description}")
    print(f"{'=' * 60}\n")

    try:
        with open(input_file, encoding="utf-8") as f:
            process = subprocess.Popen(
                cmd,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env or os.environ,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Stream output in real-time
            for line in process.stdout:
                # Filter out noise
                if not line.strip().startswith("SET"):
                    print(line, end="")

            process.wait()

            if process.returncode != 0:
                print(f"\n❌ {description} - FAILED (exit code {process.returncode})")
                return False

            print(f"\n✅ {description} - SUCCESS\n")
            return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def get_railway_credentials():
    """Get Railway database credentials from environment.

    Returns:
        Dictionary with connection details, or None if not available
    """
    # Try DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "user": parsed.username,
            "password": parsed.password,
            "database": parsed.path[1:],
        }

    # Fall back to PG* variables
    if all(
        [
            os.getenv("PGHOST"),
            os.getenv("PGUSER"),
            os.getenv("PGPASSWORD"),
            os.getenv("PGDATABASE"),
        ]
    ):
        return {
            "host": os.getenv("PGHOST"),
            "port": int(os.getenv("PGPORT", "5432")),
            "user": os.getenv("PGUSER"),
            "password": os.getenv("PGPASSWORD"),
            "database": os.getenv("PGDATABASE"),
        }

    return None


def test_connection(creds: dict) -> bool:
    """Test connection to Railway database.

    Args:
        creds: Dictionary with connection credentials

    Returns:
        True if connection successful
    """
    print("\n🔌 Testing connection to Railway PostgreSQL...")

    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    try:
        result = subprocess.run(
            [
                "psql",
                f"--host={creds['host']}",
                f"--port={creds['port']}",
                f"--username={creds['user']}",
                f"--dbname={creds['database']}",
                "--command=SELECT 1;",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        print("✅ Connection successful!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Connection failed!")
        return False
    except FileNotFoundError:
        print("❌ psql command not found!")
        print("\nThis script requires PostgreSQL client tools.")
        print("Since you're on Windows and don't have pg tools, use this instead:")
        print("\n  # Upload SQL file to Railway and restore there:")
        print("  railway run bash")
        print("  # Then in Railway shell:")
        print("  psql $DATABASE_URL < /path/to/backup.sql")
        return False


def main():
    """Main restore execution."""
    parser = argparse.ArgumentParser(
        description="Restore SQL backup to Railway PostgreSQL"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to SQL backup file")

    args = parser.parse_args()

    print("=" * 60)
    print("🚂 Railway SQL Restore Script")
    print("=" * 60)

    # Verify input file
    input_file = Path(args.input)
    if not input_file.exists():
        print(f"\n❌ File not found: {input_file}")
        sys.exit(1)

    size_bytes = input_file.stat().st_size
    size_gb = size_bytes / (1024**3)
    size_mb = size_bytes / (1024**2)

    if size_gb >= 1:
        print(f"\n📏 Backup size: {size_gb:.2f} GB")
    else:
        print(f"\n📏 Backup size: {size_mb:.2f} MB")

    # Get Railway credentials
    creds = get_railway_credentials()

    if not creds:
        print("\n❌ Railway database credentials not found!")
        print("\nPlease run with Railway CLI:")
        print(f"  railway run python {sys.argv[0]} --input {args.input}")
        sys.exit(1)

    print("\n📊 Railway Configuration:")
    print(f"  Host:     {creds['host']}")
    print(f"  Database: {creds['database']}")

    # Test connection
    if not test_connection(creds):
        sys.exit(1)

    # Confirm
    print(f"\n⚠️  This will restore {input_file.name} to Railway PostgreSQL")
    print("⏱️  Expected time: 15-30 minutes for 14GB")
    response = input("\nProceed? (y/n): ")
    if response.lower() not in ["y", "yes"]:
        print("❌ Restore cancelled")
        sys.exit(0)

    # Set up environment
    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    # Restore using psql
    psql_cmd = [
        "psql",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['user']}",
        f"--dbname={creds['database']}",
    ]

    print("\n🔄 Starting restore...")
    print("⏱️  This will take 15-30 minutes...\n")

    if not run_command_with_input(psql_cmd, input_file, "Restoring database", env):
        print("\n❌ Restore failed!")
        sys.exit(1)

    print("\n✅ Restore completed!")

    # Verify
    print("\n🔍 Running ANALYZE to update statistics...")
    analyze_cmd = [
        "psql",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['user']}",
        f"--dbname={creds['database']}",
        "--command=ANALYZE;",
    ]

    subprocess.run(analyze_cmd, env=env)

    print("\n" + "=" * 60)
    print("✅ RESTORE COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Test bot: railway run python main.py")
    print("2. Verify data: railway run psql -c 'SELECT COUNT(*) FROM messages;'")
    print("3. Deploy: git push origin master")
    print("=" * 60)


if __name__ == "__main__":
    main()
