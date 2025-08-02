"""In-memory implementation of the ServiceRepository.

This is an infrastructure adapter that implements the ServiceRepository port
for testing and development purposes.
"""

from ..application.use_cases import ServiceRepository
from ..domain.aggregates import ServiceAggregate
from ..domain.value_objects import InstanceId, ServiceName


class InMemoryServiceRepository(ServiceRepository):
    """In-memory implementation of ServiceRepository for testing."""

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        # Key is (service_name, instance_id)
        self._storage: dict[tuple[str, str], ServiceAggregate] = {}

    async def save(self, aggregate: ServiceAggregate) -> None:
        """Save a service aggregate to memory."""
        key = (str(aggregate.service_name), str(aggregate.instance_id))
        self._storage[key] = aggregate

    async def get(
        self, service_name: ServiceName, instance_id: InstanceId
    ) -> ServiceAggregate | None:
        """Get a service aggregate by ID."""
        key = (str(service_name), str(instance_id))
        return self._storage.get(key)

    async def list_by_service(self, service_name: ServiceName) -> list[ServiceAggregate]:
        """List all instances of a service."""
        service_name_str = str(service_name)
        return [
            aggregate
            for (svc_name, _), aggregate in self._storage.items()
            if svc_name == service_name_str
        ]

    async def delete(self, service_name: ServiceName, instance_id: InstanceId) -> None:
        """Delete a service aggregate from memory."""
        key = (str(service_name), str(instance_id))
        self._storage.pop(key, None)

    def clear(self) -> None:
        """Clear all stored aggregates (useful for testing)."""
        self._storage.clear()

    def get_all(self) -> list[ServiceAggregate]:
        """Get all stored aggregates (useful for testing)."""
        return list(self._storage.values())
