"""Repository for quotes operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.quote import Quote


class QuoteRepository:
    """Repository for managing quotes."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_all(self) -> list[Quote]:
        """Get all quotes.

        Returns:
            List of all Quote entries.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(select(Quote))
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting all quotes: {e}")
            return []

    async def get_by_serial_id(self, serial_id: int) -> Quote | None:
        """Get a quote by serial ID.

        Args:
            serial_id: The quote serial ID.

        Returns:
            Quote entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Quote).where(Quote.serial_id == serial_id)
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting quote by serial_id {serial_id}: {e}")
            return None

    async def get_by_author_id(self, author_id: int) -> list[Quote]:
        """Get all quotes by an author.

        Args:
            author_id: The Discord user ID of the author.

        Returns:
            List of Quote entries by the author.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Quote).where(Quote.author_id == author_id)
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting quotes by author {author_id}: {e}")
            return []

    async def get_count(self) -> int:
        """Get the total number of quotes.

        Returns:
            Total count of quotes.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(select(func.count(Quote.serial_id)))
                return result.scalar() or 0
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting quote count: {e}")
            return 0

    async def get_all_for_cache(self) -> list[dict]:
        """Get all quotes with minimal data for caching.

        Returns:
            List of dicts with quote and row_number.
        """
        try:
            session = await self.session_factory()
            try:
                # Use row_number window function
                result = await session.execute(select(Quote.quote, Quote.serial_id))
                return [
                    {"quote": row.quote, "row_number": row.serial_id} for row in result
                ]
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting quotes for cache: {e}")
            return []

    async def create(
        self,
        quote: str,
        author: str | None = None,
        author_id: int | None = None,
    ) -> Quote | None:
        """Create a new quote.

        Args:
            quote: The quote text.
            author: The author's display name.
            author_id: The Discord user ID of the author.

        Returns:
            Created Quote entry or None if failed.
        """
        try:
            session = await self.session_factory()
            try:
                entry = Quote(
                    quote=quote,
                    author=author,
                    author_id=author_id,
                    time=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(f"Created quote {entry.serial_id}")
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating quote: {e}")
            return None

    async def delete_by_serial_id(self, serial_id: int) -> bool:
        """Delete a quote by serial ID.

        Args:
            serial_id: The quote serial ID.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(delete(Quote).where(Quote.serial_id == serial_id))
                await session.commit()
                self.logger.info(f"Deleted quote {serial_id}")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting quote: {e}")
            return False

    async def delete_by_author_id(self, author_id: int) -> int:
        """Delete all quotes by an author.

        Args:
            author_id: The Discord user ID of the author.

        Returns:
            Number of quotes deleted.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    delete(Quote).where(Quote.author_id == author_id)
                )
                await session.commit()
                deleted_count = result.rowcount
                self.logger.info(
                    f"Deleted {deleted_count} quotes by author {author_id}"
                )
                return deleted_count
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting quotes by author: {e}")
            return 0

    async def exists(self, serial_id: int) -> bool:
        """Check if a quote exists with the given serial ID.

        Args:
            serial_id: The quote serial ID.

        Returns:
            True if exists, False otherwise.
        """
        entry = await self.get_by_serial_id(serial_id)
        return entry is not None
