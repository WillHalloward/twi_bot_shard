"""
Property-based tests for Twi Bot Shard.

This module contains property-based tests using the Hypothesis library
to verify that certain properties hold for a wide range of inputs.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Hypothesis for property-based testing
try:
    from hypothesis import given
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy
except ImportError:
    print("Hypothesis is not installed. Please install it with:")
    print("uv pip install hypothesis")
    sys.exit(1)

# Import Discord components

# Import project components
# Import test utilities
from typing import Never

from tests.mock_factories import (
    MockChannelFactory,
    MockContextFactory,
    MockGuildFactory,
    MockUserFactory,
)
from utils.decorators import (
    handle_errors,
    log_command,
)
from utils.error_handling import get_error_response, log_error
from utils.permissions import admin_or_me_check, is_bot_channel

# Define strategies for generating test data

# Strategy for generating command names
command_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), blacklist_characters=()
    ),
    min_size=1,
    max_size=20,
)

# Strategy for generating user IDs
user_id_strategy = st.integers(
    min_value=100000000000000000, max_value=999999999999999999
)

# Strategy for generating guild IDs
guild_id_strategy = st.integers(
    min_value=100000000000000000, max_value=999999999999999999
)

# Strategy for generating channel IDs
channel_id_strategy = st.integers(
    min_value=100000000000000000, max_value=999999999999999999
)

# Strategy for generating error messages
error_message_strategy = st.text(min_size=1, max_size=100)

# Strategy for generating log levels
log_level_strategy = st.sampled_from(
    [10, 20, 30, 40, 50]
)  # DEBUG, INFO, WARNING, ERROR, CRITICAL


# Strategy for generating exceptions
def exception_strategy() -> SearchStrategy[Exception]:
    """Generate a strategy for exceptions."""
    return st.one_of(
        st.builds(ValueError, error_message_strategy),
        st.builds(TypeError, error_message_strategy),
        st.builds(RuntimeError, error_message_strategy),
        st.builds(KeyError, st.text(min_size=1, max_size=20)),
        st.builds(IndexError, error_message_strategy),
        st.builds(AttributeError, error_message_strategy),
    )


# Tests for decorators.py


@given(command_name=command_name_strategy)
def test_log_command_preserves_function_metadata(command_name: str) -> None:
    """Test that log_command preserves function metadata."""

    # Define a test function
    async def test_func(self, ctx) -> str:
        """Test function docstring."""
        return "test"

    # Apply the decorator
    decorated = log_command(command_name)(test_func)

    # Check that the metadata is preserved
    assert decorated.__name__ == test_func.__name__
    assert decorated.__doc__ == test_func.__doc__
    assert decorated.__module__ == test_func.__module__
    assert decorated.__annotations__ == test_func.__annotations__
    assert decorated.__qualname__ == test_func.__qualname__


@given(command_name=command_name_strategy)
def test_handle_errors_preserves_function_metadata(command_name: str) -> None:
    """Test that handle_errors preserves function metadata."""

    # Define a test function
    async def test_func(self, ctx) -> str:
        """Test function docstring."""
        return "test"

    # Apply the decorator
    decorated = handle_errors(command_name)(test_func)

    # Check that the metadata is preserved
    assert decorated.__name__ == test_func.__name__
    assert decorated.__doc__ == test_func.__doc__
    assert decorated.__module__ == test_func.__module__
    assert decorated.__annotations__ == test_func.__annotations__
    assert decorated.__qualname__ == test_func.__qualname__


@pytest.mark.asyncio
@given(
    command_name=command_name_strategy,
    user_id=user_id_strategy,
    guild_id=guild_id_strategy,
    channel_id=channel_id_strategy,
)
async def test_log_command_calls_log_command_usage(
    command_name: str, user_id: int, guild_id: int, channel_id: int
) -> None:
    """Test that log_command calls log_command_usage with the correct arguments."""
    # Create mock objects
    mock_self = MagicMock()
    mock_self.log_command_usage = AsyncMock()

    # Create a mock context
    ctx = MockContextFactory.create(
        author=MockUserFactory.create(user_id=user_id),
        guild=MockGuildFactory.create(guild_id=guild_id),
        channel=MockChannelFactory.create_text_channel(channel_id=channel_id),
    )

    # Define a test function
    @log_command(command_name)
    async def test_func(self, ctx) -> str:
        return "test"

    # Call the decorated function
    await test_func(mock_self, ctx)

    # Check that log_command_usage was called with the correct arguments
    mock_self.log_command_usage.assert_called_once_with(ctx, command_name)


@pytest.mark.asyncio
@given(
    command_name=command_name_strategy,
    user_id=user_id_strategy,
    guild_id=guild_id_strategy,
    channel_id=channel_id_strategy,
    error=exception_strategy(),
)
async def test_handle_errors_catches_exceptions(
    command_name: str, user_id: int, guild_id: int, channel_id: int, error: Exception
) -> None:
    """Test that handle_errors catches exceptions and calls handle_error."""
    # Create mock objects
    mock_self = MagicMock()
    mock_self.handle_error = AsyncMock()

    # Create a mock context
    ctx = MockContextFactory.create(
        author=MockUserFactory.create(user_id=user_id),
        guild=MockGuildFactory.create(guild_id=guild_id),
        channel=MockChannelFactory.create_text_channel(channel_id=channel_id),
    )

    # Define a test function that raises an exception
    @handle_errors(command_name)
    async def test_func(self, ctx) -> Never:
        raise error

    # Call the decorated function
    await test_func(mock_self, ctx)

    # Check that handle_error was called with the correct arguments
    mock_self.handle_error.assert_called_once_with(ctx, error, command_name)


# Tests for permissions.py


@pytest.mark.asyncio
@given(user_id=user_id_strategy, guild_id=guild_id_strategy)
async def test_admin_or_me_check_returns_boolean(user_id: int, guild_id: int) -> None:
    """Test that admin_or_me_check returns a boolean value."""
    # Create mock objects
    user = MockUserFactory.create(user_id=user_id)
    # Add roles attribute to the user mock
    user.roles = []
    guild = MockGuildFactory.create(guild_id=guild_id)

    # Create a mock context
    ctx = MockContextFactory.create(author=user, guild=guild)

    # Mock the settings cog
    settings_cog = MagicMock()
    settings_cog.is_admin = AsyncMock(return_value=True)
    ctx.bot.get_cog.return_value = settings_cog

    # Call the function
    result = await admin_or_me_check(ctx)

    # Check that the result is a boolean
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_is_bot_channel_returns_boolean() -> None:
    """Test that is_bot_channel returns a boolean value for different channel IDs."""
    # Use a fixed channel ID for testing since the patch needs to be consistent
    test_channel_id = 111222333

    # Create mock objects
    channel = MockChannelFactory.create_text_channel(channel_id=test_channel_id)

    # Create a mock context
    ctx = MockContextFactory.create(channel=channel)

    # Verify the mock channel has the correct ID
    assert channel.id == test_channel_id

    # Patch the config module in utils.permissions where it's imported
    with patch('utils.permissions.config') as mock_config:
        mock_config.bot_channel_id = test_channel_id

        # Call the function (is_bot_channel is async)
        result = await is_bot_channel(ctx)

        # Check that the result is a boolean
        assert isinstance(result, bool)

        # Check that the result is True when the channel ID matches
        assert result is True

    # Patch with a different value
    with patch('utils.permissions.config') as mock_config:
        mock_config.bot_channel_id = test_channel_id + 1

        # Call the function (is_bot_channel is async)
        result = await is_bot_channel(ctx)

        # Check that the result is a boolean
        assert isinstance(result, bool)

        # Check that the result is False when the channel ID doesn't match
        assert result is False


# Tests for error_handling.py


@given(error=exception_strategy())
def test_get_error_response_returns_valid_response(error: Exception) -> None:
    """Test that get_error_response returns a valid error response."""
    # Call the function
    response = get_error_response(error)

    # Check that the response is a dictionary
    assert isinstance(response, dict)

    # Check that the response contains the required keys
    assert "message" in response
    assert "log_level" in response
    assert "ephemeral" in response

    # Check that the values have the correct types
    assert isinstance(response["message"], str)
    assert isinstance(response["log_level"], int)
    assert isinstance(response["ephemeral"], bool)


@given(
    error=exception_strategy(),
    command_name=command_name_strategy,
    user_id=user_id_strategy,
    log_level=log_level_strategy,
)
def test_log_error_does_not_raise_exceptions(
    error: Exception, command_name: str, user_id: int, log_level: int
) -> None:
    """Test that log_error does not raise exceptions."""
    # Call the function
    try:
        log_error(error, command_name, user_id, log_level)
    except Exception as e:
        raise AssertionError(f"log_error raised an exception: {e}")


# Main function to run the tests
async def main() -> None:
    """Run all property-based tests."""
    print("Running property-based tests...")

    # Run synchronous tests
    test_log_command_preserves_function_metadata()
    test_handle_errors_preserves_function_metadata()
    test_get_error_response_returns_valid_response()
    test_log_error_does_not_raise_exceptions()

    # Run asynchronous tests
    await test_log_command_calls_log_command_usage()
    await test_handle_errors_catches_exceptions()
    await test_admin_or_me_check_returns_boolean()
    await test_is_bot_channel_returns_boolean()

    print("All property-based tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
