"""
Pytest configuration and fixtures for test isolation.

This module provides fixtures and configuration to ensure proper test isolation
and prevent test interference when running the full test suite.
"""

import asyncio
import contextlib
import gc
import logging
import os
import sys
from collections.abc import Generator
from unittest.mock import _patch

import pytest


@pytest.fixture(autouse=True)
def clean_imports() -> Generator[None, None, None]:
    """
    Clean up module imports between tests to prevent state pollution.

    This fixture ensures that modules are properly reset between tests
    to prevent interference from cached module state.
    """
    # Store original import state
    dict(sys.modules)

    yield

    # Clean up modules that might have been modified during the test
    modules_to_clean = [
        "config",
        "config.__init__",
        "cogs.twi",
        "cogs.owner",
        "cogs.mods",
        "cogs.gallery",
        "cogs.patreon_poll",
        "cogs.stats",
        "utils.permissions",
        "utils.command_groups",
        "utils.db",
    ]

    for module_name in modules_to_clean:
        if module_name in sys.modules:
            # Always remove from cache to force reload on next import
            # This ensures fresh module state for each test
            with contextlib.suppress(KeyError):
                del sys.modules[module_name]

    # Force garbage collection
    gc.collect()


@pytest.fixture(autouse=True)
def reset_environment() -> Generator[None, None, None]:
    """
    Reset environment variables and config state between tests.
    """
    # Store original environment
    original_env = dict(os.environ)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

    # Force dotenv to reload on next import
    if "dotenv" in sys.modules:
        with contextlib.suppress(KeyError):
            del sys.modules["dotenv"]


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None, None, None]:
    """
    Reset logging configuration between tests.
    """
    # Store original logging state
    original_level = logging.getLogger().level
    original_handlers = logging.getLogger().handlers[:]

    yield

    # Reset logging state
    logging.getLogger().setLevel(original_level)
    logging.getLogger().handlers = original_handlers


@pytest.fixture(autouse=True)
def clean_mocks() -> Generator[None, None, None]:
    """
    Clean up all active mocks between tests to prevent state pollution.
    """
    # Store active patches before test
    try:
        if hasattr(_patch, "_active_patches"):
            list(_patch._active_patches)
    except (AttributeError, ImportError):
        pass

    yield

    # Stop all active patches that were created during the test
    try:
        # Access the internal patch registry and stop all patches
        if hasattr(_patch, "_active_patches"):
            current_patches = list(_patch._active_patches)
            for patcher in current_patches:
                try:
                    patcher.stop()
                except (RuntimeError, AttributeError):
                    # Patch might already be stopped or invalid
                    pass

            # Clear the active patches list to ensure clean state
            _patch._active_patches.clear()

    except (AttributeError, ImportError):
        # Fallback if internal API changes
        pass

    # Additional cleanup: reset any module-level mocks
    import unittest.mock

    try:
        # Reset the mock registry
        if hasattr(unittest.mock, "_mock_registry"):
            unittest.mock._mock_registry.clear()
    except (AttributeError, ImportError):
        pass


@pytest.fixture(autouse=True)
def clean_asyncio() -> Generator[None, None, None]:
    """
    Clean up asyncio state between tests.
    """
    yield

    # Clean up any remaining tasks
    try:
        loop = asyncio.get_running_loop()
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            # Wait a bit for tasks to cancel
            asyncio.create_task(asyncio.sleep(0.01))
    except RuntimeError:
        # No running loop
        pass
