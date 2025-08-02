"""Port interface for Key-Value store operations.

This module defines the abstract interface for KV store operations,
following hexagonal architecture principles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.models import ServiceDefinition


class KVStorePort(ABC):
    """Abstract interface for Key-Value store operations."""

    @abstractmethod
    async def get(self, key: str) -> ServiceDefinition | None:
        """Retrieve a service definition by key.

        Args:
            key: The service name (key)

        Returns:
            ServiceDefinition if found, None otherwise

        Raises:
            KVStoreException: If the operation fails
        """
        pass

    @abstractmethod
    async def put(self, key: str, value: ServiceDefinition) -> None:
        """Store a service definition.

        Args:
            key: The service name (key)
            value: The ServiceDefinition to store

        Raises:
            ServiceAlreadyExistsException: If the key already exists
            KVStoreException: If the operation fails
        """
        pass

    @abstractmethod
    async def update(self, key: str, value: ServiceDefinition, revision: int | None = None) -> None:
        """Update an existing service definition.

        Args:
            key: The service name (key)
            value: The updated ServiceDefinition
            revision: Optional revision for optimistic locking

        Raises:
            ServiceNotFoundException: If the key doesn't exist
            ConcurrentUpdateException: If revision mismatch
            KVStoreException: If the operation fails
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a service definition.

        Args:
            key: The service name (key)

        Raises:
            ServiceNotFoundException: If the key doesn't exist
            KVStoreException: If the operation fails
        """
        pass

    @abstractmethod
    async def list_all(self) -> list[ServiceDefinition]:
        """List all service definitions.

        Returns:
            List of all ServiceDefinitions

        Raises:
            KVStoreException: If the operation fails
        """
        pass

    @abstractmethod
    async def get_with_revision(self, key: str) -> tuple[ServiceDefinition | None, int | None]:
        """Retrieve a service definition with its revision.

        Args:
            key: The service name (key)

        Returns:
            Tuple of (ServiceDefinition, revision) or (None, None) if not found

        Raises:
            KVStoreException: If the operation fails
        """
        pass
