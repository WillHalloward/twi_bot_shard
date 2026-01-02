# PowerShell script for Cloud SQL backup
# Works better with PowerShell than .bat files

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Cloud SQL Backup using gcloud (PowerShell version)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Define gcloud paths
$GCLOUD = "C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$GSUTIL = "C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gsutil.cmd"

# Get GCP configuration
Write-Host "Getting GCP configuration..." -ForegroundColor Yellow
$PROJECT_ID = & $GCLOUD config get-value project 2>$null
$ACCOUNT = & $GCLOUD config get-value account 2>$null

if ([string]::IsNullOrEmpty($PROJECT_ID)) {
    Write-Host "ERROR: No GCP project configured!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run:"
    Write-Host "  gcloud auth login"
    Write-Host "  gcloud config set project YOUR_PROJECT_ID"
    exit 1
}

Write-Host ""
Write-Host "GCP Configuration:" -ForegroundColor Green
Write-Host "  Project: $PROJECT_ID"
Write-Host "  Account: $ACCOUNT"

# List Cloud SQL instances
Write-Host ""
Write-Host "Listing Cloud SQL instances..." -ForegroundColor Yellow
& $GCLOUD sql instances list --project=$PROJECT_ID

Write-Host ""
$INSTANCE_NAME = Read-Host "Enter Cloud SQL instance name"
if ([string]::IsNullOrEmpty($INSTANCE_NAME)) {
    Write-Host "ERROR: Instance name is required" -ForegroundColor Red
    exit 1
}

# Get database name
$DATABASE_NAME = Read-Host "Enter database name (default: cognita_db)"
if ([string]::IsNullOrEmpty($DATABASE_NAME)) {
    $DATABASE_NAME = "cognita_db"
}

# Generate filename
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$FILENAME = "cognita_backup_$TIMESTAMP.sql"
$BUCKET_NAME = "$PROJECT_ID-sql-backups"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Backup Configuration:" -ForegroundColor Cyan
Write-Host "  Instance:  $INSTANCE_NAME"
Write-Host "  Database:  $DATABASE_NAME"
Write-Host "  Bucket:    gs://$BUCKET_NAME"
Write-Host "  Filename:  $FILENAME"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$CONFIRM = Read-Host "Continue with backup? (y/n)"
if ($CONFIRM -ne "y") {
    Write-Host "Backup cancelled" -ForegroundColor Yellow
    exit 0
}

# Check/create bucket
Write-Host ""
Write-Host "Checking/creating GCS bucket..." -ForegroundColor Yellow
$bucketExists = & $GSUTIL ls "gs://$BUCKET_NAME" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating bucket gs://$BUCKET_NAME..." -ForegroundColor Yellow
    & $GSUTIL mb -p $PROJECT_ID "gs://$BUCKET_NAME"
} else {
    Write-Host "Bucket already exists" -ForegroundColor Green
}

# Export database
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Starting database export..." -ForegroundColor Cyan
Write-Host "This may take 10-30 minutes for a 14GB database..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

& $GCLOUD sql export sql $INSTANCE_NAME "gs://$BUCKET_NAME/$FILENAME" --database=$DATABASE_NAME --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Export failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "SUCCESS: Database exported to GCS!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backup location: gs://$BUCKET_NAME/$FILENAME" -ForegroundColor Cyan
Write-Host ""

# Ask to download
$DOWNLOAD = Read-Host "Download backup to local machine? (y/n)"
if ($DOWNLOAD -eq "y") {
    if (!(Test-Path "backups")) {
        New-Item -ItemType Directory -Path "backups" | Out-Null
    }

    Write-Host ""
    Write-Host "Downloading backup..." -ForegroundColor Yellow
    & $GSUTIL cp "gs://$BUCKET_NAME/$FILENAME" "backups\$FILENAME"

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "WARNING: Download failed, but backup is safe in GCS" -ForegroundColor Yellow
        Write-Host "You can download it later with:" -ForegroundColor Yellow
        Write-Host "  gsutil cp gs://$BUCKET_NAME/$FILENAME backups\"
    } else {
        Write-Host ""
        Write-Host "SUCCESS: Backup downloaded to backups\$FILENAME" -ForegroundColor Green

        # Show file size
        $fileSize = (Get-Item "backups\$FILENAME").Length
        $fileSizeGB = [math]::Round($fileSize / 1GB, 2)
        $fileSizeMB = [math]::Round($fileSize / 1MB, 2)

        if ($fileSizeGB -ge 1) {
            Write-Host "File size: $fileSizeGB GB" -ForegroundColor Cyan
        } else {
            Write-Host "File size: $fileSizeMB MB" -ForegroundColor Cyan
        }
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "1. Restore to Railway:" -ForegroundColor Yellow
Write-Host "   railway run psql < backups\$FILENAME"
Write-Host ""
Write-Host "2. Or use Railway shell:" -ForegroundColor Yellow
Write-Host "   railway shell"
Write-Host "   psql `$DATABASE_URL < /path/to/backup.sql"
Write-Host ""
Write-Host "3. To delete GCS backup after migration:" -ForegroundColor Yellow
Write-Host "   gsutil rm gs://$BUCKET_NAME/$FILENAME"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
