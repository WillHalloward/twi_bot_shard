"""Repository for gallery mementos operations."""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.gallery import GalleryMementos


class GalleryMementosRepository:
    """Repository for managing gallery mementos (repost channels)."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_all(self) -> list[GalleryMementos]:
        """Get all gallery mementos.

        Returns:
            List of all GalleryMementos entries.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(select(GalleryMementos))
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting all gallery mementos: {e}")
            return []

    async def get_by_guild_id(self, guild_id: int) -> list[GalleryMementos]:
        """Get all gallery mementos for a specific guild.

        Args:
            guild_id: The Discord guild ID.

        Returns:
            List of GalleryMementos for the guild.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMementos).where(GalleryMementos.guild_id == guild_id)
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting gallery mementos for guild {guild_id}: {e}"
            )
            return []

    async def get_by_channel_id(self, channel_id: int) -> GalleryMementos | None:
        """Get a gallery memento by channel ID.

        Args:
            channel_id: The Discord channel ID.

        Returns:
            GalleryMementos entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(GalleryMementos).where(
                        GalleryMementos.channel_id == channel_id
                    )
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting gallery memento for channel {channel_id}: {e}"
            )
            return None

    async def create(
        self, channel_name: str, channel_id: int, guild_id: int
    ) -> GalleryMementos | None:
        """Create a new gallery memento.

        Args:
            channel_name: The channel name.
            channel_id: The Discord channel ID.
            guild_id: The Discord guild ID.

        Returns:
            Created GalleryMementos entry or None if failed.
        """
        try:
            session = await self.session_factory()
            try:
                entry = GalleryMementos(
                    channel_name=channel_name,
                    channel_id=channel_id,
                    guild_id=guild_id,
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(
                    f"Created gallery memento for channel {channel_name} ({channel_id})"
                )
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating gallery memento: {e}")
            return None

    async def delete_by_channel_id(self, channel_id: int) -> bool:
        """Delete a gallery memento by channel ID.

        Args:
            channel_id: The Discord channel ID.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    delete(GalleryMementos).where(
                        GalleryMementos.channel_id == channel_id
                    )
                )
                await session.commit()
                self.logger.info(f"Deleted gallery memento for channel {channel_id}")
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error deleting gallery memento for channel {channel_id}: {e}"
            )
            return False

    async def exists(self, channel_id: int) -> bool:
        """Check if a gallery memento exists for a channel.

        Args:
            channel_id: The Discord channel ID.

        Returns:
            True if exists, False otherwise.
        """
        entry = await self.get_by_channel_id(channel_id)
        return entry is not None
