# Railway Environment Variables Setup

Complete guide for setting up environment variables in Railway.

## Required Variables

### 1. Bot Token (REQUIRED)
```
BOT_TOKEN=your_discord_bot_token_here
```
**Get from**: Discord Developer Portal → Your Application → Bot → Token

### 2. Database Variables (AUTO-PROVIDED by Railway)
✅ Railway automatically provides these when you add PostgreSQL:
- `DATABASE_URL` - Full connection string (auto-provided)
- `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` - Individual vars (auto-provided)

**You don't need to set these manually!**

### 3. Environment Type
```
ENVIRONMENT=production
```

### 4. Logging Configuration
```
LOG_FORMAT=json
LOGFILE=railway
```
JSON format works better with Railway's log aggregation.

---

## Optional API Keys (Only if you use these features)

### Google Custom Search (for search commands)
```
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
```

### OpenAI (for summarization features)
```
OPENAI_API_KEY=your_openai_api_key
```

### Twitter/X API (for Twitter features)
```
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
```

### AO3 (Archive of Our Own features)
```
AO3_USERNAME=your_ao3_username
AO3_PASSWORD=your_ao3_password
```

### Discord Webhooks (for logging/alerts)
```
WEBHOOK=your_webhook_url
WEBHOOK_TESTING_LOG=your_test_webhook_url
```

### Reddit (if using Reddit features)
```
USER_AGENT=your_reddit_user_agent
USERNAME=your_reddit_username
PASSWORD=your_reddit_password
```

### Secret Encryption Key (for encrypting sensitive data)
```
SECRET_ENCRYPTION_KEY=your_random_32_character_key
```
Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## How to Set Variables in Railway

### Option 1: Railway Dashboard (Easiest)

1. Go to https://railway.app
2. Select your project
3. Click on your service (the bot, not the database)
4. Click "Variables" tab
5. Click "New Variable"
6. Enter variable name and value
7. Click "Add"
8. Railway will auto-redeploy

### Option 2: Railway CLI

```bash
# Set a single variable
railway variables set BOT_TOKEN=your_token_here

# Set multiple variables
railway variables set ENVIRONMENT=production LOG_FORMAT=json

# View all variables
railway variables

# Delete a variable
railway variables delete VARIABLE_NAME
```

### Option 3: Bulk Import from .env

```bash
# Copy your local .env variables to Railway
railway variables set $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
```

**⚠️ Warning**: This will copy ALL variables including database credentials.
Remove database-related variables after since Railway provides them automatically.

---

## Railway-Specific Configuration

### Variables Railway Provides Automatically:
✅ `DATABASE_URL` - PostgreSQL connection string
✅ `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
✅ `RAILWAY_ENVIRONMENT` - deployment environment
✅ `RAILWAY_GIT_COMMIT_SHA` - current git commit
✅ `RAILWAY_SERVICE_NAME` - service name

**Don't set these manually!** They're auto-injected.

### Variables You MUST Set:
❗ `BOT_TOKEN` - Your Discord bot token
❗ `ENVIRONMENT` - Set to "production"

### Variables You SHOULD Set:
⚠️ `LOG_FORMAT=json` - Better Railway log integration
⚠️ `LOGFILE=railway` - Descriptive log filename

### Variables You MAY Set (if using features):
💡 `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` - Google search
💡 `OPENAI_API_KEY` - AI summarization
💡 `TWITTER_*` - Twitter integration
💡 Other API keys as needed

---

## Quick Setup Command

Copy this and modify with your actual values:

```bash
# Required
railway variables set BOT_TOKEN=YOUR_ACTUAL_DISCORD_BOT_TOKEN
railway variables set ENVIRONMENT=production
railway variables set LOG_FORMAT=json
railway variables set LOGFILE=railway

# Optional - Add only if you use these features
railway variables set GOOGLE_API_KEY=your_key
railway variables set GOOGLE_CSE_ID=your_cse_id
railway variables set OPENAI_API_KEY=your_key

# Verify
railway variables
```

---

## Checking Your Setup

### 1. View Current Variables
```bash
railway variables
```

### 2. Test Connection Locally
```bash
# This uses Railway's environment
railway run python main.py
```

**Expected output:**
```
Using Railway SSL configuration (ssl='require')
Connected to database
Bot is ready
```

### 3. Check Logs After Deployment
```bash
railway logs --follow
```

**Look for:**
✅ "Using Railway SSL configuration"
✅ "Connected to database"
✅ "Loaded X cogs"
✅ "Bot is ready"

---

## Common Issues

### Issue: "BOT_TOKEN is required but not provided"
**Fix**: Set `BOT_TOKEN` in Railway variables

### Issue: "Cannot connect to database"
**Fix**: Ensure PostgreSQL addon is added to Railway project

### Issue: Bot connects but commands don't work
**Fix**: Check if bot has proper Discord intents enabled in Discord Developer Portal

### Issue: "Missing API key" errors
**Fix**: Only set API keys for features you actually use. Most are optional.

---

## Security Best Practices

1. ✅ **Never commit secrets to git**
   - `.env` is in `.gitignore`
   - Use Railway's variable system

2. ✅ **Use different tokens for dev/prod**
   - Local development: `.env` file
   - Production: Railway variables

3. ✅ **Rotate tokens regularly**
   - Discord bot token: Every 6 months
   - API keys: Based on provider recommendations

4. ✅ **Limit permissions**
   - Discord bot: Only enable needed intents
   - API keys: Use restricted keys when possible

---

## Minimal Working Configuration

**Absolute minimum to get bot running on Railway:**

```bash
railway variables set BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN
railway variables set ENVIRONMENT=production
```

That's it! Railway provides `DATABASE_URL` automatically.

**Recommended configuration (adds logging):**

```bash
railway variables set BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN
railway variables set ENVIRONMENT=production
railway variables set LOG_FORMAT=json
railway variables set LOGFILE=railway
```

---

## Copy-Paste Template

Replace `YOUR_*` with actual values:

```bash
# === REQUIRED ===
railway variables set BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN

# === RECOMMENDED ===
railway variables set ENVIRONMENT=production
railway variables set LOG_FORMAT=json
railway variables set LOGFILE=railway

# === OPTIONAL - Only if you use these features ===
# Google Search
railway variables set GOOGLE_API_KEY=YOUR_GOOGLE_KEY
railway variables set GOOGLE_CSE_ID=YOUR_CSE_ID

# OpenAI
railway variables set OPENAI_API_KEY=YOUR_OPENAI_KEY

# Twitter (uncomment if needed)
# railway variables set TWITTER_API_KEY=YOUR_KEY
# railway variables set TWITTER_API_KEY_SECRET=YOUR_SECRET
# railway variables set TWITTER_BEARER_TOKEN=YOUR_TOKEN
# railway variables set TWITTER_ACCESS_TOKEN=YOUR_TOKEN
# railway variables set TWITTER_ACCESS_TOKEN_SECRET=YOUR_SECRET

# Webhooks (uncomment if needed)
# railway variables set WEBHOOK=YOUR_WEBHOOK_URL

# Verify all variables are set
railway variables
```

---

## Next Steps After Setting Variables

1. ✅ Variables are set in Railway
2. ✅ Database backup is complete
3. ✅ Ready to restore database
4. 🚀 Run: `railway run psql < backups/cognita_backup_*.sql`
5. 🧪 Test: `railway run python main.py`
6. 🚢 Deploy: `git push origin master`

---

**Quick Check Before Migration:**

```bash
# Should show BOT_TOKEN, ENVIRONMENT, DATABASE_URL
railway variables | grep -E 'BOT_TOKEN|ENVIRONMENT|DATABASE_URL'
```

If you see all three, you're ready to migrate! 🎯
