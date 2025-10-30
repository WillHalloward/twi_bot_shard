# Environment Variables Reference

This document provides a comprehensive reference for all environment variables used by Twi Bot Shard (Cognita).

## Table of Contents

- [Required Variables](#required-variables)
- [Optional Variables](#optional-variables)
- [API Integrations](#api-integrations)
- [Advanced Configuration](#advanced-configuration)
- [Example Configurations](#example-configurations)

## Required Variables

These variables **must** be set for the bot to function:

### Discord Configuration

```env
BOT_TOKEN=your_discord_bot_token
```

**Description:** Your Discord bot token from the Developer Portal.
**Where to get it:** Discord Developer Portal → Your Application → Bot → Reset Token
**Security:** 🔐 **Highly Sensitive** - Never commit to git or share publicly

### Database Configuration

```env
HOST=localhost
DB_USER=botuser
DB_PASSWORD=your_secure_password
DATABASE=cognita_db
PORT=5432
```

**Descriptions:**
- `HOST`: PostgreSQL server hostname or IP address
- `DB_USER`: Database username
- `DB_PASSWORD`: Database user password (🔐 **Sensitive**)
- `DATABASE`: Database name
- `PORT`: PostgreSQL port (default: 5432)

**For local development:** Use `localhost` for HOST
**For production:** Use your database server's hostname/IP

## Optional Variables

### Logging Configuration

```env
LOGFILE=dev
LOG_FORMAT=console
ENVIRONMENT=development
```

**Descriptions:**
- `LOGFILE`: Base name for log files (default: `test`)
  - `dev` - Development logs
  - `test` - Test logs
  - `prod` - Production logs

- `LOG_FORMAT`: Log output format (default: `console`)
  - `console` - Human-readable colored output
  - `json` - Structured JSON format for log aggregation
  - `file` - Console format without colors for file output

- `ENVIRONMENT`: Current environment (default: `development`)
  - `development` - Dev mode with verbose logging, lazy loading
  - `testing` - Test mode with debug logging
  - `production` - Production mode with warning-level logging

### Bot Behavior

```env
KILL_AFTER=0
```

**Description:** Time in seconds before bot automatically exits (default: `0`)
**Usage:**
- `0` - Disabled (bot runs indefinitely)
- `>0` - Bot will exit after specified seconds (useful for testing)

## API Integrations

All API integrations are **optional** but required for specific features.

### Google Search Integration

Required for: Google search commands

```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id
```

**Where to get:**
1. Google API Key: [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. CSE ID: [Custom Search Engine](https://programmablesearchengine.google.com/)

**Requirements:** If one is set, both must be set
**Security:** 🔐 `GOOGLE_API_KEY` is sensitive

### OpenAI Integration

Required for: AI-powered features, summarization

```env
OPENAI_API_KEY=your_openai_api_key
```

**Where to get:** [OpenAI Platform](https://platform.openai.com/api-keys)
**Security:** 🔐 **Highly Sensitive**

### Reddit Integration

Required for: Reddit content fetching, Patreon poll tracking

```env
CLIENT_ID=your_reddit_client_id
CLIENT_SECRET=your_reddit_client_secret
USER_AGENT=python:twi_bot_shard:v1.0 by /u/your_username
USERNAME=your_reddit_username
PASSWORD=your_reddit_password
```

**Where to get:**
1. Create app at [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Select "script" type
3. Note the CLIENT_ID and CLIENT_SECRET

**Requirements:** If any Reddit variable is set, all must be set
**Security:** 🔐 `CLIENT_SECRET` and `PASSWORD` are sensitive
**User Agent Format:** `platform:app_id:version by /u/username`

### Twitter Integration

Required for: Twitter/X content fetching and reposting

```env
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
```

**Where to get:** [Twitter Developer Portal](https://developer.twitter.com/)
1. Create a Project and App
2. Generate API Keys and Access Tokens
3. Enable OAuth 1.0a if needed

**Requirements:** If any Twitter variable is set, all must be set
**Security:** 🔐 **All values are sensitive**

### AO3 Integration

Required for: Archive of Our Own content fetching

```env
AO3_USERNAME=your_ao3_username
AO3_PASSWORD=your_ao3_password
```

**Requirements:** If one is set, both must be set
**Security:** 🔐 `AO3_PASSWORD` is sensitive
**Note:** AO3 account may be needed for accessing restricted works

### Webhook Logging

Required for: Remote logging to Discord webhooks

```env
WEBHOOK_TESTING_LOG=https://discord.com/api/webhooks/...
WEBHOOK=https://discord.com/api/webhooks/...
```

**Descriptions:**
- `WEBHOOK_TESTING_LOG`: Webhook for development/testing logs
- `WEBHOOK`: Webhook for production logs

**Where to get:** Discord Server Settings → Integrations → Webhooks
**Security:** 🔐 **Both are sensitive** (provide channel access)

### Security Configuration

```env
SECRET_ENCRYPTION_KEY=your_32_character_encryption_key
```

**Description:** Encryption key for sensitive data storage
**Security:** 🔐 **Highly Sensitive**
**Generation:** Use a cryptographically secure random 32+ character string
**Note:** If not set, sensitive data will not be encrypted (warning logged)

**Generate a key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Advanced Configuration

### Complex JSON Structures

These variables accept JSON-formatted values for complex configuration:

#### Cookies

```env
COOKIES={"patreon_device_id":"your_device_id"}
```

**Description:** HTTP cookies for external service requests
**Usage:** Currently used for Patreon poll scraping
**Format:** Valid JSON object

#### Headers

```env
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0"}
```

**Description:** HTTP headers for external service requests
**Usage:** Custom headers for API requests
**Format:** Valid JSON object

#### Channel ID Mappings

```env
CHANNEL_IDS={"announcements":123456789012345678,"logs":234567890123456789}
```

**Description:** Custom channel ID mappings
**Usage:** Override default hardcoded channel IDs
**Format:** Valid JSON object with string keys and integer values

#### Role ID Mappings

```env
ROLE_IDS={"admin":345678901234567890,"moderator":456789012345678901}
```

**Description:** Custom role ID mappings
**Usage:** Override default hardcoded role IDs
**Format:** Valid JSON object with string keys and integer values

### Hardcoded Values

The following values are hardcoded in `config/__init__.py` but can be overridden via JSON in `.env`:

#### Bot Owner

```python
BOT_OWNER_ID=268608466690506753  # Hardcoded in config
```

**Description:** Discord user ID of the bot owner
**Usage:** Owner-only commands and admin privileges
**Override:** Not available via .env (modify config/__init__.py if needed)

#### Special Role IDs

```python
SPECIAL_ROLE_IDS = {
    "acid_jars": 346842555448557568,
    "acid_flies": 346842589984718848,
    "frying_pans": 346842629633343490,
    "enchanted_soup": 416001891970056192,
    "barefoot_clients": 416002473032024086,
}
```

**Description:** Special community role IDs for notifications
**Usage:** Role-based ping systems
**Override:** Via `ROLE_IDS` JSON in .env (partial override)

#### Special Channel IDs

```python
INN_GENERAL_CHANNEL_ID=346842161704075265
BOT_CHANNEL_ID=361694671631548417
FALLBACK_ADMIN_ROLE_ID=346842813687922689
```

**Description:** Hardcoded channel and role IDs
**Override:** Via `CHANNEL_IDS` or `ROLE_IDS` in .env

#### Password-Allowed Channels

```python
PASSWORD_ALLOWED_CHANNEL_IDS = [
    620021401516113940,
    346842161704075265,
    521403093892726785,
    362248294849576960,
    359864559361851392,
    668721870488469514,
    964519175320125490,
]
```

**Description:** Channels where password command is allowed
**Override:** Not available via .env

## Example Configurations

### Minimal Development Setup

```env
# Required only
BOT_TOKEN=your_bot_token_here
HOST=localhost
DB_USER=botuser
DB_PASSWORD=devpassword
DATABASE=cognita_db
PORT=5432

# Development settings
ENVIRONMENT=development
LOG_FORMAT=console
LOGFILE=dev
KILL_AFTER=0
```

### Full Development Setup

```env
# Discord & Database (required)
BOT_TOKEN=your_bot_token_here
HOST=localhost
DB_USER=botuser
DB_PASSWORD=devpassword
DATABASE=cognita_db
PORT=5432

# Development settings
ENVIRONMENT=development
LOG_FORMAT=console
LOGFILE=dev
KILL_AFTER=0

# Optional APIs (for full feature testing)
GOOGLE_API_KEY=your_google_key
GOOGLE_CSE_ID=your_cse_id
OPENAI_API_KEY=your_openai_key

# Reddit (for Patreon tracking)
CLIENT_ID=your_reddit_client_id
CLIENT_SECRET=your_reddit_secret
USER_AGENT=python:twi_bot_shard:v1.0dev by /u/yourname
USERNAME=your_reddit_user
PASSWORD=your_reddit_pass

# Security
SECRET_ENCRYPTION_KEY=your_generated_encryption_key
```

### Production Setup

```env
# Discord & Database
BOT_TOKEN=prod_bot_token_here
HOST=your_db_server.com
DB_USER=prod_user
DB_PASSWORD=strong_production_password
DATABASE=cognita_prod
PORT=5432

# Production settings
ENVIRONMENT=production
LOG_FORMAT=json
LOGFILE=prod
KILL_AFTER=0

# Webhooks for monitoring
WEBHOOK=https://discord.com/api/webhooks/prod/...

# All API keys
GOOGLE_API_KEY=prod_google_key
GOOGLE_CSE_ID=prod_cse_id
OPENAI_API_KEY=prod_openai_key
TWITTER_API_KEY=prod_twitter_key
TWITTER_API_KEY_SECRET=prod_twitter_secret
TWITTER_BEARER_TOKEN=prod_bearer_token
TWITTER_ACCESS_TOKEN=prod_access_token
TWITTER_ACCESS_TOKEN_SECRET=prod_access_secret
CLIENT_ID=prod_reddit_id
CLIENT_SECRET=prod_reddit_secret
USER_AGENT=python:twi_bot_shard:v1.0 by /u/produser
USERNAME=prod_reddit_user
PASSWORD=prod_reddit_pass
AO3_USERNAME=prod_ao3_user
AO3_PASSWORD=prod_ao3_pass

# Security
SECRET_ENCRYPTION_KEY=production_encryption_key_32chars_plus

# Complex configurations
COOKIES={"patreon_device_id":"prod_device_id"}
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
```

## Validation

The bot includes automatic validation for environment variables:

### Required Fields

The bot will fail to start if any required variable is missing:
- `BOT_TOKEN`
- `HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DATABASE`

### Consistency Checks

The bot validates that multi-part credentials are complete:
- **Twitter:** All 5 variables required if any are set
- **Google:** Both API_KEY and CSE_ID required if either is set
- **Reddit:** All 5 variables required if any are set
- **AO3:** Both USERNAME and PASSWORD required if either is set

### Type Validation

The bot validates data types:
- `PORT` must be an integer
- `KILL_AFTER` must be an integer
- `COOKIES`, `HEADERS`, `CHANNEL_IDS`, `ROLE_IDS` must be valid JSON

### Error Messages

Validation errors provide specific feedback:
```
ValueError: Missing required environment variables: BOT_TOKEN, DB_PASSWORD
ValueError: Invalid PORT value: abc. Must be an integer.
ValueError: Missing Twitter API credentials: twitter_bearer_token
ValueError: Invalid JSON in COOKIES environment variable: ...
```

## Security Best Practices

### 1. Never Commit Secrets

```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore
```

### 2. Use Strong Passwords

```bash
# Generate a strong database password
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Restrict File Permissions

```bash
# Limit .env file access
chmod 600 .env
```

### 4. Use Different Credentials Per Environment

Never reuse production credentials in development!

### 5. Rotate Sensitive Credentials Regularly

- Bot tokens
- API keys
- Database passwords
- Encryption keys

### 6. Monitor for Exposed Secrets

Use tools like:
- [GitGuardian](https://www.gitguardian.com/)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog)

## Troubleshooting

### Missing Required Variables

**Error:** `ValueError: Missing required environment variables: BOT_TOKEN`

**Solution:** Add all required variables to `.env`:
```env
BOT_TOKEN=...
HOST=...
DB_USER=...
DB_PASSWORD=...
DATABASE=...
```

### Invalid JSON Format

**Error:** `ValueError: Invalid JSON in COOKIES environment variable`

**Solution:** Ensure JSON is valid:
```env
# Correct
COOKIES={"key":"value"}

# Incorrect
COOKIES={key:value}  # Missing quotes
COOKIES={'key':'value'}  # Use double quotes, not single
```

### Incomplete API Credentials

**Error:** `ValueError: Missing Twitter API credentials: twitter_bearer_token`

**Solution:** Provide all required variables for that API:
```env
TWITTER_API_KEY=...
TWITTER_API_KEY_SECRET=...
TWITTER_BEARER_TOKEN=...        # Don't forget this one!
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...
```

### Environment Not Loaded

**Problem:** Variables in `.env` not being read

**Solutions:**
1. Ensure `.env` is in project root directory
2. Check file is named exactly `.env` (not `.env.txt`)
3. Verify no spaces around `=` in variable definitions
4. Restart the bot after changing `.env`

## Related Documentation

- [Getting Started Guide](../getting-started.md) - Initial setup
- [Configuration Module](../../reference/configuration.md) - Technical reference
- [Security Guide](../../advanced/security.md) - Security best practices
- [Deployment Guide](../../../operations/deployment/production.md) - Production deployment

---

**Need help?** See the [troubleshooting guide](../../../user/troubleshooting.md) or file an issue.
