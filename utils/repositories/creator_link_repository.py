"""Repository for creator links operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.creator_links import CreatorLink


class CreatorLinkRepository:
    """Repository for managing creator links."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_all_for_cache(self) -> list[dict]:
        """Get all creator links with minimal data for caching.

        Returns:
            List of dicts with title and user_id.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(CreatorLink.title, CreatorLink.user_id)
                )
                return [{"title": row.title, "user_id": row.user_id} for row in result]
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting creator links for cache: {e}")
            return []

    async def get_by_user_id(self, user_id: int) -> list[CreatorLink]:
        """Get all creator links for a user, ordered by weight descending.

        Args:
            user_id: The Discord user ID.

        Returns:
            List of CreatorLink entries for the user.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(CreatorLink)
                    .where(CreatorLink.user_id == user_id)
                    .order_by(CreatorLink.weight.desc())
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting creator links for user {user_id}: {e}")
            return []

    async def get_by_user_and_title(
        self, user_id: int, title: str
    ) -> CreatorLink | None:
        """Get a creator link by user ID and title (case-insensitive).

        Args:
            user_id: The Discord user ID.
            title: The link title.

        Returns:
            CreatorLink entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(CreatorLink).where(
                        CreatorLink.user_id == user_id,
                        func.lower(CreatorLink.title) == func.lower(title),
                    )
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting creator link for user {user_id}, title {title}: {e}"
            )
            return None

    async def create(
        self,
        user_id: int,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> CreatorLink | None:
        """Create a new creator link.

        Args:
            user_id: The Discord user ID.
            title: The link title.
            link: The URL.
            nsfw: Whether the link is NSFW.
            weight: Priority weight for ordering.
            feature: Whether to feature this link.

        Returns:
            Created CreatorLink entry or None if failed.

        Raises:
            IntegrityError: If a duplicate entry exists (unique constraint violation).
        """
        try:
            session = await self.session_factory()
            try:
                entry = CreatorLink(
                    user_id=user_id,
                    title=title,
                    link=link,
                    nsfw=nsfw,
                    weight=weight,
                    feature=feature,
                    last_changed=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(f"Created creator link '{title}' for user {user_id}")
                return entry
            finally:
                await session.close()
        except IntegrityError:
            # Re-raise IntegrityError so callers can handle duplicate entries
            raise
        except Exception as e:
            self.logger.error(f"Error creating creator link: {e}")
            return None

    async def update(
        self,
        user_id: int,
        title: str,
        link: str,
        nsfw: bool = False,
        weight: int = 0,
        feature: bool = True,
    ) -> bool:
        """Update an existing creator link.

        Args:
            user_id: The Discord user ID.
            title: The link title (case-insensitive match).
            link: The new URL.
            nsfw: Whether the link is NSFW.
            weight: Priority weight for ordering.
            feature: Whether to feature this link.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(CreatorLink)
                    .where(
                        CreatorLink.user_id == user_id,
                        func.lower(CreatorLink.title) == func.lower(title),
                    )
                    .values(
                        link=link,
                        nsfw=nsfw,
                        weight=weight,
                        feature=feature,
                        last_changed=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
                await session.commit()
                self.logger.info(f"Updated creator link '{title}' for user {user_id}")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating creator link: {e}")
            return False

    async def delete(self, user_id: int, title: str) -> bool:
        """Delete a creator link by user ID and title.

        Args:
            user_id: The Discord user ID.
            title: The link title (case-insensitive match).

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    delete(CreatorLink).where(
                        CreatorLink.user_id == user_id,
                        func.lower(CreatorLink.title) == func.lower(title),
                    )
                )
                await session.commit()
                self.logger.info(f"Deleted creator link '{title}' for user {user_id}")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting creator link: {e}")
            return False

    async def exists(self, user_id: int, title: str) -> bool:
        """Check if a creator link exists for a user with the given title.

        Args:
            user_id: The Discord user ID.
            title: The link title.

        Returns:
            True if exists, False otherwise.
        """
        entry = await self.get_by_user_and_title(user_id, title)
        return entry is not None
