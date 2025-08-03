"""Basic implementation of Service Discovery without caching."""

from __future__ import annotations

import secrets

from ..domain.models import ServiceInstance
from ..ports.logger import LoggerPort
from ..ports.service_discovery import (
    InstanceSelector,
    SelectionStrategy,
    ServiceDiscoveryPort,
)
from ..ports.service_registry import ServiceRegistryPort


class BasicServiceDiscovery(ServiceDiscoveryPort):
    """Basic service discovery implementation without caching.

    This implementation queries the service registry on every discovery request
    and provides various instance selection strategies.
    """

    def __init__(
        self,
        service_registry: ServiceRegistryPort,
        logger: LoggerPort | None = None,
    ):
        """Initialize basic service discovery.

        Args:
            service_registry: The service registry to query instances from
            logger: Optional logger for debugging
        """
        self._registry = service_registry
        self._logger = logger
        self._selectors: dict[SelectionStrategy, InstanceSelector] = {}
        self._round_robin_counters: dict[str, int] = {}

    async def discover_instances(
        self, service_name: str, only_healthy: bool = True
    ) -> list[ServiceInstance]:
        """Discover instances of a service.

        Args:
            service_name: Name of the service to discover
            only_healthy: Whether to return only healthy instances

        Returns:
            List of discovered service instances
        """
        try:
            # Get all instances from registry
            instances = await self._registry.list_instances(service_name)

            if self._logger:
                self._logger.debug(
                    "Discovered service instances",
                    service=service_name,
                    total_count=len(instances),
                )

            # Filter for healthy instances if requested
            if only_healthy:
                healthy_instances = [i for i in instances if i.is_healthy()]
                if self._logger and len(healthy_instances) < len(instances):
                    self._logger.info(
                        "Filtered unhealthy instances",
                        service=service_name,
                        total=len(instances),
                        healthy=len(healthy_instances),
                    )
                return healthy_instances

            return instances

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to discover service instances",
                    service=service_name,
                    error=str(e),
                )
            # Return empty list on failure to allow graceful degradation
            return []

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
        """
        # Discover healthy instances
        instances = await self.discover_instances(service_name, only_healthy=True)
        if not instances:
            if self._logger:
                self._logger.warning(
                    "No healthy instances available",
                    service=service_name,
                )
            return None

        # Get selector for strategy
        selector = await self.get_selector(strategy)

        # Select instance
        selected = await selector.select(instances, service_name, preferred_instance_id)

        if self._logger and selected:
            self._logger.debug(
                "Selected service instance",
                service=service_name,
                instance=selected.instance_id,
                strategy=strategy.value,
            )

        return selected

    async def get_selector(self, strategy: SelectionStrategy) -> InstanceSelector:
        """Get instance selector for the specified strategy.

        Args:
            strategy: Selection strategy

        Returns:
            Instance selector implementation

        Raises:
            ValueError: If strategy is not supported
        """
        if strategy not in self._selectors:
            if strategy == SelectionStrategy.ROUND_ROBIN:
                self._selectors[strategy] = RoundRobinSelector(self._round_robin_counters)
            elif strategy == SelectionStrategy.RANDOM:
                self._selectors[strategy] = RandomSelector()
            elif strategy == SelectionStrategy.STICKY:
                self._selectors[strategy] = StickySelector()
            else:
                raise ValueError(f"Unsupported selection strategy: {strategy}")

        return self._selectors[strategy]

    async def invalidate_cache(self, service_name: str | None = None) -> None:
        """Invalidate discovery cache for a service or all services.

        This implementation has no cache, so this is a no-op.

        Args:
            service_name: Optional service name to invalidate, None for all
        """
        # No-op for basic implementation without caching
        if self._logger:
            self._logger.debug(
                "Cache invalidation requested (no-op for basic discovery)",
                service=service_name,
            )


class RoundRobinSelector:
    """Round-robin instance selector."""

    def __init__(self, counters: dict[str, int]):
        """Initialize with shared counter dict.

        Args:
            counters: Shared counter dictionary for tracking positions
        """
        self._counters = counters

    async def select(
        self,
        instances: list[ServiceInstance],
        service_name: str,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select instance using round-robin algorithm."""
        if not instances:
            return None

        # Initialize counter if needed
        if service_name not in self._counters:
            self._counters[service_name] = 0

        # Get current position and increment
        index = self._counters[service_name] % len(instances)
        self._counters[service_name] += 1

        return instances[index]


class RandomSelector:
    """Random instance selector."""

    async def select(
        self,
        instances: list[ServiceInstance],
        service_name: str,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select instance randomly."""
        if not instances:
            return None

        return secrets.choice(instances)


class StickySelector:
    """Sticky/preferred instance selector."""

    async def select(
        self,
        instances: list[ServiceInstance],
        service_name: str,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select preferred instance if available and healthy."""
        if not instances:
            return None

        # Try to find preferred instance
        if preferred_instance_id:
            for instance in instances:
                if instance.instance_id == preferred_instance_id:
                    return instance

        # Fallback to first available instance
        return instances[0]
