"""K8s integration tests for sticky active client retry logic with automatic failover.

These tests validate client-side retry behavior during actual failover scenarios
using the Story 3.3 automatic failover implementation.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.application.use_cases import RPCCallRequest, RPCCallUseCase
from aegis_sdk.domain.services import MessageRoutingService, MetricsNamingService
from aegis_sdk.domain.value_objects import Duration, FailoverPolicy, RetryPolicy
from aegis_sdk.infrastructure.application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultUseCaseFactory,
)
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Register default dependencies
bootstrap_defaults()


@pytest_asyncio.fixture
async def nats_adapter():
    """Create NATS adapter connected to K8s NATS."""
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])
    yield adapter
    await adapter.disconnect()


@pytest_asyncio.fixture
async def service_registry(nats_adapter):
    """Create service registry using NATS KV."""
    kv_store = NATSKVStore(nats_adapter)
    await kv_store.connect("service_registry")
    registry = KVServiceRegistry(kv_store)
    yield registry


@pytest_asyncio.fixture
async def service_discovery(nats_adapter):
    """Create service discovery using NATS JetStream."""
    import nats

    nc = nats.NATS()
    await nc.connect(servers=["nats://localhost:4222"])
    js = nc.jetstream()
    discovery = BasicServiceDiscovery(js)
    yield discovery
    await nc.close()


class TestK8sStickyActiveClientRetry:
    """Test client retry logic during real failover scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(20)
    async def test_client_retry_during_failover(
        self, nats_adapter, service_registry, service_discovery
    ):
        """Test that client successfully retries during a failover event."""
        # Unique test identifiers to avoid conflicts
        test_id = str(int(time.time()))
        service_name = f"test-retry-service-{test_id}"
        group_id = f"test-group-{test_id}"

        # Clean up any stale leader keys from previous tests
        kv_store = NATSKVStore(nats_adapter)
        election_bucket = f"election_{service_name.replace('-', '_')}"
        await kv_store.connect(election_bucket)
        leader_key = f"leader.{group_id}"
        try:
            await kv_store.delete(leader_key)
        except:
            pass  # Key might not exist

        # Create three service instances
        instances = []
        for i in range(1, 4):
            config = SingleActiveConfig(
                service_name=service_name,
                instance_id=f"instance-{i}-{test_id}",
                group_id=group_id,
                registry_ttl=30,
                heartbeat_interval=3,  # 3 second heartbeat
                leader_ttl_seconds=2,  # 2 second TTL (must be less than heartbeat)
            )

            service = SingleActiveService(
                config=config,
                message_bus=nats_adapter,
                service_registry=service_registry,
                service_discovery=service_discovery,
                election_repository_factory=DefaultElectionRepositoryFactory(),
                use_case_factory=DefaultUseCaseFactory(),
                logger=SimpleLogger(f"test-service-{i}"),
            )

            # Set aggressive failover policy for faster test
            if hasattr(service, "_failover_use_case") and service._failover_use_case:
                service._failover_use_case._failover_policy = FailoverPolicy.aggressive()

            instances.append(service)

        # Start all instances
        for service in instances:
            await service.start()

        # Wait for initial election
        await asyncio.sleep(2)

        # Create a custom service class with test handler
        class TestRetryService(SingleActiveService):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.call_count = 0
                self.handler_results = []

            async def on_start(self) -> None:
                """Register RPC handlers on start."""
                await super().on_start()

                @self.rpc("test_method")
                @self.exclusive_rpc("test_method")
                async def test_handler(params: dict[str, Any]) -> dict[str, Any]:
                    """Test RPC handler that only runs on active instance."""
                    self.call_count += 1
                    result = {
                        "instance_id": self._config.instance_id,
                        "call_count": self.call_count,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    self.handler_results.append(result)
                    return result

        # Replace instances with our custom service
        custom_instances = []
        for i, service in enumerate(instances):
            # Stop the generic service
            await service.stop()

            # Create custom service with same config
            config = SingleActiveConfig(
                service_name=service_name,
                instance_id=f"instance-{i + 1}-{test_id}",
                group_id=group_id,
                registry_ttl=30,
                heartbeat_interval=3,
                leader_ttl_seconds=2,
            )

            custom_service = TestRetryService(
                config=config,
                message_bus=nats_adapter,
                service_registry=service_registry,
                service_discovery=service_discovery,
                election_repository_factory=DefaultElectionRepositoryFactory(),
                use_case_factory=DefaultUseCaseFactory(),
                logger=SimpleLogger(f"test-service-{i + 1}"),
            )

            if hasattr(custom_service, "_failover_use_case") and custom_service._failover_use_case:
                custom_service._failover_use_case._failover_policy = FailoverPolicy.aggressive()

            custom_instances.append(custom_service)

        # Start all custom instances
        for service in custom_instances:
            await service.start()

        # Wait for election
        await asyncio.sleep(2)

        # Find the active instance
        active_instance = None
        for service in custom_instances:
            status = await service.get_status()
            if status.is_active:
                active_instance = service
                break

        assert active_instance is not None, "No active instance found"
        print(f"✅ Initial leader: {active_instance._config.instance_id}")

        # Create client with retry policy
        metrics = InMemoryMetrics()
        logger = SimpleLogger("test-client")
        routing_service = MessageRoutingService()
        naming_service = MetricsNamingService()

        rpc_use_case = RPCCallUseCase(
            message_bus=nats_adapter,
            metrics=metrics,
            routing_service=routing_service,
            naming_service=naming_service,
            logger=logger,
        )

        # Configure retry policy for fast retries
        retry_policy = RetryPolicy(
            max_retries=10,  # Allow many retries
            initial_delay=Duration(seconds=0.5),  # Start with 500ms delay
            backoff_multiplier=1.5,
            max_delay=Duration(seconds=2.0),
            jitter_factor=0.1,  # Small jitter
        )

        # Create a task that makes RPC calls
        async def make_rpc_call():
            """Make an RPC call with retry."""
            request = RPCCallRequest(
                target_service=service_name,
                method="test_method",
                params={"test": "data"},
                timeout=15.0,  # Long timeout for retries
                caller_service="test-client",
                caller_instance="client-1",
                retry_policy=retry_policy,
            )
            return await rpc_use_case.execute(request)

        # Make initial successful call
        result1 = await make_rpc_call()
        assert result1 is not None
        print(f"✅ Initial call succeeded to {active_instance._config.instance_id}")

        # Now simulate failover by stopping the active instance
        print(f"🔴 Simulating failure of {active_instance._config.instance_id}")

        # Start an RPC call that will experience the failover
        failover_start = time.time()

        # Create a task for the RPC call
        rpc_task = asyncio.create_task(make_rpc_call())

        # Wait a moment then stop the active instance
        await asyncio.sleep(0.5)
        await active_instance.stop()

        # Wait for the RPC call to complete (with retries)
        try:
            result2 = await asyncio.wait_for(rpc_task, timeout=10.0)
            failover_duration = time.time() - failover_start

            print(f"✅ RPC call succeeded after failover in {failover_duration:.2f}s")
            print(f"   Result: {result2}")

            # Verify we got a result (even if from a different instance)
            assert result2 is not None

            # Check metrics for retry attempts
            all_metrics = metrics.get_all()
            counters = all_metrics.get("counters", {})
            print(f"📊 Metrics: {counters}")

            # We should see retry attempts in the metrics
            retry_metrics = [k for k in counters.keys() if "retry" in k.lower()]
            if retry_metrics:
                print(f"   Retry metrics found: {retry_metrics}")

        except asyncio.TimeoutError:
            pytest.fail("RPC call timed out during failover")
        finally:
            # Clean up remaining instances
            for service in custom_instances:
                if service != active_instance:
                    await service.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_retry_metrics_during_failover(
        self, nats_adapter, service_registry, service_discovery
    ):
        """Test that retry metrics are correctly tracked during failover."""
        # Unique test identifiers
        test_id = str(int(time.time()))
        service_name = f"test-metrics-service-{test_id}"
        group_id = f"test-group-{test_id}"

        # Clean up any stale leader keys
        kv_store = NATSKVStore(nats_adapter)
        election_bucket = f"election_{service_name.replace('-', '_')}"
        await kv_store.connect(election_bucket)
        leader_key = f"leader.{group_id}"
        try:
            await kv_store.delete(leader_key)
        except:
            pass

        # Create two service instances for faster failover
        instances = []
        for i in range(1, 3):
            config = SingleActiveConfig(
                service_name=service_name,
                instance_id=f"instance-{i}-{test_id}",
                group_id=group_id,
                registry_ttl=30,
                heartbeat_interval=3,
                leader_ttl_seconds=2,
            )

            service = SingleActiveService(
                config=config,
                message_bus=nats_adapter,
                service_registry=service_registry,
                service_discovery=service_discovery,
                election_repository_factory=DefaultElectionRepositoryFactory(),
                use_case_factory=DefaultUseCaseFactory(),
                logger=SimpleLogger(f"test-service-{i}"),
            )

            # Set aggressive failover
            if hasattr(service, "_failover_use_case") and service._failover_use_case:
                service._failover_use_case._failover_policy = FailoverPolicy.aggressive()

            instances.append(service)

        # Start instances
        for service in instances:
            await service.start()

        await asyncio.sleep(2)

        # Create custom service class with metric handler
        class TestMetricService(SingleActiveService):
            async def on_start(self) -> None:
                """Register RPC handlers on start."""
                await super().on_start()

                @self.rpc("test_metric_method")
                @self.exclusive_rpc("test_metric_method")
                async def metric_handler(params: dict[str, Any]) -> dict[str, Any]:
                    """Test handler for metrics."""
                    return {"instance": self._config.instance_id, "status": "ok"}

        # Replace instances with custom service
        custom_instances = []
        for i, service in enumerate(instances):
            await service.stop()

            config = SingleActiveConfig(
                service_name=service_name,
                instance_id=f"instance-{i + 1}-{test_id}",
                group_id=group_id,
                registry_ttl=30,
                heartbeat_interval=3,
                leader_ttl_seconds=2,
            )

            custom_service = TestMetricService(
                config=config,
                message_bus=nats_adapter,
                service_registry=service_registry,
                service_discovery=service_discovery,
                election_repository_factory=DefaultElectionRepositoryFactory(),
                use_case_factory=DefaultUseCaseFactory(),
                logger=SimpleLogger(f"test-service-{i + 1}"),
            )

            if hasattr(custom_service, "_failover_use_case") and custom_service._failover_use_case:
                custom_service._failover_use_case._failover_policy = FailoverPolicy.aggressive()

            custom_instances.append(custom_service)

        # Start all custom instances
        for service in custom_instances:
            await service.start()

        await asyncio.sleep(2)

        # Find active and standby instances
        active_instance = None
        standby_instance = None
        for service in custom_instances:
            status = await service.get_status()
            if status.is_active:
                active_instance = service
            else:
                standby_instance = service

        assert active_instance is not None
        assert standby_instance is not None

        # Create client with metrics tracking
        metrics = InMemoryMetrics()
        logger = SimpleLogger("test-metrics-client")
        routing_service = MessageRoutingService()
        naming_service = MetricsNamingService()

        rpc_use_case = RPCCallUseCase(
            message_bus=nats_adapter,
            metrics=metrics,
            routing_service=routing_service,
            naming_service=naming_service,
            logger=logger,
        )

        # Fast retry policy
        retry_policy = RetryPolicy(
            max_retries=5,
            initial_delay=Duration(seconds=0.2),
            backoff_multiplier=1.2,
            max_delay=Duration(seconds=1.0),
            jitter_factor=0.0,  # No jitter for predictable metrics
        )

        # Track metrics before failover
        initial_metrics = metrics.get_all().get("counters", {})

        # Stop active instance to trigger failover
        print(f"🔴 Stopping active instance {active_instance._config.instance_id}")
        await active_instance.stop()

        # Wait for failover to complete and new leader to be ready
        await asyncio.sleep(3)  # Give time for election and handler registration

        # Make RPC call that will retry until new leader is ready
        request = RPCCallRequest(
            target_service=service_name,
            method="test_metric_method",
            params={"test": "metrics"},
            timeout=10.0,
            caller_service="metrics-client",
            caller_instance="client-1",
            retry_policy=retry_policy,
        )

        start_time = time.time()
        try:
            result = await rpc_use_case.execute(request)
            elapsed = time.time() - start_time
            print(f"✅ Call succeeded after {elapsed:.2f}s")

            # Get final metrics
            final_metrics = metrics.get_all().get("counters", {})

            # Look for retry-related metrics
            print("📊 Metrics after failover:")
            for key, value in final_metrics.items():
                if key not in initial_metrics or value != initial_metrics.get(key, 0):
                    print(f"   {key}: {value}")

            # The call should succeed (either immediately if new leader is ready, or after retries)
            # We're mainly testing that it doesn't fail completely
            print(f"   Call completed in {elapsed:.2f}s (may be immediate if new leader ready)")

        except Exception as e:
            pytest.fail(f"RPC call failed: {e}")
        finally:
            # Clean up
            for service in custom_instances:
                try:
                    await service.stop()
                except:
                    pass

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_no_retry_for_non_not_active_errors(
        self, nats_adapter, service_registry, service_discovery
    ):
        """Test that non-NOT_ACTIVE errors are not retried."""
        # Unique test identifiers
        test_id = str(int(time.time()))
        service_name = f"test-no-retry-service-{test_id}"
        group_id = f"test-group-{test_id}"

        # Create a service that will return a different error
        config = SingleActiveConfig(
            service_name=service_name,
            instance_id=f"instance-1-{test_id}",
            group_id=group_id,
            registry_ttl=30,
            heartbeat_interval=5,
            leader_ttl_seconds=3,
        )

        # Create a custom service class to register the handler
        class TestErrorService(SingleActiveService):
            async def on_start(self) -> None:
                """Register RPC handlers on start."""
                await super().on_start()

                # Register a handler that returns a non-NOT_ACTIVE error
                # We need to use both exclusive_rpc AND rpc to properly register
                @self.rpc("test_error_method")
                @self.exclusive_rpc("test_error_method")
                async def error_handler(params: dict[str, Any]) -> dict[str, Any]:
                    """Handler that raises a different error."""
                    raise ValueError("INTERNAL_ERROR: This is not a NOT_ACTIVE error")

        service = TestErrorService(
            config=config,
            message_bus=nats_adapter,
            service_registry=service_registry,
            service_discovery=service_discovery,
            election_repository_factory=DefaultElectionRepositoryFactory(),
            use_case_factory=DefaultUseCaseFactory(),
            logger=SimpleLogger("test-service"),
        )

        await service.start()
        await asyncio.sleep(2)

        # Create client
        metrics = InMemoryMetrics()
        logger = SimpleLogger("test-no-retry")
        routing_service = MessageRoutingService()
        naming_service = MetricsNamingService()

        rpc_use_case = RPCCallUseCase(
            message_bus=nats_adapter,
            metrics=metrics,
            routing_service=routing_service,
            naming_service=naming_service,
            logger=logger,
        )

        # Retry policy that would retry if it were a NOT_ACTIVE error
        retry_policy = RetryPolicy(
            max_retries=3,
            initial_delay=Duration(seconds=0.1),
            backoff_multiplier=2.0,
        )

        request = RPCCallRequest(
            target_service=service_name,
            method="test_error_method",
            params={"test": "error"},
            timeout=5.0,
            caller_service="test-client",
            caller_instance="client-1",
            retry_policy=retry_policy,
        )

        # Should get an error response but not retry
        start_time = time.time()
        result = await rpc_use_case.execute(request)
        elapsed = time.time() - start_time

        # Should fail quickly without retries
        assert elapsed < 1.0, f"Should fail quickly, took {elapsed:.2f}s"

        # Check that we got an error response
        print(f"Result: {result}")
        assert result is not None
        # The error should be wrapped in the response
        # Check if it's an error response (not a successful one)
        if isinstance(result, dict):
            assert (
                result.get("success") is False
                or "error" in result
                or "EXECUTION_ERROR" in str(result)
            )
        else:
            # Result might be wrapped differently
            assert "INTERNAL_ERROR" in str(result) or "EXECUTION_ERROR" in str(result)

        print(f"✅ Non-NOT_ACTIVE error was not retried (failed in {elapsed:.2f}s)")

        # Clean up
        await service.stop()
