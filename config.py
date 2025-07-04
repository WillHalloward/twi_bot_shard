"""
Configuration module for Twi Bot Shard.

This module is a backward-compatible wrapper around the new configuration system.
It imports all configuration variables from the new module to maintain compatibility
with existing code that imports from this module.
"""

# Import all configuration variables from the new module
from config.__init__ import (
    bot_token,
    google_api_key,
    google_cse_id,
    host,
    DB_user,
    DB_password,
    database,
    port,
    kill_after,
    client_id,
    client_secret,
    user_agent,
    username,
    password,
    logging_level,
    logfile,
    log_format,
    webhook_testing_log,
    webhook,
    twitter_api_key,
    twitter_api_key_secret,
    twitter_bearer_token,
    twitter_access_token,
    twitter_access_token_secret,
    ao3_username,
    ao3_password,
    openai_api_key,
    secret_encryption_key,
    cookies,
    headers,
    channel_ids,
    role_ids,
    bot_channel_id,
    inn_general_channel_id,
    password_allowed_channel_ids,
    config,
    Environment,
    BotConfig,
    load_from_env,
    ENVIRONMENT,
)
