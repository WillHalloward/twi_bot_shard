# Railway Migration Guide

Complete guide for migrating Twi Bot Shard (Cognita) from Google Cloud Platform to Railway.

## Cost Comparison

| Service | Current (GCP) | Railway | Annual Savings |
|---------|---------------|---------|----------------|
| Compute (VM) | $40/month | $5/month base | $420/year |
| PostgreSQL (14GB) | $50-80/month | $3-7/month usage | $564-876/year |
| **Total** | **$90-120/month** | **$8-12/month** | **$984-1,296/year** |

**Savings: ~90% cost reduction**

---

## Prerequisites

- [x] Railway account: https://railway.app
- [x] Railway CLI installed: `npm install -g @railway/cli`
- [x] Docker Desktop installed (for local testing)
- [x] PostgreSQL client tools: `psql`, `pg_dump`, `pg_restore`
- [x] Access to current GCP Cloud SQL instance

---

## Phase 1: Railway Setup (15 minutes)

### 1.1 Create Railway Project

```bash
# Login to Railway
railway login

# Create new project
railway init
# Name: twi-bot-shard

# Link to GitHub repository
railway link
```

### 1.2 Add PostgreSQL Database

**Via Railway Dashboard:**
1. Go to your project: https://railway.app/project/<your-project>
2. Click "+ New" → "Database" → "Add PostgreSQL"
3. Railway will provision a Postgres instance in ~30 seconds
4. Save connection details shown in "Variables" tab

**Connection Variables (auto-provided by Railway):**
- `DATABASE_URL` - Full connection string
- `PGHOST` - Database host
- `PGPORT` - Database port (usually 5432)
- `PGUSER` - Database user (usually `postgres`)
- `PGPASSWORD` - Database password
- `PGDATABASE` - Database name (usually `railway`)

### 1.3 Add Environment Variables

In Railway Dashboard → Your Service → Variables:

```bash
# Required
BOT_TOKEN=<your-discord-bot-token>
ENVIRONMENT=production
LOG_FORMAT=json

# Railway auto-provides these from Postgres addon:
# DATABASE_URL, PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

# Optional API Keys (if used)
GOOGLE_API_KEY=<your-key>
GOOGLE_CSE_ID=<your-id>
OPENAI_API_KEY=<your-key>
TWITTER_API_KEY=<your-key>
# ... add others as needed
```

---

## Phase 2: Database Migration (30-60 minutes)

### 2.1 Backup Current Cloud SQL Database

```bash
# Get Cloud SQL instance connection details
# (From GCP Console → SQL → your instance)

# Create backup using pg_dump
pg_dump \
  --host=<CLOUD_SQL_IP> \
  --port=5432 \
  --username=<DB_USER> \
  --dbname=<DATABASE_NAME> \
  --format=custom \
  --blobs \
  --verbose \
  --file=cognita_backup_$(date +%Y%m%d).dump

# Expected: ~14GB dump file (takes 10-20 minutes)

# Optional: Compress for faster transfer
gzip cognita_backup_*.dump
# Result: ~3-5GB compressed file
```

### 2.2 Verify Backup Integrity

```bash
# Check dump file size
ls -lh cognita_backup_*.dump*

# List tables in backup (without restoring)
pg_restore --list cognita_backup_*.dump | head -20
```

### 2.3 Restore to Railway PostgreSQL

```bash
# Get Railway database credentials
railway variables

# Test connection first
psql postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE> \
  -c "SELECT version();"

# Restore database (uncompressed)
pg_restore \
  --host=<PGHOST> \
  --port=<PGPORT> \
  --username=<PGUSER> \
  --dbname=<PGDATABASE> \
  --verbose \
  --no-owner \
  --no-acl \
  cognita_backup_*.dump

# OR restore from compressed backup
gunzip -c cognita_backup_*.dump.gz | \
  pg_restore \
    --host=<PGHOST> \
    --port=<PGPORT> \
    --username=<PGUSER> \
    --dbname=<PGDATABASE> \
    --verbose \
    --no-owner \
    --no-acl

# Expected: 15-30 minutes for 14GB
# You'll see progress like:
# pg_restore: creating TABLE "public.messages"
# pg_restore: creating INDEX "public.messages_channel_id_idx"
# ...
```

### 2.4 Verify Migration Success

```bash
# Connect to Railway database
psql postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE>

# Check database size
SELECT pg_size_pretty(pg_database_size('railway'));
-- Expected: ~14 GB

# List all tables
\dt
-- Should match your Cloud SQL tables

# Check row counts for critical tables
SELECT
  schemaname,
  tablename,
  n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 20;

# Verify specific tables exist
SELECT COUNT(*) FROM messages;
SELECT COUNT(*) FROM gallery_mementos;
SELECT COUNT(*) FROM users;

# Exit psql
\q
```

### 2.5 Run Database Optimizations

```bash
# Apply database optimizations to Railway
psql postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE> \
  -f database/optimizations/base.sql

# Run ANALYZE to update statistics
psql postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE> \
  -c "ANALYZE;"
```

---

## Phase 3: Update Bot Configuration (10 minutes)

### 3.1 Update Connection String Parsing

Railway provides `DATABASE_URL` in the format:
```
postgresql://postgres:password@host:port/database
```

Update your bot to parse this URL OR use Railway's individual env vars.

**Option A: Use DATABASE_URL (recommended)**

Add this to your `config/__init__.py` or database connection setup:

```python
import os
from urllib.parse import urlparse

# Check if Railway DATABASE_URL is available
database_url = os.getenv("DATABASE_URL")

if database_url:
    # Parse Railway's DATABASE_URL
    parsed = urlparse(database_url)
    host = parsed.hostname
    port = parsed.port or 5432
    db_user = parsed.username
    db_password = parsed.password
    database = parsed.path[1:]  # Remove leading '/'
else:
    # Fall back to individual env vars
    host = os.getenv("HOST")
    port = int(os.getenv("PORT", 5432))
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    database = os.getenv("DATABASE")
```

**Option B: Use Railway's PG* variables**

Railway auto-provides:
- `PGHOST` → maps to your `HOST`
- `PGPORT` → maps to your `PORT`
- `PGUSER` → maps to your `DB_USER`
- `PGPASSWORD` → maps to your `DB_PASSWORD`
- `PGDATABASE` → maps to your `DATABASE`

Update your `.env` parsing to check these first:

```python
host = os.getenv("PGHOST") or os.getenv("HOST")
port = int(os.getenv("PGPORT") or os.getenv("PORT", 5432))
db_user = os.getenv("PGUSER") or os.getenv("DB_USER")
db_password = os.getenv("PGPASSWORD") or os.getenv("DB_PASSWORD")
database = os.getenv("PGDATABASE") or os.getenv("DATABASE")
```

### 3.2 Update SSL Configuration

Railway enforces SSL but doesn't require custom certificates.

Update your database connection code (likely in `main.py`):

```python
# Before (GCP with custom SSL certs)
ssl_context = ssl.create_default_context(cafile='ssl-cert/server-ca.pem')
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_REQUIRED

pool = await asyncpg.create_pool(
    host=host,
    port=port,
    user=db_user,
    password=db_password,
    database=database,
    ssl=ssl_context  # Custom SSL context
)

# After (Railway with default SSL)
pool = await asyncpg.create_pool(
    host=host,
    port=port,
    user=db_user,
    password=db_password,
    database=database,
    ssl='require'  # Railway's default SSL
)
```

---

## Phase 4: Deploy to Railway (5 minutes)

### 4.1 Test Locally with Docker

```bash
# Build Docker image
docker build -t twi-bot-shard .

# Test locally (use Railway DB credentials)
docker run --env-file .env twi-bot-shard

# Verify bot connects successfully
# Check logs for "Bot is ready" message
```

### 4.2 Deploy to Railway

**Option A: Deploy from GitHub (recommended)**

```bash
# Connect GitHub repository to Railway
# In Railway Dashboard:
# 1. Click your service
# 2. Settings → "Connect Repo"
# 3. Select your GitHub repo
# 4. Railway will auto-deploy on every push to master/main

# Push changes
git add .
git commit -m "feat: add Railway deployment configuration"
git push origin master

# Railway will automatically:
# - Build Docker image
# - Deploy to production
# - Start the bot
```

**Option B: Deploy via Railway CLI**

```bash
# Deploy from local directory
railway up

# Monitor deployment logs
railway logs
```

### 4.3 Monitor Deployment

```bash
# Watch deployment logs in real-time
railway logs --follow

# Check service status
railway status

# Open Railway dashboard to view metrics
railway open
```

---

## Phase 5: Verification & Testing (30 minutes)

### 5.1 Verify Bot is Running

1. Check Railway Dashboard → Deployments
   - Status should be "Active"
   - CPU/Memory usage should be visible

2. Check Discord
   - Bot should show as "Online"
   - Test basic commands

### 5.2 Test Critical Functionality

```bash
# In Discord, test these commands:
!ping              # Basic connectivity
!stats             # Database read operations
!quote random      # Full-text search
!gallery list      # Gallery operations
!info              # Bot information
```

### 5.3 Monitor Performance

**Railway Dashboard Metrics:**
- CPU usage: Should be <20% normally
- Memory: Should be <500MB normally
- Database connections: Should be 5-20

**Bot Logs:**
```bash
# Check for any errors
railway logs | grep -i error

# Check database queries
railway logs | grep -i "query"

# Check startup time
railway logs | grep -i "startup"
```

---

## Phase 6: Post-Migration Cleanup (1 week later)

### 6.1 Keep Cloud SQL as Backup

**For the first week:**
- Keep Cloud SQL running (but bot uses Railway)
- Monitor Railway for stability
- Watch for any edge cases or bugs

### 6.2 Final Database Sync (Optional)

If you had any data changes during migration testing:

```bash
# Dump only new data from Cloud SQL (data after migration date)
pg_dump \
  --host=<CLOUD_SQL_IP> \
  --username=<DB_USER> \
  --dbname=<DATABASE> \
  --data-only \
  --table=messages \
  --table=users \
  -f incremental_data.sql

# Apply to Railway
psql postgresql://<PGUSER>:<PGPASSWORD>@<PGHOST>:<PGPORT>/<PGDATABASE> \
  -f incremental_data.sql
```

### 6.3 Delete GCP Resources

**After 1 week of stable Railway operation:**

```bash
# Delete Cloud SQL instance
gcloud sql instances delete <instance-name>

# Delete GCE VM (if applicable)
gcloud compute instances delete <instance-name>

# Delete static IPs, firewall rules, etc.
# Review GCP Console for any remaining resources
```

---

## Rollback Plan

If anything goes wrong during migration:

### Immediate Rollback (5 minutes)

**Option 1: Keep GCP running, just revert connection**
```bash
# In Railway Dashboard → Variables
# Change database env vars back to GCP Cloud SQL:
HOST=<gcp-cloud-sql-ip>
DB_USER=<original-user>
DB_PASSWORD=<original-password>
DATABASE=<original-database>

# Redeploy
railway up --detach
```

**Option 2: Roll back to GCE VM**
```bash
# SSH to GCE VM
gcloud compute ssh <instance-name>

# Stop Railway-connected bot
# Start bot with old .env file pointing to Cloud SQL
python main.py
```

---

## Troubleshooting

### Issue: "Connection refused" to Railway Postgres

**Solution:**
```bash
# Verify Railway Postgres is running
railway logs --service postgres

# Check if DATABASE_URL is set
railway variables | grep DATABASE

# Test connection manually
psql $(railway variables get DATABASE_URL)
```

### Issue: "SSL connection required"

**Solution:**
```python
# Update asyncpg connection to require SSL
pool = await asyncpg.create_pool(..., ssl='require')
```

### Issue: Bot connects but queries are slow

**Solution:**
```bash
# Run ANALYZE on all tables
psql $(railway variables get DATABASE_URL) -c "ANALYZE;"

# Check if indexes were restored
psql $(railway variables get DATABASE_URL) -c "\di"

# Re-apply optimizations
psql $(railway variables get DATABASE_URL) -f database/optimizations/base.sql
```

### Issue: Docker build fails

**Solution:**
```bash
# Check Docker logs
docker build -t twi-bot-shard . --no-cache

# If Python package installation fails, update requirements
uv pip compile pyproject.toml -o requirements.txt
```

---

## Railway-Specific Tips

### Automatic Backups
Railway automatically backs up your database:
- **Hobby Plan**: Daily backups, 7-day retention
- **Pro Plan**: Daily backups, 14-day retention

Access backups: Railway Dashboard → Postgres service → Backups

### Manual Backups
```bash
# Create manual backup
railway run pg_dump -Fc > manual_backup_$(date +%Y%m%d).dump

# Restore from manual backup
railway run pg_restore -d $DATABASE_URL manual_backup_*.dump
```

### Monitoring & Alerts
- Railway Dashboard shows real-time CPU/Memory/Network
- Set up alerts: Dashboard → Project Settings → Notifications
- Connect to Discord/Slack for deployment notifications

### Scaling
If you need more resources:
- Railway auto-scales within your plan limits
- Upgrade to Pro plan for dedicated resources
- Horizontal scaling: Add replicas (Pro plan only)

---

## Cost Optimization Tips

1. **Use Railway's $5 free trial credits**
   - Test migration without paying upfront
   - Free trial includes Postgres + compute

2. **Monitor usage dashboard**
   - Railway shows exact costs daily
   - Optimize if CPU/memory usage is high

3. **Consider Pro plan if usage grows**
   - More predictable pricing
   - Better performance
   - Longer backup retention

4. **Set spending limits**
   - Railway Dashboard → Billing → Usage Limits
   - Prevents surprise bills

---

## Support Resources

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Railway Status**: https://status.railway.app
- **Railway CLI Help**: `railway --help`

---

## Next Steps After Migration

1. ✅ **Add Redis caching** (Railway Redis addon: $3-5/month)
2. ✅ **Set up monitoring** (Sentry, Railway metrics)
3. ✅ **Configure auto-scaling** (if needed)
4. ✅ **Set up staging environment** (Railway makes this easy)
5. ✅ **Implement health checks** (already in Dockerfile)

---

**Estimated Total Migration Time**: 2-3 hours
**Estimated Annual Savings**: $984-1,296
**Complexity**: Medium (mostly waiting for database restore)

Good luck with the migration! 🚂
