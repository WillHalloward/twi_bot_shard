"""Service container for dependency injection.

This module provides a service container for managing dependencies in the Twi Bot Shard project.
It allows for registering services and retrieving them when needed, promoting loose coupling
and better testability.
"""

from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")


class ServiceContainer:
    """A container for managing service dependencies.

    This class provides methods for registering services and retrieving them.
    Services can be registered as instances, factories, or singletons.
    """

    def __init__(self) -> None:
        """Initialize an empty service container."""
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[..., Any]] = {}
        self._singletons: dict[str, bool] = {}
        self._singleton_instances: dict[str, Any] = {}

    def register(self, service_id: str, service: Any) -> None:
        """Register a service instance.

        Args:
            service_id: The identifier for the service.
            service: The service instance.
        """
        self._services[service_id] = service

    def register_factory(
        self, service_id: str, factory: Callable[..., Any], singleton: bool = False
    ) -> None:
        """Register a service factory.

        Args:
            service_id: The identifier for the service.
            factory: A callable that creates the service.
            singleton: Whether the service should be a singleton.
        """
        self._factories[service_id] = factory
        self._singletons[service_id] = singleton

    def register_class(
        self, service_id: str, cls: type[T], singleton: bool = False
    ) -> None:
        """Register a service class.

        Args:
            service_id: The identifier for the service.
            cls: The class to instantiate.
            singleton: Whether the service should be a singleton.
        """
        self.register_factory(service_id, lambda: cls(), singleton)

    def get(self, service_id: str) -> Any:
        """Get a service by its identifier.

        Args:
            service_id: The identifier for the service.

        Returns:
            The service instance.

        Raises:
            KeyError: If the service is not registered.
        """
        # Check if it's a direct service
        if service_id in self._services:
            return self._services[service_id]

        # Check if it's a factory
        if service_id in self._factories:
            # Check if it's a singleton and already instantiated
            if (
                self._singletons.get(service_id, False)
                and service_id in self._singleton_instances
            ):
                return self._singleton_instances[service_id]

            # Create a new instance
            instance = self._factories[service_id]()

            # Store singleton instances
            if self._singletons.get(service_id, False):
                self._singleton_instances[service_id] = instance

            return instance

        raise KeyError(f"Service '{service_id}' not found in container")

    def get_typed(self, service_id: str, expected_type: type[T]) -> T:
        """Get a service by its identifier and cast it to the expected type.

        Args:
            service_id: The identifier for the service.
            expected_type: The expected type of the service.

        Returns:
            The service instance cast to the expected type.

        Raises:
            KeyError: If the service is not registered.
            TypeError: If the service is not of the expected type.
        """
        service = self.get(service_id)
        if not isinstance(service, expected_type):
            raise TypeError(
                f"Service '{service_id}' is not of type {expected_type.__name__}"
            )
        return cast(expected_type, service)

    def has(self, service_id: str) -> bool:
        """Check if a service is registered.

        Args:
            service_id: The identifier for the service.

        Returns:
            True if the service is registered, False otherwise.
        """
        return service_id in self._services or service_id in self._factories
