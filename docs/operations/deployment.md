# Twi Bot Shard Deployment Guide

This guide provides comprehensive instructions for deploying the Twi Bot Shard in various environments, from local development to production on Railway.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Development](#docker-development)
4. [Railway Deployment](#railway-deployment)
5. [Branching Strategy](#branching-strategy)
6. [Environment Variables](#environment-variables)
7. [Database Setup](#database-setup)
8. [Post-Deployment Verification](#post-deployment-verification)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying Twi Bot Shard, ensure you have the following:

### System Requirements

- **Python**: Version 3.12 or higher
- **PostgreSQL**: Version 13 or higher (Railway provides this)
- **Discord Bot Token**: Created through the [Discord Developer Portal](https://discord.com/developers/applications)

### Required Accounts

- **Discord Developer Account**: For creating and managing the bot
- **Railway Account**: For cloud deployment
- **Google Cloud Account** (optional): If using Google services for search functionality
- **OpenAI Account** (optional): If using AI features

### Development Tools

- **Git**: For version control
- **Docker** (optional): For local containerized development

## Local Development

### 1. Clone the Repository

```bash
git clone https://github.com/username/twi_bot_shard.git
cd twi_bot_shard
```

### 2. Set Up Virtual Environment

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### 3. Configure Environment Variables

Create a `.env` file in the project root with the required variables. See [Environment Variables](#environment-variables) for the full list.

### 4. Set Up the Database

1. Create a PostgreSQL database:

```bash
createdb twi_bot_shard
```

2. Apply the database schema:

```bash
psql -d twi_bot_shard -f database/init.sql
```

3. Apply database optimizations:

```bash
psql -d twi_bot_shard -f database/optimizations/base.sql
```

### 5. Run the Bot

```bash
python main.py
```

## Docker Development

### 1. Build the Docker Image

```bash
docker build -t twi-bot-shard:latest .
```

### 2. Run with Docker Compose

Create a `docker-compose.yml` file for local development:

```yaml
version: '3.8'

services:
  bot:
    image: twi-bot-shard:latest
    restart: unless-stopped
    env_file: .env
    environment:
      - DB_SSL=disable
    volumes:
      - ./logs:/app/logs
    depends_on:
      - db

  db:
    image: postgres:13-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DATABASE}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/01-schema.sql

volumes:
  postgres_data:
```

Start the services:

```bash
docker-compose up -d
```

### 3. Check Logs

```bash
docker-compose logs -f bot
```

## Railway Deployment

The bot is deployed on Railway using automatic deployments from GitHub branches.

### Initial Setup

1. **Create a Railway Project**
   - Go to [Railway](https://railway.app) and create a new project
   - Connect your GitHub repository to Railway

2. **Add PostgreSQL Service**
   - In your Railway project, add a PostgreSQL database service
   - Railway will automatically provide the `DATABASE_URL` environment variable

3. **Configure Environment Variables**
   - Go to the bot service settings in Railway
   - Add all required environment variables (see [Environment Variables](#environment-variables))
   - Set `DB_SSL=disable` if using Railway's pgvector template (it doesn't support SSL)

4. **Set Up Deployment Branches**
   - Configure two Railway environments:
     - **Staging environment**: Deploys from `staging` branch
     - **Production environment**: Deploys from `production` branch

### Database Initialization

For a new Railway deployment, you'll need to initialize the database schema:

1. Connect to your Railway PostgreSQL instance using the provided credentials
2. Run the schema file:

```bash
# Using Railway CLI
railway run psql -f database/init.sql

# Or connect directly using the DATABASE_URL from Railway
psql $DATABASE_URL -f database/init.sql
```

### SSL Configuration

Railway handles SSL differently than traditional deployments:

- **Railway pgvector template**: Does not support SSL. Set `DB_SSL=disable`
- **Standard Railway PostgreSQL**: Supports SSL. Set `DB_SSL=require` or leave unset

The bot automatically detects Railway (via `DATABASE_URL` environment variable) and adjusts SSL settings accordingly. You can override this with the `DB_SSL` environment variable:

| Value | Description |
|-------|-------------|
| `disable`, `false`, `no`, `off` | Disable SSL entirely |
| `require` | Require SSL connection |
| `prefer` | Prefer SSL but allow non-SSL |

## Branching Strategy

The project uses a two-branch deployment strategy with Railway:

### Branches

- **`staging` branch**: Development branch, deploys to staging environment on Railway
- **`production` branch**: Protected branch, deploys to production environment on Railway

### Workflow

1. All development work happens on `staging` (or feature branches merged into `staging`)
2. Test changes in the staging environment
3. Create a PR from `staging` to `production` when ready to release
4. After PR approval and merge, production deployment happens automatically

### Branch Protection

- The `production` branch is protected and requires PR reviews before merging
- Direct pushes to `production` are not allowed
- This ensures all production changes are reviewed and tested in staging first

### Example Workflow

```bash
# Work on staging branch
git checkout staging
git pull origin staging

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push to staging (triggers staging deployment)
git push origin staging

# After testing in staging, create PR to production
# Use GitHub UI or gh CLI:
gh pr create --base production --head staging --title "Release: new feature"
```

## Environment Variables

### Required Variables

```env
# Discord Configuration
BOT_TOKEN=your_discord_bot_token

# Database Configuration (Railway provides DATABASE_URL automatically)
# For local development, use individual variables:
HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DATABASE=your_database_name
PORT=5432

# SSL Configuration (Railway-specific)
DB_SSL=disable  # For Railway pgvector template
```

### Optional Variables

```env
# Google Services
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id

# Twitter/X API
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret

# AO3
AO3_USERNAME=your_ao3_username
AO3_PASSWORD=your_ao3_password

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Reddit/DeviantArt OAuth
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
USER_AGENT=your_user_agent
USERNAME=your_username
PASSWORD=your_password

# Webhooks
WEBHOOK_TESTING_LOG=your_webhook_testing_log
WEBHOOK=your_webhook

# Logging
LOGFILE=test

# Auto-shutdown (useful for testing)
KILL_AFTER=0
```

## Database Setup

### Schema Files

The database schema is located at `database/init.sql`. This file contains all table definitions, indexes, and constraints.

### Applying Optimizations

After initial setup, apply performance optimizations:

```bash
# Base optimizations
psql -d your_database -f database/optimizations/base.sql

# Or run the optimization script
python scripts/database/apply_optimizations.py
```

### Migrations

Database migrations are stored in `database/migrations/`. Apply them in order:

```bash
psql -d your_database -f database/migrations/001_add_pgvector.sql
```

## Post-Deployment Verification

After deploying the bot, verify that it's working correctly:

1. **Check Bot Status**: Ensure the bot is online in Discord
2. **Run Basic Commands**: Test basic commands like `/help` and `/ping`
3. **Check Database Connection**: Verify that the bot can connect to the database
4. **Monitor Logs**: Check Railway logs for any errors

### Railway Log Monitoring

```bash
# Using Railway CLI
railway logs

# Or view logs in the Railway dashboard
```

### Verification Checklist

- [ ] Bot appears online in Discord
- [ ] Basic commands respond correctly
- [ ] Database queries work (test a stats command)
- [ ] No error messages in Railway logs
- [ ] All cogs loaded successfully (check startup logs)

## Troubleshooting

### Common Issues

#### Bot Doesn't Connect to Discord

1. Check if the `BOT_TOKEN` is correct
2. Ensure the bot has the necessary intents enabled in the Discord Developer Portal
3. Check network connectivity to Discord's API
4. Verify the token hasn't been regenerated

#### Database Connection Issues

1. Verify database credentials in environment variables
2. For Railway: Check that `DATABASE_URL` is properly set
3. Check SSL configuration - try setting `DB_SSL=disable` for Railway pgvector
4. Verify the database service is running in Railway

#### Deployment Fails on Railway

1. Check the build logs in Railway dashboard
2. Ensure all dependencies are in `requirements.txt`
3. Verify the Dockerfile builds locally
4. Check for any syntax errors in Python files

#### Bot Crashes on Startup

1. Check Railway logs for error messages
2. Verify all required environment variables are set
3. Ensure the database schema has been applied
4. Check for missing dependencies

### Getting Help

If you encounter issues not covered in this guide:

1. Check the project's GitHub repository for known issues
2. Review the Railway documentation for platform-specific issues
3. Check the logs for specific error messages

### Useful Commands

```bash
# Railway CLI commands
railway login          # Authenticate with Railway
railway link           # Link local project to Railway
railway logs           # View deployment logs
railway run <cmd>      # Run command in Railway environment
railway variables      # View/set environment variables

# Git commands for deployment
git log staging..production  # See commits not yet in production
git diff staging production  # See differences between branches
```

---

For more detailed information on specific topics, see:
- [CLAUDE.md](/CLAUDE.md) - Project overview and development guidelines
- [Environment Variables](/docs/developer/environment-variables.md) - Detailed environment configuration
- [Getting Started](/docs/developer/getting-started.md) - Development setup guide
