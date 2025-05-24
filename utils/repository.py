"""
Repository pattern implementation for SQLAlchemy.

This module provides base repository classes and specific implementations
for different entities in the application.
"""

from collections.abc import Sequence
from typing import TypeVar, Generic, Optional, Type, Any, TypeAlias

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Select

# Type variables for generic repository
T = TypeVar('T')
ID = TypeVar('ID')

# Type aliases
EntityType: TypeAlias = Type[T]
FilterDict: TypeAlias = dict[str, Any]

class BaseRepository(Generic[T, ID]):
    """Base repository for SQLAlchemy models.
    
    This class provides common CRUD operations for SQLAlchemy models.
    
    Attributes:
        session_maker: Factory function to create database sessions.
        entity_type: The SQLAlchemy model class this repository manages.
    """
    
    def __init__(self, session_maker, entity_type: EntityType):
        """Initialize the repository.
        
        Args:
            session_maker: Factory function to create database sessions.
            entity_type: The SQLAlchemy model class this repository manages.
        """
        self.session_maker = session_maker
        self.entity_type = entity_type
    
    async def get_by_id(self, entity_id: ID) -> Optional[T]:
        """Get an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to retrieve.
            
        Returns:
            The entity if found, None otherwise.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type).where(self.entity_type.id == entity_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def get_all(self) -> Sequence[T]:
        """Get all entities.
        
        Returns:
            A sequence of all entities.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def find_by(self, **filters: Any) -> Sequence[T]:
        """Find entities matching the given filters.
        
        Args:
            **filters: Keyword arguments for filtering entities.
            
        Returns:
            A sequence of matching entities.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type)
            
            for attr, value in filters.items():
                stmt = stmt.where(getattr(self.entity_type, attr) == value)
                
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def create(self, entity: T) -> T:
        """Create a new entity.
        
        Args:
            entity: The entity to create.
            
        Returns:
            The created entity with its ID populated.
        """
        async with self.session_maker() as session:
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return entity
    
    async def update(self, entity: T) -> T:
        """Update an existing entity.
        
        Args:
            entity: The entity to update.
            
        Returns:
            The updated entity.
        """
        async with self.session_maker() as session:
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return entity
    
    async def delete(self, entity_id: ID) -> bool:
        """Delete an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to delete.
            
        Returns:
            True if the entity was deleted, False otherwise.
        """
        async with self.session_maker() as session:
            stmt = delete(self.entity_type).where(self.entity_type.id == entity_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def count(self) -> int:
        """Count all entities.
        
        Returns:
            The number of entities.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type)
            result = await session.execute(stmt)
            return len(result.scalars().all())

class MessageRepository(BaseRepository):
    """Repository for message entities.
    
    This class provides specialized methods for working with message entities.
    """
    
    async def get_messages_by_channel(self, channel_id: int) -> Sequence[T]:
        """Get all messages in a channel.
        
        Args:
            channel_id: The ID of the channel.
            
        Returns:
            A sequence of messages in the channel.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type).where(self.entity_type.channel_id == channel_id)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def get_messages_by_user(self, user_id: int) -> Sequence[T]:
        """Get all messages by a user.
        
        Args:
            user_id: The ID of the user.
            
        Returns:
            A sequence of messages by the user.
        """
        async with self.session_maker() as session:
            stmt = select(self.entity_type).where(self.entity_type.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def save_message(self, message_data: dict[str, Any]) -> T:
        """Save a message.
        
        Args:
            message_data: The message data to save.
            
        Returns:
            The saved message entity.
        """
        entity = self.entity_type(**message_data)
        return await self.create(entity)
    
    async def mark_as_deleted(self, message_id: int) -> bool:
        """Mark a message as deleted.
        
        Args:
            message_id: The ID of the message to mark as deleted.
            
        Returns:
            True if the message was marked as deleted, False otherwise.
        """
        async with self.session_maker() as session:
            stmt = update(self.entity_type).where(self.entity_type.id == message_id).values(deleted=True)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0