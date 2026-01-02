#!/usr/bin/env python3
"""Backup script for exporting database from Google Cloud SQL.

This script automates the process of creating a pg_dump backup from
Cloud SQL, with proper error handling and progress reporting.

Usage:
    python scripts/migration/backup_cloudsql.py

    Or with custom filename:
    python scripts/migration/backup_cloudsql.py --output my_backup.dump

Environment variables required:
    - HOST: Cloud SQL host/IP
    - DB_USER: Database username
    - DB_PASSWORD: Database password (optional, will prompt if not set)
    - DATABASE: Database name
    - PORT: Database port (default: 5432)
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a shell command with error handling.

    Args:
        cmd: Command and arguments as list
        description: Description of what the command does

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"📋 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,  # Show output in real-time
            text=True
        )
        print(f"\n✅ {description} - SUCCESS\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - FAILED")
        print(f"Error code: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"\n❌ Command not found: {cmd[0]}")
        print("Please ensure PostgreSQL client tools (pg_dump) are installed.")
        print("\nInstallation instructions:")
        print("  - Windows: https://www.postgresql.org/download/windows/")
        print("  - Mac: brew install postgresql")
        print("  - Linux: sudo apt-get install postgresql-client")
        return False


def get_env_or_prompt(var_name: str, prompt_text: str, required: bool = True, secret: bool = False) -> str | None:
    """Get environment variable or prompt user.

    Args:
        var_name: Name of environment variable
        prompt_text: Text to show when prompting user
        required: Whether this value is required
        secret: Whether to hide input (for passwords)

    Returns:
        The value, or None if not required and not provided
    """
    value = os.getenv(var_name)

    if not value:
        if secret:
            import getpass
            value = getpass.getpass(f"{prompt_text}: ")
        else:
            value = input(f"{prompt_text}: ").strip()

    if required and not value:
        print(f"❌ Error: {var_name} is required but not provided")
        sys.exit(1)

    return value


def main():
    """Main backup execution."""
    parser = argparse.ArgumentParser(
        description="Backup Google Cloud SQL database using pg_dump"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output filename (default: cognita_backup_YYYYMMDD_HHMMSS.dump)",
        default=None
    )
    parser.add_argument(
        "--compress",
        "-c",
        action="store_true",
        help="Compress backup with gzip after creation"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["custom", "plain", "directory"],
        default="custom",
        help="Backup format (default: custom, recommended for large databases)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 Cloud SQL Database Backup Script")
    print("=" * 60)

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get database connection details
    host = get_env_or_prompt("HOST", "Cloud SQL Host/IP", required=True)
    port = os.getenv("PORT", "5432")
    db_user = get_env_or_prompt("DB_USER", "Database Username", required=True)
    db_password = get_env_or_prompt("DB_PASSWORD", "Database Password", required=True, secret=True)
    database = get_env_or_prompt("DATABASE", "Database Name", required=True)

    # Generate output filename if not provided
    if not args.output:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"cognita_backup_{timestamp}.dump"

    # Create backups directory if it doesn't exist
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)

    backup_path = backup_dir / args.output

    # Display configuration
    print("\n📊 Backup Configuration:")
    print(f"  Host:     {host}")
    print(f"  Port:     {port}")
    print(f"  User:     {db_user}")
    print(f"  Database: {database}")
    print(f"  Output:   {backup_path}")
    print(f"  Format:   {args.format}")
    print(f"  Compress: {'Yes' if args.compress else 'No'}")

    # Confirm before proceeding
    response = input("\n⚠️  Continue with backup? (y/n): ")
    if response.lower() not in ['y', 'yes']:
        print("❌ Backup cancelled")
        sys.exit(0)

    # Set PGPASSWORD environment variable for pg_dump
    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    # Build pg_dump command
    format_flag = {
        "custom": "c",
        "plain": "p",
        "directory": "d"
    }[args.format]

    pg_dump_cmd = [
        "pg_dump",
        f"--host={host}",
        f"--port={port}",
        f"--username={db_user}",
        f"--dbname={database}",
        f"--format={format_flag}",
        "--blobs",
        "--verbose",
        f"--file={backup_path}"
    ]

    # Execute backup
    print("\n🔄 Starting database backup...")
    print("⏱️  This may take 10-30 minutes for a 14GB database...\n")

    # Run pg_dump with custom environment
    try:
        process = subprocess.Popen(
            pg_dump_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Stream output in real-time
        for line in process.stdout:
            print(line, end='')

        process.wait()

        if process.returncode != 0:
            print(f"\n❌ Backup failed with exit code {process.returncode}")
            sys.exit(1)

        print("\n✅ Backup completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during backup: {e}")
        sys.exit(1)

    # Get backup file size
    backup_size = backup_path.stat().st_size
    backup_size_mb = backup_size / (1024 * 1024)
    backup_size_gb = backup_size / (1024 * 1024 * 1024)

    if backup_size_gb >= 1:
        size_str = f"{backup_size_gb:.2f} GB"
    else:
        size_str = f"{backup_size_mb:.2f} MB"

    print(f"\n📦 Backup file size: {size_str}")
    print(f"📁 Backup location: {backup_path.absolute()}")

    # Compress if requested
    if args.compress:
        print("\n🗜️  Compressing backup with gzip...")
        compress_cmd = ["gzip", str(backup_path)]

        if run_command(compress_cmd, "Compressing backup"):
            compressed_path = Path(f"{backup_path}.gz")
            compressed_size = compressed_path.stat().st_size
            compressed_size_mb = compressed_size / (1024 * 1024)
            compressed_size_gb = compressed_size / (1024 * 1024 * 1024)

            if compressed_size_gb >= 1:
                compressed_size_str = f"{compressed_size_gb:.2f} GB"
            else:
                compressed_size_str = f"{compressed_size_mb:.2f} MB"

            compression_ratio = (1 - compressed_size / backup_size) * 100

            print(f"\n📦 Compressed size: {compressed_size_str}")
            print(f"📉 Compression ratio: {compression_ratio:.1f}%")
            print(f"📁 Compressed file: {compressed_path.absolute()}")

    # Summary
    print("\n" + "=" * 60)
    print("✅ BACKUP COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify backup integrity (optional):")
    print(f"   pg_restore --list {backup_path}")
    print("\n2. Proceed with Railway restore:")
    print(f"   python scripts/migration/restore_railway.py --input {backup_path}")
    print("\n3. Keep this backup safe until migration is verified (1-2 weeks)")
    print("=" * 60)


if __name__ == "__main__":
    main()
