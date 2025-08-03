"""Comprehensive integration tests for Service Discovery with K8s NATS cluster."""

from __future__ import annotations

import asyncio

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.domain.exceptions import ServiceUnavailableError
from aegis_sdk.infrastructure import (
    BasicServiceDiscovery,
    CacheConfig,
    CachedServiceDiscovery,
    InMemoryMetrics,
    KVServiceRegistry,
    NATSAdapter,
    NATSKVStore,
    WatchableCacheConfig,
    WatchableCachedServiceDiscovery,
    WatchConfig,
)
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.ports.service_discovery import SelectionStrategy


@pytest.mark.integration
@pytest.mark.k8s
@pytest.mark.asyncio
class TestServiceDiscoveryK8sIntegration:
    """Test Service Discovery with real K8s NATS cluster.

    These tests require a running K8s cluster with NATS deployed.
    Use `make dev-update` and `make port-forward` before running.
    """

    @pytest.fixture
    async def nats_adapter(self):
        """Create NATS adapter connected to K8s cluster."""
        adapter = NATSAdapter()
        await adapter.connect("nats://localhost:4222")
        yield adapter
        await adapter.close()

    @pytest.fixture
    async def kv_store(self, nats_adapter):
        """Create KV Store for testing."""
        store = NATSKVStore(nats_adapter)
        await store.connect("test-service-discovery-k8s", ttl=300)

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

    @pytest.fixture
    async def test_service_a(self, nats_adapter, kv_store, logger, metrics):
        """Create test service A with multiple instances."""
        # Create and start instances
        instances = []
        for i in range(3):
            service = Service(
                name="test-service-a",
                version="1.0.0",
                adapter=nats_adapter,
                kv_store=kv_store,
                logger=logger,
                metrics=metrics,
            )
            service._instance_id = f"service-a-{i + 1}"

            # Add RPC handler
            @service.rpc("echo")
            async def echo_handler(params):
                return {"message": params.get("message"), "instance": service._instance_id}

            await service.start()
            instances.append(service)

        yield instances

        # Cleanup
        for service in instances:
            await service.stop()

    @pytest.fixture
    async def test_service_b(self, nats_adapter, kv_store, logger, metrics):
        """Create test service B with single instance."""
        service = Service(
            name="test-service-b",
            version="2.0.0",
            adapter=nats_adapter,
            kv_store=kv_store,
            logger=logger,
            metrics=metrics,
        )
        service._instance_id = "service-b-1"

        @service.rpc("process")
        async def process_handler(params):
            # Simulate processing
            await asyncio.sleep(0.1)
            return {"result": "processed", "instance": service._instance_id}

        await service.start()
        yield service
        await service.stop()

    async def test_full_discovery_flow_with_k8s_cluster(
        self, registry, test_service_a, test_service_b, logger
    ):
        """Test complete discovery flow with real K8s NATS cluster."""
        # Create discovery
        discovery = BasicServiceDiscovery(registry, logger)

        # Wait for services to register
        await asyncio.sleep(1.0)

        # Discover service A instances
        instances_a = await discovery.discover_instances("test-service-a")
        assert len(instances_a) == 3
        assert all(i.service_name == "test-service-a" for i in instances_a)
        assert all(i.is_healthy() for i in instances_a)

        # Discover service B instances
        instances_b = await discovery.discover_instances("test-service-b")
        assert len(instances_b) == 1
        assert instances_b[0].service_name == "test-service-b"
        assert instances_b[0].is_healthy()

        # Test selection strategies
        for _ in range(10):
            # Round-robin should cycle through all instances
            instance = await discovery.select_instance(
                "test-service-a", strategy=SelectionStrategy.ROUND_ROBIN
            )
            assert instance is not None
            assert instance.service_name == "test-service-a"

        # Random selection
        selected_ids = set()
        for _ in range(30):
            instance = await discovery.select_instance(
                "test-service-a", strategy=SelectionStrategy.RANDOM
            )
            selected_ids.add(instance.instance_id)

        # Should have selected all instances at least once
        assert len(selected_ids) == 3

    async def test_multiple_service_instances_registration_and_discovery(
        self, nats_adapter, kv_store, registry, logger, metrics
    ):
        """Test registration and discovery of multiple service instances."""
        # Create multiple services with varying instance counts
        services_config = [
            ("api-gateway", 2),
            ("user-service", 5),
            ("order-service", 3),
            ("payment-service", 1),
        ]

        all_services = []

        # Start all services
        for service_name, instance_count in services_config:
            for i in range(instance_count):
                service = Service(
                    name=service_name,
                    version="1.0.0",
                    adapter=nats_adapter,
                    kv_store=kv_store,
                    logger=logger,
                    metrics=metrics,
                )
                service._instance_id = f"{service_name}-{i + 1}"
                await service.start()
                all_services.append(service)

        # Wait for registration
        await asyncio.sleep(1.0)

        # Create discovery
        discovery = BasicServiceDiscovery(registry, logger)

        # Verify all services are discoverable
        for service_name, expected_count in services_config:
            instances = await discovery.discover_instances(service_name)
            assert len(instances) == expected_count
            assert all(i.is_healthy() for i in instances)
            assert all(i.service_name == service_name for i in instances)

        # Test listing all services
        all_registered = await registry.list_all_services()
        assert len(all_registered) == len(services_config)

        for service_name, expected_count in services_config:
            assert service_name in all_registered
            assert len(all_registered[service_name]) == expected_count

        # Cleanup
        for service in all_services:
            await service.stop()

    async def test_cache_behavior_under_various_scenarios(
        self, registry, test_service_a, logger, metrics
    ):
        """Test cache behavior in different scenarios."""
        # Create cached discovery with short TTL
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = CacheConfig(ttl_seconds=2.0, max_entries=10)
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Wait for services to register
        await asyncio.sleep(1.0)

        # Scenario 1: Cache hit within TTL
        instances1 = await discovery.discover_instances("test-service-a")
        assert len(instances1) == 3

        instances2 = await discovery.discover_instances("test-service-a")
        assert instances1 == instances2  # Should be from cache

        stats = discovery.get_cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

        # Scenario 2: Cache miss after TTL expiration
        await asyncio.sleep(2.5)  # Wait for TTL to expire

        instances3 = await discovery.discover_instances("test-service-a")
        assert len(instances3) == 3

        stats = discovery.get_cache_stats()
        assert stats["cache_misses"] == 2

        # Scenario 3: Cache invalidation
        await discovery.invalidate_cache("test-service-a")
        instances4 = await discovery.discover_instances("test-service-a")

        stats = discovery.get_cache_stats()
        assert stats["cache_misses"] == 3

        # Scenario 4: Multiple services in cache
        await discovery.discover_instances("test-service-a")
        await discovery.discover_instances("non-existent-service")

        stats = discovery.get_cache_stats()
        assert stats["cache_size"] == 2

        # Scenario 5: Cache size limit
        for i in range(15):
            await discovery.discover_instances(f"service-{i}")

        stats = discovery.get_cache_stats()
        assert stats["cache_size"] <= config.max_entries

    async def test_failover_when_instances_become_unhealthy(
        self, nats_adapter, kv_store, registry, logger, metrics
    ):
        """Test failover behavior when instances become unhealthy."""
        # Create service with 3 instances
        services = []
        for i in range(3):
            service = Service(
                name="failover-test",
                version="1.0.0",
                adapter=nats_adapter,
                kv_store=kv_store,
                logger=logger,
                metrics=metrics,
            )
            service._instance_id = f"failover-{i + 1}"

            @service.rpc("health_check")
            async def health_handler(params):
                return {"status": "ok", "instance": service._instance_id}

            await service.start()
            services.append(service)

        # Create cached discovery
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = CacheConfig(ttl_seconds=1.0)  # Short TTL for faster testing
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Wait for registration
        await asyncio.sleep(1.0)

        # All instances should be healthy
        instances = await discovery.discover_instances("failover-test")
        assert len(instances) == 3

        # Make one instance unhealthy
        unhealthy_instance = services[0]._instance_data
        unhealthy_instance.status = "UNHEALTHY"
        await registry.update_heartbeat(unhealthy_instance, ttl_seconds=60)

        # Invalidate cache to force fresh discovery
        await discovery.invalidate_cache("failover-test")

        # Should only get healthy instances
        healthy_instances = await discovery.discover_instances("failover-test", only_healthy=True)
        assert len(healthy_instances) == 2
        assert all(i.is_healthy() for i in healthy_instances)

        # Test selection with only healthy instances
        for _ in range(10):
            selected = await discovery.select_instance("failover-test")
            assert selected is not None
            assert selected.is_healthy()
            assert selected.instance_id != "failover-1"

        # Make all instances unhealthy
        for service in services:
            service._instance_data.status = "UNHEALTHY"
            await registry.update_heartbeat(service._instance_data, ttl_seconds=60)

        await discovery.invalidate_cache("failover-test")

        # Should return empty list when all unhealthy
        unhealthy_instances = await discovery.discover_instances("failover-test", only_healthy=True)
        assert len(unhealthy_instances) == 0

        # Selection should return None
        selected = await discovery.select_instance("failover-test")
        assert selected is None

        # Cleanup
        for service in services:
            await service.stop()

    async def test_concurrent_discovery_requests(self, registry, test_service_a, logger, metrics):
        """Test concurrent discovery requests for thread safety."""
        # Create cached discovery
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = CacheConfig(ttl_seconds=5.0)
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Wait for registration
        await asyncio.sleep(1.0)

        # Define concurrent discovery tasks
        async def discover_task(service_name: str, count: int):
            results = []
            for _ in range(count):
                instances = await discovery.discover_instances(service_name)
                results.append(len(instances))
                # Small random delay
                await asyncio.sleep(0.01)
            return results

        # Run many concurrent discoveries
        tasks = []
        for i in range(20):
            # Mix of different services
            service_name = "test-service-a" if i % 2 == 0 else "non-existent"
            tasks.append(discover_task(service_name, 5))

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception)

        # Verify consistent results
        for i, result in enumerate(results):
            if i % 2 == 0:  # test-service-a
                assert all(count == 3 for count in result)
            else:  # non-existent
                assert all(count == 0 for count in result)

        # Test concurrent selections
        async def select_task(count: int):
            selections = []
            for _ in range(count):
                instance = await discovery.select_instance(
                    "test-service-a", strategy=SelectionStrategy.ROUND_ROBIN
                )
                if instance:
                    selections.append(instance.instance_id)
            return selections

        # Run concurrent selections
        select_tasks = [select_task(10) for _ in range(10)]
        select_results = await asyncio.gather(*select_tasks)

        # All should have results
        for selections in select_results:
            assert len(selections) == 10
            assert all(s.startswith("service-a-") for s in selections)

    async def test_service_discovery_with_rpc_integration(
        self, nats_adapter, kv_store, test_service_a, test_service_b, logger, metrics
    ):
        """Test service discovery integrated with RPC calls."""
        # Create a client service that uses discovery
        client = Service(
            name="client-service",
            version="1.0.0",
            adapter=nats_adapter,
            kv_store=kv_store,
            logger=logger,
            metrics=metrics,
        )

        # Enable discovery in RPC calls
        client._discovery_enabled = True

        await client.start()

        # Wait for all services to register
        await asyncio.sleep(1.0)

        try:
            # Test RPC calls with discovery to service A (multiple instances)
            responses = []
            for i in range(9):  # Should cycle through all 3 instances
                result = await client.call_rpc("test-service-a", "echo", {"message": f"Hello {i}"})
                responses.append(result)

            # Verify responses
            assert len(responses) == 9
            assert all(r["message"].startswith("Hello") for r in responses)

            # Check that all instances were used (round-robin)
            instance_ids = [r["instance"] for r in responses]
            unique_instances = set(instance_ids)
            assert len(unique_instances) == 3  # All 3 instances used

            # Each instance should have been called 3 times
            for instance_id in unique_instances:
                assert instance_ids.count(instance_id) == 3

            # Test RPC to service B
            result = await client.call_rpc("test-service-b", "process", {"data": "test"})
            assert result["result"] == "processed"
            assert result["instance"] == "service-b-1"

            # Test RPC to non-existent service
            with pytest.raises(ServiceUnavailableError):
                await client.call_rpc("non-existent-service", "method", {})

        finally:
            await client.stop()

    async def test_watchable_discovery_with_k8s_cluster(
        self, nats_adapter, kv_store, registry, logger, metrics
    ):
        """Test watchable cached discovery with K8s cluster."""
        # Create watchable discovery
        basic_discovery = BasicServiceDiscovery(registry, logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,  # Long TTL to test watch effectiveness
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=1.0,
                max_reconnect_attempts=5,
            ),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, kv_store, config, metrics, logger
        ) as discovery:
            # Start with no services
            instances = await discovery.discover_instances("watch-test")
            assert len(instances) == 0

            # Wait for watch to establish
            await asyncio.sleep(0.5)

            # Start a new service
            service = Service(
                name="watch-test",
                version="1.0.0",
                adapter=nats_adapter,
                kv_store=kv_store,
                logger=logger,
                metrics=metrics,
            )
            service._instance_id = "watch-test-1"
            await service.start()

            # Wait for watch event
            await asyncio.sleep(1.0)

            # Discovery should find the new instance without TTL expiration
            instances = await discovery.discover_instances("watch-test")
            assert len(instances) == 1
            assert instances[0].instance_id == "watch-test-1"

            # Add another instance
            service2 = Service(
                name="watch-test",
                version="1.0.0",
                adapter=nats_adapter,
                kv_store=kv_store,
                logger=logger,
                metrics=metrics,
            )
            service2._instance_id = "watch-test-2"
            await service2.start()

            # Wait for watch event
            await asyncio.sleep(1.0)

            # Should find both instances
            instances = await discovery.discover_instances("watch-test")
            assert len(instances) == 2

            # Stop first service
            await service.stop()

            # Wait for deregistration
            await asyncio.sleep(1.0)

            # Should only find second instance
            instances = await discovery.discover_instances("watch-test")
            assert len(instances) == 1
            assert instances[0].instance_id == "watch-test-2"

            # Verify watch stats
            stats = discovery.get_watch_stats()
            assert stats["enabled"]
            assert stats["running"]
            assert stats["reconnect_attempts"] == 0

            # Cleanup
            await service2.stop()
