"""Service Discovery port - Interface for client-side service discovery."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol

from ..domain.models import ServiceInstance


class SelectionStrategy(str, Enum):
    """Instance selection strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    STICKY = "sticky"


class InstanceSelector(Protocol):
    """Protocol for instance selection strategies."""

    async def select(
        self,
        instances: list[ServiceInstance],
        service_name: str,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select an instance from available instances.

        Args:
            instances: List of available service instances
            service_name: Name of the service
            preferred_instance_id: Optional preferred instance for sticky selection

        Returns:
            Selected instance or None if no healthy instances available
        """
        ...


class ServiceDiscoveryPort(ABC):
    """Abstract interface for service discovery operations.

    This port defines the contract for client-side service discovery,
    enabling clients to discover and select healthy service instances.
    """

    @abstractmethod
    async def discover_instances(
        self, service_name: str, only_healthy: bool = True
    ) -> list[ServiceInstance]:
        """Discover instances of a service.

        Args:
            service_name: Name of the service to discover
            only_healthy: Whether to return only healthy instances

        Returns:
            List of discovered service instances

        Raises:
            DiscoveryError: If discovery operation fails
        """
        ...

    @abstractmethod
    async def select_instance(
        self,
        service_name: str,
        strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select a single instance using the specified strategy.

        Args:
            service_name: Name of the service
            strategy: Selection strategy to use
            preferred_instance_id: Optional preferred instance for sticky selection

        Returns:
            Selected instance or None if no healthy instances available

        Raises:
            DiscoveryError: If discovery operation fails
        """
        ...

    @abstractmethod
    async def get_selector(self, strategy: SelectionStrategy) -> InstanceSelector:
        """Get instance selector for the specified strategy.

        Args:
            strategy: Selection strategy

        Returns:
            Instance selector implementation

        Raises:
            ValueError: If strategy is not supported
        """
        ...

    @abstractmethod
    async def invalidate_cache(self, service_name: str | None = None) -> None:
        """Invalidate discovery cache for a service or all services.

        Args:
            service_name: Optional service name to invalidate, None for all
        """
        ...
