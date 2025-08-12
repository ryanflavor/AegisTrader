"""Tests for Cached Service Discovery implementation."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.cached_service_discovery import (
    CacheConfig,
    CachedServiceDiscovery,
)
from aegis_sdk.ports.service_discovery import SelectionStrategy


class TestCachedServiceDiscovery:
    """Test cases for CachedServiceDiscovery implementation."""

    @pytest.fixture
    def mock_inner_discovery(self):
        """Create a mock inner service discovery."""
        inner = Mock()
        inner.discover_instances = AsyncMock()
        inner.select_instance = AsyncMock()
        inner.get_selector = AsyncMock()
        inner.invalidate_cache = AsyncMock()
        return inner

    @pytest.fixture
    def mock_metrics(self):
        """Create a mock metrics port."""
        metrics = Mock()
        metrics.increment = Mock()
        return metrics

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
        """Create sample service instances."""
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
        ]

    @pytest.fixture
    def cache_config(self):
        """Create cache configuration with short TTL for testing."""
        return CacheConfig(ttl_seconds=0.1, max_entries=10, enable_metrics=True)

    @pytest.fixture
    def cached_discovery(self, mock_inner_discovery, cache_config, mock_metrics, mock_logger):
        """Create CachedServiceDiscovery instance."""
        return CachedServiceDiscovery(
            inner=mock_inner_discovery,
            config=cache_config,
            metrics=mock_metrics,
            logger=mock_logger,
        )

    @pytest.mark.asyncio
    async def test_cache_hit(
        self, cached_discovery, mock_inner_discovery, sample_instances, mock_metrics
    ):
        """Test cache hit scenario."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # First call - cache miss
        instances1 = await cached_discovery.discover_instances("test-service")
        assert instances1 == sample_instances
        mock_inner_discovery.discover_instances.assert_called_once_with("test-service", True)

        # Second call - cache hit
        instances2 = await cached_discovery.discover_instances("test-service")
        assert instances2 == sample_instances
        # Inner discovery should not be called again
        assert mock_inner_discovery.discover_instances.call_count == 1

        # Verify metrics
        assert mock_metrics.increment.call_count == 2
        mock_metrics.increment.assert_any_call("service_discovery.cache.misses.test-service")
        mock_metrics.increment.assert_any_call("service_discovery.cache.hits.test-service")

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cached_discovery, mock_inner_discovery, sample_instances):
        """Test cache expiration after TTL."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # First call
        await cached_discovery.discover_instances("test-service")
        assert mock_inner_discovery.discover_instances.call_count == 1

        # Wait for cache to expire (TTL is 0.1 seconds in test config)
        time.sleep(0.15)

        # Second call after expiration - should call inner again
        await cached_discovery.discover_instances("test-service")
        assert mock_inner_discovery.discover_instances.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_with_health_filter(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test that health filter is included in cache key."""
        healthy_instances = sample_instances
        all_instances = [
            *sample_instances,
            ServiceInstance(
                service_name="test-service",
                instance_id="unhealthy",
                version="1.0.0",
                status="UNHEALTHY",
                last_heartbeat=datetime.now(UTC),
            ),
        ]

        # Mock different responses based on only_healthy parameter
        async def discover_side_effect(service_name, only_healthy=True):
            return healthy_instances if only_healthy else all_instances

        mock_inner_discovery.discover_instances.side_effect = discover_side_effect

        # Request healthy instances
        healthy = await cached_discovery.discover_instances("test-service", True)
        assert len(healthy) == 2

        # Request all instances - should be a cache miss
        all_inst = await cached_discovery.discover_instances("test-service", False)
        assert len(all_inst) == 3

        # Both calls should hit the inner discovery
        assert mock_inner_discovery.discover_instances.call_count == 2

    @pytest.mark.asyncio
    async def test_stale_cache_on_failure(
        self, cached_discovery, mock_inner_discovery, sample_instances, mock_logger
    ):
        """Test returning stale cache when discovery fails."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # First call - populate cache
        await cached_discovery.discover_instances("test-service")

        # Wait for cache to expire
        time.sleep(0.15)

        # Make inner discovery fail
        mock_inner_discovery.discover_instances.side_effect = Exception("Discovery failed")

        # Should return stale cache
        instances = await cached_discovery.discover_instances("test-service")
        assert instances == sample_instances
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_stale_cache_on_first_failure(self, cached_discovery, mock_inner_discovery):
        """Test that exception is raised when no cache exists."""
        mock_inner_discovery.discover_instances.side_effect = Exception("Discovery failed")

        # Should raise exception when no cache exists
        with pytest.raises(Exception, match="Discovery failed"):
            await cached_discovery.discover_instances("test-service")

    @pytest.mark.asyncio
    async def test_cache_invalidation_single_service(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test cache invalidation for a single service."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # Populate cache for multiple services
        await cached_discovery.discover_instances("service1")
        await cached_discovery.discover_instances("service2")
        assert len(cached_discovery._cache) == 2

        # Invalidate only service1
        await cached_discovery.invalidate_cache("service1")

        # service1 cache should be gone, service2 should remain
        assert "service1:True" not in cached_discovery._cache
        assert "service2:True" in cached_discovery._cache

        # Inner invalidate should be called
        mock_inner_discovery.invalidate_cache.assert_called_once_with("service1")

    @pytest.mark.asyncio
    async def test_cache_invalidation_all(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test cache invalidation for all services."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # Populate cache
        await cached_discovery.discover_instances("service1")
        await cached_discovery.discover_instances("service2")
        cached_discovery._cache_hits = 5
        cached_discovery._cache_misses = 2

        # Invalidate all
        await cached_discovery.invalidate_cache()

        # All cache should be cleared
        assert len(cached_discovery._cache) == 0
        assert cached_discovery._cache_hits == 0
        assert cached_discovery._cache_misses == 0

        # Inner invalidate should be called
        mock_inner_discovery.invalidate_cache.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, mock_inner_discovery, mock_metrics, mock_logger):
        """Test that cache respects max entries limit."""
        config = CacheConfig(ttl_seconds=10, max_entries=3)
        cached_discovery = CachedServiceDiscovery(
            inner=mock_inner_discovery,
            config=config,
            metrics=mock_metrics,
            logger=mock_logger,
        )

        # Create different instances for each service
        async def discover_side_effect(service_name, only_healthy=True):
            return [
                ServiceInstance(
                    service_name=service_name,
                    instance_id=f"{service_name}-1",
                    version="1.0.0",
                    status="ACTIVE",
                    last_heartbeat=datetime.now(UTC),
                )
            ]

        mock_inner_discovery.discover_instances.side_effect = discover_side_effect

        # Add 4 services (exceeds max_entries of 3)
        for i in range(4):
            await cached_discovery.discover_instances(f"service{i}")

        # Cache should only have 3 entries (oldest evicted)
        assert len(cached_discovery._cache) == 3
        assert "service0:True" not in cached_discovery._cache  # Evicted
        assert "service3:True" in cached_discovery._cache  # Latest

    @pytest.mark.asyncio
    async def test_select_instance_uses_cache(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test that select_instance uses cached discovery."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # Mock selector
        mock_selector = Mock()
        mock_selector.select = AsyncMock(return_value=sample_instances[0])
        mock_inner_discovery.get_selector.return_value = mock_selector

        # First select - should discover
        instance1 = await cached_discovery.select_instance("test-service")
        assert instance1 == sample_instances[0]
        assert mock_inner_discovery.discover_instances.call_count == 1

        # Second select - should use cache
        instance2 = await cached_discovery.select_instance("test-service")
        assert instance2 == sample_instances[0]
        assert mock_inner_discovery.discover_instances.call_count == 1  # No new call

    @pytest.mark.asyncio
    async def test_get_selector_delegates_to_inner(self, cached_discovery, mock_inner_discovery):
        """Test that get_selector delegates to inner implementation."""
        mock_selector = Mock()
        mock_inner_discovery.get_selector.return_value = mock_selector

        selector = await cached_discovery.get_selector(SelectionStrategy.ROUND_ROBIN)

        assert selector == mock_selector
        mock_inner_discovery.get_selector.assert_called_once_with(SelectionStrategy.ROUND_ROBIN)

    def test_get_cache_stats(self, cached_discovery):
        """Test cache statistics retrieval."""
        cached_discovery._total_requests = 100
        cached_discovery._cache_hits = 75
        cached_discovery._cache_misses = 25
        cached_discovery._cache["service1:True"] = Mock()
        cached_discovery._cache["service2:True"] = Mock()

        stats = cached_discovery.get_cache_stats()

        assert stats["total_requests"] == 100
        assert stats["cache_hits"] == 75
        assert stats["cache_misses"] == 25
        assert stats["hit_rate"] == 0.75
        assert stats["cache_size"] == 2
        assert stats["config"]["ttl_seconds"] == 0.1
        assert stats["config"]["max_entries"] == 10

    def test_hit_rate_calculation(self, cached_discovery):
        """Test hit rate calculation edge cases."""
        # No requests yet
        assert cached_discovery._get_hit_rate() == 0.0

        # Some hits and misses
        cached_discovery._cache_hits = 3
        cached_discovery._cache_misses = 1
        assert cached_discovery._get_hit_rate() == 0.75

        # Only hits
        cached_discovery._cache_hits = 10
        cached_discovery._cache_misses = 0
        assert cached_discovery._get_hit_rate() == 1.0

    @pytest.mark.asyncio
    async def test_cache_hit_increments_counter_and_entry_hits(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test that cache hits properly increment counters and entry hits."""
        # First, populate cache through normal discovery
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # First call - cache miss
        await cached_discovery.discover_instances("test-service")
        assert cached_discovery._cache_hits == 0
        assert cached_discovery._cache_misses == 1

        # Get the cache entry
        entry = cached_discovery._cache["test-service:True"]
        assert entry.hits == 0

        # Second call - cache hit
        await cached_discovery.discover_instances("test-service")
        assert cached_discovery._cache_hits == 1
        assert cached_discovery._cache_misses == 1

        # Entry hits should now be incremented
        assert entry.hits == 1

        # Third call - another cache hit
        await cached_discovery.discover_instances("test-service")
        assert cached_discovery._cache_hits == 2
        assert entry.hits == 2

    @pytest.mark.asyncio
    async def test_select_instance_returns_none_when_no_instances(
        self, cached_discovery, mock_inner_discovery
    ):
        """Test select_instance returns None when no instances are available."""
        # Mock discover to return empty list
        mock_inner_discovery.discover_instances.return_value = []

        # Should return None
        result = await cached_discovery.select_instance("empty-service")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_hit_when_service_not_in_cache(
        self, cached_discovery, mock_metrics, mock_logger
    ):
        """Test _record_hit when service is not in cache (edge case)."""
        # Record hit for non-existent service in cache
        cached_discovery._record_hit("non-cached-service")

        # Should still increment cache hits
        assert cached_discovery._cache_hits == 1

        # Should still record metrics if enabled
        mock_metrics.increment.assert_called_once_with(
            "service_discovery.cache.hits.non-cached-service"
        )

    @pytest.mark.asyncio
    async def test_metrics_disabled(self, mock_inner_discovery, mock_metrics, mock_logger):
        """Test that metrics can be disabled."""
        config = CacheConfig(enable_metrics=False)
        cached_discovery = CachedServiceDiscovery(
            inner=mock_inner_discovery,
            config=config,
            metrics=mock_metrics,
            logger=mock_logger,
        )

        mock_inner_discovery.discover_instances.return_value = []

        # Make a request
        await cached_discovery.discover_instances("test-service")

        # Metrics should not be called
        mock_metrics.increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_evict_old_entries(
        self, cached_discovery, mock_inner_discovery, sample_instances
    ):
        """Test that old entries are evicted on new discoveries."""
        mock_inner_discovery.discover_instances.return_value = sample_instances

        # Add entry that will expire
        await cached_discovery.discover_instances("old-service")

        # Wait for it to expire
        time.sleep(0.15)

        # Add new entry - should trigger eviction
        await cached_discovery.discover_instances("new-service")

        # Old entry should be evicted
        assert "old-service:True" not in cached_discovery._cache
        assert "new-service:True" in cached_discovery._cache
