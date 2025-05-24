# Setup Guide - Twi Bot Shard (Cognita)

This guide provides detailed instructions for setting up and configuring the Twi Bot Shard (Cognita) Discord bot.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher installed
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
pip install -r requirements.txt
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

1. Create a `secrets.py` file in the root directory with the following template:

```python
import logging

# Discord Bot Token
bot_token = "YOUR_BOT_TOKEN"

# Database Configuration
host = 'YOUR_DATABASE_HOST'
DB_user = 'YOUR_DATABASE_USER'
DB_password = 'YOUR_DATABASE_PASSWORD'
database = 'cognita_db'
port = 5432

# API Keys
google_api_key = "YOUR_GOOGLE_API_KEY"
google_cse_id = "YOUR_GOOGLE_CSE_ID"
openai_api_key = "YOUR_OPENAI_API_KEY"

# Patreon Configuration (if using Patreon features)
cookies = {
    'patreon_device_id': 'YOUR_DEVICE_ID',
    # Add other cookies as needed
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0',
    # Add other headers as needed
}

# Reddit Configuration (if using Reddit features)
client_id = "YOUR_REDDIT_CLIENT_ID"
client_secret = "YOUR_REDDIT_CLIENT_SECRET"
user_agent = "python:twi_bot_shard:v1.0 by /u/your_username"
username = "YOUR_REDDIT_USERNAME"
password = "YOUR_REDDIT_PASSWORD"

# Twitter Configuration (if using Twitter features)
twitter_api_key = "YOUR_TWITTER_API_KEY"
twitter_api_key_secret = "YOUR_TWITTER_API_KEY_SECRET"
twitter_bearer_token = "YOUR_TWITTER_BEARER_TOKEN"
twitter_access_token = "YOUR_TWITTER_ACCESS_TOKEN"
twitter_access_token_secret = "YOUR_TWITTER_ACCESS_TOKEN_SECRET"

# AO3 Configuration (if using AO3 features)
ao3_username = "YOUR_AO3_USERNAME"
ao3_password = "YOUR_AO3_PASSWORD"

# Logging Configuration
logging_level = logging.INFO
logfile = 'bot_log'

# Webhook URLs for logging
webhook_testing_log = "YOUR_TESTING_WEBHOOK_URL"
webhook = "YOUR_PRODUCTION_WEBHOOK_URL"

# Auto-exit Configuration
kill_after = 0  # Time in seconds after which the bot will automatically exit (0 to disable)
```

2. Replace all placeholder values with your actual credentials

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
```
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
```
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
   - Verify your database credentials in `secrets.py`
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

Check the log file specified in your `secrets.py` configuration for detailed error information.

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
