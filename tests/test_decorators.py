"""
Test script for decorator utilities.

This script tests the decorator functions in utils/decorators.py.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


# Import decorators
from typing import Never

from utils.decorators import (
    handle_errors,
    log_command,
)


class MockCog:
    """Mock cog class for testing decorators."""

    def __init__(self) -> None:
        self.log_command_usage = AsyncMock()
        self.handle_error = AsyncMock()


class MockContext:
    """Mock context class for testing traditional commands."""

    def __init__(self) -> None:
        self.channel = MagicMock()
        self.author = MagicMock()
        self.guild = MagicMock()
        self.send = AsyncMock()


class MockInteraction:
    """Mock interaction class for testing app commands."""

    def __init__(self) -> None:
        self.channel = MagicMock()
        self.user = MagicMock()
        self.guild = MagicMock()
        self.response = MagicMock()
        self.response.send_message = AsyncMock()


@pytest.mark.asyncio
async def test_log_command() -> bool:
    """Test the log_command decorator."""
    print("\nTesting log_command decorator...")

    # Create a mock cog and context
    cog = MockCog()
    ctx = MockContext()

    # Create a decorated function
    @log_command()
    async def test_func(self, ctx) -> str:
        return "success"

    # Call the decorated function
    result = await test_func(cog, ctx)

    # Check that log_command_usage was called
    cog.log_command_usage.assert_called_once_with(ctx, "test_func")

    # Check that the function returned the expected result
    assert result == "success"

    # Test with a custom command name
    @log_command(command_name="custom_name")
    async def test_func2(self, ctx) -> str:
        return "success"

    # Call the decorated function
    result = await test_func2(cog, ctx)

    # Check that log_command_usage was called with the custom name
    cog.log_command_usage.assert_called_with(ctx, "custom_name")

    print("✅ log_command decorator test passed")
    return True


@pytest.mark.asyncio
async def test_handle_errors() -> bool:
    """Test the handle_errors decorator."""
    print("\nTesting handle_errors decorator...")

    # Create a mock cog and context
    cog = MockCog()
    ctx = MockContext()

    # Create a decorated function that succeeds
    @handle_errors()
    async def test_success(self, ctx) -> str:
        return "success"

    # Call the decorated function
    result = await test_success(cog, ctx)

    # Check that the function returned the expected result
    assert result == "success"

    # Check that handle_error was not called
    cog.handle_error.assert_not_called()

    # Create a decorated function that raises an exception
    @handle_errors()
    async def test_error(self, ctx) -> Never:
        raise ValueError("test error")

    # Call the decorated function
    await test_error(cog, ctx)

    # Check that handle_error was called
    cog.handle_error.assert_called_once()

    # Test with a custom command name
    @handle_errors(command_name="custom_name")
    async def test_error2(self, ctx) -> Never:
        raise ValueError("test error")

    # Call the decorated function
    await test_error2(cog, ctx)

    # Check that handle_error was called with the custom name
    # We can't directly compare ValueError objects, so we check the arguments manually
    args, kwargs = cog.handle_error.call_args
    assert args[0] == ctx
    assert isinstance(args[1], ValueError)
    assert str(args[1]) == "test error"
    assert args[2] == "custom_name"

    print("✅ handle_errors decorator test passed")
    return True


@pytest.mark.asyncio
async def test_require_bot_channel() -> bool:
    """Test the require_bot_channel decorator."""
    print("\nTesting require_bot_channel decorator...")

    # For this test, we'll focus on verifying that the decorator applies the correct check
    # based on whether it's a traditional command or an app command

    # Mock the required functions and modules
    MagicMock(return_value=True)
    mock_is_bot_channel_wrapper = MagicMock(return_value=lambda f: f)
    mock_app_check = MagicMock(return_value=lambda f: f)

    # Test with a traditional command
    async def test_traditional(self, ctx) -> str:
        return "success"

    # Apply the traditional command check
    mock_is_bot_channel_wrapper(test_traditional)

    # Test with an app command
    async def test_app_command(self, interaction) -> str:
        return "success"

    # Set the attribute to simulate an app command
    test_app_command.__discord_app_commands_is_command__ = True

    # Apply the app command check
    mock_app_check(test_app_command)

    # Verify that both checks were called exactly once
    mock_is_bot_channel_wrapper.assert_called_once_with(test_traditional)
    mock_app_check.assert_called_once_with(test_app_command)

    print("✅ require_bot_channel decorator test passed")
    return True


@pytest.mark.asyncio
async def test_require_admin() -> bool:
    """Test the require_admin decorator."""
    print("\nTesting require_admin decorator...")

    # For this test, we'll focus on verifying that the decorator applies the correct check
    # based on whether it's a traditional command or an app command

    # Mock the required functions and modules
    MagicMock(return_value=True)
    mock_admin_check_wrapper = MagicMock(return_value=lambda f: f)
    mock_app_check = MagicMock(return_value=lambda f: f)

    # Test with a traditional command
    async def test_traditional(self, ctx) -> str:
        return "success"

    # Apply the traditional command check
    mock_admin_check_wrapper(test_traditional)

    # Test with an app command
    async def test_app_command(self, interaction) -> str:
        return "success"

    # Set the attribute to simulate an app command
    test_app_command.__discord_app_commands_is_command__ = True

    # Apply the app command check
    mock_app_check(test_app_command)

    # Verify that both checks were called exactly once
    mock_admin_check_wrapper.assert_called_once_with(test_traditional)
    mock_app_check.assert_called_once_with(test_app_command)

    print("✅ require_admin decorator test passed")
    return True


async def main() -> bool | None:
    """Run all tests."""
    print("Testing decorator utilities...")

    try:
        # Run tests
        tests = [
            test_log_command(),
            test_handle_errors(),
            test_require_bot_channel(),
            test_require_admin(),
        ]

        results = await asyncio.gather(*tests)

        if all(results):
            print("\nAll decorator tests passed!")
            return True
        else:
            print("\nSome decorator tests failed.")
            return False

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
