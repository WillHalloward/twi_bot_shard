#!/usr/bin/env python3
"""Backup script using Google Cloud SQL export (no pg_dump needed).

This script uses gcloud CLI to export your Cloud SQL database directly
to a Google Cloud Storage bucket, then optionally downloads it locally.

This method is easier on Windows and doesn't require PostgreSQL client tools.

Usage:
    python scripts/migration/backup_cloudsql_gcloud.py

Prerequisites:
    - gcloud CLI installed and authenticated
    - A GCS bucket (script can create one for you)

Environment variables:
    - GCP_PROJECT_ID: Your GCP project ID (or set via gcloud config)
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path


def run_command(
    cmd: list[str], description: str, capture_output: bool = False
) -> tuple[bool, str]:
    """Run a shell command with error handling.

    Args:
        cmd: Command and arguments as list
        description: Description of what the command does
        capture_output: Whether to capture and return output

    Returns:
        Tuple of (success: bool, output: str)
    """
    print(f"\n{'=' * 60}")
    print(f"📋 {description}")
    print(f"{'=' * 60}")

    if not capture_output:
        print(f"Command: {' '.join(cmd)}\n")

    try:
        if capture_output:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, result.stdout.strip()
        else:
            result = subprocess.run(cmd, check=True)
            print(f"\n✅ {description} - SUCCESS\n")
            return True, ""
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - FAILED")
        print(f"Error code: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False, ""
    except FileNotFoundError:
        print(f"\n❌ Command not found: {cmd[0]}")
        print("\nPlease install gcloud CLI:")
        print("https://cloud.google.com/sdk/docs/install")
        return False, ""


def get_gcloud_config() -> dict:
    """Get current gcloud configuration.

    Returns:
        Dictionary with project, account, etc.
    """
    success, output = run_command(
        ["gcloud", "config", "list", "--format=json"],
        "Getting gcloud configuration",
        capture_output=True,
    )

    if success:
        return json.loads(output)
    return {}


def list_sql_instances(project_id: str) -> list[dict]:
    """List Cloud SQL instances in project.

    Args:
        project_id: GCP project ID

    Returns:
        List of instance dictionaries
    """
    success, output = run_command(
        [
            "gcloud",
            "sql",
            "instances",
            "list",
            f"--project={project_id}",
            "--format=json",
        ],
        "Listing Cloud SQL instances",
        capture_output=True,
    )

    if success:
        return json.loads(output)
    return []


def get_or_create_bucket(project_id: str, bucket_name: str) -> bool:
    """Get existing or create new GCS bucket.

    Args:
        project_id: GCP project ID
        bucket_name: Bucket name

    Returns:
        True if bucket exists or was created
    """
    # Check if bucket exists
    success, _ = run_command(
        ["gsutil", "ls", f"gs://{bucket_name}"],
        f"Checking if bucket gs://{bucket_name} exists",
        capture_output=True,
    )

    if success:
        print(f"✅ Bucket gs://{bucket_name} already exists")
        return True

    # Create bucket
    print(f"\n📦 Creating bucket gs://{bucket_name}...")
    success, _ = run_command(
        ["gsutil", "mb", "-p", project_id, f"gs://{bucket_name}"],
        f"Creating bucket gs://{bucket_name}",
    )

    return success


def export_database(
    instance_name: str,
    database_name: str,
    bucket_name: str,
    filename: str,
    project_id: str,
) -> bool:
    """Export Cloud SQL database to GCS.

    Args:
        instance_name: Cloud SQL instance name
        database_name: Database name
        bucket_name: GCS bucket name
        filename: Output filename
        project_id: GCP project ID

    Returns:
        True if export successful
    """
    gcs_uri = f"gs://{bucket_name}/{filename}"

    print(f"\n🔄 Exporting database to {gcs_uri}...")
    print("⏱️  This may take 10-30 minutes for a 14GB database...")
    print("You can monitor progress in GCP Console → SQL → Operations\n")

    cmd = [
        "gcloud",
        "sql",
        "export",
        "sql",
        instance_name,
        gcs_uri,
        f"--database={database_name}",
        f"--project={project_id}",
    ]

    # Start export (this will wait for completion)
    success, _ = run_command(cmd, "Exporting database to GCS")

    return success


def download_from_gcs(bucket_name: str, filename: str, local_path: Path) -> bool:
    """Download file from GCS to local machine.

    Args:
        bucket_name: GCS bucket name
        filename: File to download
        local_path: Local destination path

    Returns:
        True if download successful
    """
    gcs_uri = f"gs://{bucket_name}/{filename}"

    print(f"\n⬇️  Downloading {gcs_uri} to {local_path}...")

    cmd = ["gsutil", "cp", gcs_uri, str(local_path)]

    success, _ = run_command(cmd, "Downloading backup from GCS")

    if success:
        size_bytes = local_path.stat().st_size
        size_gb = size_bytes / (1024**3)
        size_mb = size_bytes / (1024**2)

        if size_gb >= 1:
            print(f"📦 Downloaded file size: {size_gb:.2f} GB")
        else:
            print(f"📦 Downloaded file size: {size_mb:.2f} MB")

    return success


def main():
    """Main backup execution."""
    print("=" * 60)
    print("🚀 Cloud SQL Backup Script (using gcloud)")
    print("=" * 60)

    # Get gcloud configuration
    config = get_gcloud_config()

    if not config or "core" not in config:
        print("\n❌ gcloud CLI not configured!")
        print("\nPlease run:")
        print("  gcloud auth login")
        print("  gcloud config set project YOUR_PROJECT_ID")
        sys.exit(1)

    project_id = config.get("core", {}).get("project")
    account = config.get("core", {}).get("account")

    if not project_id:
        print("\n❌ No GCP project configured!")
        print("\nPlease run:")
        print("  gcloud config set project YOUR_PROJECT_ID")
        sys.exit(1)

    print("\n📊 GCP Configuration:")
    print(f"  Project: {project_id}")
    print(f"  Account: {account}")

    # List Cloud SQL instances
    instances = list_sql_instances(project_id)

    if not instances:
        print("\n❌ No Cloud SQL instances found in this project!")
        sys.exit(1)

    print(f"\n💾 Found {len(instances)} Cloud SQL instance(s):")
    for i, instance in enumerate(instances, 1):
        print(
            f"  {i}. {instance['name']} ({instance.get('databaseVersion', 'unknown')})"
        )

    # Select instance
    if len(instances) == 1:
        instance = instances[0]
        print(f"\n✅ Using instance: {instance['name']}")
    else:
        choice = input(f"\nSelect instance (1-{len(instances)}): ").strip()
        try:
            instance = instances[int(choice) - 1]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            sys.exit(1)

    instance_name = instance["name"]

    # Get database name
    database_name = input("\nEnter database name (default: cognita_db): ").strip()
    if not database_name:
        database_name = "cognita_db"

    # Generate filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cognita_backup_{timestamp}.sql"

    # GCS bucket name (must be globally unique)
    bucket_name = f"{project_id}-sql-backups"

    print("\n📊 Backup Configuration:")
    print(f"  Instance:  {instance_name}")
    print(f"  Database:  {database_name}")
    print(f"  GCS Bucket: gs://{bucket_name}")
    print(f"  Filename:  {filename}")

    # Confirm
    response = input("\n⚠️  Continue with backup? (y/n): ")
    if response.lower() not in ["y", "yes"]:
        print("❌ Backup cancelled")
        sys.exit(0)

    # Create or verify bucket
    if not get_or_create_bucket(project_id, bucket_name):
        print("\n❌ Failed to create/access bucket")
        sys.exit(1)

    # Export database
    if not export_database(
        instance_name, database_name, bucket_name, filename, project_id
    ):
        print("\n❌ Database export failed")
        sys.exit(1)

    print("\n✅ Database exported to GCS successfully!")

    # Ask if user wants to download
    response = input("\n⬇️  Download backup to local machine? (y/n): ")

    if response.lower() in ["y", "yes"]:
        # Create backups directory
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        local_path = backup_dir / filename

        if download_from_gcs(bucket_name, filename, local_path):
            print(f"\n✅ Backup downloaded to: {local_path.absolute()}")
        else:
            print("\n⚠️  Download failed, but backup is available in GCS")
            print("You can download it later with:")
            print(f"  gsutil cp gs://{bucket_name}/{filename} backups/")

    # Summary
    print("\n" + "=" * 60)
    print("✅ BACKUP COMPLETE")
    print("=" * 60)
    print(f"\n📦 Backup location: gs://{bucket_name}/{filename}")

    if (backup_dir / filename).exists():
        print(f"📁 Local copy: {(backup_dir / filename).absolute()}")

    print("\nNext steps:")
    print("1. Verify backup (download and inspect if needed)")
    print("\n2. Convert SQL to custom format for pg_restore:")
    print("   # This requires pg_dump/pg_restore tools")
    print("   # OR you can restore the SQL file directly:")
    print(f"   railway run psql < backups/{filename}")

    print("\n3. Alternative: Use this SQL backup directly with Railway:")
    print(f"   railway run psql -f backups/{filename}")

    print("\n4. To delete the GCS backup after migration:")
    print(f"   gsutil rm gs://{bucket_name}/{filename}")
    print("=" * 60)


if __name__ == "__main__":
    main()
