"""Tests for Basic Service Discovery implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.ports.service_discovery import SelectionStrategy


class TestBasicServiceDiscovery:
    """Test cases for BasicServiceDiscovery implementation."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock service registry."""
        registry = Mock()
        registry.list_instances = AsyncMock()
        return registry

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.debug = Mock()
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        return logger

    @pytest.fixture
    def sample_instances(self):
        """Create sample service instances for testing."""
        return [
            ServiceInstance(
                service_name="test-service",
                instance_id="instance-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="test-service",
                instance_id="instance-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="test-service",
                instance_id="instance-3",
                version="1.0.0",
                status="UNHEALTHY",
                last_heartbeat=datetime.now(UTC),
            ),
        ]

    @pytest.fixture
    def discovery(self, mock_registry, mock_logger):
        """Create BasicServiceDiscovery instance."""
        return BasicServiceDiscovery(mock_registry, mock_logger)

    @pytest.mark.asyncio
    async def test_discover_instances_healthy_only(
        self, discovery, mock_registry, sample_instances, mock_logger
    ):
        """Test discovering only healthy instances."""
        mock_registry.list_instances.return_value = sample_instances

        # Discover healthy instances
        instances = await discovery.discover_instances("test-service", only_healthy=True)

        # Should return only healthy instances
        assert len(instances) == 2
        assert all(i.status != "UNHEALTHY" for i in instances)
        assert instances[0].instance_id == "instance-1"
        assert instances[1].instance_id == "instance-2"

        # Verify registry was called
        mock_registry.list_instances.assert_called_once_with("test-service")

        # Verify logging
        mock_logger.debug.assert_called()
        mock_logger.info.assert_called_once()  # For filtering message

    @pytest.mark.asyncio
    async def test_discover_instances_all(
        self, discovery, mock_registry, sample_instances, mock_logger
    ):
        """Test discovering all instances including unhealthy."""
        mock_registry.list_instances.return_value = sample_instances

        # Discover all instances
        instances = await discovery.discover_instances("test-service", only_healthy=False)

        # Should return all instances
        assert len(instances) == 3
        assert any(i.status == "UNHEALTHY" for i in instances)

        # Verify no filtering log
        assert mock_logger.info.call_count == 0

    @pytest.mark.asyncio
    async def test_discover_instances_empty_service(self, discovery, mock_registry, mock_logger):
        """Test discovering instances for service with no instances."""
        mock_registry.list_instances.return_value = []

        instances = await discovery.discover_instances("empty-service")

        assert instances == []
        mock_registry.list_instances.assert_called_once_with("empty-service")

    @pytest.mark.asyncio
    async def test_discover_instances_error_handling(self, discovery, mock_registry, mock_logger):
        """Test error handling during discovery."""
        mock_registry.list_instances.side_effect = Exception("Registry error")

        # Should return empty list on error
        instances = await discovery.discover_instances("test-service")

        assert instances == []
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_instance_round_robin(self, discovery, mock_registry, sample_instances):
        """Test round-robin instance selection."""
        # Only return healthy instances
        healthy_instances = [i for i in sample_instances if i.is_healthy()]
        mock_registry.list_instances.return_value = healthy_instances

        # Select multiple times
        selections = []
        for _ in range(4):
            instance = await discovery.select_instance(
                "test-service", strategy=SelectionStrategy.ROUND_ROBIN
            )
            selections.append(instance.instance_id if instance else None)

        # Should cycle through instances
        assert selections == ["instance-1", "instance-2", "instance-1", "instance-2"]

    @pytest.mark.asyncio
    async def test_select_instance_random(self, discovery, mock_registry, sample_instances):
        """Test random instance selection."""
        healthy_instances = [i for i in sample_instances if i.is_healthy()]
        mock_registry.list_instances.return_value = healthy_instances

        # Select multiple times to verify randomness
        selections = set()
        for _ in range(20):
            instance = await discovery.select_instance(
                "test-service", strategy=SelectionStrategy.RANDOM
            )
            if instance:
                selections.add(instance.instance_id)

        # Should eventually select both instances
        assert len(selections) == 2
        assert "instance-1" in selections
        assert "instance-2" in selections

    @pytest.mark.asyncio
    async def test_select_instance_sticky_with_preferred(
        self, discovery, mock_registry, sample_instances
    ):
        """Test sticky selection with preferred instance."""
        healthy_instances = [i for i in sample_instances if i.is_healthy()]
        mock_registry.list_instances.return_value = healthy_instances

        # Select with preferred instance
        instance = await discovery.select_instance(
            "test-service",
            strategy=SelectionStrategy.STICKY,
            preferred_instance_id="instance-2",
        )

        assert instance.instance_id == "instance-2"

    @pytest.mark.asyncio
    async def test_select_instance_sticky_without_preferred(
        self, discovery, mock_registry, sample_instances
    ):
        """Test sticky selection without preferred instance."""
        healthy_instances = [i for i in sample_instances if i.is_healthy()]
        mock_registry.list_instances.return_value = healthy_instances

        # Select without preferred instance
        instance = await discovery.select_instance(
            "test-service", strategy=SelectionStrategy.STICKY
        )

        # Should select first instance
        assert instance.instance_id == "instance-1"

    @pytest.mark.asyncio
    async def test_select_instance_sticky_preferred_not_found(
        self, discovery, mock_registry, sample_instances
    ):
        """Test sticky selection when preferred instance is not found."""
        healthy_instances = [i for i in sample_instances if i.is_healthy()]
        mock_registry.list_instances.return_value = healthy_instances

        # Select with non-existent preferred instance
        instance = await discovery.select_instance(
            "test-service",
            strategy=SelectionStrategy.STICKY,
            preferred_instance_id="non-existent",
        )

        # Should fallback to first instance
        assert instance.instance_id == "instance-1"

    @pytest.mark.asyncio
    async def test_select_instance_no_healthy_instances(
        self, discovery, mock_registry, mock_logger
    ):
        """Test selection when no healthy instances available."""
        # Only unhealthy instance
        mock_registry.list_instances.return_value = [
            ServiceInstance(
                service_name="test-service",
                instance_id="unhealthy-1",
                version="1.0.0",
                status="UNHEALTHY",
                last_heartbeat=datetime.now(UTC),
            )
        ]

        instance = await discovery.select_instance("test-service")

        assert instance is None
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_selector_all_strategies(self, discovery):
        """Test getting selectors for all strategies."""
        # Get each selector type
        round_robin = await discovery.get_selector(SelectionStrategy.ROUND_ROBIN)
        random = await discovery.get_selector(SelectionStrategy.RANDOM)
        sticky = await discovery.get_selector(SelectionStrategy.STICKY)

        # Verify they implement the protocol
        assert hasattr(round_robin, "select")
        assert hasattr(random, "select")
        assert hasattr(sticky, "select")

        # Verify same selector is returned on subsequent calls
        round_robin2 = await discovery.get_selector(SelectionStrategy.ROUND_ROBIN)
        assert round_robin is round_robin2

    @pytest.mark.asyncio
    async def test_get_selector_invalid_strategy(self, discovery):
        """Test getting selector with invalid strategy."""
        with pytest.raises(ValueError) as exc_info:
            await discovery.get_selector("invalid")  # type: ignore

        assert "Unsupported selection strategy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalidate_cache_noop(self, discovery, mock_logger):
        """Test that cache invalidation is a no-op for basic discovery."""
        # Should not raise any errors
        await discovery.invalidate_cache("test-service")
        await discovery.invalidate_cache()

        # Should log debug messages
        assert mock_logger.debug.call_count == 2

    @pytest.mark.asyncio
    async def test_round_robin_maintains_state_across_services(self, discovery, mock_registry):
        """Test that round-robin maintains separate counters per service."""
        # Setup two services
        service1_instances = [
            ServiceInstance(
                service_name="service1",
                instance_id="s1-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service1",
                instance_id="s1-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
        ]

        service2_instances = [
            ServiceInstance(
                service_name="service2",
                instance_id="s2-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service2",
                instance_id="s2-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
        ]

        # Mock registry to return different instances based on service name
        def list_instances_side_effect(service_name):
            if service_name == "service1":
                return service1_instances
            elif service_name == "service2":
                return service2_instances
            return []

        mock_registry.list_instances.side_effect = list_instances_side_effect

        # Select from both services
        s1_instance1 = await discovery.select_instance(
            "service1", strategy=SelectionStrategy.ROUND_ROBIN
        )
        s2_instance1 = await discovery.select_instance(
            "service2", strategy=SelectionStrategy.ROUND_ROBIN
        )
        s1_instance2 = await discovery.select_instance(
            "service1", strategy=SelectionStrategy.ROUND_ROBIN
        )
        s2_instance2 = await discovery.select_instance(
            "service2", strategy=SelectionStrategy.ROUND_ROBIN
        )

        # Verify independent counters
        assert s1_instance1.instance_id == "s1-1"
        assert s1_instance2.instance_id == "s1-2"
        assert s2_instance1.instance_id == "s2-1"
        assert s2_instance2.instance_id == "s2-2"


class TestSelectors:
    """Test individual selector implementations."""

    @pytest.mark.asyncio
    async def test_round_robin_selector_empty_instances(self):
        """Test round-robin selector with empty instance list."""
        from aegis_sdk.infrastructure.basic_service_discovery import RoundRobinSelector

        selector = RoundRobinSelector({})
        result = await selector.select([], "test-service")
        assert result is None

    @pytest.mark.asyncio
    async def test_random_selector_empty_instances(self):
        """Test random selector with empty instance list."""
        from aegis_sdk.infrastructure.basic_service_discovery import RandomSelector

        selector = RandomSelector()
        result = await selector.select([], "test-service")
        assert result is None

    @pytest.mark.asyncio
    async def test_sticky_selector_empty_instances(self):
        """Test sticky selector with empty instance list."""
        from aegis_sdk.infrastructure.basic_service_discovery import StickySelector

        selector = StickySelector()
        result = await selector.select([], "test-service", "preferred")
        assert result is None
