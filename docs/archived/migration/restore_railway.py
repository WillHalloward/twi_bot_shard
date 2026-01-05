#!/usr/bin/env python3
"""Restore script for importing database backup to Railway PostgreSQL.

This script automates the process of restoring a pg_dump backup to
Railway's PostgreSQL, with proper error handling and verification.

Usage:
    python scripts/migration/restore_railway.py --input backups/cognita_backup.dump

    Or let Railway CLI provide credentials automatically:
    railway run python scripts/migration/restore_railway.py --input backups/cognita_backup.dump

Environment variables (automatically provided by Railway):
    - DATABASE_URL: Full PostgreSQL connection string
    OR
    - PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE: Individual connection params
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def run_command(cmd: list[str], description: str, env: dict | None = None) -> bool:
    """Run a shell command with error handling.

    Args:
        cmd: Command and arguments as list
        description: Description of what the command does
        env: Optional environment variables

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'=' * 60}")
    print(f"📋 {description}")
    print(f"{'=' * 60}")
    # Don't print password in command
    safe_cmd = " ".join(cmd).replace(os.getenv("PGPASSWORD", ""), "***")
    print(f"Command: {safe_cmd}\n")

    try:
        process = subprocess.Popen(
            cmd,
            env=env or os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Stream output in real-time
        for line in process.stdout:
            print(line, end="")

        process.wait()

        if process.returncode != 0:
            print(f"\n❌ {description} - FAILED (exit code {process.returncode})")
            return False

        print(f"\n✅ {description} - SUCCESS\n")
        return True
    except FileNotFoundError:
        print(f"\n❌ Command not found: {cmd[0]}")
        print("Please ensure PostgreSQL client tools (pg_restore, psql) are installed.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def get_railway_credentials():
    """Get Railway database credentials from environment.

    Returns:
        Dictionary with connection details, or None if not available
    """
    # Try DATABASE_URL first (Railway's standard format)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "user": parsed.username,
            "password": parsed.password,
            "database": parsed.path[1:],  # Remove leading '/'
        }

    # Fall back to individual PG* variables
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


def verify_backup_file(backup_path: Path) -> bool:
    """Verify that backup file exists and is valid.

    Args:
        backup_path: Path to backup file

    Returns:
        True if valid, False otherwise
    """
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_path}")
        return False

    # Check if file is compressed
    if backup_path.suffix == ".gz":
        print(f"📦 Detected compressed backup: {backup_path}")
        print("💡 Tip: The script will automatically decompress during restore")

    # Check file size
    size_bytes = backup_path.stat().st_size
    size_gb = size_bytes / (1024**3)
    size_mb = size_bytes / (1024**2)

    if size_gb >= 1:
        print(f"📏 Backup size: {size_gb:.2f} GB")
    else:
        print(f"📏 Backup size: {size_mb:.2f} MB")

    if size_bytes == 0:
        print("❌ Backup file is empty!")
        return False

    return True


def test_connection(creds: dict) -> bool:
    """Test connection to Railway database.

    Args:
        creds: Dictionary with connection credentials

    Returns:
        True if connection successful, False otherwise
    """
    print("\n🔌 Testing connection to Railway PostgreSQL...")

    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    test_cmd = [
        "psql",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['user']}",
        f"--dbname={creds['database']}",
        "--command=SELECT version();",
    ]

    return run_command(test_cmd, "Testing database connection", env)


def get_table_count(creds: dict) -> int | None:
    """Get current table count in database.

    Args:
        creds: Dictionary with connection credentials

    Returns:
        Number of tables, or None if query failed
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    query_cmd = [
        "psql",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['user']}",
        f"--dbname={creds['database']}",
        "--tuples-only",
        "--no-align",
        "--command=SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';",
    ]

    try:
        result = subprocess.run(
            query_cmd, env=env, capture_output=True, text=True, check=True
        )
        return int(result.stdout.strip())
    except Exception:
        return None


def main():
    """Main restore execution."""
    parser = argparse.ArgumentParser(
        description="Restore database backup to Railway PostgreSQL"
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to backup file (e.g., backups/cognita_backup.dump)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Drop existing database objects before restore (use with caution!)",
    )
    parser.add_argument(
        "--skip-verify", action="store_true", help="Skip post-restore verification"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🚂 Railway Database Restore Script")
    print("=" * 60)

    # Get Railway credentials
    creds = get_railway_credentials()

    if not creds:
        print("\n❌ Railway database credentials not found!")
        print("\nPlease either:")
        print(
            "1. Run with Railway CLI: railway run python scripts/migration/restore_railway.py -i <file>"
        )
        print("2. Set DATABASE_URL environment variable")
        print(
            "3. Set PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE environment variables"
        )
        print("\nTo get Railway credentials:")
        print("  railway variables  # List all variables")
        sys.exit(1)

    # Verify backup file
    backup_path = Path(args.input)
    if not verify_backup_file(backup_path):
        sys.exit(1)

    # Display configuration
    print("\n📊 Restore Configuration:")
    print(f"  Host:     {creds['host']}")
    print(f"  Port:     {creds['port']}")
    print(f"  User:     {creds['user']}")
    print(f"  Database: {creds['database']}")
    print(f"  Input:    {backup_path}")
    print(f"  Clean:    {'Yes (⚠️ DESTRUCTIVE)' if args.clean else 'No'}")

    # Test connection
    if not test_connection(creds):
        print("\n❌ Cannot connect to Railway database. Please check credentials.")
        sys.exit(1)

    # Check if database already has tables
    table_count = get_table_count(creds)
    if table_count and table_count > 0:
        print(f"\n⚠️  WARNING: Database already contains {table_count} tables!")
        if not args.clean:
            print("Consider using --clean flag to drop existing objects first.")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() not in ["y", "yes"]:
            print("❌ Restore cancelled")
            sys.exit(0)

    # Final confirmation
    print("\n⚠️  This will restore the backup to Railway PostgreSQL.")
    print("⏱️  Expected time: 15-30 minutes for 14GB database")
    response = input("\nProceed with restore? (y/n): ")
    if response.lower() not in ["y", "yes"]:
        print("❌ Restore cancelled")
        sys.exit(0)

    # Set up environment for pg_restore
    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    # Build pg_restore command
    restore_cmd = [
        "pg_restore",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--username={creds['user']}",
        f"--dbname={creds['database']}",
        "--verbose",
        "--no-owner",  # Don't try to restore ownership
        "--no-acl",  # Don't try to restore access privileges
    ]

    if args.clean:
        restore_cmd.append("--clean")

    # Handle compressed backups
    if backup_path.suffix == ".gz":
        print("\n🗜️  Detected gzip compression, will decompress on-the-fly...")
        # Use gunzip -c to decompress and pipe to pg_restore
        decompress_cmd = ["gunzip", "-c", str(backup_path)]
        restore_cmd_without_file = restore_cmd  # pg_restore will read from stdin

        try:
            print("\n🔄 Starting restore from compressed backup...")
            print("⏱️  This may take 15-30 minutes...\n")

            decompress_proc = subprocess.Popen(
                decompress_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            restore_proc = subprocess.Popen(
                restore_cmd_without_file,
                stdin=decompress_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            decompress_proc.stdout.close()

            # Stream output
            for line in restore_proc.stdout:
                print(line, end="")

            restore_proc.wait()

            if restore_proc.returncode != 0:
                print(f"\n❌ Restore failed with exit code {restore_proc.returncode}")
                sys.exit(1)

        except Exception as e:
            print(f"\n❌ Error during restore: {e}")
            sys.exit(1)

    else:
        # Uncompressed backup
        restore_cmd.append(str(backup_path))

        print("\n🔄 Starting restore...")
        print("⏱️  This may take 15-30 minutes...\n")

        if not run_command(restore_cmd, "Restoring database", env):
            print("\n❌ Restore failed")
            sys.exit(1)

    print("\n✅ Restore completed!")

    # Verification
    if not args.skip_verify:
        print("\n🔍 Verifying restore...")

        # Run ANALYZE to update statistics
        print("\n📊 Updating database statistics...")
        analyze_cmd = [
            "psql",
            f"--host={creds['host']}",
            f"--port={creds['port']}",
            f"--username={creds['user']}",
            f"--dbname={creds['database']}",
            "--command=ANALYZE;",
        ]
        run_command(analyze_cmd, "Running ANALYZE", env)

        # Check table count
        new_table_count = get_table_count(creds)
        if new_table_count:
            print(f"\n📊 Total tables restored: {new_table_count}")

        # Check database size
        size_query = "SELECT pg_size_pretty(pg_database_size(current_database()));"
        size_cmd = [
            "psql",
            f"--host={creds['host']}",
            f"--port={creds['port']}",
            f"--username={creds['user']}",
            f"--dbname={creds['database']}",
            "--tuples-only",
            "--no-align",
            f"--command={size_query}",
        ]

        try:
            result = subprocess.run(
                size_cmd, env=env, capture_output=True, text=True, check=True
            )
            db_size = result.stdout.strip()
            print(f"💾 Database size: {db_size}")
        except Exception:
            pass

        # List tables
        print("\n📋 Listing restored tables...")
        list_cmd = [
            "psql",
            f"--host={creds['host']}",
            f"--port={creds['port']}",
            f"--username={creds['user']}",
            f"--dbname={creds['database']}",
            "--command=\\dt",
        ]
        run_command(list_cmd, "Listing tables", env)

    # Summary
    print("\n" + "=" * 60)
    print("✅ RESTORE COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Test bot connection to Railway database:")
    print("   railway run python main.py")
    print("\n2. Verify critical data:")
    print("   railway run psql -c 'SELECT COUNT(*) FROM messages;'")
    print("   railway run psql -c 'SELECT COUNT(*) FROM gallery_mementos;'")
    print("\n3. Run database optimizations:")
    print("   railway run psql -f database/optimizations/base.sql")
    print("\n4. Deploy bot to Railway:")
    print("   git push origin master  # If GitHub connected")
    print("   railway up  # Or deploy via CLI")
    print("=" * 60)


if __name__ == "__main__":
    main()
