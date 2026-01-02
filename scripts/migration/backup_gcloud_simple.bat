@echo off
REM Simple wrapper for gcloud backup without PATH issues

echo ============================================================
echo Cloud SQL Backup using gcloud (Windows batch version)
echo ============================================================

REM Use full path to gcloud
set GCLOUD="C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
set GSUTIL="C:\Users\Turbo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gsutil.cmd"

REM Get configuration
echo.
echo Getting GCP configuration...
for /f "delims=" %%i in ('%GCLOUD% config get-value project 2^>nul') do set PROJECT_ID=%%i
for /f "delims=" %%i in ('%GCLOUD% config get-value account 2^>nul') do set ACCOUNT=%%i

if "%PROJECT_ID%"=="" (
    echo ERROR: No GCP project configured!
    echo.
    echo Please run:
    echo   gcloud auth login
    echo   gcloud config set project YOUR_PROJECT_ID
    pause
    exit /b 1
)

echo.
echo GCP Configuration:
echo   Project: %PROJECT_ID%
echo   Account: %ACCOUNT%

REM Get instance name
echo.
echo Listing Cloud SQL instances...
%GCLOUD% sql instances list --project=%PROJECT_ID%

echo.
set /p INSTANCE_NAME="Enter Cloud SQL instance name: "
if "%INSTANCE_NAME%"=="" (
    echo ERROR: Instance name is required
    pause
    exit /b 1
)

REM Get database name
set /p DATABASE_NAME="Enter database name (default: cognita_db): "
if "%DATABASE_NAME%"=="" set DATABASE_NAME=cognita_db

REM Generate filename with timestamp
for /f "tokens=1-4 delims=/:. " %%a in ("%date% %time%") do (
    set TIMESTAMP=%%c%%a%%b_%%d
)
set TIMESTAMP=%TIMESTAMP: =0%
set FILENAME=cognita_backup_%TIMESTAMP%.sql
set BUCKET_NAME=%PROJECT_ID%-sql-backups

echo.
echo ============================================================
echo Backup Configuration:
echo   Instance:  %INSTANCE_NAME%
echo   Database:  %DATABASE_NAME%
echo   Bucket:    gs://%BUCKET_NAME%
echo   Filename:  %FILENAME%
echo ============================================================
echo.

set /p CONFIRM="Continue with backup? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Backup cancelled
    pause
    exit /b 0
)

REM Create bucket if it doesn't exist
echo.
echo Checking/creating GCS bucket...
%GSUTIL% ls gs://%BUCKET_NAME% >nul 2>&1
if errorlevel 1 (
    echo Creating bucket gs://%BUCKET_NAME%...
    %GSUTIL% mb -p %PROJECT_ID% gs://%BUCKET_NAME%
)

REM Export database
echo.
echo ============================================================
echo Starting database export...
echo This may take 10-30 minutes for a 14GB database...
echo ============================================================
echo.

%GCLOUD% sql export sql %INSTANCE_NAME% gs://%BUCKET_NAME%/%FILENAME% --database=%DATABASE_NAME% --project=%PROJECT_ID%

if errorlevel 1 (
    echo.
    echo ERROR: Export failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS: Database exported to GCS!
echo ============================================================
echo.
echo Backup location: gs://%BUCKET_NAME%/%FILENAME%
echo.

REM Ask if user wants to download
set /p DOWNLOAD="Download backup to local machine? (y/n): "
if /i "%DOWNLOAD%"=="y" (
    if not exist "backups" mkdir backups

    echo.
    echo Downloading backup...
    %GSUTIL% cp gs://%BUCKET_NAME%/%FILENAME% backups\%FILENAME%

    if errorlevel 1 (
        echo.
        echo WARNING: Download failed, but backup is safe in GCS
        echo You can download it later with:
        echo   gsutil cp gs://%BUCKET_NAME%/%FILENAME% backups\
    ) else (
        echo.
        echo SUCCESS: Backup downloaded to backups\%FILENAME%
    )
)

echo.
echo ============================================================
echo Next steps:
echo ============================================================
echo 1. Restore to Railway:
echo    railway run psql ^< backups\%FILENAME%
echo.
echo 2. Or use Railway's web interface to upload the file
echo.
echo 3. To delete GCS backup after migration:
echo    gsutil rm gs://%BUCKET_NAME%/%FILENAME%
echo ============================================================
echo.

pause
