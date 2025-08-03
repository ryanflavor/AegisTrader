"""Integration tests for Watchable Cached Service Discovery with KV Store watch support."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

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
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


@pytest.mark.integration
@pytest.mark.asyncio
class TestWatchableServiceDiscoveryIntegration:
    """Test Watchable Service Discovery with real NATS KV Store."""

    @pytest.fixture
    async def nats_adapter(self):
        """Create NATS adapter connected to local instance."""
        adapter = NATSAdapter()
        await adapter.connect("nats://localhost:4222")
        yield adapter
        await adapter.close()

    @pytest.fixture
    async def kv_store(self, nats_adapter):
        """Create KV Store for testing."""
        store = NATSKVStore(nats_adapter)
        await store.connect("test-service-discovery-watch", ttl=60)

        # Clear any existing data
        await store.clear()

        yield store

        # Cleanup
        await store.clear()
        await store.disconnect()

    @pytest.fixture
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

    async def test_watch_updates_cache_on_instance_add(self, kv_store, registry, logger, metrics):
        """Test that watch updates cache when new instance is added."""
        # Create discovery with watch enabled
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,  # Long TTL to ensure watch triggers first
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Initial discovery should return empty
            instances = await discovery.discover_instances("test-service")
            assert len(instances) == 0

            # Wait a bit for watch to establish
            await asyncio.sleep(0.5)

            # Register a new instance through registry
            instance = ServiceInstance(
                service_name="test-service",
                instance_id="instance-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(instance, ttl_seconds=60)

            # Wait for watch event to propagate
            await asyncio.sleep(0.5)

            # Cache should be invalidated and next discovery should find the instance
            instances = await discovery.discover_instances("test-service")
            assert len(instances) == 1
            assert instances[0].instance_id == "instance-1"

            # Verify cache was invalidated by watch
            stats = discovery.get_cache_stats()
            assert stats["cache_misses"] > 0  # Should have cache miss after invalidation

    async def test_watch_updates_cache_on_instance_removal(
        self, kv_store, registry, logger, metrics
    ):
        """Test that watch updates cache when instance is removed."""
        # First register some instances
        instance1 = ServiceInstance(
            service_name="removal-test",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        instance2 = ServiceInstance(
            service_name="removal-test",
            instance_id="instance-2",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )

        await registry.register(instance1, ttl_seconds=60)
        await registry.register(instance2, ttl_seconds=60)

        # Create discovery with watch enabled
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Initial discovery should find both instances
            instances = await discovery.discover_instances("removal-test")
            assert len(instances) == 2

            # Wait for watch to establish
            await asyncio.sleep(0.5)

            # Remove one instance
            await registry.deregister("removal-test", "instance-1")

            # Wait for watch event
            await asyncio.sleep(0.5)

            # Next discovery should only find one instance
            instances = await discovery.discover_instances("removal-test")
            assert len(instances) == 1
            assert instances[0].instance_id == "instance-2"

    async def test_watch_handles_connection_failures(self, kv_store, registry, logger, metrics):
        """Test that watch handles connection failures gracefully."""
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=10.0,
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=0.5,  # Fast reconnect for testing
                max_reconnect_attempts=3,
            ),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        )

        # Watch should be running
        assert discovery.is_watch_enabled()

        # Simulate connection failure by disconnecting KV store
        await kv_store.disconnect()

        # Wait for reconnect attempts
        await asyncio.sleep(2.0)

        # Watch stats should show reconnect attempts
        stats = discovery.get_watch_stats()
        assert stats["reconnect_attempts"] > 0

        # Cleanup
        await discovery.stop_watch()

    async def test_watch_disabled_by_config(self, kv_store, registry, logger, metrics):
        """Test that watch can be disabled via configuration."""
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=10.0,
            watch=WatchConfig(enabled=False),  # Watch disabled
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        )

        # Watch should not be running
        assert not discovery.is_watch_enabled()

        # Discovery should still work without watch
        instances = await discovery.discover_instances("test-service")
        assert isinstance(instances, list)

        # Stats should show watch is disabled
        stats = discovery.get_watch_stats()
        assert not stats["enabled"]
        assert not stats["running"]

    async def test_watch_handles_multiple_services(self, kv_store, registry, logger, metrics):
        """Test that watch correctly handles updates for multiple services."""
        # Register instances for multiple services
        services = ["service-a", "service-b", "service-c"]
        for service_name in services:
            instance = ServiceInstance(
                service_name=service_name,
                instance_id=f"{service_name}-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(instance, ttl_seconds=60)

        # Create discovery with watch
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Discover all services to populate cache
            for service_name in services:
                instances = await discovery.discover_instances(service_name)
                assert len(instances) == 1

            # Wait for watch to establish
            await asyncio.sleep(0.5)

            # Update one service
            new_instance = ServiceInstance(
                service_name="service-b",
                instance_id="service-b-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(new_instance, ttl_seconds=60)

            # Wait for watch event
            await asyncio.sleep(0.5)

            # Check that only service-b cache was invalidated
            instances_a = await discovery.discover_instances("service-a")
            instances_b = await discovery.discover_instances("service-b")
            instances_c = await discovery.discover_instances("service-c")

            assert len(instances_a) == 1  # Unchanged
            assert len(instances_b) == 2  # Updated
            assert len(instances_c) == 1  # Unchanged

    async def test_watch_performance_under_load(self, kv_store, registry, logger, metrics):
        """Test watch performance with many rapid updates."""
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=10.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Wait for watch to establish
            await asyncio.sleep(0.5)

            # Perform many rapid updates
            update_count = 20
            for i in range(update_count):
                instance = ServiceInstance(
                    service_name="load-test",
                    instance_id=f"instance-{i}",
                    version="1.0.0",
                    status="ACTIVE",
                    last_heartbeat=datetime.now(UTC),
                )
                await registry.register(instance, ttl_seconds=60)

                # Small delay between updates
                await asyncio.sleep(0.05)

            # Wait for all events to process
            await asyncio.sleep(1.0)

            # Verify all instances are discoverable
            instances = await discovery.discover_instances("load-test")
            assert len(instances) == update_count

            # Check watch stats
            stats = discovery.get_watch_stats()
            assert stats["running"]
            assert stats["reconnect_attempts"] == 0  # Should not have failed

    async def test_concurrent_discovery_with_watch(self, kv_store, registry, logger, metrics):
        """Test concurrent discovery requests while watch is active."""
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=5.0,
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Register initial instance
            instance = ServiceInstance(
                service_name="concurrent-test",
                instance_id="instance-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            )
            await registry.register(instance, ttl_seconds=60)

            # Wait for watch
            await asyncio.sleep(0.5)

            # Create concurrent discovery tasks
            async def discover_task():
                return await discovery.discover_instances("concurrent-test")

            # Run many concurrent discoveries
            tasks = [discover_task() for _ in range(50)]
            results = await asyncio.gather(*tasks)

            # All should return the same result
            for result in results:
                assert len(result) == 1
                assert result[0].instance_id == "instance-1"

            # Check cache hit rate
            stats = discovery.get_cache_stats()
            assert stats["cache_hits"] > 40  # Most should be cache hits
