import asyncio
import logging
from contextlib import asynccontextmanager

from discord import Webhook


class WebhookManager:
    def __init__(self, http_client) -> None:
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def get_webhook(self, webhook_url: str, max_retries: int = 2):
        """Context manager for webhook operations with automatic session management.

        Args:
            webhook_url: The webhook URL to use
            max_retries: Maximum number of retries on session errors

        Yields:
            discord.Webhook: Ready-to-use webhook instance
        """
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
