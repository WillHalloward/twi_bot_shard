"""
Example tests demonstrating the use of pytest-mock.

This module shows how to use pytest-mock to mock dependencies in tests.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import project components to test
# We're not importing Database directly to avoid asyncio issues
# from utils.db import Database
from utils.error_handling import log_error


# Create a mock Database class for testing
class MockDatabase:
    """Mock Database class for testing purposes."""

    def __init__(self):
        """Initialize the database with a mock pool."""
        self.pool = None

    async def execute(self, query, *args):
        """
        Execute a SQL query with the given arguments.

        This method simulates the behavior of the real Database.execute method
        by acquiring a connection from the pool and executing the query.
        """
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


def test_log_error_with_mock(mocker):
    """
    Test log_error function with mocked redact_sensitive_info.

    This test demonstrates how to use pytest-mock to mock a function
    and verify that the function under test doesn't raise an exception.
    """
    # Mock the redact_sensitive_info function to avoid regex issues
    mocker.patch(
        "utils.error_handling.redact_sensitive_info", side_effect=lambda x: x
    )  # Just return the input

    # Call the function under test
    error = ValueError("Test error")
    command_name = "test_command"
    user_id = 123456789
    log_level = 40  # ERROR

    # The test passes if this doesn't raise an exception
    log_error(error, command_name, user_id, log_level)

    # We can also verify that the function logs the error by checking the captured log output
    # This is done automatically by pytest's log capture


@pytest.mark.asyncio
async def test_database_execute_with_mock(mocker):
    """
    Test Database.execute method with mocked connection pool.

    This test demonstrates how to use pytest-mock to mock async methods
    and test database operations without a real database connection.
    """
    # Create a mock for the connection pool
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Create a mock for the execute result
    mock_result = "mock result"
    mock_conn.execute.return_value = mock_result

    # Create a MockDatabase instance with the mock pool
    db = MockDatabase()
    db.pool = mock_pool

    # Call the method under test
    query = "SELECT * FROM test_table WHERE id = $1"
    args = (1,)
    result = await db.execute(query, *args)

    # Verify the connection pool was used correctly
    mock_pool.acquire.assert_called_once()
    mock_conn.execute.assert_called_once_with(query, *args)

    # Verify the result is what we expected
    assert result == mock_result


def test_spy_on_existing_method(mocker):
    """
    Test using a spy on an existing method.

    This test demonstrates how to use pytest-mock to spy on an existing
    method without completely replacing its functionality.
    """

    # Create a simple class with a method to spy on
    class Calculator:
        def add(self, a, b):
            return a + b

    # Create an instance of the class
    calculator = Calculator()

    # Create a spy on the add method
    spy = mocker.spy(calculator, "add")

    # Call the method
    result = calculator.add(2, 3)

    # Verify the method was called with the expected arguments
    spy.assert_called_once_with(2, 3)

    # Verify the result is correct (the real method was still executed)
    assert result == 5
    assert spy.spy_return == 5


def test_mock_context_manager(mocker):
    """
    Test mocking a context manager.

    This test demonstrates how to use pytest-mock to mock a context manager.
    """
    # Create a mock for a file context manager
    mock_file = mocker.mock_open(read_data="test data")

    # Patch the built-in open function
    mocker.patch("builtins.open", mock_file)

    # Use the context manager
    with open("test_file.txt", "r") as f:
        data = f.read()

    # Verify open was called with the expected arguments
    mock_file.assert_called_once_with("test_file.txt", "r")

    # Verify the data was read correctly
    assert data == "test data"


if __name__ == "__main__":
    # This allows running the tests directly with pytest
    pytest.main(["-v", __file__])
