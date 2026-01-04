import asyncio
import logging
from contextlib import asynccontextmanager

from discord import Webhook

import config


class _DisabledWebhook:
    """A no-op webhook that silently ignores all operations when webhooks are disabled."""

    async def send(self, *args, **kwargs):
        """Silently ignore send operations."""
        pass


class WebhookManager:
    def __init__(self, http_client) -> None:
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
        self._disabled_webhook = _DisabledWebhook()

    @asynccontextmanager
    async def get_webhook(self, webhook_url: str, max_retries: int = 2):
        """Context manager for webhook operations with automatic session management.

        Args:
            webhook_url: The webhook URL to use
            max_retries: Maximum number of retries on session errors

        Yields:
            discord.Webhook: Ready-to-use webhook instance, or a no-op webhook if disabled
        """
        # In staging mode with webhooks disabled, return a no-op webhook
        if not config.webhooks_enabled:
            self.logger.debug("Webhooks disabled - skipping webhook operation")
            yield self._disabled_webhook
            return

        session = None
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # Get a fresh session for this operation
                session = await self.http_client.get_fresh_session()
                webhook = Webhook.from_url(webhook_url, session=session)

                yield webhook
                break  # Success, exit retry loop

            except Exception as e:
                error_msg = str(e).lower()
                if "session is closed" in error_msg or "cannot reuse" in error_msg:
                    retry_count += 1
                    self.logger.warning(
                        f"Session error on webhook operation (attempt {retry_count}/{max_retries + 1}): {e}"
                    )

                    if session and not session.closed:
                        await session.close()
                    session = None

                    if retry_count <= max_retries:
                        await asyncio.sleep(0.1 * retry_count)  # Brief backoff
                        continue
                    else:
                        raise
                else:
                    # Non-session error, don't retry
                    raise
            finally:
                # Always clean up the session
                if session and not session.closed:
                    await session.close()
