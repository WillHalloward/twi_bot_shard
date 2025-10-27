"""Repository for gallery_mementos table.

This module provides a repository for accessing gallery_mementos data.
"""

from sqlalchemy import select

from models.tables.gallery import GalleryMementos
from utils.repository import BaseRepository


class GalleryRepository(BaseRepository):
    """Repository for gallery_mementos table."""

    def __init__(self, session_maker) -> None:
        """Initialize the repository.

        Args:
            session_maker: Factory function to create database sessions.
        """
        super().__init__(session_maker, GalleryMementos)

    async def get_by_guild(self, guild_id: int) -> list[GalleryMementos]:
        """Get all gallery channels for a guild.

        Args:
            guild_id: The ID of the guild.

        Returns:
            A list of gallery channels for the guild.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(self.entity_type).where(self.entity_type.guild_id == guild_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_channel_id(self, channel_id: int) -> GalleryMementos | None:
        """Get a gallery channel by its channel ID.

        Args:
            channel_id: The ID of the channel.

        Returns:
            The gallery channel if found, None otherwise.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(self.entity_type).where(
                self.entity_type.channel_id == channel_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_channel(
        self, channel_name: str, channel_id: int, guild_id: int
    ) -> GalleryMementos:
        """Add a new gallery channel.

        Args:
            channel_name: The name of the channel.
            channel_id: The ID of the channel.
            guild_id: The ID of the guild.

        Returns:
            The created gallery channel.
        """
        gallery = GalleryMementos(
            channel_name=channel_name, channel_id=channel_id, guild_id=guild_id
        )
        return await self.create(gallery)

    async def delete_channel(self, channel_name: str) -> bool:
        """Delete a gallery channel by its name.

        Args:
            channel_name: The name of the channel.

        Returns:
            True if the channel was deleted, False otherwise.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(self.entity_type).where(
                self.entity_type.channel_name == channel_name
            )
            result = await session.execute(stmt)
            channel = result.scalar_one_or_none()

            if not channel:
                return False

            session.delete(channel)
            await session.commit()
            return True
