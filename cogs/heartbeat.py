"""Liveness heartbeat cog for Twi Bot Shard.

Implements a dead-man's-switch: while the bot is connected to Discord, a
background task sends a check-in to Sentry's cron monitoring every 5 minutes.
Sentry watches for those check-ins externally — if they stop (process dead,
hung, OOM-killed, or silently disconnected), Sentry raises a missed-check-in
issue (~15 min) that routes to Discord like any other alert.

This catches the "unreachable but not throwing errors" failure mode that the
exception-based reporting can't, precisely because the alert is driven by an
external observer reacting to the *absence* of a signal — a check inside the
bot can't fire when the bot itself is dead.

The heartbeat is a no-op unless SENTRY_DSN is configured, so local development
and tests are unaffected.
"""

import asyncio

from discord.ext import commands, tasks

import config
from utils.base_cog import BaseCog
from utils.sentry_setup import capture_exception, send_heartbeat


class Heartbeat(BaseCog):
    """Sends periodic liveness check-ins to Sentry cron monitoring."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the cog and start the heartbeat loop (outside test mode)."""
        super().__init__(bot)
        # Mirror the project convention: don't start background loops in tests.
        if config.logfile != "test":
            self.heartbeat_loop.start()
            self.logger.info("heartbeat_loop_started")
        else:
            self.logger.info("heartbeat_loop_disabled", reason="test_mode")

    async def cog_unload(self) -> None:
        """Stop the heartbeat loop when the cog is unloaded."""
        if hasattr(self, "heartbeat_loop") and self.heartbeat_loop.is_running():
            self.heartbeat_loop.cancel()
            self.logger.info("heartbeat_loop_stopped")

    @tasks.loop(minutes=5)
    async def heartbeat_loop(self) -> None:
        """Send one liveness check-in, only while genuinely connected.

        Skipping the check-in when the bot is closed means a sustained outage
        shows up as missed check-ins in Sentry rather than false "healthy"
        pings.
        """
        if self.bot.is_closed():
            return
        send_heartbeat()

    @heartbeat_loop.error
    async def heartbeat_loop_error(self, error: Exception) -> None:
        """Report a heartbeat-loop crash to Sentry and restart the loop.

        A discord.py ``tasks.loop`` stops permanently after an unhandled
        exception, so without this the liveness signal would die silently —
        the worst case, since a dead heartbeat is indistinguishable from a dead
        bot. We capture the error explicitly (with traceback and tags, unlike
        the bare log record the default logging integration would send) and
        restart after a short backoff so transient faults don't hammer.
        """
        self.logger.error(
            "heartbeat_loop_error",
            error=str(error),
            error_type=type(error).__name__,
        )
        capture_exception(error, command_name="heartbeat_loop")
        await asyncio.sleep(60)
        self.heartbeat_loop.restart()

    @heartbeat_loop.before_loop
    async def before_heartbeat(self) -> None:
        """Wait until the bot is connected before the first check-in.

        This also means a startup that hangs before reaching READY produces no
        check-ins, so Sentry will flag it — exactly the desired failsafe.
        """
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Required entry point for cog loading."""
    await bot.add_cog(Heartbeat(bot))
