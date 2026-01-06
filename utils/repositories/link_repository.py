"""Repository for links/tags operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.link import Link


class LinkRepository:
    """Repository for managing links/tags."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_all(self) -> list[Link]:
        """Get all links.

        Returns:
            List of all Link entries.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(select(Link))
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting all links: {e}")
            return []

    async def get_by_title(self, title: str) -> Link | None:
        """Get a link by title (case-insensitive).

        Args:
            title: The link title.

        Returns:
            Link entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Link).where(func.lower(Link.title) == func.lower(title))
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting link by title {title}: {e}")
            return None

    async def get_by_tag(self, tag: str) -> list[Link]:
        """Get all links with a specific tag.

        Args:
            tag: The tag to filter by.

        Returns:
            List of Link entries with the tag.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(select(Link).where(Link.tag == tag))
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting links by tag {tag}: {e}")
            return []

    async def get_titles_by_tag(self, tag: str) -> list[str]:
        """Get all link titles with a specific tag.

        Args:
            tag: The tag to filter by.

        Returns:
            List of titles.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Link.title).where(Link.tag == tag)
                )
                return [row.title for row in result if row.title]
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting titles by tag {tag}: {e}")
            return []

    async def get_by_guild_id(self, guild_id: int) -> list[Link]:
        """Get all links for a specific guild.

        Args:
            guild_id: The Discord guild ID.

        Returns:
            List of Link entries for the guild.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Link).where(Link.guild_id == guild_id)
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting links for guild {guild_id}: {e}")
            return []

    async def create(
        self,
        title: str,
        content: str | None = None,
        tag: str | None = None,
        user_who_added: str | None = None,
        id_user_who_added: int | None = None,
        embed: bool | None = None,
        guild_id: int | None = None,
    ) -> Link | None:
        """Create a new link.

        Args:
            title: The link title.
            content: The link content/URL.
            tag: Optional tag for categorization.
            user_who_added: Username of who added the link.
            id_user_who_added: User ID of who added the link.
            embed: Whether to embed the link.
            guild_id: The Discord guild ID.

        Returns:
            Created Link entry or None if failed.
        """
        try:
            session = await self.session_factory()
            try:
                entry = Link(
                    title=title,
                    content=content,
                    tag=tag,
                    user_who_added=user_who_added,
                    id_user_who_added=id_user_who_added,
                    time_added=datetime.now(UTC).replace(tzinfo=None),
                    embed=embed,
                    guild_id=guild_id,
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(f"Created link '{title}'")
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating link: {e}")
            return None

    async def update(
        self,
        title: str,
        content: str | None = None,
        tag: str | None = None,
        embed: bool | None = None,
    ) -> bool:
        """Update an existing link by title.

        Args:
            title: The link title (case-insensitive match).
            content: New content/URL.
            tag: New tag.
            embed: New embed setting.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                values = {}
                if content is not None:
                    values["content"] = content
                if tag is not None:
                    values["tag"] = tag
                if embed is not None:
                    values["embed"] = embed

                if values:
                    await session.execute(
                        update(Link)
                        .where(func.lower(Link.title) == func.lower(title))
                        .values(**values)
                    )
                    await session.commit()
                    self.logger.info(f"Updated link '{title}'")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating link: {e}")
            return False

    async def delete_by_title(self, title: str) -> bool:
        """Delete a link by title (case-insensitive).

        Args:
            title: The link title.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    delete(Link).where(func.lower(Link.title) == func.lower(title))
                )
                await session.commit()
                self.logger.info(f"Deleted link '{title}'")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error deleting link: {e}")
            return False

    async def exists(self, title: str) -> bool:
        """Check if a link exists with the given title.

        Args:
            title: The link title.

        Returns:
            True if exists, False otherwise.
        """
        entry = await self.get_by_title(title)
        return entry is not None
