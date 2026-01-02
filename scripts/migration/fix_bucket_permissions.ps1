# Fix GCS bucket permissions for Cloud SQL export

$GCLOUD = "C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$GSUTIL = "C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gsutil.cmd"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Fixing GCS Bucket Permissions for Cloud SQL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Get project ID
$PROJECT_ID = & $GCLOUD config get-value project 2>$null
$BUCKET_NAME = "$PROJECT_ID-sql-backups"

Write-Host "Project: $PROJECT_ID" -ForegroundColor Green
Write-Host "Bucket:  gs://$BUCKET_NAME" -ForegroundColor Green
Write-Host ""

# Get Cloud SQL service account
Write-Host "Getting Cloud SQL service account..." -ForegroundColor Yellow
$SERVICE_ACCOUNT = & $GCLOUD sql instances describe psql-remote-linux --project=$PROJECT_ID --format="value(serviceAccountEmailAddress)"

if ([string]::IsNullOrEmpty($SERVICE_ACCOUNT)) {
    Write-Host "ERROR: Could not get service account" -ForegroundColor Red
    exit 1
}

Write-Host "Service Account: $SERVICE_ACCOUNT" -ForegroundColor Green
Write-Host ""

# Grant permissions
Write-Host "Granting storage.objectAdmin role to service account..." -ForegroundColor Yellow
& $GSUTIL iam ch serviceAccount:${SERVICE_ACCOUNT}:objectAdmin "gs://$BUCKET_NAME"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to grant permissions" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "SUCCESS: Permissions granted!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run the backup script again:" -ForegroundColor Yellow
Write-Host "  .\scripts\migration\backup_gcloud.ps1" -ForegroundColor Cyan
Write-Host ""
