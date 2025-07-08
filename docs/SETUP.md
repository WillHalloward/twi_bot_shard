# Setup Guide - Twi Bot Shard (Cognita)

This guide provides detailed instructions for setting up and configuring the Twi Bot Shard (Cognita) Discord bot.

> **💡 Quick Start**: For a brief installation overview, see the [README.md](../README.md#quick-start)  
> **👨‍💻 Developers**: For development-specific setup and testing, see [Development Guidelines](../.junie/guidelines.md)

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.12.9 installed
- PostgreSQL database server (version 12 or higher recommended)
- A Discord account and the ability to create a bot
- Basic knowledge of command line operations

## Step 1: Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give your bot a name
3. Navigate to the "Bot" tab and click "Add Bot"
4. Under the "Privileged Gateway Intents" section, enable:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
5. Click "Reset Token" and copy your bot token (you'll need this later)
6. Navigate to the "OAuth2" tab, then "URL Generator"
7. Select the following scopes:
   - bot
   - applications.commands
8. Select the following bot permissions:
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Use External Emojis
   - Manage Messages (if you want moderation features)
9. Copy the generated URL and use it to invite the bot to your server

## Step 2: Clone the Repository

```bash
git clone https://github.com/yourusername/twi_bot_shard.git
cd twi_bot_shard
```

## Step 3: Install Dependencies

```bash
uv pip install -e .
```

## Step 4: PostgreSQL Setup

1. Install PostgreSQL if you haven't already
2. Create a new database for the bot:
   ```sql
   CREATE DATABASE cognita_db;
   ```
3. Create a user for the bot (or use an existing one):
   ```sql
   CREATE USER botuser WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE cognita_db TO botuser;
   ```
4. Set up SSL certificates for secure database connection:
   - Place your SSL certificates in the `ssl-cert` directory:
     - `server-ca.pem`: Server certificate authority
     - `client-cert.pem`: Client certificate
     - `client-key.pem`: Client key

## Step 5: Database Schema Setup

Run the following SQL commands to set up the necessary tables (you may need to adjust these based on the current schema):

```sql
-- Command history table
CREATE TABLE command_history (
    serial SERIAL PRIMARY KEY,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    user_id BIGINT,
    command_name TEXT,
    channel_id BIGINT,
    guild_id BIGINT,
    slash_command BOOLEAN,
    args TEXT,
    started_successfully BOOLEAN,
    finished_successfully BOOLEAN,
    run_time INTERVAL
);

-- Links table
CREATE TABLE links (
    name TEXT PRIMARY KEY,
    url TEXT,
    tag TEXT
);

-- Add other tables as needed for your specific implementation
```

## Step 6: Configuration

1. Create a `.env` file in the root directory with the following template:

```
# Discord Bot Token
BOT_TOKEN=your_discord_bot_token

# Database Configuration
HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DATABASE=cognita_db
PORT=5432

# API Keys
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id
OPENAI_API_KEY=your_openai_api_key

# Reddit Configuration (if using Reddit features)
CLIENT_ID=your_reddit_client_id
CLIENT_SECRET=your_reddit_client_secret
USER_AGENT=python:twi_bot_shard:v1.0 by /u/your_username
USERNAME=your_reddit_username
PASSWORD=your_reddit_password

# Twitter Configuration (if using Twitter features)
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret

# AO3 Configuration (if using AO3 features)
AO3_USERNAME=your_ao3_username
AO3_PASSWORD=your_ao3_password

# Security Configuration (optional)
SECRET_ENCRYPTION_KEY=your_secret_encryption_key  # For encrypting sensitive data

# Logging Configuration
LOGFILE=test
LOG_FORMAT=console  # Options: console, json
ENVIRONMENT=development  # Options: development, testing, production

# Webhook URLs for logging
WEBHOOK_TESTING_LOG=your_testing_webhook_url
WEBHOOK=your_production_webhook_url

# Auto-exit Configuration
KILL_AFTER=0  # Time in seconds after which the bot will automatically exit (0 to disable)

# Complex structures as JSON (for Patreon cookies and headers)
COOKIES={"patreon_device_id":"your_device_id"}
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0"}

# Discord Configuration (optional JSON structures)
CHANNEL_IDS={}  # Custom channel ID mappings as JSON
ROLE_IDS={}     # Custom role ID mappings as JSON
```

2. Replace all placeholder values with your actual credentials

The configuration is loaded in `config.py` using the `python-dotenv` package, which reads these environment variables from the `.env` file.

## Step 7: Running the Bot

1. Start the bot:
```bash
python main.py
```

2. The bot should now be running and connected to your Discord server

## Optional: Setting Up as a Service

### Windows (using NSSM)

1. Download and install [NSSM](https://nssm.cc/)
2. Open Command Prompt as Administrator
3. Navigate to the NSSM installation directory
4. Run:
```cmd
nssm install CognitaBot
```
5. In the Application tab:
   - Path: Path to your Python executable
   - Startup directory: Path to your project directory
   - Arguments: main.py
6. Configure other settings as needed and click "Install service"

### Linux (using Systemd)

1. Create a systemd service file:
```bash
sudo nano /etc/systemd/system/cognita.service
```

2. Add the following content:
```ini
[Unit]
Description=Cognita Discord Bot
After=network.target postgresql.service

[Service]
User=your_username
WorkingDirectory=/path/to/twi_bot_shard
ExecStart=/path/to/python /path/to/twi_bot_shard/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable cognita.service
sudo systemctl start cognita.service
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Verify your database credentials in the `.env` file
   - Check that PostgreSQL is running
   - Ensure SSL certificates are correctly configured

2. **Bot Not Responding to Commands**:
   - Check that the bot has the necessary permissions in your Discord server
   - Verify that the command prefix is correct (default is `!`)
   - Check the bot's logs for any errors

3. **Missing Dependencies**:
   - Run `pip install -r requirements.txt` again
   - Check for any error messages during installation

4. **SSL Certificate Issues**:
   - Ensure all certificates are in the correct format
   - Verify file paths in `main.py`

### Logs

Check the log file in the `logs` directory (specified by the `LOGFILE` environment variable in your `.env` file) for detailed error information.

## Updating the Bot

To update the bot to the latest version:

1. Pull the latest changes:
```bash
git pull
```

2. Install any new dependencies:
```bash
pip install -r requirements.txt
```

3. Restart the bot

## Additional Resources

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Discord Developer Portal](https://discord.com/developers/docs/intro)

If you encounter any issues not covered in this guide, please refer to the project's issue tracker or contact the maintainer.
