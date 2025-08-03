"""Tests for Service Discovery port interface."""

from abc import ABC

import pytest

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.ports.service_discovery import (
    InstanceSelector,
    SelectionStrategy,
    ServiceDiscoveryPort,
)


class TestServiceDiscoveryPort:
    """Test cases for ServiceDiscoveryPort interface."""

    def test_service_discovery_port_is_abstract(self):
        """Test that ServiceDiscoveryPort is an abstract base class."""
        assert issubclass(ServiceDiscoveryPort, ABC)

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            ServiceDiscoveryPort()

    def test_service_discovery_port_defines_interface(self):
        """Test that ServiceDiscoveryPort defines all required methods."""
        # Check all abstract methods are defined
        abstract_methods = {
            "discover_instances",
            "select_instance",
            "get_selector",
            "invalidate_cache",
        }

        # Get all abstract methods from the class
        actual_abstract_methods = {
            name
            for name, method in ServiceDiscoveryPort.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert abstract_methods == actual_abstract_methods

    def test_service_discovery_port_method_signatures(self):
        """Test that port methods have correct signatures."""
        # Test discovery methods
        discover_method = ServiceDiscoveryPort.discover_instances
        assert discover_method.__name__ == "discover_instances"
        assert hasattr(discover_method, "__isabstractmethod__")

        select_method = ServiceDiscoveryPort.select_instance
        assert select_method.__name__ == "select_instance"

        get_selector_method = ServiceDiscoveryPort.get_selector
        assert get_selector_method.__name__ == "get_selector"

        invalidate_method = ServiceDiscoveryPort.invalidate_cache
        assert invalidate_method.__name__ == "invalidate_cache"


class TestSelectionStrategy:
    """Test cases for SelectionStrategy enum."""

    def test_selection_strategy_values(self):
        """Test that SelectionStrategy has expected values."""
        assert SelectionStrategy.ROUND_ROBIN.value == "round_robin"
        assert SelectionStrategy.RANDOM.value == "random"
        assert SelectionStrategy.STICKY.value == "sticky"

    def test_selection_strategy_is_string_enum(self):
        """Test that SelectionStrategy is a string enum."""
        assert isinstance(SelectionStrategy.ROUND_ROBIN, str)
        assert SelectionStrategy.ROUND_ROBIN == "round_robin"


class TestInstanceSelector:
    """Test cases for InstanceSelector protocol."""

    def test_instance_selector_is_protocol(self):
        """Test that InstanceSelector is a protocol."""
        from typing import Protocol

        assert issubclass(InstanceSelector.__class__, type(Protocol))

    def test_instance_selector_defines_select_method(self):
        """Test that InstanceSelector defines select method."""
        assert hasattr(InstanceSelector, "select")


class TestServiceDiscoveryPortImplementation:
    """Test cases for ServiceDiscoveryPort implementation contract."""

    @pytest.fixture
    def mock_implementation(self):
        """Create a mock implementation of ServiceDiscoveryPort."""
        from datetime import UTC, datetime

        class MockServiceDiscovery(ServiceDiscoveryPort):
            def __init__(self):
                self.cache = {}
                self.selectors = {}
                self._round_robin_counters = {}

            async def discover_instances(
                self, service_name: str, only_healthy: bool = True
            ) -> list[ServiceInstance]:
                # Mock instances for testing
                instances = [
                    ServiceInstance(
                        service_name=service_name,
                        instance_id=f"{service_name}-1",
                        version="1.0.0",
                        status="ACTIVE",
                        last_heartbeat=datetime.now(UTC),
                    ),
                    ServiceInstance(
                        service_name=service_name,
                        instance_id=f"{service_name}-2",
                        version="1.0.0",
                        status="ACTIVE",
                        last_heartbeat=datetime.now(UTC),
                    ),
                    ServiceInstance(
                        service_name=service_name,
                        instance_id=f"{service_name}-3",
                        version="1.0.0",
                        status="UNHEALTHY",
                        last_heartbeat=datetime.now(UTC),
                    ),
                ]

                if only_healthy:
                    return [i for i in instances if i.is_healthy()]
                return instances

            async def select_instance(
                self,
                service_name: str,
                strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN,
                preferred_instance_id: str | None = None,
            ) -> ServiceInstance | None:
                instances = await self.discover_instances(service_name, only_healthy=True)
                if not instances:
                    return None

                selector = await self.get_selector(strategy)
                return await selector.select(instances, service_name, preferred_instance_id)

            async def get_selector(self, strategy: SelectionStrategy) -> InstanceSelector:
                if strategy == SelectionStrategy.ROUND_ROBIN:
                    return self._get_round_robin_selector()
                elif strategy == SelectionStrategy.RANDOM:
                    return self._get_random_selector()
                elif strategy == SelectionStrategy.STICKY:
                    return self._get_sticky_selector()
                else:
                    raise ValueError(f"Unsupported strategy: {strategy}")

            def _get_round_robin_selector(self) -> InstanceSelector:
                class RoundRobinSelector:
                    def __init__(self, counters):
                        self.counters = counters

                    async def select(
                        self,
                        instances: list[ServiceInstance],
                        service_name: str,
                        preferred_instance_id: str | None = None,
                    ) -> ServiceInstance | None:
                        if not instances:
                            return None

                        if service_name not in self.counters:
                            self.counters[service_name] = 0

                        index = self.counters[service_name] % len(instances)
                        self.counters[service_name] += 1
                        return instances[index]

                return RoundRobinSelector(self._round_robin_counters)

            def _get_random_selector(self) -> InstanceSelector:
                import secrets

                class RandomSelector:
                    async def select(
                        self,
                        instances: list[ServiceInstance],
                        service_name: str,
                        preferred_instance_id: str | None = None,
                    ) -> ServiceInstance | None:
                        if not instances:
                            return None
                        return secrets.choice(instances)

                return RandomSelector()

            def _get_sticky_selector(self) -> InstanceSelector:
                class StickySelector:
                    async def select(
                        self,
                        instances: list[ServiceInstance],
                        service_name: str,
                        preferred_instance_id: str | None = None,
                    ) -> ServiceInstance | None:
                        if not instances:
                            return None

                        if preferred_instance_id:
                            for instance in instances:
                                if instance.instance_id == preferred_instance_id:
                                    return instance

                        # Fallback to first instance
                        return instances[0]

                return StickySelector()

            async def invalidate_cache(self, service_name: str | None = None) -> None:
                if service_name:
                    self.cache.pop(service_name, None)
                else:
                    self.cache.clear()

        return MockServiceDiscovery()

    @pytest.mark.asyncio
    async def test_discover_instances(self, mock_implementation):
        """Test instance discovery."""
        # Test discovering healthy instances
        instances = await mock_implementation.discover_instances("test-service")
        assert len(instances) == 2  # Only healthy instances
        assert all(i.is_healthy() for i in instances)

        # Test discovering all instances
        all_instances = await mock_implementation.discover_instances(
            "test-service", only_healthy=False
        )
        assert len(all_instances) == 3
        assert sum(1 for i in all_instances if not i.is_healthy()) == 1

    @pytest.mark.asyncio
    async def test_select_instance_round_robin(self, mock_implementation):
        """Test round-robin instance selection."""
        # Select instances multiple times
        selections = []
        for _ in range(4):
            instance = await mock_implementation.select_instance(
                "test-service", strategy=SelectionStrategy.ROUND_ROBIN
            )
            selections.append(instance.instance_id if instance else None)

        # Should cycle through instances
        assert selections[0] == "test-service-1"
        assert selections[1] == "test-service-2"
        assert selections[2] == "test-service-1"  # Cycles back
        assert selections[3] == "test-service-2"

    @pytest.mark.asyncio
    async def test_select_instance_random(self, mock_implementation):
        """Test random instance selection."""
        # Select multiple times
        selections = set()
        for _ in range(20):
            instance = await mock_implementation.select_instance(
                "test-service", strategy=SelectionStrategy.RANDOM
            )
            if instance:
                selections.add(instance.instance_id)

        # Should eventually select both healthy instances
        assert len(selections) == 2
        assert "test-service-1" in selections
        assert "test-service-2" in selections

    @pytest.mark.asyncio
    async def test_select_instance_sticky(self, mock_implementation):
        """Test sticky instance selection."""
        # Test with preferred instance
        instance = await mock_implementation.select_instance(
            "test-service",
            strategy=SelectionStrategy.STICKY,
            preferred_instance_id="test-service-2",
        )
        assert instance.instance_id == "test-service-2"

        # Test with non-existent preferred instance
        instance = await mock_implementation.select_instance(
            "test-service",
            strategy=SelectionStrategy.STICKY,
            preferred_instance_id="non-existent",
        )
        assert instance.instance_id == "test-service-1"  # Falls back to first

        # Test without preferred instance
        instance = await mock_implementation.select_instance(
            "test-service", strategy=SelectionStrategy.STICKY
        )
        assert instance.instance_id == "test-service-1"

    @pytest.mark.asyncio
    async def test_select_instance_no_healthy_instances(self, mock_implementation):
        """Test selection when no healthy instances available."""

        # Mock a service with no instances
        async def empty_discover(service_name, only_healthy=True):
            return []

        mock_implementation.discover_instances = empty_discover

        instance = await mock_implementation.select_instance("empty-service")
        assert instance is None

    @pytest.mark.asyncio
    async def test_get_selector(self, mock_implementation):
        """Test getting instance selectors."""
        # Test getting each selector type
        round_robin_selector = await mock_implementation.get_selector(SelectionStrategy.ROUND_ROBIN)
        assert hasattr(round_robin_selector, "select")

        random_selector = await mock_implementation.get_selector(SelectionStrategy.RANDOM)
        assert hasattr(random_selector, "select")

        sticky_selector = await mock_implementation.get_selector(SelectionStrategy.STICKY)
        assert hasattr(sticky_selector, "select")

    @pytest.mark.asyncio
    async def test_get_selector_invalid_strategy(self, mock_implementation):
        """Test getting selector with invalid strategy."""
        # Create invalid strategy
        invalid_strategy = "invalid"  # type: ignore

        with pytest.raises(ValueError) as exc_info:
            await mock_implementation.get_selector(invalid_strategy)

        assert "Unsupported strategy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, mock_implementation):
        """Test cache invalidation."""
        # Add some cache entries
        mock_implementation.cache = {
            "service1": ["instance1", "instance2"],
            "service2": ["instance3", "instance4"],
        }

        # Invalidate specific service
        await mock_implementation.invalidate_cache("service1")
        assert "service1" not in mock_implementation.cache
        assert "service2" in mock_implementation.cache

        # Invalidate all
        await mock_implementation.invalidate_cache()
        assert len(mock_implementation.cache) == 0


class TestServiceDiscoveryPortContract:
    """Test that implementations must follow the port contract."""

    def test_implementation_must_override_all_methods(self):
        """Test that incomplete implementations raise TypeError."""

        # Create incomplete implementation
        class IncompleteServiceDiscovery(ServiceDiscoveryPort):
            async def discover_instances(
                self, service_name: str, only_healthy: bool = True
            ) -> list[ServiceInstance]:
                return []

            # Missing other methods

        # Should not be able to instantiate
        with pytest.raises(TypeError) as exc_info:
            IncompleteServiceDiscovery()

        error_msg = str(exc_info.value)
        assert "Can't instantiate abstract class" in error_msg

    def test_selector_implementation(self):
        """Test that InstanceSelector implementations work correctly."""
        from datetime import UTC, datetime

        class TestSelector:
            """Test implementation of InstanceSelector protocol."""

            async def select(
                self,
                instances: list[ServiceInstance],
                service_name: str,
                preferred_instance_id: str | None = None,
            ) -> ServiceInstance | None:
                return instances[0] if instances else None

        # Create test instance
        selector = TestSelector()

        # Test with instances
        instances = [
            ServiceInstance(
                service_name="test",
                instance_id="test-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
        ]

        import asyncio

        result = asyncio.run(selector.select(instances, "test"))
        assert result == instances[0]

        # Test with empty list
        result = asyncio.run(selector.select([], "test"))
        assert result is None
