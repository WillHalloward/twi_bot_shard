"""
Configuration module for Twi Bot Shard.

This module provides a centralized configuration system with validation
and support for different environments (development, testing, production).
It includes secure handling of sensitive configuration values and comprehensive
validation to ensure all required values are present and properly formatted.
"""

import os
import json
import logging
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Set
from pydantic import BaseModel, Field, field_validator, model_validator


# Define environment types
class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


# Define log format types
class LogFormat(str, Enum):
    JSON = "json"
    CONSOLE = "console"


# Load environment
ENVIRONMENT = os.getenv("ENVIRONMENT", Environment.DEVELOPMENT)


# Base configuration model with validation
class BotConfig(BaseModel):
    """
    Base configuration model with validation.

    This model defines all configuration settings for the bot, including required
    and optional values. It includes validators to ensure all required values are
    present and properly formatted. Sensitive values are marked for secure handling.
    """

    # Bot settings
    bot_token: str = Field(..., description="Discord bot token", json_schema_extra={"sensitive": True})
    logging_level: int = Field(logging.INFO, description="Logging level")
    logfile: str = Field("test", description="Log file name")
    log_format: LogFormat = Field(
        LogFormat.CONSOLE, description="Log output format (json or console)"
    )
    kill_after: int = Field(
        0, description="Time in seconds to run before exiting, 0 disables"
    )

    # Database settings
    host: str = Field(..., description="Database host")
    db_user: str = Field(..., description="Database user")
    db_password: str = Field(..., description="Database password", json_schema_extra={"sensitive": True})
    database: str = Field(..., description="Database name")
    port: int = Field(5432, description="Database port")

    # API keys
    google_api_key: Optional[str] = Field(
        None, description="Google API key", json_schema_extra={"sensitive": True}
    )
    google_cse_id: Optional[str] = Field(
        None, description="Google Custom Search Engine ID"
    )
    client_id: Optional[str] = Field(None, description="Client ID")
    client_secret: Optional[str] = Field(
        None, description="Client secret", json_schema_extra={"sensitive": True}
    )
    openai_api_key: Optional[str] = Field(
        None, description="OpenAI API key", json_schema_extra={"sensitive": True}
    )

    # Reddit settings
    user_agent: Optional[str] = Field(None, description="Reddit user agent")
    username: Optional[str] = Field(None, description="Reddit username")
    password: Optional[str] = Field(None, description="Reddit password", json_schema_extra={"sensitive": True})

    # Webhook settings
    webhook_testing_log: Optional[str] = Field(
        None, description="Webhook for testing logs", json_schema_extra={"sensitive": True}
    )
    webhook: Optional[str] = Field(None, description="Webhook URL", json_schema_extra={"sensitive": True})

    # Twitter settings
    twitter_api_key: Optional[str] = Field(
        None, description="Twitter API key", json_schema_extra={"sensitive": True}
    )
    twitter_api_key_secret: Optional[str] = Field(
        None, description="Twitter API key secret", json_schema_extra={"sensitive": True}
    )
    twitter_bearer_token: Optional[str] = Field(
        None, description="Twitter bearer token", json_schema_extra={"sensitive": True}
    )
    twitter_access_token: Optional[str] = Field(
        None, description="Twitter access token", json_schema_extra={"sensitive": True}
    )
    twitter_access_token_secret: Optional[str] = Field(
        None, description="Twitter access token secret", json_schema_extra={"sensitive": True}
    )

    # AO3 settings
    ao3_username: Optional[str] = Field(None, description="AO3 username")
    ao3_password: Optional[str] = Field(
        None, description="AO3 password", json_schema_extra={"sensitive": True}
    )

    # Secret encryption key
    secret_encryption_key: Optional[str] = Field(
        None, description="Encryption key for secrets", json_schema_extra={"sensitive": True}
    )

    # Complex structures
    cookies: Dict[str, str] = Field(
        default_factory=dict, description="Cookies for HTTP requests"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Headers for HTTP requests"
    )

    # Channel IDs and other hardcoded values
    channel_ids: Dict[str, int] = Field(default_factory=dict, description="Channel IDs")
    role_ids: Dict[str, int] = Field(default_factory=dict, description="Role IDs")

    # Special IDs
    bot_owner_id: int = Field(268608466690506753, description="Bot owner user ID")
    fallback_admin_role_id: int = Field(
        346842813687922689, description="Fallback admin role ID"
    )

    # Special channel lists
    password_allowed_channel_ids: List[int] = Field(
        [
            620021401516113940,
            346842161704075265,
            521403093892726785,
            362248294849576960,
            359864559361851392,
            668721870488469514,
            964519175320125490,
        ],
        description="Channel IDs where the password command is allowed",
    )

    # Special role lists
    special_role_ids: Dict[str, int] = Field(
        {
            "acid_jars": 346842555448557568,
            "acid_flies": 346842589984718848,
            "frying_pans": 346842629633343490,
            "enchanted_soup": 416001891970056192,
            "barefoot_clients": 416002473032024086,
        },
        description="Special role IDs for role-based notifications",
    )

    # Special channel IDs
    inn_general_channel_id: int = Field(
        346842161704075265, description="Inn General channel ID"
    )
    bot_channel_id: int = Field(361694671631548417, description="Bot channel ID")

    # Class variables to track configuration
    _sensitive_fields: Set[str] = {
        "bot_token",
        "db_password",
        "google_api_key",
        "client_secret",
        "openai_api_key",
        "password",
        "webhook_testing_log",
        "webhook",
        "twitter_api_key",
        "twitter_api_key_secret",
        "twitter_bearer_token",
        "twitter_access_token",
        "twitter_access_token_secret",
        "ao3_password",
        "secret_encryption_key",
    }

    _required_fields: Set[str] = {
        "bot_token",
        "host",
        "db_user",
        "db_password",
        "database",
    }

    _optional_api_fields: Set[str] = {
        "google_api_key",
        "google_cse_id",
        "client_id",
        "client_secret",
        "openai_api_key",
        "twitter_api_key",
        "twitter_api_key_secret",
        "twitter_bearer_token",
        "twitter_access_token",
        "twitter_access_token_secret",
    }

    @field_validator("bot_token")
    @classmethod
    def bot_token_must_not_be_empty(cls, v):
        """Validate that the bot token is not empty."""
        if not v:
            raise ValueError("Bot token must not be empty")
        return v

    @field_validator("host", "db_user", "db_password", "database")
    @classmethod
    def db_settings_must_not_be_empty(cls, v, info):
        """Validate that database settings are not empty."""
        if not v:
            raise ValueError(f'{info.field_name} must not be empty')
        return v

    @model_validator(mode='before')
    @classmethod
    def check_api_keys_consistency(cls, values):
        """
        Validate that API keys are consistent (e.g., if one Twitter key is provided, all should be).

        This validator ensures that if one part of a multi-part API credential is provided,
        all required parts are also provided.
        """
        # Check Twitter API credentials
        twitter_keys = [
            "twitter_api_key",
            "twitter_api_key_secret",
            "twitter_bearer_token",
            "twitter_access_token",
            "twitter_access_token_secret",
        ]

        # If any Twitter key is provided, all should be provided
        if any(values.get(key) for key in twitter_keys):
            missing = [key for key in twitter_keys if not values.get(key)]
            if missing:
                raise ValueError(
                    f"Missing Twitter API credentials: {', '.join(missing)}"
                )

        # Check Google API credentials
        if values.get("google_api_key") and not values.get("google_cse_id"):
            raise ValueError(
                "Google CSE ID is required when Google API key is provided"
            )

        if values.get("google_cse_id") and not values.get("google_api_key"):
            raise ValueError(
                "Google API key is required when Google CSE ID is provided"
            )

        # Check Reddit credentials
        if any(
            [values.get("user_agent"), values.get("username"), values.get("password")]
        ):
            missing = []
            if not values.get("user_agent"):
                missing.append("user_agent")
            if not values.get("username"):
                missing.append("username")
            if not values.get("password"):
                missing.append("password")

            if missing:
                raise ValueError(f"Missing Reddit credentials: {', '.join(missing)}")

        # Check AO3 credentials
        if values.get("ao3_username") and not values.get("ao3_password"):
            raise ValueError("AO3 password is required when AO3 username is provided")

        if values.get("ao3_password") and not values.get("ao3_username"):
            raise ValueError("AO3 username is required when AO3 password is provided")

        return values

    @classmethod
    def get_sensitive_fields(cls) -> Set[str]:
        """Get the set of sensitive field names that should be handled securely."""
        return cls._sensitive_fields

    @classmethod
    def get_required_fields(cls) -> Set[str]:
        """Get the set of required field names."""
        return cls._required_fields

    @classmethod
    def get_optional_api_fields(cls) -> Set[str]:
        """Get the set of optional API field names."""
        return cls._optional_api_fields


# Load configuration from environment variables
def load_from_env() -> BotConfig:
    """
    Load configuration from environment variables.

    This function loads configuration values from environment variables, with support
    for loading from a .env file. It includes validation to ensure all required values
    are present and properly formatted, and provides helpful error messages if any
    required values are missing.

    Returns:
        BotConfig: A validated configuration object

    Raises:
        ValueError: If required environment variables are missing or invalid
        json.JSONDecodeError: If JSON-formatted environment variables are invalid
    """
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Track missing required variables
    missing_vars = []

    # Helper function to get environment variables with validation
    def get_env(name, default=None, required=False):
        value = os.getenv(name, default)
        if required and (value is None or value == ""):
            missing_vars.append(name)
        return value

    # Get required environment variables
    bot_token = get_env("BOT_TOKEN", "", required=True)
    host = get_env("HOST", "", required=True)
    db_user = get_env("DB_USER", "", required=True)
    db_password = get_env("DB_PASSWORD", "", required=True)
    database = get_env("DATABASE", "", required=True)

    # Get optional environment variables with defaults
    port = get_env("PORT", "5432")
    kill_after = get_env("KILL_AFTER", "0")
    logfile = get_env("LOGFILE", "test")
    log_format = get_env("LOG_FORMAT", LogFormat.CONSOLE)

    # Get optional API keys and credentials
    google_api_key = get_env("GOOGLE_API_KEY")
    google_cse_id = get_env("GOOGLE_CSE_ID")
    client_id = get_env("CLIENT_ID")
    client_secret = get_env("CLIENT_SECRET")
    openai_api_key = get_env("OPENAI_API_KEY")

    # Reddit settings
    user_agent = get_env("USER_AGENT")
    username = get_env("USERNAME")
    password = get_env("PASSWORD")

    # Webhook settings
    webhook_testing_log = get_env("WEBHOOK_TESTING_LOG")
    webhook = get_env("WEBHOOK")

    # Twitter settings
    twitter_api_key = get_env("TWITTER_API_KEY")
    twitter_api_key_secret = get_env("TWITTER_API_KEY_SECRET")
    twitter_bearer_token = get_env("TWITTER_BEARER_TOKEN")
    twitter_access_token = get_env("TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret = get_env("TWITTER_ACCESS_TOKEN_SECRET")

    # AO3 settings
    ao3_username = get_env("AO3_USERNAME")
    ao3_password = get_env("AO3_PASSWORD")

    # Secret encryption key
    secret_encryption_key = get_env("SECRET_ENCRYPTION_KEY")

    # Check for missing required variables
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Load complex structures from JSON with error handling
    try:
        cookies = json.loads(get_env("COOKIES", "{}"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in COOKIES environment variable: {e}")

    try:
        headers = json.loads(get_env("HEADERS", "{}"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in HEADERS environment variable: {e}")

    # Load channel IDs and role IDs with error handling
    try:
        channel_ids = json.loads(get_env("CHANNEL_IDS", "{}"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in CHANNEL_IDS environment variable: {e}")

    try:
        role_ids = json.loads(get_env("ROLE_IDS", "{}"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ROLE_IDS environment variable: {e}")

    # Parse numeric values with error handling
    try:
        port_int = int(port)
    except ValueError:
        raise ValueError(f"Invalid PORT value: {port}. Must be an integer.")

    try:
        kill_after_int = int(kill_after)
    except ValueError:
        raise ValueError(f"Invalid KILL_AFTER value: {kill_after}. Must be an integer.")

    # Create configuration object
    try:
        config = BotConfig(
            bot_token=bot_token,
            google_api_key=google_api_key,
            google_cse_id=google_cse_id,
            host=host,
            db_user=db_user,
            db_password=db_password,
            database=database,
            port=port_int,
            kill_after=kill_after_int,
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
            logfile=logfile,
            log_format=LogFormat(log_format),
            webhook_testing_log=webhook_testing_log,
            webhook=webhook,
            twitter_api_key=twitter_api_key,
            twitter_api_key_secret=twitter_api_key_secret,
            twitter_bearer_token=twitter_bearer_token,
            twitter_access_token=twitter_access_token,
            twitter_access_token_secret=twitter_access_token_secret,
            ao3_username=ao3_username,
            ao3_password=ao3_password,
            openai_api_key=openai_api_key,
            secret_encryption_key=secret_encryption_key,
            cookies=cookies,
            headers=headers,
            channel_ids=channel_ids,
            role_ids=role_ids,
        )
    except ValueError as e:
        # Add more context to validation errors
        raise ValueError(f"Configuration validation error: {e}")

    # Log a warning if no encryption key is provided
    if not secret_encryption_key:
        logging.warning(
            "No SECRET_ENCRYPTION_KEY provided. Sensitive data will not be encrypted."
        )

    return config


# Create configuration object based on environment
if ENVIRONMENT == Environment.DEVELOPMENT:
    config = load_from_env()
elif ENVIRONMENT == Environment.TESTING:
    config = load_from_env()
    # Override settings for testing environment
    config.logfile = "test"
    config.logging_level = logging.DEBUG
elif ENVIRONMENT == Environment.PRODUCTION:
    config = load_from_env()
    # Override settings for production environment
    config.logging_level = logging.WARNING
else:
    raise ValueError(f"Unknown environment: {ENVIRONMENT}")

# Export configuration variables for backward compatibility
bot_token = config.bot_token
google_api_key = config.google_api_key
google_cse_id = config.google_cse_id
host = config.host
DB_user = config.db_user
DB_password = config.db_password
database = config.database
port = config.port
kill_after = config.kill_after
client_id = config.client_id
client_secret = config.client_secret
user_agent = config.user_agent
username = config.username
password = config.password
logging_level = config.logging_level
logfile = config.logfile
log_format = config.log_format
webhook_testing_log = config.webhook_testing_log
webhook = config.webhook
twitter_api_key = config.twitter_api_key
twitter_api_key_secret = config.twitter_api_key_secret
twitter_bearer_token = config.twitter_bearer_token
twitter_access_token = config.twitter_access_token
twitter_access_token_secret = config.twitter_access_token_secret
ao3_username = config.ao3_username
ao3_password = config.ao3_password
openai_api_key = config.openai_api_key
secret_encryption_key = config.secret_encryption_key
cookies = config.cookies
headers = config.headers
channel_ids = config.channel_ids
role_ids = config.role_ids
bot_channel_id = config.bot_channel_id
inn_general_channel_id = config.inn_general_channel_id
password_allowed_channel_ids = config.password_allowed_channel_ids
