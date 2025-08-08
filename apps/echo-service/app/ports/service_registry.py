"""Port interface for service registry operations.

This port defines the contract for registering service definitions
and instances with the platform's service registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models import ServiceRegistrationData


class ServiceRegistryPort(ABC):
    """Port interface for service registry operations."""

    @abstractmethod
    async def register_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Register service definition with the platform.

        Args:
            registration: Service registration data containing definition and metadata

        Raises:
            RegistrationError: If registration fails
        """
        ...

    @abstractmethod
    async def update_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Update existing service definition.

        Args:
            registration: Updated service registration data

        Raises:
            RegistrationError: If update fails
        """
        ...

    @abstractmethod
    async def check_service_exists(self, service_name: str) -> bool:
        """Check if a service definition already exists.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service exists, False otherwise
        """
        ...

    @abstractmethod
    async def register_instance(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Register a service instance with TTL.

        Args:
            service_name: Name of the service
            instance_id: Unique instance identifier
            instance_data: Instance metadata and status
            ttl_seconds: Time-to-live in seconds

        Raises:
            RegistrationError: If instance registration fails
        """
        ...

    @abstractmethod
    async def update_instance_heartbeat(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Update instance heartbeat to maintain registration.

        Args:
            service_name: Name of the service
            instance_id: Unique instance identifier
            instance_data: Updated instance metadata
            ttl_seconds: Time-to-live in seconds

        Raises:
            RegistrationError: If heartbeat update fails
        """
        ...

    @abstractmethod
    async def deregister_instance(self, service_name: str, instance_id: str) -> None:
        """Remove a service instance from the registry.

        Args:
            service_name: Name of the service
            instance_id: Instance to deregister

        Raises:
            RegistrationError: If deregistration fails
        """
        ...


class RegistrationError(Exception):
    """Exception raised when service registration fails."""

    def __init__(self, message: str, service_name: str | None = None) -> None:
        """Initialize registration error.

        Args:
            message: Error message
            service_name: Service that failed to register
        """
        super().__init__(message)
        self.service_name = service_name
