"""Sentry error-reporting integration for Cognita bot.

This module wires the bot's error handling into `Sentry <https://sentry.io>`_.
It is intentionally a no-op unless the ``SENTRY_DSN`` environment variable is
set, so local development and the test suite are unaffected.

Sentry is fed exclusively from the existing error-handling choke point
(:func:`utils.error_handling.log_error`), and every event is run through the
project's :func:`redact_sensitive_info` scrubber via ``before_send`` so that no
unredacted secrets ever leave the process.

Environment variables:
    SENTRY_DSN: The project DSN from sentry.io. When unset, Sentry is disabled.
    SENTRY_TRACES_SAMPLE_RATE: Optional float (0.0-1.0) for performance tracing.
        Defaults to 0.0 (error reporting only, no performance overhead/quota).
"""

import logging
import os

logger = logging.getLogger("sentry")

# Whether sentry_sdk.init() has run successfully this process. Guards the
# capture helpers so they're cheap no-ops when Sentry is disabled.
_initialized: bool = False


def _before_send(event: dict, hint: dict) -> dict | None:
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
            if value.get("value"):
                value["value"] = redact_sensitive_info(value["value"])

        logentry = event.get("logentry")
        if logentry and logentry.get("message"):
            logentry["message"] = redact_sensitive_info(logentry["message"])
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
