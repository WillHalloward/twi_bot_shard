"""Repository for server settings operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.server_settings import ServerSettings


class ServerSettingsRepository:
    """Repository for managing server settings."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_by_guild_id(self, guild_id: int) -> ServerSettings | None:
        """Get server settings for a guild.

        Args:
            guild_id: The Discord guild ID.

        Returns:
            ServerSettings entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(ServerSettings).where(ServerSettings.guild_id == guild_id)
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting server settings for guild {guild_id}: {e}"
            )
            return None

    async def get_admin_role_id(self, guild_id: int) -> int | None:
        """Get the admin role ID for a guild.

        Args:
            guild_id: The Discord guild ID.

        Returns:
            Admin role ID or None if not set.
        """
        settings = await self.get_by_guild_id(guild_id)
        return settings.admin_role_id if settings else None

    async def create(
        self, guild_id: int, admin_role_id: int | None = None
    ) -> ServerSettings | None:
        """Create server settings for a guild.

        Args:
            guild_id: The Discord guild ID.
            admin_role_id: Optional admin role ID.

        Returns:
            Created ServerSettings entry or None if failed.
        """
        try:
            session = await self.session_factory()
            try:
                entry = ServerSettings(
                    guild_id=guild_id,
                    admin_role_id=admin_role_id,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(f"Created server settings for guild {guild_id}")
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating server settings: {e}")
            return None

    async def update_admin_role(self, guild_id: int, admin_role_id: int) -> bool:
        """Update the admin role for a guild.

        Args:
            guild_id: The Discord guild ID.
            admin_role_id: The new admin role ID.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            session = await self.session_factory()
            try:
                await session.execute(
                    update(ServerSettings)
                    .where(ServerSettings.guild_id == guild_id)
                    .values(
                        admin_role_id=admin_role_id,
                        updated_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
                await session.commit()
                self.logger.info(
                    f"Updated admin role for guild {guild_id} to {admin_role_id}"
                )
                return True
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error updating admin role: {e}")
            return False

    async def upsert(self, guild_id: int, admin_role_id: int) -> ServerSettings | None:
        """Create or update server settings for a guild.

        Args:
            guild_id: The Discord guild ID.
            admin_role_id: The admin role ID.

        Returns:
            ServerSettings entry or None if failed.
        """
        existing = await self.get_by_guild_id(guild_id)
        if existing:
            success = await self.update_admin_role(guild_id, admin_role_id)
            if success:
                return await self.get_by_guild_id(guild_id)
            return None
        return await self.create(guild_id, admin_role_id)

    async def get_all_admin_roles(self) -> list[dict]:
        """Get all guild admin roles.

        Returns:
            List of dicts with guild_id and admin_role_id.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(ServerSettings.guild_id, ServerSettings.admin_role_id).where(
                        ServerSettings.admin_role_id.isnot(None)
                    )
                )
                return [
                    {"guild_id": row.guild_id, "admin_role_id": row.admin_role_id}
                    for row in result
                ]
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting all admin roles: {e}")
            return []
