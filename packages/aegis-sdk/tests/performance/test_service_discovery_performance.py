"""Performance tests for Service Discovery implementations.

These tests verify that service discovery can handle high-concurrency
scenarios efficiently without data races or performance degradation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure import (
    BasicServiceDiscovery,
    CacheConfig,
    CachedServiceDiscovery,
    InMemoryMetrics,
)
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.ports.service_discovery import SelectionStrategy
from aegis_sdk.ports.service_registry import ServiceRegistryPort


class MockServiceRegistry(ServiceRegistryPort):
    """Mock service registry for performance testing."""

    def __init__(self, instance_count: int = 100):
        """Initialize with a specified number of instances per service."""
        self.instance_count = instance_count
        self.services = {}
        self._generate_instances()

    def _generate_instances(self) -> None:
        """Generate test instances for multiple services."""
        services = [
            "api-gateway",
            "user-service",
            "order-service",
            "payment-service",
            "inventory-service",
        ]

        for service in services:
            instances = []
            for i in range(self.instance_count):
                instances.append(
                    ServiceInstance(
                        service_name=service,
                        instance_id=f"{service}-{i:03d}",
                        version="1.0.0",
                        status="ACTIVE",
                    )
                )
            self.services[service] = instances

    async def register(self, instance: ServiceInstance, ttl_seconds: int = 30) -> None:
        """Mock register method."""
        pass

    async def deregister(self, instance: ServiceInstance) -> None:
        """Mock deregister method."""
        pass

    async def update_heartbeat(self, instance: ServiceInstance, ttl_seconds: int = 30) -> None:
        """Mock heartbeat update."""
        pass

    async def list_instances(self, service_name: str) -> list[ServiceInstance]:
        """Return pre-generated instances for the service."""
        # Simulate some network latency
        await asyncio.sleep(0.001)
        return self.services.get(service_name, [])

    async def list_all_services(self) -> dict[str, list[ServiceInstance]]:
        """Return all services."""
        await asyncio.sleep(0.005)
        return self.services.copy()

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get specific instance."""
        instances = self.services.get(service_name, [])
        for instance in instances:
            if instance.instance_id == instance_id:
                return instance
        return None


@pytest.mark.performance
@pytest.mark.asyncio
class TestServiceDiscoveryPerformance:
    """Performance tests for service discovery implementations."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry with many instances."""
        return MockServiceRegistry(instance_count=100)

    @pytest.fixture
    def logger(self):
        """Create logger for testing."""
        return SimpleLogger()

    @pytest.fixture
    def metrics(self):
        """Create metrics for testing."""
        return InMemoryMetrics()

    async def test_concurrent_discovery_basic(self, mock_registry, logger):
        """Test concurrent discovery with BasicServiceDiscovery."""
        discovery = BasicServiceDiscovery(mock_registry, logger)

        # Define concurrent discovery task
        async def discover_task(service_name: str, count: int) -> list[float]:
            """Perform multiple discoveries and measure time."""
            times = []
            for _ in range(count):
                start = time.time()
                instances = await discovery.discover_instances(service_name)
                elapsed = time.time() - start
                times.append(elapsed)
                assert len(instances) == 100  # Verify we got all instances
            return times

        # Run many concurrent discovery operations
        services = ["user-service", "order-service", "payment-service"]
        tasks = []
        for service in services:
            for _ in range(10):  # 10 concurrent clients per service
                tasks.append(discover_task(service, 10))  # 10 discoveries each

        start_time = time.time()
        all_times = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        all_discovery_times = [t for times in all_times for t in times]
        avg_discovery_time = sum(all_discovery_times) / len(all_discovery_times)
        max_discovery_time = max(all_discovery_times)

        print("\nBasic Discovery Performance:")
        print(f"Total operations: {len(all_discovery_times)}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average discovery time: {avg_discovery_time * 1000:.2f}ms")
        print(f"Max discovery time: {max_discovery_time * 1000:.2f}ms")
        print(f"Operations/second: {len(all_discovery_times) / total_time:.0f}")

        # Performance assertions
        assert avg_discovery_time < 0.01  # Average should be under 10ms
        assert max_discovery_time < 0.05  # Max should be under 50ms

    async def test_concurrent_discovery_cached(self, mock_registry, logger, metrics):
        """Test concurrent discovery with CachedServiceDiscovery."""
        basic_discovery = BasicServiceDiscovery(mock_registry, logger)
        config = CacheConfig(ttl_seconds=5.0, max_entries=100)
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Warm up the cache
        for service in ["user-service", "order-service", "payment-service"]:
            await discovery.discover_instances(service)

        # Define concurrent discovery task
        async def discover_task(service_name: str, count: int) -> tuple[list[float], int, int]:
            """Perform multiple discoveries and track cache hits."""
            times = []
            hits_before = discovery._cache_hits
            for _ in range(count):
                start = time.time()
                instances = await discovery.discover_instances(service_name)
                elapsed = time.time() - start
                times.append(elapsed)
                assert len(instances) == 100
            hits_after = discovery._cache_hits
            return times, hits_after - hits_before, count

        # Run many concurrent discovery operations
        services = ["user-service", "order-service", "payment-service"]
        tasks = []
        for service in services:
            for _ in range(20):  # 20 concurrent clients per service
                tasks.append(discover_task(service, 50))  # 50 discoveries each

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        all_times = []
        total_hits = 0
        total_requests = 0
        for times, hits, requests in results:
            all_times.extend(times)
            total_hits += hits
            total_requests += requests

        avg_discovery_time = sum(all_times) / len(all_times)
        max_discovery_time = max(all_times)
        cache_hit_rate = total_hits / total_requests

        print("\nCached Discovery Performance:")
        print(f"Total operations: {len(all_times)}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average discovery time: {avg_discovery_time * 1000:.3f}ms")
        print(f"Max discovery time: {max_discovery_time * 1000:.3f}ms")
        print(f"Operations/second: {len(all_times) / total_time:.0f}")
        print(f"Cache hit rate: {cache_hit_rate:.2%}")

        # Performance assertions
        assert avg_discovery_time < 0.001  # Average should be under 1ms (mostly cache hits)
        assert max_discovery_time < 0.01  # Max should be under 10ms
        assert cache_hit_rate > 0.95  # Should have >95% cache hit rate

    async def test_concurrent_selection_strategies(self, mock_registry, logger):
        """Test concurrent instance selection with different strategies."""
        discovery = BasicServiceDiscovery(mock_registry, logger)

        # Test each selection strategy
        strategies = [
            SelectionStrategy.ROUND_ROBIN,
            SelectionStrategy.RANDOM,
            SelectionStrategy.STICKY,
        ]

        for strategy in strategies:
            # Define selection task with strategy passed as parameter
            async def select_task(
                count: int, select_strategy: SelectionStrategy
            ) -> tuple[list[float], set[str]]:
                """Perform selections and track distribution."""
                times = []
                selected_ids = set()
                for _ in range(count):
                    start = time.time()
                    instance = await discovery.select_instance(
                        "user-service",
                        strategy=select_strategy,
                        preferred_instance_id=(
                            "user-service-050"
                            if select_strategy == SelectionStrategy.STICKY
                            else None
                        ),
                    )
                    elapsed = time.time() - start
                    times.append(elapsed)
                    if instance:
                        selected_ids.add(instance.instance_id)
                return times, selected_ids

            # Run concurrent selections
            tasks = []
            for _ in range(10):  # 10 concurrent selectors
                tasks.append(select_task(100, strategy))  # 100 selections each

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            # Analyze results
            all_times = []
            all_selected = set()
            for times, selected in results:
                all_times.extend(times)
                all_selected.update(selected)

            avg_selection_time = sum(all_times) / len(all_times)
            max_selection_time = max(all_times)

            print(f"\n{strategy.value} Selection Performance:")
            print(f"Total operations: {len(all_times)}")
            print(f"Total time: {total_time:.3f}s")
            print(f"Average selection time: {avg_selection_time * 1000:.3f}ms")
            print(f"Max selection time: {max_selection_time * 1000:.3f}ms")
            print(f"Operations/second: {len(all_times) / total_time:.0f}")
            print(f"Unique instances selected: {len(all_selected)}")

            # Performance assertions
            assert avg_selection_time < 0.002  # Average should be under 2ms
            assert max_selection_time < 0.01  # Max should be under 10ms

            # Strategy-specific assertions
            if strategy == SelectionStrategy.ROUND_ROBIN:
                # Should select all instances in round-robin
                assert len(all_selected) == 100
            elif strategy == SelectionStrategy.STICKY:
                # Should mostly select the preferred instance
                assert "user-service-050" in all_selected

    async def test_cache_performance_under_load(self, mock_registry, logger, metrics):
        """Test cache performance with many services and high concurrency."""
        basic_discovery = BasicServiceDiscovery(mock_registry, logger)
        config = CacheConfig(ttl_seconds=2.0, max_entries=50)  # Limited cache size
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Define task that discovers multiple services
        async def multi_service_task(services: list[str], count: int) -> dict[str, Any]:
            """Discover multiple services and measure performance."""
            results = {
                "times": [],
                "cache_hits": 0,
                "cache_misses": 0,
            }

            for _ in range(count):
                for service in services:
                    hits_before = discovery._cache_hits
                    misses_before = discovery._cache_misses

                    start = time.time()
                    instances = await discovery.discover_instances(service)
                    elapsed = time.time() - start

                    results["times"].append(elapsed)
                    results["cache_hits"] += discovery._cache_hits - hits_before
                    results["cache_misses"] += discovery._cache_misses - misses_before

                    assert len(instances) > 0

            return results

        # Run with all services
        all_services = list(mock_registry.services.keys())
        tasks = []
        for i in range(20):  # 20 concurrent workers
            # Each worker gets a subset of services
            services = all_services[i % len(all_services) :] + all_services[: i % len(all_services)]
            tasks.append(multi_service_task(services[:3], 20))

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Aggregate results
        all_times = []
        total_hits = 0
        total_misses = 0
        for result in results:
            all_times.extend(result["times"])
            total_hits += result["cache_hits"]
            total_misses += result["cache_misses"]

        avg_time = sum(all_times) / len(all_times)
        hit_rate = total_hits / (total_hits + total_misses)

        print("\nCache Under Load Performance:")
        print(f"Total operations: {len(all_times)}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average operation time: {avg_time * 1000:.3f}ms")
        print(f"Operations/second: {len(all_times) / total_time:.0f}")
        print(f"Cache hit rate: {hit_rate:.2%}")
        print(f"Final cache size: {len(discovery._cache)}")

        # Performance assertions
        assert avg_time < 0.005  # Average should be under 5ms
        assert hit_rate > 0.5  # Should have reasonable hit rate despite limited cache

    async def test_concurrent_cache_invalidation(self, mock_registry, logger, metrics):
        """Test performance impact of concurrent cache invalidations."""
        basic_discovery = BasicServiceDiscovery(mock_registry, logger)
        config = CacheConfig(ttl_seconds=10.0)
        discovery = CachedServiceDiscovery(basic_discovery, config, metrics, logger)

        # Warm up cache
        for service in mock_registry.services:
            await discovery.discover_instances(service)

        # Define tasks
        async def discovery_task(service: str, count: int) -> list[float]:
            """Continuously discover instances."""
            times = []
            for _ in range(count):
                start = time.time()
                await discovery.discover_instances(service)
                times.append(time.time() - start)
            return times

        async def invalidation_task(service: str, count: int) -> int:
            """Periodically invalidate cache."""
            for _ in range(count):
                await asyncio.sleep(0.1)  # Invalidate every 100ms
                await discovery.invalidate_cache(service)
            return count

        # Run discovery and invalidation concurrently
        tasks = []
        services = list(mock_registry.services.keys())

        # Discovery tasks
        for service in services:
            for _ in range(5):
                tasks.append(discovery_task(service, 50))

        # Invalidation tasks
        for service in services:
            tasks.append(invalidation_task(service, 5))

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Separate discovery times from invalidation counts
        discovery_times = []
        invalidation_count = 0
        for result in results:
            if isinstance(result, list):
                discovery_times.extend(result)
            else:
                invalidation_count += result

        avg_time = sum(discovery_times) / len(discovery_times)

        print("\nConcurrent Invalidation Performance:")
        print(f"Total discoveries: {len(discovery_times)}")
        print(f"Total invalidations: {invalidation_count}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average discovery time: {avg_time * 1000:.3f}ms")
        print(f"Discoveries/second: {len(discovery_times) / total_time:.0f}")

        # Performance assertions
        assert avg_time < 0.005  # Should maintain good performance despite invalidations


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s", "-m", "performance"])
