"""Repository for report operations."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.report import Report


class ReportRepository:
    """Repository for managing user reports."""

    def __init__(self, session_factory: Callable[[], Awaitable[AsyncSession]]) -> None:
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)

    async def get_by_message_and_user(
        self, message_id: int, user_id: int
    ) -> Report | None:
        """Get a report by message ID and user ID.

        Args:
            message_id: The Discord message ID.
            user_id: The Discord user ID who made the report.

        Returns:
            Report entry or None if not found.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Report).where(
                        Report.message_id == message_id, Report.user_id == user_id
                    )
                )
                return result.scalar_one_or_none()
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting report for message {message_id}, user {user_id}: {e}"
            )
            return None

    async def create(
        self,
        message_id: int,
        user_id: int,
        reason: str,
        anonymous: bool,
        additional_info: str,
        reported_user_id: int,
        guild_id: int | None,
        channel_id: int,
    ) -> Report | None:
        """Create a new report.

        Args:
            message_id: The Discord message ID being reported.
            user_id: The Discord user ID making the report.
            reason: The reason for the report.
            anonymous: Whether the report is anonymous.
            additional_info: Additional information about the report.
            reported_user_id: The Discord user ID being reported.
            guild_id: The Discord guild ID.
            channel_id: The Discord channel ID.

        Returns:
            Created Report entry or None if failed.
        """
        try:
            session = await self.session_factory()
            try:
                entry = Report(
                    message_id=message_id,
                    user_id=user_id,
                    reason=reason,
                    anonymous=anonymous,
                    additional_info=additional_info,
                    reported_user_id=reported_user_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                self.logger.info(
                    f"Created report for message {message_id} by user {user_id}"
                )
                return entry
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error creating report: {e}")
            return None

    async def exists(self, message_id: int, user_id: int) -> bool:
        """Check if a report exists for a message from a user.

        Args:
            message_id: The Discord message ID.
            user_id: The Discord user ID.

        Returns:
            True if exists, False otherwise.
        """
        entry = await self.get_by_message_and_user(message_id, user_id)
        return entry is not None

    async def get_by_guild(self, guild_id: int) -> list[Report]:
        """Get all reports for a guild.

        Args:
            guild_id: The Discord guild ID.

        Returns:
            List of Report entries for the guild.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Report)
                    .where(Report.guild_id == guild_id)
                    .order_by(Report.created_at.desc())
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(f"Error getting reports for guild {guild_id}: {e}")
            return []

    async def get_by_reported_user(self, reported_user_id: int) -> list[Report]:
        """Get all reports against a user.

        Args:
            reported_user_id: The Discord user ID being reported.

        Returns:
            List of Report entries against the user.
        """
        try:
            session = await self.session_factory()
            try:
                result = await session.execute(
                    select(Report)
                    .where(Report.reported_user_id == reported_user_id)
                    .order_by(Report.created_at.desc())
                )
                return list(result.scalars().all())
            finally:
                await session.close()
        except Exception as e:
            self.logger.error(
                f"Error getting reports for reported user {reported_user_id}: {e}"
            )
            return []
