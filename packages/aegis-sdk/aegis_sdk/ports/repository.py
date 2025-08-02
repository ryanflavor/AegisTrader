"""Repository port interface for domain aggregates.

This module defines the repository interface following hexagonal architecture principles.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..domain.aggregates import ServiceAggregate
from ..domain.value_objects import InstanceId, ServiceName


class ServiceRepository(ABC):
    """Abstract repository for service aggregates.

    This is a port interface that must be implemented by infrastructure adapters.
    """

    @abstractmethod
    async def save(self, aggregate: ServiceAggregate) -> None:
        """Save a service aggregate."""
        ...

    @abstractmethod
    async def get(
        self, service_name: ServiceName, instance_id: InstanceId
    ) -> ServiceAggregate | None:
        """Get a service aggregate by ID."""
        ...

    @abstractmethod
    async def list_by_service(self, service_name: ServiceName) -> Sequence[ServiceAggregate]:
        """List all instances of a service."""
        ...

    @abstractmethod
    async def delete(self, service_name: ServiceName, instance_id: InstanceId) -> None:
        """Delete a service aggregate."""
        ...
