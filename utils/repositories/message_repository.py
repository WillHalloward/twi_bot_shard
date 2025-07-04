"""
Repository for messages table.

This module provides a repository for accessing messages data.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.tables.messages import Message
from utils.repository import MessageRepository as BaseMessageRepository


class MessageRepository(BaseMessageRepository):
    """Repository for messages table."""

    def __init__(self, session_maker):
        """Initialize the repository.

        Args:
            session_maker: Factory function to create database sessions.
        """
        super().__init__(session_maker, Message)

    async def save_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Save multiple messages.

        Args:
            messages: A list of message data dictionaries.
        """
        session = await self.session_maker()
        async with session as session:
            message_entities = [Message(**message_data) for message_data in messages]
            session.add_all(message_entities)
            await session.commit()

    async def get_message_count_by_channel(self, channel_id: int) -> int:
        """Get the count of messages in a channel.

        Args:
            channel_id: The ID of the channel.

        Returns:
            The count of messages in the channel.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(func.count()).where(self.entity_type.channel_id == channel_id)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def get_message_count_by_user(self, user_id: int) -> int:
        """Get the count of messages by a user.

        Args:
            user_id: The ID of the user.

        Returns:
            The count of messages by the user.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = select(func.count()).where(self.entity_type.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def get_messages_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Message]:
        """Get messages within a date range.

        Args:
            start_date: The start date.
            end_date: The end date.

        Returns:
            A list of messages within the date range.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                select(self.entity_type)
                .where(self.entity_type.created_at >= start_date)
                .where(self.entity_type.created_at <= end_date)
                .order_by(self.entity_type.created_at)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_messages_by_server(self, server_id: int) -> List[Message]:
        """Get all messages in a server.

        Args:
            server_id: The ID of the server.

        Returns:
            A list of messages in the server.
        """
        session = await self.session_maker()
        async with session as session:
            stmt = (
                select(self.entity_type)
                .where(self.entity_type.server_id == server_id)
                .order_by(self.entity_type.created_at)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def mark_message_as_deleted(self, message_id: int) -> bool:
        """Mark a message as deleted.

        Args:
            message_id: The ID of the message.

        Returns:
            True if the message was marked as deleted, False otherwise.
        """
        return await self.mark_as_deleted(message_id)
