"""Service Registry port - Interface for service registration infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.models import ServiceInstance


class ServiceRegistryPort(ABC):
    """Abstract interface for service registry operations.

    This port defines the contract for service registration implementations,
    supporting registration, heartbeat updates, and service discovery.
    """

    @abstractmethod
    async def register(self, instance: ServiceInstance, ttl_seconds: int) -> None:
        """Register a service instance with TTL.

        Args:
            instance: The service instance to register
            ttl_seconds: Time-to-live in seconds for the registration

        Raises:
            RegistryError: If registration fails
        """
        ...

    @abstractmethod
    async def update_heartbeat(self, instance: ServiceInstance, ttl_seconds: int) -> None:
        """Update heartbeat for a service instance.

        Args:
            instance: The service instance to update
            ttl_seconds: Time-to-live in seconds for the registration

        Raises:
            RegistryError: If update fails
            InstanceNotFoundError: If instance is not registered
        """
        ...

    @abstractmethod
    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Remove a service instance from the registry.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier

        Raises:
            RegistryError: If deregistration fails
        """
        ...

    @abstractmethod
    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier

        Returns:
            ServiceInstance if found, None otherwise
        """
        ...

    @abstractmethod
    async def list_instances(self, service_name: str) -> list[ServiceInstance]:
        """List all instances of a service.

        Args:
            service_name: Name of the service

        Returns:
            List of active service instances
        """
        ...

    @abstractmethod
    async def list_all_services(self) -> dict[str, list[ServiceInstance]]:
        """List all services and their instances.

        Returns:
            Dictionary mapping service names to their instances
        """
        ...
