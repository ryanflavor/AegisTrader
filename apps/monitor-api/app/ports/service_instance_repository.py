"""Port for service instance repository operations.

This module defines the interface for service instance storage operations,
following the repository pattern for clean separation of concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..domain.models import ServiceInstance


class ServiceInstanceRepositoryPort(Protocol):
    """Protocol interface for service instance repository operations."""

    async def get_all_instances(self) -> list[ServiceInstance]:
        """Retrieve all service instances.

        Returns:
            List of all service instances

        Raises:
            KVStoreException: If retrieval fails
        """
        ...

    async def get_instances_by_service(self, service_name: str) -> list[ServiceInstance]:
        """Retrieve all instances of a specific service.

        Args:
            service_name: Name of the service

        Returns:
            List of service instances for the given service

        Raises:
            KVStoreException: If retrieval fails
        """
        ...

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Retrieve a specific service instance.

        Args:
            service_name: Name of the service
            instance_id: ID of the instance

        Returns:
            ServiceInstance if found, None otherwise

        Raises:
            KVStoreException: If retrieval fails
        """
        ...

    async def count_active_instances(self) -> int:
        """Count the number of active service instances.

        Returns:
            Number of instances with ACTIVE status

        Raises:
            KVStoreException: If counting fails
        """
        ...

    async def get_instances_by_status(self, status: str) -> list[ServiceInstance]:
        """Retrieve all instances with a specific status.

        Args:
            status: Status to filter by (ACTIVE, UNHEALTHY, STANDBY)

        Returns:
            List of service instances with the given status

        Raises:
            KVStoreException: If retrieval fails
        """
        ...
