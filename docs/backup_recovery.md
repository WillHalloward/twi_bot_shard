# Twi Bot Shard Backup and Recovery Guide

This guide provides comprehensive information on backing up the Twi Bot Shard application and its data, as well as procedures for recovery in case of failures.

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Database Backups](#database-backups)
3. [Configuration Backups](#configuration-backups)
4. [Code Repository Backups](#code-repository-backups)
5. [Backup Verification](#backup-verification)
6. [Recovery Procedures](#recovery-procedures)
7. [Disaster Recovery](#disaster-recovery)

## Backup Strategy

The backup strategy for Twi Bot Shard follows these key principles:

1. **Comprehensive Coverage**: Back up all critical components (database, configuration, code)
2. **Regular Schedule**: Perform backups at defined intervals based on data criticality
3. **Multiple Locations**: Store backups in multiple geographic locations
4. **Secure Storage**: Encrypt sensitive backup data
5. **Verified Recovery**: Regularly test backup restoration
6. **Retention Policy**: Maintain backups according to defined retention periods

### Backup Types

| Type | Description | Frequency | Retention |
|------|-------------|-----------|-----------|
| Full Database Backup | Complete backup of the entire database | Daily | 30 days |
| Incremental Database Backup | Backup of changes since last full backup | Hourly | 7 days |
| Configuration Backup | Backup of all configuration files | After changes | 90 days |
| Code Repository Backup | Backup of the code repository | Weekly | 1 year |
| Log Archive | Compressed archive of application logs | Weekly | 90 days |

## Database Backups

The PostgreSQL database is the most critical component to back up as it contains all persistent data for the bot.

### Automated Backup Script

Create a file named `backup_database.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/database"
DB_NAME="twi_bot_shard"
DB_USER="postgres"
RETENTION_DAYS=30

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup
echo "Creating backup: $BACKUP_FILE"
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_FILE

# Set permissions
chmod 600 $BACKUP_FILE

# Remove old backups
find $BACKUP_DIR -name "${DB_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
echo "Backup completed: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"
```

### Setting Up Automated Backups

1. Make the script executable:
   ```bash
   chmod +x backup_database.sh
   ```

2. Schedule with cron:
   ```bash
   # Edit crontab
   crontab -e
   
   # Add this line for daily backups at 2 AM
   0 2 * * * /path/to/backup_database.sh >> /var/log/db_backup.log 2>&1
   ```

### Using Docker

If running in Docker, create a backup container:

```yaml
# Add to docker-compose.yml
services:
  db-backup:
    image: postgres:13-alpine
    volumes:
      - ./backup_database.sh:/backup.sh
      - ./backups:/backups
      - postgres_data:/var/lib/postgresql/data:ro
    environment:
      PGPASSWORD: ${DB_PASSWORD}
    entrypoint: ["/bin/sh", "-c"]
    command: ["crond -f -d 8"]
    depends_on:
      - db
```

Add a cron job to the container:
```bash
# /etc/cron.d/backup-cron
0 2 * * * root /backup.sh
```

### Cloud Storage Backup

To store backups in cloud storage (AWS S3 example):

```bash
#!/bin/bash
# Add to backup_database.sh

# Upload to S3
aws s3 cp $BACKUP_FILE s3://twi-bot-backups/database/

# Verify upload
if aws s3 ls s3://twi-bot-backups/database/$(basename $BACKUP_FILE) > /dev/null; then
  echo "Upload to S3 successful"
else
  echo "Upload to S3 failed"
  # Send alert
  curl -X POST -H "Content-Type: application/json" -d '{"content":"Database backup upload failed"}' $DISCORD_WEBHOOK_URL
fi
```

## Configuration Backups

Configuration files contain critical settings that need to be backed up separately from the code repository.

### Files to Back Up

1. Environment variables (`.env` file)
2. SSL certificates in `ssl-cert/` directory
3. Custom configuration files
4. Docker Compose files

### Backup Script

Create a file named `backup_config.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/config"
SOURCE_DIR="/app"
RETENTION_DAYS=90

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"

# Create backup
echo "Creating configuration backup: $BACKUP_FILE"
tar -czf $BACKUP_FILE \
    $SOURCE_DIR/.env \
    $SOURCE_DIR/ssl-cert \
    $SOURCE_DIR/docker-compose.yml \
    $SOURCE_DIR/prometheus.yml \
    $SOURCE_DIR/alertmanager.yml

# Set permissions
chmod 600 $BACKUP_FILE

# Remove old backups
find $BACKUP_DIR -name "config_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
echo "Configuration backup completed: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"

# Upload to cloud storage
aws s3 cp $BACKUP_FILE s3://twi-bot-backups/config/
```

### Backup After Changes

It's important to back up configuration files whenever changes are made. Add this to your deployment process:

```bash
# Add to deployment script
./backup_config.sh
```

## Code Repository Backups

The code repository should be backed up regularly, even though it's typically stored in a version control system like Git.

### GitHub Repository Backup

If using GitHub, you can use GitHub's API to create a backup:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/repository"
REPO_OWNER="username"
REPO_NAME="twi_bot_shard"
GITHUB_TOKEN="your_github_token"
RETENTION_DAYS=365

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${REPO_NAME}_${TIMESTAMP}.tar.gz"

# Create backup
echo "Creating repository backup: $BACKUP_FILE"
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/tarball" \
  -o $BACKUP_FILE

# Set permissions
chmod 600 $BACKUP_FILE

# Remove old backups
find $BACKUP_DIR -name "${REPO_NAME}_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
echo "Repository backup completed: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"
```

### Local Git Repository Backup

For local Git repositories:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/repository"
REPO_DIR="/app"
RETENTION_DAYS=365

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/repo_${TIMESTAMP}.tar.gz"

# Create backup
echo "Creating repository backup: $BACKUP_FILE"
cd $REPO_DIR && git bundle create - --all | gzip > $BACKUP_FILE

# Set permissions
chmod 600 $BACKUP_FILE

# Remove old backups
find $BACKUP_DIR -name "repo_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
echo "Repository backup completed: $BACKUP_FILE ($(du -h $BACKUP_FILE | cut -f1))"
```

## Backup Verification

Regularly verify that backups can be restored to ensure they're usable in case of an emergency.

### Database Backup Verification

Create a script named `verify_db_backup.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/database"
TEST_DB_NAME="twi_bot_shard_test"
DB_USER="postgres"

# Find the latest backup
LATEST_BACKUP=$(find $BACKUP_DIR -name "twi_bot_shard_*.sql.gz" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)

if [ -z "$LATEST_BACKUP" ]; then
  echo "No backup found"
  exit 1
fi

echo "Verifying backup: $LATEST_BACKUP"

# Drop test database if it exists
dropdb -U $DB_USER --if-exists $TEST_DB_NAME

# Create test database
createdb -U $DB_USER $TEST_DB_NAME

# Restore backup
gunzip -c $LATEST_BACKUP | psql -U $DB_USER -d $TEST_DB_NAME

# Verify restoration
if psql -U $DB_USER -d $TEST_DB_NAME -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | grep -q "[1-9]"; then
  echo "✅ Backup verification successful"
else
  echo "❌ Backup verification failed"
  # Send alert
  curl -X POST -H "Content-Type: application/json" -d '{"content":"Database backup verification failed"}' $DISCORD_WEBHOOK_URL
  exit 1
fi

# Clean up
dropdb -U $DB_USER $TEST_DB_NAME
```

### Schedule Verification

Schedule regular verification:

```bash
# Add to crontab
0 3 * * 0 /path/to/verify_db_backup.sh >> /var/log/backup_verify.log 2>&1
```

## Recovery Procedures

### Database Recovery

#### Full Database Restoration

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/database"
DB_NAME="twi_bot_shard"
DB_USER="postgres"

# Find the backup to restore (replace with specific backup if needed)
BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(find $BACKUP_DIR -name "twi_bot_shard_*.sql.gz" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
fi

echo "Restoring database from: $BACKUP_FILE"

# Stop the application
docker-compose down

# Drop and recreate the database
dropdb -U $DB_USER --if-exists $DB_NAME
createdb -U $DB_USER $DB_NAME

# Restore from backup
gunzip -c $BACKUP_FILE | psql -U $DB_USER -d $DB_NAME

# Verify restoration
if psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | grep -q "[1-9]"; then
  echo "✅ Database restoration successful"
else
  echo "❌ Database restoration failed"
  exit 1
fi

# Restart the application
docker-compose up -d

echo "Recovery completed"
```

#### Point-in-Time Recovery

For PostgreSQL point-in-time recovery:

1. Configure WAL archiving in `postgresql.conf`:
   ```
   wal_level = replica
   archive_mode = on
   archive_command = 'cp %p /backups/wal/%f'
   ```

2. Restore to a specific point in time:
   ```bash
   # Create recovery.conf
   echo "restore_command = 'cp /backups/wal/%f %p'" > recovery.conf
   echo "recovery_target_time = '2023-06-15 14:30:00'" >> recovery.conf
   
   # Restore base backup and apply WAL files
   pg_ctl start
   ```

### Configuration Recovery

To restore configuration files:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/config"
DEST_DIR="/app"

# Find the backup to restore
BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(find $BACKUP_DIR -name "config_*.tar.gz" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
fi

echo "Restoring configuration from: $BACKUP_FILE"

# Create temporary directory
TEMP_DIR=$(mktemp -d)

# Extract backup
tar -xzf $BACKUP_FILE -C $TEMP_DIR

# Copy files to destination
cp -r $TEMP_DIR/.env $DEST_DIR/
cp -r $TEMP_DIR/ssl-cert $DEST_DIR/
cp -r $TEMP_DIR/docker-compose.yml $DEST_DIR/
cp -r $TEMP_DIR/prometheus.yml $DEST_DIR/
cp -r $TEMP_DIR/alertmanager.yml $DEST_DIR/

# Clean up
rm -rf $TEMP_DIR

echo "Configuration restoration completed"
```

### Code Repository Recovery

To restore the code repository:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/repository"
DEST_DIR="/app"

# Find the backup to restore
BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(find $BACKUP_DIR -name "repo_*.tar.gz" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
fi

echo "Restoring repository from: $BACKUP_FILE"

# Create temporary directory
TEMP_DIR=$(mktemp -d)

# Extract backup
mkdir -p $TEMP_DIR/repo
gunzip -c $BACKUP_FILE | tar -x -C $TEMP_DIR/repo

# Initialize new repository
rm -rf $DEST_DIR
mkdir -p $DEST_DIR
cd $DEST_DIR
git init

# Import from bundle
cd $TEMP_DIR/repo
git bundle unbundle $BACKUP_FILE
git checkout main

# Copy to destination
cp -r $TEMP_DIR/repo/* $DEST_DIR/

# Clean up
rm -rf $TEMP_DIR

echo "Repository restoration completed"
```

## Disaster Recovery

### Disaster Recovery Plan

The disaster recovery plan outlines the steps to recover the entire system in case of a catastrophic failure.

#### Recovery Time Objectives (RTO)

| Component | RTO |
|-----------|-----|
| Bot Service | 1 hour |
| Database | 2 hours |
| Full System | 4 hours |

#### Recovery Point Objectives (RPO)

| Component | RPO |
|-----------|-----|
| Database | 1 hour |
| Configuration | 24 hours |
| Code Repository | 1 week |

### Full System Recovery Procedure

1. **Provision New Infrastructure**:
   ```bash
   # Using Terraform
   cd infrastructure
   terraform init
   terraform apply
   ```

2. **Restore Code Repository**:
   ```bash
   ./restore_repository.sh
   ```

3. **Restore Configuration**:
   ```bash
   ./restore_config.sh
   ```

4. **Restore Database**:
   ```bash
   ./restore_database.sh
   ```

5. **Rebuild and Deploy Application**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

6. **Verify System Functionality**:
   ```bash
   ./verify_system.sh
   ```

### Disaster Recovery Testing

Conduct regular disaster recovery tests to ensure the procedures work as expected:

1. **Quarterly Tests**: Perform a full recovery test in an isolated environment
2. **Documentation Updates**: Update recovery procedures based on test results
3. **Team Training**: Ensure all team members are familiar with recovery procedures

### Disaster Recovery Checklist

Create a checklist for disaster recovery:

```
[ ] Assess the situation and declare disaster if necessary
[ ] Notify stakeholders
[ ] Provision new infrastructure
[ ] Restore code repository
[ ] Restore configuration
[ ] Restore database
[ ] Deploy application
[ ] Verify functionality
[ ] Update DNS/routing if necessary
[ ] Monitor system for issues
[ ] Document the incident and recovery process
[ ] Conduct post-mortem analysis
```

---

This backup and recovery guide will be updated as the infrastructure and requirements evolve. For the latest information, refer to the project's documentation repository.