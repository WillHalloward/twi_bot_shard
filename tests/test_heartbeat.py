"""Tests for the heartbeat liveness cog's environment gate.

The dead-man's-switch loop must run only in deployed environments
(staging/production) and must be gated on the environment enum, not on
incidental configuration like the logfile name (audit findings 07/08).
"""

import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Keep a reference to the module object: the autouse clean_imports fixture in
# conftest.py removes "config" from sys.modules after every test, so
# patch("config.<name>") would patch a freshly re-imported config module
# instead of the one cogs.heartbeat actually holds a reference to. Patching
# heartbeat_module.config targets the right object regardless.
import cogs.heartbeat as heartbeat_module
from cogs.heartbeat import Heartbeat


def _make_bot() -> MagicMock:
    """Create a minimal mock bot for the Heartbeat cog."""
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.is_closed = MagicMock(return_value=True)
    return bot


def _patch_env(*, production: bool, staging: bool) -> tuple[Any, Any]:
    """Patch the environment helpers on the config module heartbeat uses."""
    return (
        patch.object(heartbeat_module.config, "is_production", return_value=production),
        patch.object(heartbeat_module.config, "is_staging", return_value=staging),
    )


class TestHeartbeatGate:
    """The loop starts iff ENVIRONMENT is staging or production."""

    @pytest.mark.asyncio
    async def test_loop_starts_in_staging(self) -> None:
        """Staging is a deployed environment; the loop must run."""
        prod_patch, staging_patch = _patch_env(production=False, staging=True)
        with prod_patch, staging_patch:
            cog = Heartbeat(_make_bot())
        try:
            assert cog.heartbeat_loop.is_running()
        finally:
            cog.heartbeat_loop.cancel()

    @pytest.mark.asyncio
    async def test_loop_starts_in_production(self) -> None:
        """Production is a deployed environment; the loop must run."""
        prod_patch, staging_patch = _patch_env(production=True, staging=False)
        with prod_patch, staging_patch:
            cog = Heartbeat(_make_bot())
        try:
            assert cog.heartbeat_loop.is_running()
        finally:
            cog.heartbeat_loop.cancel()

    @pytest.mark.asyncio
    async def test_loop_skipped_outside_deployed_environments(self) -> None:
        """Development/testing must not start the loop."""
        prod_patch, staging_patch = _patch_env(production=False, staging=False)
        with prod_patch, staging_patch:
            cog = Heartbeat(_make_bot())
        assert not cog.heartbeat_loop.is_running()

    @pytest.mark.asyncio
    async def test_gate_ignores_logfile(self) -> None:
        """Regression: a non-"test" logfile alone must not enable the loop."""
        prod_patch, staging_patch = _patch_env(production=False, staging=False)
        with (
            prod_patch,
            staging_patch,
            patch.object(heartbeat_module.config, "logfile", "railway"),
        ):
            cog = Heartbeat(_make_bot())
        assert not cog.heartbeat_loop.is_running()


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])
