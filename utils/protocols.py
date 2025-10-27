"""Protocol classes for defining interfaces in the application.

This module provides Protocol classes for defining interfaces for various
components in the application, such as repositories and services.
"""

from collections.abc import Sequence
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base

# Type variables
T = TypeVar("T", bound=Base)
ID = TypeVar("ID")


@runtime_checkable
class DatabaseServiceProtocol(Protocol[T]):
    """Protocol for database services."""

    async def create(self, session: AsyncSession, **kwargs) -> T:
        """Create a new record."""
        ...

    async def get_by_id(self, session: AsyncSession, id_value: Any) -> T | None:
        """Get a record by primary key."""
        ...

    async def get_all(self, session: AsyncSession) -> list[T]:
        """Get all records."""
        ...

    async def get_by_field(
        self, session: AsyncSession, field_name: str, field_value: Any
    ) -> list[T]:
        """Get records by field value."""
        ...

    async def update(self, session: AsyncSession, id_value: Any, **kwargs) -> T | None:
        """Update a record."""
        ...

    async def delete(self, session: AsyncSession, id_value: Any) -> bool:
        """Delete a record."""
        ...

    async def execute_query(self, session: AsyncSession, query: Any) -> list[T]:
        """Execute a custom query."""
        ...


@runtime_checkable
class RepositoryProtocol(Protocol[T, ID]):
    """Protocol for repositories."""

    async def get_by_id(self, entity_id: ID) -> T | None:
        """Get an entity by its ID."""
        ...

    async def get_all(self) -> Sequence[T]:
        """Get all entities."""
        ...

    async def find_by(self, **filters: Any) -> Sequence[T]:
        """Find entities matching the given filters."""
        ...

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        ...

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        ...

    async def delete(self, entity_id: ID) -> bool:
        """Delete an entity by its ID."""
        ...

    async def count(self) -> int:
        """Count all entities."""
        ...


@runtime_checkable
class MessageRepositoryProtocol(RepositoryProtocol[T, ID], Protocol[T, ID]):
    """Protocol for message repositories."""

    async def get_messages_by_channel(self, channel_id: int) -> Sequence[T]:
        """Get all messages in a channel."""
        ...

    async def get_messages_by_user(self, user_id: int) -> Sequence[T]:
        """Get all messages by a user."""
        ...

    async def save_message(self, message_data: dict[str, Any]) -> T:
        """Save a message."""
        ...

    async def mark_as_deleted(self, message_id: int) -> bool:
        """Mark a message as deleted."""
        ...


@runtime_checkable
class RepositoryFactoryProtocol(Protocol):
    """Protocol for repository factories."""

    def register_repository(
        self, model_class: type[T], repository_class: type[Any]
    ) -> None:
        """Register a repository class for a model."""
        ...

    def get_repository(self, model_class: type[T]) -> Any:
        """Get a repository for a model."""
        ...


@runtime_checkable
class GenericRepositoryProtocol(Protocol[T]):
    """Protocol for generic repositories."""

    async def get_all(self) -> list[T]:
        """Get all records of the model."""
        ...

    async def get_by_id(self, id_value: Any) -> T | None:
        """Get a record by its ID."""
        ...

    async def get_by_field(self, field_name: str, field_value: Any) -> list[T]:
        """Get records by a field value."""
        ...

    async def create(self, **kwargs) -> T:
        """Create a new record."""
        ...

    async def update(self, id_value: Any, **kwargs) -> T | None:
        """Update a record."""
        ...

    async def delete(self, id_value: Any) -> bool:
        """Delete a record."""
        ...
