# Database Migration Scripts

Automated scripts for migrating your 14GB PostgreSQL database from Google Cloud SQL to Railway.

## Quick Start

```bash
# 1. Backup from Cloud SQL (10-20 minutes)
python scripts/migration/backup_cloudsql.py

# 2. Restore to Railway (15-30 minutes)
railway run python scripts/migration/restore_railway.py --input backups/cognita_backup_*.dump

# 3. Verify migration
railway run psql -c "SELECT COUNT(*) FROM messages;"
```

## Prerequisites

### Required Tools

- **PostgreSQL Client Tools** (pg_dump, pg_restore, psql)
  - Windows: https://www.postgresql.org/download/windows/
  - Mac: `brew install postgresql`
  - Linux: `sudo apt-get install postgresql-client`

- **Railway CLI**
  ```bash
  npm install -g @railway/cli
  railway login
  railway link  # Link to your project
  ```

- **gcloud CLI** (for Cloud SQL)
  ```bash
  gcloud auth login
  gcloud config set project YOUR_PROJECT_ID
  ```

### Environment Setup

Create a `.env` file with your Cloud SQL credentials:

```bash
# Cloud SQL (for backup)
HOST=35.xxx.xxx.xxx  # Your Cloud SQL IP
PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DATABASE=your_database_name

# Bot token (required for Railway)
BOT_TOKEN=your_discord_bot_token
```

Railway will auto-provide `DATABASE_URL` when you deploy.

---

## Script 1: backup_cloudsql.py

Exports your Cloud SQL database using `pg_dump`.

### Basic Usage

```bash
python scripts/migration/backup_cloudsql.py
```

### Options

```bash
# Custom output filename
python scripts/migration/backup_cloudsql.py --output my_backup.dump

# Compress with gzip (saves ~70% space)
python scripts/migration/backup_cloudsql.py --compress

# Plain SQL format (easier to inspect)
python scripts/migration/backup_cloudsql.py --format plain
```

### What It Does

1. ✅ Reads Cloud SQL credentials from `.env`
2. ✅ Creates `backups/` directory
3. ✅ Runs `pg_dump` with optimal flags for large databases
4. ✅ Shows real-time progress
5. ✅ Verifies backup file size
6. ✅ Optionally compresses with gzip

### Output

```
backups/
  cognita_backup_20260102_143022.dump  (~14 GB)
  cognita_backup_20260102_143022.dump.gz  (~4 GB if compressed)
```

### Troubleshooting

**Error: "pg_dump: command not found"**
- Install PostgreSQL client tools (see Prerequisites)

**Error: "connection refused"**
- Check Cloud SQL IP is correct
- Verify your IP is whitelisted in Cloud SQL settings
- Check firewall rules

**Backup is very slow**
- Normal for 14GB database (10-30 minutes)
- Use `--compress` to reduce file size

---

## Script 2: restore_railway.py

Imports your backup to Railway PostgreSQL.

### Basic Usage

```bash
# Railway CLI automatically provides credentials
railway run python scripts/migration/restore_railway.py --input backups/cognita_backup_*.dump
```

### Options

```bash
# Drop existing tables first (⚠️ DESTRUCTIVE)
railway run python scripts/migration/restore_railway.py --input backup.dump --clean

# Skip post-restore verification (faster)
railway run python scripts/migration/restore_railway.py --input backup.dump --skip-verify

# Restore compressed backup (automatic detection)
railway run python scripts/migration/restore_railway.py --input backup.dump.gz
```

### What It Does

1. ✅ Gets Railway credentials from `DATABASE_URL` env var
2. ✅ Tests connection to Railway database
3. ✅ Warns if database already has tables
4. ✅ Runs `pg_restore` with Railway-compatible flags
5. ✅ Handles compressed backups automatically
6. ✅ Runs `ANALYZE` to update statistics
7. ✅ Verifies table count and database size

### Output

```
📊 Total tables restored: 25
💾 Database size: 14 GB
✅ RESTORE COMPLETE
```

### Troubleshooting

**Error: "Railway database credentials not found"**
- Run with `railway run` prefix
- Or manually set `DATABASE_URL` from Railway dashboard

**Error: "Database already contains X tables"**
- Use `--clean` flag to drop existing tables
- Or manually drop tables: `railway run psql -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`

**Restore fails halfway**
- Check Railway storage limits (100GB on Hobby plan)
- Check connection stability
- Resume is not supported, must restart

---

## Complete Migration Workflow

### Step 1: Prepare Railway

```bash
# Login to Railway
railway login

# Link to your project
railway link

# Add PostgreSQL to project (if not already added)
# Do this via Railway dashboard: New → Database → PostgreSQL

# Verify connection
railway run psql -c "SELECT version();"
```

### Step 2: Backup Cloud SQL

```bash
# Standard backup (uncompressed)
python scripts/migration/backup_cloudsql.py

# OR compressed backup (recommended, saves transfer time)
python scripts/migration/backup_cloudsql.py --compress

# Verify backup
pg_restore --list backups/cognita_backup_*.dump | head -20
```

**Expected time:** 10-20 minutes for 14GB

### Step 3: Restore to Railway

```bash
# Restore backup
railway run python scripts/migration/restore_railway.py \
  --input backups/cognita_backup_20260102.dump

# If database already has tables:
railway run python scripts/migration/restore_railway.py \
  --input backups/cognita_backup_20260102.dump \
  --clean
```

**Expected time:** 15-30 minutes for 14GB

### Step 4: Verify Migration

```bash
# Check table counts
railway run psql -c "
  SELECT schemaname, tablename, n_live_tup AS row_count
  FROM pg_stat_user_tables
  ORDER BY n_live_tup DESC
  LIMIT 10;
"

# Check specific tables
railway run psql -c "SELECT COUNT(*) FROM messages;"
railway run psql -c "SELECT COUNT(*) FROM gallery_mementos;"
railway run psql -c "SELECT COUNT(*) FROM users;"

# Check database size
railway run psql -c "
  SELECT pg_size_pretty(pg_database_size(current_database()));
"
```

### Step 5: Run Optimizations

```bash
# Apply database optimizations
railway run psql -f database/optimizations/base.sql

# Update statistics
railway run psql -c "ANALYZE;"
```

### Step 6: Test Bot Locally

```bash
# Test connection to Railway from local machine
railway run python main.py

# Bot should start and connect successfully
# Check logs for:
# ✅ "Using Railway SSL configuration"
# ✅ "Connected to database"
# ✅ "Bot is ready"
```

### Step 7: Deploy to Railway

```bash
# If GitHub is connected (recommended):
git add .
git commit -m "feat: migrate to Railway"
git push origin master
# Railway auto-deploys

# OR deploy via CLI:
railway up

# Monitor deployment:
railway logs --follow
```

### Step 8: Final Verification

```bash
# Check bot is online in Discord
# Test critical commands:
!ping              # Basic connectivity
!stats             # Database reads
!gallery list      # Gallery operations
!quote random      # Search functionality

# Monitor Railway dashboard for:
# - CPU usage (<20% normal)
# - Memory usage (<500MB normal)
# - Database connections (5-20)
```

---

## Rollback Procedure

If something goes wrong:

### Option 1: Keep GCP Running (Safest)

```bash
# In Railway dashboard → Variables
# Change DATABASE_URL back to GCP:
HOST=<gcp-cloud-sql-ip>
DB_USER=<original-user>
DB_PASSWORD=<original-password>
DATABASE=<original-database>
PORT=5432

# Redeploy
railway up --detach
```

### Option 2: Restore from Backup

```bash
# Delete Railway database content
railway run psql -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-restore from Cloud SQL backup
railway run python scripts/migration/restore_railway.py \
  --input backups/cognita_backup_*.dump \
  --clean
```

---

## Performance Tips

### Faster Backups

```bash
# Use compression (70% smaller, but slower to create)
python scripts/migration/backup_cloudsql.py --compress

# Use directory format for parallel restore (faster)
python scripts/migration/backup_cloudsql.py --format directory
```

### Faster Restores

```bash
# Skip verification to save ~2 minutes
railway run python scripts/migration/restore_railway.py \
  --input backup.dump \
  --skip-verify

# Use compressed backups (smaller transfer)
railway run python scripts/migration/restore_railway.py \
  --input backup.dump.gz
```

### Monitoring Progress

```bash
# In another terminal, watch database size grow:
watch -n 10 'railway run psql -c "SELECT pg_size_pretty(pg_database_size(current_database()));"'

# Watch table count increase:
watch -n 10 'railway run psql -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='\''public'\'';"'
```

---

## Common Issues

### Issue: Connection Timeout During Restore

**Cause:** Large database, slow connection, or Railway limits

**Solution:**
```bash
# Increase timeout in restore command (not implemented yet)
# OR break into smaller chunks:
railway run pg_restore --table=messages backup.dump
railway run pg_restore --table=users backup.dump
# ... repeat for each table
```

### Issue: Out of Memory on Restore

**Cause:** Railway memory limits

**Solution:**
- Railway Hobby plan should handle 14GB easily
- If fails, upgrade to Pro plan ($20/month)
- Or use `--no-tablespaces` flag

### Issue: SSL Connection Failed

**Cause:** Railway requires SSL, your client doesn't support it

**Solution:**
```bash
# Set SSL mode in environment
export PGSSLMODE=require
railway run python scripts/migration/restore_railway.py --input backup.dump
```

### Issue: Table Already Exists

**Cause:** Previous restore attempt left data

**Solution:**
```bash
# Use --clean flag to drop existing objects
railway run python scripts/migration/restore_railway.py \
  --input backup.dump \
  --clean

# OR manually drop all tables:
railway run psql -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

---

## Cost Breakdown

**One-time migration costs:**
- Time investment: 2-3 hours
- No monetary cost (uses existing infrastructure)

**Ongoing Railway costs (14GB database):**
- Base: $5/month (Hobby plan)
- Compute: ~$3-5/month (bot CPU usage)
- Storage: Included (14GB < 100GB limit)
- **Total: $8-12/month**

**Savings vs GCP:**
- GCP: $90-120/month
- Railway: $8-12/month
- **Annual savings: $984-1,296**

---

## Support

If you encounter issues:

1. **Check script output** - Detailed error messages are provided
2. **Verify credentials** - Use `railway variables` to check
3. **Test connection** - Use `railway run psql -c "SELECT 1;"`
4. **Check Railway status** - https://status.railway.app
5. **Review logs** - `railway logs --follow`

**Railway Discord:** https://discord.gg/railway
**Railway Docs:** https://docs.railway.app

---

## Success Checklist

Before considering migration complete:

- [ ] Backup created successfully (~14GB file)
- [ ] Backup verified with `pg_restore --list`
- [ ] Railway database restored successfully
- [ ] Table counts match Cloud SQL
- [ ] Database size matches (~14GB)
- [ ] Bot connects to Railway locally
- [ ] Bot deploys to Railway successfully
- [ ] Critical commands work (!stats, !gallery, !quote)
- [ ] No errors in Railway logs
- [ ] CPU/Memory usage looks normal
- [ ] Cloud SQL kept running as backup (1 week)

---

**Total Migration Time:** 2-3 hours
**Database Size:** 14GB
**Downtime:** <5 minutes (during final switchover)
**Annual Cost Savings:** ~$1,000
