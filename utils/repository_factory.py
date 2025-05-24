"""
Repository factory for creating repository instances.

This module provides a factory for creating repository instances for database access.
It uses the service container to manage repository dependencies and ensures that
repositories are created with the correct session factory.
"""
from typing import Any, Callable, Dict, Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base
from utils.db_service import DatabaseService
from utils.service_container import ServiceContainer

T = TypeVar('T', bound=Base)

class RepositoryFactory:
    """
    Factory for creating repository instances.

    This class provides methods for registering and creating repository classes.
    It ensures that repositories are created with the correct session factory.
    """

    def __init__(self, container: ServiceContainer, session_factory: Callable[[], AsyncSession]):
        """
        Initialize the repository factory.

        Args:
            container: The service container to use for managing repositories.
            session_factory: A callable that returns a new database session.
        """
        self.container = container
        self.session_factory = session_factory
        self._repository_classes: Dict[str, Type[Any]] = {}

    def register_repository(self, model_class: Type[T], repository_class: Type[Any]) -> None:
        """
        Register a repository class for a model.

        Args:
            model_class: The model class.
            repository_class: The repository class to use for the model.
        """
        model_name = model_class.__name__
        repository_id = f"repository.{model_name.lower()}"
        self._repository_classes[repository_id] = repository_class

        # Register the repository factory in the container
        self.container.register_factory(
            repository_id,
            lambda: repository_class(self.session_factory),
            singleton=True
        )

    def get_repository(self, model_class: Type[T]) -> Any:
        """
        Get a repository for a model.

        Args:
            model_class: The model class.

        Returns:
            The repository instance.

        Raises:
            KeyError: If no repository is registered for the model.
        """
        model_name = model_class.__name__
        repository_id = f"repository.{model_name.lower()}"

        if not self.container.has(repository_id):
            # If no specific repository is registered, create a generic one
            self.container.register_factory(
                repository_id,
                lambda: GenericRepository(model_class, self.session_factory),
                singleton=True
            )

        return self.container.get(repository_id)


class GenericRepository:
    """
    Generic repository for database access.

    This class provides basic CRUD operations for a model using DatabaseService.
    It can be used as a fallback when no specific repository is registered.
    """

    def __init__(self, model_class: Type[T], session_factory: Callable[[], AsyncSession]):
        """
        Initialize the generic repository.

        Args:
            model_class: The model class.
            session_factory: A callable that returns a new database session.
        """
        self.model_class = model_class
        self.session_factory = session_factory
        self.service = DatabaseService(model_class)

    async def get_all(self):
        """Get all records of the model."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.get_all(session)

    async def get_by_id(self, id_value: Any):
        """Get a record by its ID."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.get_by_id(session, id_value)

    async def get_by_field(self, field_name: str, field_value: Any):
        """Get records by a field value."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.get_by_field(session, field_name, field_value)

    async def create(self, **kwargs):
        """Create a new record."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.create(session, **kwargs)

    async def update(self, id_value: Any, **kwargs):
        """Update a record."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.update(session, id_value, **kwargs)

    async def delete(self, id_value: Any):
        """Delete a record."""
        session = await self.session_factory()
        async with session as session:
            return await self.service.delete(session, id_value)
