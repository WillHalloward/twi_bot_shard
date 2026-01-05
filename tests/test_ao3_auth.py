"""
Unit tests for AO3 async authentication with retry logic.

This module tests the async AO3 authentication system in cogs/other.py,
including the executor pattern for non-blocking auth, retry logic with
exponential backoff, and the ao3_status admin command.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import Discord components

# Import the cog to test
from cogs.other import OtherCogs

# Import test utilities
from tests.mock_factories import MockInteractionFactory
from tests.test_utils import TestSetup, TestTeardown


class TestAO3SessionInitialization:
    """Tests for AO3 session initialization."""

    @pytest.mark.asyncio
    async def test_ao3_session_state_initialization(self):
        """Test that AO3 session state variables are initialized."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Verify state variables exist
        assert hasattr(cog, "ao3_session")
        assert hasattr(cog, "ao3_login_successful")
        assert hasattr(cog, "ao3_login_in_progress")

        # Verify initial states
        assert cog.ao3_session is None
        assert cog.ao3_login_successful is False
        assert cog.ao3_login_in_progress is False

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_initialize_ao3_session_success_first_try(self):
        """Test successful AO3 auth on first attempt."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Mock AO3.Session to return a successful session
        mock_session = MagicMock()
        mock_session.is_authed = True

        with patch("cogs.other.AO3.Session", return_value=mock_session):
            # Call the initialization method
            await cog._initialize_ao3_session(max_retries=3)

            # Verify session was set
            assert cog.ao3_session is not None
            assert cog.ao3_login_successful is True
            assert cog.ao3_login_in_progress is False

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_initialize_ao3_session_retry_logic(self):
        """Test that AO3 auth retries on failure."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Mock AO3.Session to fail first, then succeed
        call_count = 0

        def mock_ao3_session_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails
                raise Exception("Auth failed")
            else:
                # Second call succeeds
                mock_session = MagicMock()
                mock_session.is_authed = True
                return mock_session

        with patch("cogs.other.AO3.Session", side_effect=mock_ao3_session_side_effect):
            # Mock asyncio.sleep to avoid delays in testing
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Call the initialization method
                await cog._initialize_ao3_session(max_retries=3)

                # Verify it retried and succeeded
                assert call_count == 2
                assert cog.ao3_login_successful is True

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_initialize_ao3_session_all_retries_fail(self):
        """Test that AO3 auth handles all retries failing."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Mock AO3.Session to always fail
        with patch(
            "cogs.other.AO3.Session", side_effect=Exception("Auth always fails")
        ):
            # Mock asyncio.sleep to avoid delays
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Call the initialization method
                await cog._initialize_ao3_session(max_retries=3)

                # Verify all retries failed
                assert cog.ao3_session is None
                assert cog.ao3_login_successful is False
                assert cog.ao3_login_in_progress is False

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_initialize_ao3_session_prevents_concurrent_init(self):
        """Test that concurrent initialization attempts are prevented."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Set login_in_progress to True
        cog.ao3_login_in_progress = True

        # Mock AO3.Session
        with patch("cogs.other.AO3.Session") as mock_ao3:
            # Call initialization
            await cog._initialize_ao3_session()

            # Verify AO3.Session was NOT called (concurrent call prevented)
            mock_ao3.assert_not_called()

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestAO3StatusCommand:
    """Tests for the /admin ao3_status command."""

    @pytest.mark.asyncio
    async def test_ao3_status_when_logged_in(self):
        """Test ao3_status command when session is active."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Set successful login state
        cog.ao3_login_successful = True
        cog.ao3_session = MagicMock()

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern
        await cog.ao3_status.callback(cog, interaction)

        # Verify response sent
        assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_ao3_status_when_not_logged_in(self):
        """Test ao3_status command when session is not active."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Set failed login state
        cog.ao3_login_successful = False
        cog.ao3_session = None

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Call the command using callback pattern
        await cog.ao3_status.callback(cog, interaction)

        # Verify response sent
        assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)

    @pytest.mark.asyncio
    async def test_ao3_status_manual_retry(self):
        """Test manual retry from ao3_status command."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Set failed login state
        cog.ao3_login_successful = False
        cog.ao3_session = None

        # Mock interaction
        interaction = MockInteractionFactory.create()

        # Mock _initialize_ao3_session
        cog._initialize_ao3_session = AsyncMock()

        # Call with retry option - this would come from a button interaction
        # For now, just test that the command responds
        await cog.ao3_status.callback(cog, interaction)

        # Verify response sent
        assert interaction.response.defer.called or interaction.followup.send.called

        # Cleanup
        await TestTeardown.teardown_bot(bot)


class TestAO3ExecutorPattern:
    """Tests for the executor pattern used in AO3 auth."""

    @pytest.mark.asyncio
    async def test_ao3_uses_executor_for_blocking_call(self):
        """Test that AO3.Session is called in executor, not main loop."""
        # Create a test bot
        bot = await TestSetup.create_test_bot()

        # Create the OtherCogs
        cog = OtherCogs(bot)

        # Mock AO3.Session
        mock_session = MagicMock()
        mock_session.is_authed = True

        # Track if run_in_executor was called
        executor_called = False

        async def mock_run_in_executor(executor, func, *args):
            nonlocal executor_called
            executor_called = True
            # Simulate executor running the blocking function
            return func(*args)

        with patch("cogs.other.AO3.Session", return_value=mock_session):
            # Get event loop and mock run_in_executor
            loop = asyncio.get_event_loop()
            original_run_in_executor = loop.run_in_executor
            loop.run_in_executor = mock_run_in_executor

            try:
                # Call initialization
                await cog._initialize_ao3_session(max_retries=1)

                # Verify executor was used
                assert executor_called is True
            finally:
                # Restore original
                loop.run_in_executor = original_run_in_executor

        # Cleanup
        await TestTeardown.teardown_bot(bot)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main(["-v", __file__])
