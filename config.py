import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Simple variables
bot_token = os.getenv("BOT_TOKEN")
google_api_key = os.getenv("GOOGLE_API_KEY")
google_cse_id = os.getenv("GOOGLE_CSE_ID")
host = os.getenv("HOST")
DB_user = os.getenv("DB_USER")
DB_password = os.getenv("DB_PASSWORD")
database = os.getenv("DATABASE")
port = int(os.getenv("PORT", "5432"))
kill_after = int(os.getenv("KILL_AFTER", "0"))  # Time in seconds to run before exiting, 0 disables
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
user_agent = os.getenv("USER_AGENT")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
logging_level = logging.INFO
logfile = os.getenv("LOGFILE", "test")
webhook_testing_log = os.getenv("WEBHOOK_TESTING_LOG")
webhook = os.getenv("WEBHOOK")
twitter_api_key = os.getenv("TWITTER_API_KEY")
twitter_api_key_secret = os.getenv("TWITTER_API_KEY_SECRET")
twitter_bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN")
twitter_access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
ao3_username = os.getenv("AO3_USERNAME")
ao3_password = os.getenv("AO3_PASSWORD")
openai_api_key = os.getenv("OPENAI_API_KEY")

# Complex structures - Option A (JSON)
cookies = json.loads(os.getenv("COOKIES", "{}"))
headers = json.loads(os.getenv("HEADERS", "{}"))
