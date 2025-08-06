"""Integration test for client-side retry logic with sticky active pattern.

This test validates the client-side optimizations implemented in Story 3.2,
specifically the automatic retry behavior when receiving NOT_ACTIVE errors.
"""

import asyncio
import time
import uuid

import pytest
import pytest_asyncio

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.application.use_cases import RPCCallRequest, RPCCallUseCase
from aegis_sdk.domain.services import MessageRoutingService, MetricsNamingService
from aegis_sdk.domain.value_objects import RetryPolicy
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class TestStickyServiceWithRetry(SingleActiveService):
    """Test service for sticky active pattern that can simulate failover."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.process_count = 0
        self.is_running = True
        self._simulate_not_active = False  # Flag to simulate NOT_ACTIVE responses

    async def on_start(self):
        """Register RPC handlers."""

        @self.exclusive_rpc("process_with_failover")
        async def process_with_failover(params: dict) -> dict:
            """Process request - only active instance handles this."""
            # The exclusive_rpc decorator automatically returns NOT_ACTIVE if not active
            # When simulate_standby(True) is called, it sets is_active=False
            # so the decorator will return NOT_ACTIVE automatically
            self.process_count += 1
            return {
                "instance_id": self.instance_id,
                "process_count": self.process_count,
                "request_id": params.get("request_id", "unknown"),
            }

        @self.rpc("get_status")
        async def get_status(params: dict) -> dict:
            """Get instance status."""
            return {
                "instance_id": self.instance_id,
                "is_active": self.is_active,
                "process_count": self.process_count,
                "simulating_not_active": self._simulate_not_active,
            }

    def simulate_standby(self, enabled: bool = True) -> None:
        """Simulate standby mode for testing by manipulating is_active."""
        # To properly test NOT_ACTIVE response, we need to set is_active
        # because the exclusive_rpc decorator checks this field
        self._simulate_not_active = enabled
        if enabled:
            self._original_is_active = self.is_active
            self.is_active = False
        else:
            # Restore original state
            if hasattr(self, "_original_is_active"):
                self.is_active = self._original_is_active

    async def stop(self) -> None:
        """Stop the service."""
        self.is_running = False
        await super().stop()


@pytest.mark.integration
@pytest.mark.asyncio
class TestStickyActiveClientRetry:
    """Test client-side retry logic for sticky active pattern."""

    @classmethod
    def setup_class(cls):
        """Setup test class by registering default dependencies."""
        bootstrap_defaults()

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create NATS adapter."""
        config = NATSConnectionConfig()
        adapter = NATSAdapter(config=config)
        await adapter.connect("nats://localhost:4222")

        # Create KV stores
        kv_store1 = NATSKVStore(nats_adapter=adapter)
        await kv_store1.connect("service_instances")

        kv_store2 = NATSKVStore(nats_adapter=adapter)
        await kv_store2.connect("sticky_active")

        yield adapter

        # Clean up
        try:
            await kv_store1.clear()
            await kv_store2.clear()
        except Exception:
            pass

        await adapter.disconnect()

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return SimpleLogger("test-client-retry")

    @pytest.fixture
    def metrics(self):
        """Create metrics for tracking retry behavior."""
        return InMemoryMetrics()

    async def create_service_instance(
        self,
        nats_adapter,
        service_name="sticky-retry-test",
        group_id="retry-test-group",
        instance_id=None,
    ):
        """Create a single service instance."""
        if instance_id is None:
            instance_id = f"sticky-service-{uuid.uuid4().hex[:8]}"

        logger = SimpleLogger(instance_id)

        # Create KV stores
        kv_store_registry = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_registry.connect("service_instances")

        kv_store_election = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_election.connect("sticky_active")

        service_registry = KVServiceRegistry(kv_store=kv_store_registry, logger=logger)
        election_repository = NatsKvElectionRepository(kv_store=kv_store_election, logger=logger)
        metrics = InMemoryMetrics()

        config = SingleActiveConfig(
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            leader_ttl_seconds=2,
            registry_ttl=30,
            heartbeat_interval=5,
        )

        service = TestStickyServiceWithRetry(
            config=config,
            message_bus=nats_adapter,
            service_registry=service_registry,
            election_repository=election_repository,
            logger=logger,
            metrics=metrics,
        )

        return service

    def create_rpc_use_case(self, nats_adapter, metrics, logger):
        """Create RPCCallUseCase with retry logic."""
        routing_service = MessageRoutingService()
        naming_service = MetricsNamingService()

        return RPCCallUseCase(
            message_bus=nats_adapter,
            metrics=metrics,
            routing_service=routing_service,
            naming_service=naming_service,
            logger=logger,
        )

    @pytest.mark.asyncio
    async def test_automatic_retry_on_not_active(self, nats_adapter, logger, metrics):
        """Test that client automatically retries on NOT_ACTIVE errors."""
        services = []

        try:
            # Create 3 service instances
            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"retry-test-{i}"
                )
                services.append(service)
                await service.start()
                await asyncio.sleep(0.5)

            # Wait for election
            await asyncio.sleep(3)

            # Find the active instance
            active_service = next(s for s in services if s.is_active)
            logger.info(f"Active instance: {active_service.instance_id}")

            # Create RPC use case with retry logic
            rpc_use_case = self.create_rpc_use_case(nats_adapter, metrics, logger)

            # Simulate the active instance appearing as standby (simulating failover start)
            active_service.simulate_standby(True)  # This will trigger NOT_ACTIVE response

            # Make RPC call with default retry policy
            request = RPCCallRequest(
                target_service="sticky-retry-test",
                method="process_with_failover",
                params={"request_id": "test-retry-1"},
                timeout=10.0,
                caller_service="test-client-service",
                caller_instance="test-client",
            )

            # The call should initially fail with NOT_ACTIVE, then succeed after retry
            # when we restore the active status
            start_time = time.time()

            # Restore active status after a delay to simulate failover recovery
            async def restore_active():
                await asyncio.sleep(0.5)  # Simulate failover time (shorter than total retry time)
                active_service.simulate_standby(False)  # Restore normal operation

            restore_task = asyncio.create_task(restore_active())

            try:
                result = await rpc_use_case.execute(request)
                elapsed = time.time() - start_time

                # Verify the call succeeded
                assert result is not None
                assert result.get("success") is not False

                # Verify retry metrics were recorded
                retry_metrics = metrics.get_metrics()
                assert any("retry.not_active" in k for k in retry_metrics)
                assert any("retry.success" in k for k in retry_metrics)

                logger.info(f"Call succeeded after {elapsed:.2f}s with retries")

            finally:
                await restore_task

        finally:
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_configurable_retry_policy(self, nats_adapter, logger, metrics):
        """Test that retry policy is configurable."""
        services = []

        try:
            # Create service instances
            for i in range(2):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"config-test-{i}"
                )
                services.append(service)
                await service.start()
                await asyncio.sleep(0.5)

            # Wait for election
            await asyncio.sleep(3)

            # Create RPC use case
            rpc_use_case = self.create_rpc_use_case(nats_adapter, metrics, logger)

            # Create custom retry policy with specific settings
            custom_policy = RetryPolicy(
                max_retries=5,
                initial_delay=0.05,  # 50ms
                backoff_multiplier=1.5,
                max_delay=2.0,
                jitter_factor=0.1,
            )

            # Force all instances to simulate standby to ensure retries
            for service in services:
                service.simulate_standby(True)

            # Make RPC call with custom retry policy
            request = RPCCallRequest(
                target_service="sticky-retry-test",
                method="process_with_failover",
                params={"request_id": "test-custom-retry"},
                timeout=10.0,
                caller_service="test-client-service",
                caller_instance="test-client",
                retry_policy=custom_policy,
            )

            # This should exhaust retries since all instances are forced to standby
            with pytest.raises(Exception) as exc_info:
                await rpc_use_case.execute(request)

            # Verify it retried the expected number of times
            assert "5 retries" in str(exc_info.value)

            # Verify retry metrics
            retry_metrics = metrics.get_metrics()
            not_active_retries = retry_metrics.get(
                "rpc.sticky-retry-test.process_with_failover.retry.not_active", 0
            )
            assert not_active_retries >= 5

        finally:
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_failover_latency_tracking(self, nats_adapter, logger, metrics):
        """Test that failover latency is properly tracked."""
        services = []

        try:
            # Create service instances
            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"latency-test-{i}"
                )
                services.append(service)
                await service.start()
                await asyncio.sleep(0.5)

            # Wait for election
            await asyncio.sleep(3)

            # Find active instance
            active_service = next(s for s in services if s.is_active)

            # Create RPC use case
            rpc_use_case = self.create_rpc_use_case(nats_adapter, metrics, logger)

            # Simulate failover scenario
            active_service.simulate_standby(True)

            # Schedule recovery
            async def recover():
                await asyncio.sleep(0.4)  # Simulate failover delay (within retry window)
                active_service.simulate_standby(False)

            recover_task = asyncio.create_task(recover())

            # Make RPC call
            request = RPCCallRequest(
                target_service="sticky-retry-test",
                method="process_with_failover",
                params={"request_id": "latency-test"},
                timeout=10.0,
                caller_service="test-client-service",
                caller_instance="test-client",
            )

            start_time = time.time()
            result = await rpc_use_case.execute(request)
            elapsed = time.time() - start_time

            await recover_task

            # Verify success
            assert result is not None

            # Verify latency metrics
            retry_metrics = metrics.get_metrics()
            failover_latency = retry_metrics.get(
                "rpc.sticky-retry-test.process_with_failover.failover.latency", 0
            )

            # Latency should be recorded and should be at least the failover delay
            assert failover_latency > 0.3  # Should be at least 300ms (close to recovery time)
            assert elapsed > 0.3  # Total time should also reflect the delay

            logger.info(
                f"Failover completed in {elapsed:.2f}s, tracked latency: {failover_latency:.2f}s"
            )

        finally:
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_exponential_backoff_with_jitter(self, nats_adapter, logger, metrics):
        """Test that exponential backoff with jitter is applied correctly."""
        services = []

        try:
            # Create a single service that will stay in standby
            service = await self.create_service_instance(nats_adapter, instance_id="backoff-test")
            services.append(service)
            await service.start()
            service.simulate_standby(True)  # Keep it simulating standby

            # Wait a bit
            await asyncio.sleep(2)

            # Create RPC use case with real logger for tracking
            test_logger = SimpleLogger("backoff-test-logger")

            rpc_use_case = self.create_rpc_use_case(nats_adapter, metrics, test_logger)

            # Create retry policy with predictable settings
            retry_policy = RetryPolicy(
                max_retries=3,
                initial_delay=0.1,  # 100ms
                backoff_multiplier=2.0,
                max_delay=1.0,
                jitter_factor=0.0,  # No jitter for predictable testing
            )

            # Make RPC call that will fail
            request = RPCCallRequest(
                target_service="sticky-retry-test",
                method="process_with_failover",
                params={"request_id": "backoff-test"},
                timeout=10.0,
                caller_service="test-client-service",
                caller_instance="test-client",
                retry_policy=retry_policy,
            )

            start_time = time.time()
            with pytest.raises(Exception):
                await rpc_use_case.execute(request)
            elapsed = time.time() - start_time

            # Expected delays: 0 (first attempt), 0.1, 0.2, 0.4 = total 0.7s minimum
            expected_min_time = 0.7
            assert elapsed >= expected_min_time, (
                f"Expected at least {expected_min_time}s, got {elapsed:.2f}s"
            )

            # Verify exponential backoff timing through elapsed time
            # Expected delays: 0 (first attempt), 0.1, 0.2, 0.4 = total 0.7s minimum
            # The actual elapsed time confirms exponential backoff was applied
            logger.info(f"Total elapsed time with backoff: {elapsed:.2f}s")

        finally:
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_no_retry_for_other_errors(self, nats_adapter, logger, metrics):
        """Test that non-NOT_ACTIVE errors are not retried."""
        services = []

        try:
            # Create a mock service that returns a different error
            class ErrorService(TestStickyServiceWithRetry):
                async def on_start(self):
                    @self.exclusive_rpc("fail_with_error")
                    async def fail_with_error(params: dict) -> dict:
                        return {
                            "success": False,
                            "error": "INTERNAL_ERROR",
                            "message": "Something went wrong",
                        }

            # Create and start the error service
            logger_instance = SimpleLogger("error-service")
            kv_store_registry = NATSKVStore(nats_adapter=nats_adapter)
            await kv_store_registry.connect("service_instances")
            kv_store_election = NATSKVStore(nats_adapter=nats_adapter)
            await kv_store_election.connect("sticky_active")

            config = SingleActiveConfig(
                service_name="error-test-service",
                instance_id="error-instance",
                group_id="error-test",
                leader_ttl_seconds=2,
                heartbeat_interval=5,
            )

            service = ErrorService(
                config=config,
                message_bus=nats_adapter,
                service_registry=KVServiceRegistry(
                    kv_store=kv_store_registry, logger=logger_instance
                ),
                election_repository=NatsKvElectionRepository(
                    kv_store=kv_store_election, logger=logger_instance
                ),
                logger=logger_instance,
                metrics=InMemoryMetrics(),
            )
            services.append(service)
            await service.start()
            await asyncio.sleep(2)

            # Create RPC use case
            rpc_use_case = self.create_rpc_use_case(nats_adapter, metrics, logger)

            # Make RPC call - should fail immediately without retry
            request = RPCCallRequest(
                target_service="error-test-service",
                method="fail_with_error",
                params={"request_id": "error-test"},
                timeout=5.0,
                caller_service="test-client-service",
                caller_instance="test-client",
            )

            with pytest.raises(Exception) as exc_info:
                await rpc_use_case.execute(request)

            # Should fail immediately without retries
            assert "INTERNAL_ERROR" in str(exc_info.value)

            # Verify no retry metrics for this error
            retry_metrics = metrics.get_metrics()
            not_active_retries = retry_metrics.get(
                "rpc.error-test-service.fail_with_error.retry.not_active", 0
            )
            assert not_active_retries == 0, "Should not retry for non-NOT_ACTIVE errors"

        finally:
            for service in services:
                await service.stop()
