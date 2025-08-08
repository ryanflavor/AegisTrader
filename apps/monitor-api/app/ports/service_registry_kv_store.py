"""Port interface for Service Registry KV Store operations.

This port defines the specific KV store operations needed by the service registry,
following Interface Segregation Principle.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.models import ServiceDefinition


class ServiceRegistryKVStorePort(Protocol):
    """Protocol interface for service registry KV store operations.

    This interface defines only the operations needed by the service registry,
    ensuring a clean separation between domain needs and infrastructure capabilities.
    """

    async def connect(self, nats_url: str) -> None:
        """Connect to the KV store.

        Args:
            nats_url: NATS server URL

        Raises:
            KVStoreException: If connection fails
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from the KV store."""
        ...

    async def get(self, key: str) -> ServiceDefinition | None:
        """Retrieve a service definition by key.

        Args:
            key: The service name

        Returns:
            ServiceDefinition if found, None otherwise

        Raises:
            KVStoreException: If the operation fails
        """
        ...

    async def put(self, key: str, value: ServiceDefinition) -> None:
        """Store a service definition.

        Args:
            key: The service name
            value: The ServiceDefinition to store

        Raises:
            ServiceAlreadyExistsException: If the key already exists
            KVStoreException: If the operation fails
        """
        ...

    async def update(self, key: str, value: ServiceDefinition, revision: int | None = None) -> None:
        """Update an existing service definition.

        Args:
            key: The service name
            value: The updated ServiceDefinition
            revision: Optional revision for optimistic locking

        Raises:
            ServiceNotFoundException: If the key doesn't exist
            ConcurrentUpdateException: If revision mismatch
            KVStoreException: If the operation fails
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete a service definition.

        Args:
            key: The service name

        Raises:
            ServiceNotFoundException: If the key doesn't exist
            KVStoreException: If the operation fails
        """
        ...

    async def list_all(self) -> list[ServiceDefinition]:
        """List all service definitions.

        Returns:
            List of all ServiceDefinitions

        Raises:
            KVStoreException: If the operation fails
        """
        ...

    async def get_with_revision(self, key: str) -> tuple[ServiceDefinition | None, int | None]:
        """Get a service definition with its revision number.

        Args:
            key: The service name

        Returns:
            Tuple of (ServiceDefinition, revision) or (None, None) if not found

        Raises:
            KVStoreException: If the operation fails
        """
        ...
