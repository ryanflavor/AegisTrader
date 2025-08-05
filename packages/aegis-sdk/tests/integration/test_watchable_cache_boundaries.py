"""Tests to document the boundaries and limitations of watchable cache."""

import asyncio
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure import (
    BasicServiceDiscovery,
    InMemoryMetrics,
    KVServiceRegistry,
    NATSKVStore,
    WatchableCacheConfig,
    WatchableCachedServiceDiscovery,
    WatchConfig,
)
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


@pytest.mark.integration
@pytest.mark.asyncio
class TestWatchableCacheBoundaries:
    """Document the boundaries and limitations of watchable cache behavior."""

    @pytest_asyncio.fixture
    async def nats_adapter(self, nats_container):
        """Create NATS adapter connected to test container."""
        config = NATSConnectionConfig()

        adapter = NATSAdapter(config=config)
        await adapter.connect(nats_container)
        yield adapter
        await adapter.disconnect()

    @pytest_asyncio.fixture
    async def kv_store(self, nats_adapter):
        """Create KV Store for testing."""
        store = NATSKVStore(nats_adapter)
        await store.connect("test-cache-boundaries", enable_ttl=True)
        await store.clear()
        yield store
        await store.clear()
        await store.disconnect()

    @pytest_asyncio.fixture
    async def registry(self, kv_store):
        """Create service registry."""
        return KVServiceRegistry(kv_store)

    @pytest.fixture
    def logger(self):
        """Create logger for testing."""
        return SimpleLogger()

    @pytest.fixture
    def metrics(self):
        """Create metrics for testing."""
        return InMemoryMetrics()

    async def test_cache_invalidation_is_lazy(self, kv_store, registry, logger, metrics):
        """Test that cache invalidation is lazy - data is not refreshed until requested.

        This is the current design:
        - Watch events only mark cache as invalid
        - Fresh data is fetched on next request
        - This avoids unnecessary load when data changes frequently
        """
        # Register initial instance
        instance = ServiceInstance(
            service_name="lazy-test",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        await registry.register(instance, ttl_seconds=60)

        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Initial discovery - cache miss
            instances = await discovery.discover_instances("lazy-test")
            assert len(instances) == 1

            stats1 = discovery.get_cache_stats()
            assert stats1["cache_misses"] == 1
            assert stats1["cache_hits"] == 0

            # Second call - cache hit
            instances = await discovery.discover_instances("lazy-test")
            stats2 = discovery.get_cache_stats()
            assert stats2["cache_hits"] == 1

            # Register another instance
            instance2 = ServiceInstance(
                service_name="lazy-test",
                instance_id="instance-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(instance2, ttl_seconds=60)

            # Wait for watch to detect change
            await asyncio.sleep(1.0)

            # Cache is invalidated but NOT refreshed yet
            # Next call will be a cache miss
            instances = await discovery.discover_instances("lazy-test")
            assert len(instances) == 2  # Fresh data fetched

            stats3 = discovery.get_cache_stats()
            assert stats3["cache_misses"] == 2  # Another miss due to invalidation

    async def test_cache_ttl_overrides_watch(self, kv_store, registry, logger, metrics):
        """Test that cache TTL expiration works independently of watch events.

        Even with watch enabled, cache entries expire based on TTL.
        """
        instance = ServiceInstance(
            service_name="ttl-test",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        await registry.register(instance, ttl_seconds=60)

        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=1.0,  # Very short TTL
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Initial discovery
            instances = await discovery.discover_instances("ttl-test")
            assert len(instances) == 1

            # Wait for TTL to expire
            await asyncio.sleep(1.5)

            # Cache should be expired regardless of watch
            instances = await discovery.discover_instances("ttl-test")
            stats = discovery.get_cache_stats()
            assert stats["cache_misses"] == 2  # Both calls were misses

    async def test_watch_does_not_detect_all_changes(self, kv_store, registry, logger, metrics):
        """Test that watch might miss rapid changes or have race conditions.

        This documents known limitations:
        - Rapid changes might coalesce
        - Watch establishment has a delay
        - Some operations might not trigger watch events
        """
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Rapid registration and deregistration
            for i in range(5):
                instance = ServiceInstance(
                    service_name="rapid-test",
                    instance_id=f"instance-{i}",
                    version="1.0.0",
                    status="ACTIVE",
                    last_heartbeat=datetime.now(UTC),
                )
                await registry.register(instance, ttl_seconds=60)
                await registry.deregister("rapid-test", f"instance-{i}")

            # Watch might not catch all these changes
            await asyncio.sleep(1.0)

            # Final state should be empty
            instances = await discovery.discover_instances("rapid-test")
            assert len(instances) == 0

    async def test_concurrent_access_behavior(self, kv_store, registry, logger, metrics):
        """Test cache behavior under concurrent access.

        Documents that concurrent requests might all miss cache if invalidated.
        """
        instance = ServiceInstance(
            service_name="concurrent-test",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        await registry.register(instance, ttl_seconds=60)

        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Prime the cache
            await discovery.discover_instances("concurrent-test")

            # Invalidate cache
            await discovery.invalidate_cache("concurrent-test")

            # Concurrent access after invalidation
            async def discover():
                return await discovery.discover_instances("concurrent-test")

            # All might miss cache and query backend
            await asyncio.gather(*[discover() for _ in range(10)])

            stats = discovery.get_cache_stats()
            # Multiple misses possible due to race conditions
            assert stats["cache_misses"] >= 2

    async def test_watch_reconnection_behavior(self, kv_store, registry, logger, metrics):
        """Test that watch reconnection might lose events.

        If watch disconnects and reconnects, events during downtime are lost.
        """
        instance1 = ServiceInstance(
            service_name="reconnect-test",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        await registry.register(instance1, ttl_seconds=60)

        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(
                enabled=True,
                max_reconnect_attempts=1,  # Minimal reconnection for this test
            ),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Initial discovery
            instances = await discovery.discover_instances("reconnect-test")
            assert len(instances) == 1

            # Simulate watch failure (in real scenario, this would be network issue)
            # For this test, we just document the behavior

            # Changes during "downtime" might not invalidate cache
            instance2 = ServiceInstance(
                service_name="reconnect-test",
                instance_id="instance-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(instance2, ttl_seconds=60)

            # Without watch, cache won't be invalidated until TTL expires
            # This is a known limitation
