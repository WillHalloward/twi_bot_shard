"""Sentry error-reporting integration for Cognita bot.

This module wires the bot's error handling into `Sentry <https://sentry.io>`_.
It is intentionally a no-op unless the ``SENTRY_DSN`` environment variable is
set, so local development and the test suite are unaffected.

Sentry is fed from several paths: the error-handling choke point
(:func:`utils.error_handling.log_error`), the global escalation handlers wired in
``setup_global_exception_handler`` (the ``on_error`` event-dispatch net, the
asyncio ``loop.set_exception_handler``, and ``sys.excepthook``), the background
``@tasks.loop`` ``.error`` handlers, the liveness heartbeat
(:func:`send_heartbeat`), and Sentry's default ``LoggingIntegration`` (any
ERROR-level log becomes an event). Every event is run through the project's
:func:`redact_sensitive_info` scrubber via ``before_send`` so that no unredacted
secrets ever leave the process.

Environment variables:
    SENTRY_DSN: The project DSN from sentry.io. When unset, Sentry is disabled.
    SENTRY_TRACES_SAMPLE_RATE: Optional float (0.0-1.0) for performance tracing.
        Defaults to 0.0 (error reporting only, no performance overhead/quota).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-only import; avoids a hard runtime dependency on sentry_sdk so the
    # module still imports cleanly when the package is absent.
    from sentry_sdk.types import Event, Hint

logger = logging.getLogger("sentry")

# Whether sentry_sdk.init() has run successfully this process. Guards the
# capture helpers so they're cheap no-ops when Sentry is disabled.
_initialized: bool = False


def _before_send(event: Event, hint: Hint) -> Event | None:
    """Scrub sensitive data from outgoing Sentry events.

    Runs exception messages and the log entry message through the project's
    existing redaction patterns. Stacktrace frames (file paths, code) are left
    intact since they're code locations, not secrets, and are the whole point
    of the report.

    Args:
        event: The Sentry event payload about to be sent.
        hint: Sentry-provided context (unused, but part of the hook signature).

    Returns:
        The scrubbed event, or None to drop it.
    """
    # Imported lazily to avoid a circular import with utils.error_handling.
    from utils.error_handling import redact_sensitive_info

    try:
        for value in event.get("exception", {}).get("values", []):
            message = value.get("value")
            if isinstance(message, str):
                value["value"] = redact_sensitive_info(message)

        # Typed as a read-only Mapping in Sentry's stubs, but a mutable dict at
        # runtime; annotate Any so the in-place scrub type-checks.
        logentry: Any = event.get("logentry")
        if logentry:
            message = logentry.get("message")
            if isinstance(message, str):
                logentry["message"] = redact_sensitive_info(message)
    except Exception as exc:  # pragma: no cover - defensive; never block sending
        logger.debug(f"Sentry before_send scrubbing failed: {exc}")

    return event


def init_sentry(
    environment: str | None = None,
    release: str | None = None,
) -> bool:
    """Initialise Sentry if a DSN is configured.

    Safe to call unconditionally: when ``SENTRY_DSN`` is unset (local dev,
    tests) this logs a debug line and returns False without side effects.

    Args:
        environment: Deployment environment tag (e.g. "production",
            "staging"). Falls back to the bot's configured environment.
        release: Release identifier, typically a git SHA, used by Sentry to
            tie errors to a specific deploy.

    Returns:
        True if Sentry was initialised, False otherwise.
    """
    global _initialized

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.debug("SENTRY_DSN not set; Sentry error reporting disabled.")
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but the 'sentry-sdk' package is not installed; "
            "Sentry error reporting disabled. Run `uv pip install -e .`."
        )
        return False

    if environment is None:
        from config import get_environment

        environment = str(get_environment())

    try:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    except ValueError:
        traces_sample_rate = 0.0

    # NOTE: default_integrations is left enabled on purpose. The default
    # LoggingIntegration is a secondary safety net — it turns any ERROR-level
    # stdlib log record (which includes structlog output, discord.py's event
    # logger, and asyncio's task-exception logger) into a Sentry event. The
    # primary, richer path is the explicit capture_exception() calls in
    # utils/error_handling.py (log_error, on_error, the asyncio handler) and the
    # uncaught-exception hook, which attach the exception object, a full
    # traceback, and Discord context tags. Listener errors not otherwise
    # captured still lean on this logging integration, so do NOT pass
    # integrations=[...] or default_integrations=False here without first wiring
    # explicit capture_exception() calls for those paths — doing so would
    # silently drop that coverage.
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        # Never attach IPs/usernames automatically; we add only the IDs we
        # explicitly choose in capture_exception().
        send_default_pii=False,
        traces_sample_rate=traces_sample_rate,
        before_send=_before_send,
    )

    _initialized = True
    logger.info(
        "Sentry initialised (environment=%s, release=%s)",
        environment,
        release or "unknown",
    )
    return True


def capture_exception(
    error: Exception,
    *,
    command_name: str | None = None,
    user_id: int | None = None,
    guild_id: int | None = None,
    channel_id: int | None = None,
    additional_context: str | None = None,
) -> None:
    """Send an exception to Sentry with Discord context, if Sentry is enabled.

    A cheap no-op when Sentry is not initialised. Context is attached as tags
    (for filtering/grouping in the Sentry UI) rather than PII.

    Args:
        error: The exception to report.
        command_name: Name of the command that raised the error, if any.
        user_id: Discord user ID that triggered the error.
        guild_id: Discord guild ID where the error occurred.
        channel_id: Discord channel ID where the error occurred.
        additional_context: Free-form extra context to attach.
    """
    if not _initialized:
        return

    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        if command_name is not None:
            scope.set_tag("command", command_name)
        if guild_id is not None:
            scope.set_tag("guild_id", str(guild_id))
        if user_id is not None:
            # Recorded as id-only; send_default_pii stays False.
            scope.set_user({"id": str(user_id)})
        if channel_id is not None:
            scope.set_context("discord", {"channel_id": channel_id})
        if additional_context:
            scope.set_context("additional", {"info": additional_context})

        sentry_sdk.capture_exception(error)


# Slug for the liveness heartbeat cron monitor. Sentry auto-creates the monitor
# from the monitor_config on the first check-in (upsert), so no UI setup needed.
HEARTBEAT_MONITOR_SLUG = "twi-bot-heartbeat"


def send_heartbeat() -> None:
    """Send a liveness check-in to Sentry's cron monitoring, if Sentry is enabled.

    Acts as a dead-man's-switch: a background task calls this on a fixed
    interval while the bot is connected. Sentry expects a check-in every 5
    minutes and tolerates a 10-minute margin; if check-ins stop (process dead,
    hung, OOM-killed, or disconnected), Sentry raises a missed-check-in issue
    (~15 min) which routes to Discord like any other issue.

    A cheap no-op when Sentry is not initialised.
    """
    if not _initialized:
        return

    from sentry_sdk.crons import capture_checkin

    capture_checkin(
        monitor_slug=HEARTBEAT_MONITOR_SLUG,
        status="ok",
        monitor_config={
            "schedule": {"type": "interval", "value": 5, "unit": "minute"},
            "checkin_margin": 10,  # minutes of tolerance (covers redeploys)
            "max_runtime": 2,
            "timezone": "UTC",
            "failure_issue_threshold": 1,
            "recovery_threshold": 1,
        },
    )
