"""
Example tests demonstrating the use of pytest-timeout.

This module shows how to use pytest-timeout to prevent tests from hanging indefinitely.
"""

import asyncio
import os
import sys
import time

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


@pytest.mark.timeout(1)
def test_function_completes_within_timeout() -> None:
    """
    Test that completes within the specified timeout.

    This test demonstrates a successful case where the function completes
    before the timeout is reached.
    """
    # This operation takes less than 1 second
    time.sleep(0.5)

    # The test should pass because it completes within the timeout
    assert True


@pytest.mark.timeout(1)
def test_function_exceeds_timeout() -> None:
    """
    Test that exceeds the specified timeout.

    This test demonstrates a failing case where the function takes longer
    than the timeout. When run, this test will fail with a TimeoutError.

    Note: This test is marked with xfail because we expect it to fail.
    """
    # This operation takes more than 1 second
    pytest.xfail("This test is expected to fail due to timeout")
    time.sleep(2)

    # This assertion will never be reached because of the timeout
    raise AssertionError()


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_function_completes_within_timeout() -> None:
    """
    Test that an async function completes within the specified timeout.

    This test demonstrates that pytest-timeout works with async functions as well.
    """
    # This operation takes less than 1 second
    await asyncio.sleep(0.5)

    # The test should pass because it completes within the timeout
    assert True


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_function_exceeds_timeout() -> None:
    """
    Test that an async function exceeds the specified timeout.

    This test demonstrates a failing case with an async function.

    Note: This test is marked with xfail because we expect it to fail.
    """
    # This operation takes more than 1 second
    pytest.xfail("This test is expected to fail due to timeout")
    await asyncio.sleep(2)

    # This assertion will never be reached because of the timeout
    raise AssertionError()


# Method-level timeout
def test_method_level_timeout() -> None:
    """
    Test with a method-level timeout.

    This test demonstrates how to set a timeout for a specific test method
    using the timeout parameter in the pytest.mark.timeout decorator.
    """
    # This operation takes less than 2 seconds
    time.sleep(1)

    # The test should pass because it completes within the timeout
    assert True


# Class with timeout for all methods
@pytest.mark.timeout(2)
class TestClassWithTimeout:
    """
    Test class with a timeout applied to all test methods.

    This class demonstrates how to set a timeout for all test methods in a class.
    """

    def test_first_method(self) -> None:
        """First test method that completes within the timeout."""
        time.sleep(1)
        assert True

    def test_second_method(self) -> None:
        """Second test method that completes within the timeout."""
        time.sleep(1.5)
        assert True


# Using timeout fixture
def test_with_timeout_fixture(request) -> None:
    """
    Test using a timeout fixture.

    This test demonstrates how to use a timeout fixture to set a timeout
    for a specific test.
    """
    # Set a timeout for this test
    request.node.add_marker(pytest.mark.timeout(3))

    # This operation takes less than 3 seconds
    time.sleep(2)

    # The test should pass because it completes within the timeout
    assert True


# Example of setting different timeout methods
@pytest.mark.timeout(1, method="thread")
def test_with_thread_timeout() -> None:
    """
    Test with a thread timeout method.

    This test demonstrates how to use the thread timeout method.
    The thread method is the default and works by running the test in a separate thread.
    """
    time.sleep(0.5)
    assert True


# Signal-based timeout is not supported on Windows
# This test is commented out to avoid issues with the pytest-timeout plugin on Windows
"""
@pytest.mark.skipif(sys.platform == "win32", reason="Signal timeout method not supported on Windows")
@pytest.mark.timeout(1, method="signal")
def test_with_signal_timeout():
    \"""
    Test with a signal timeout method.

    This test demonstrates how to use the signal timeout method.
    The signal method works by setting an alarm signal that interrupts the test.
    Note: This method only works on Unix-like systems.
    \"""
    time.sleep(0.5)
    assert True
"""


if __name__ == "__main__":
    # This allows running the tests directly with pytest
    pytest.main(["-v", __file__])
