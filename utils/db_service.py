"""
Database service for SQLAlchemy ORM.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base

T = TypeVar("T", bound=Base)


class DatabaseService(Generic[T]):
    """Generic database service for CRUD operations."""

    def __init__(self, model: Type[T]):
        """Initialize the database service with a model class.

        Args:
            model: The SQLAlchemy model class to use for operations.
        """
        self.model = model

    async def create(self, session: AsyncSession, **kwargs) -> T:
        """Create a new record.

        Args:
            session: The SQLAlchemy async session.
            **kwargs: The attributes to set on the new record.

        Returns:
            The created record.
        """
        obj = self.model(**kwargs)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    async def get_by_id(self, session: AsyncSession, id_value: Any) -> Optional[T]:
        """Get a record by primary key.

        Args:
            session: The SQLAlchemy async session.
            id_value: The primary key value.

        Returns:
            The record if found, None otherwise.
        """
        primary_key = next(iter(self.model.__table__.primary_key.columns))
        stmt = select(self.model).where(primary_key == id_value)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_all(self, session: AsyncSession) -> List[T]:
        """Get all records.

        Args:
            session: The SQLAlchemy async session.

        Returns:
            A list of all records.
        """
        stmt = select(self.model)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_field(
        self, session: AsyncSession, field_name: str, field_value: Any
    ) -> List[T]:
        """Get records by field value.

        Args:
            session: The SQLAlchemy async session.
            field_name: The name of the field to filter by.
            field_value: The value to filter for.

        Returns:
            A list of matching records.
        """
        stmt = select(self.model).where(getattr(self.model, field_name) == field_value)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self, session: AsyncSession, id_value: Any, **kwargs
    ) -> Optional[T]:
        """Update a record.

        Args:
            session: The SQLAlchemy async session.
            id_value: The primary key value.
            **kwargs: The attributes to update.

        Returns:
            The updated record if found, None otherwise.
        """
        primary_key = next(iter(self.model.__table__.primary_key.columns))
        stmt = update(self.model).where(primary_key == id_value).values(**kwargs)
        await session.execute(stmt)
        await session.commit()
        return await self.get_by_id(session, id_value)

    async def delete(self, session: AsyncSession, id_value: Any) -> bool:
        """Delete a record.

        Args:
            session: The SQLAlchemy async session.
            id_value: The primary key value.

        Returns:
            True if the record was deleted, False otherwise.
        """
        primary_key = next(iter(self.model.__table__.primary_key.columns))
        stmt = delete(self.model).where(primary_key == id_value)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    async def execute_query(self, session: AsyncSession, query: Any) -> List[T]:
        """Execute a custom query.

        Args:
            session: The SQLAlchemy async session.
            query: The SQLAlchemy query to execute.

        Returns:
            A list of matching records.
        """
        result = await session.execute(query)
        return list(result.scalars().all())
