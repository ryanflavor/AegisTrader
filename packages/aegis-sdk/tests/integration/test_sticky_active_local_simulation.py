"""Integration tests for sticky active pattern in local simulation.

Tests the leader election, failover, and request handling behavior
without requiring a full k8s cluster.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class StickyServiceForTesting(SingleActiveService):
    """Service implementation for testing sticky active pattern."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.process_count = 0
        self.last_processed = None
        self.is_running = True

    async def on_start(self):
        """Register RPC handlers."""

        @self.exclusive_rpc("process_request")
        async def process_request(params: dict) -> dict:
            """Process request - only active instance should handle this."""
            # This will only be called if the instance is active
            # The exclusive_rpc decorator handles the active check
            self.process_count += 1
            return {
                "instance_id": self.instance_id,
                "process_count": self.process_count,
                "request_id": params.get("request_id", "unknown"),
            }

        @self.rpc("get_status")
        async def get_status(params: dict) -> dict:
            """Get instance status - all instances can handle this."""
            return {
                "instance_id": self.instance_id,
                "is_active": self.is_active,
                "process_count": self.process_count,
                "group_id": self.group_id,
            }

    async def stop(self) -> None:
        """Stop the service and set is_running to False."""
        self.is_running = False
        await super().stop()


@pytest.mark.integration
class TestStickyActiveLocalSimulation:
    """Test sticky active pattern without k8s dependency."""

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create and connect NATS adapter."""
        # Register default dependencies
        from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults

        bootstrap_defaults()

        # Connect to NATS
        config = NATSConnectionConfig()
        adapter = NATSAdapter(config=config)
        await adapter.connect("nats://localhost:4222")

        # Create KV stores and ensure buckets exist (use underscores for bucket names)
        kv_store1 = NATSKVStore(nats_adapter=adapter)
        await kv_store1.connect("service_instances")

        kv_store2 = NATSKVStore(nats_adapter=adapter)
        await kv_store2.connect("sticky_active")

        yield adapter

        # Clean up KV store data after tests
        try:
            # Clear any election data
            kv_store_election = NATSKVStore(nats_adapter=adapter)
            await kv_store_election.connect("sticky_active")
            await kv_store_election.clear()

            # Clear any service registry data
            kv_store_registry = NATSKVStore(nats_adapter=adapter)
            await kv_store_registry.connect("service_instances")
            await kv_store_registry.clear()
        except Exception:
            pass  # Ignore errors during cleanup

        await adapter.disconnect()

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return SimpleLogger("test-sticky-local")

    async def create_service_instance(
        self,
        nats_adapter: NATSAdapter,
        service_name: str = "sticky-test-service",
        instance_id: str | None = None,
        group_id: str = "test-group",
    ) -> StickyServiceForTesting:
        """Create a test service instance with all required dependencies."""
        if instance_id is None:
            instance_id = f"sticky-service-{uuid.uuid4().hex[:8]}"

        logger = SimpleLogger(instance_id)

        # Create and connect KV store for service registry (use underscores for bucket names)
        kv_store_registry = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_registry.connect("service_instances")

        # Create and connect KV store for election (use underscores for bucket names)
        kv_store_election = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_election.connect("sticky_active")

        service_registry = KVServiceRegistry(kv_store=kv_store_registry, logger=logger)
        election_repository = NatsKvElectionRepository(kv_store=kv_store_election, logger=logger)
        metrics = InMemoryMetrics()

        # Create config object (leader_ttl must be less than heartbeat_interval)
        config = SingleActiveConfig(
            service_name=service_name,
            instance_id=instance_id,
            version="1.0.0",
            group_id=group_id,
            leader_ttl_seconds=5,
            registry_ttl=30,
            heartbeat_interval=10,  # Must be greater than leader_ttl
        )

        service = StickyServiceForTesting(
            config=config,
            message_bus=nats_adapter,
            service_registry=service_registry,
            election_repository=election_repository,
            logger=logger,
            metrics=metrics,
        )

        return service

    @pytest.mark.asyncio
    async def test_leader_election_with_three_instances(self, nats_adapter, logger):
        """Test that exactly one instance becomes leader when starting 3 instances."""
        services: list[StickyServiceForTesting] = []

        try:
            # Create and start 3 service instances
            logger.info("Creating 3 service instances...")

            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"sticky-service-pod-{i}"
                )
                await service.start()
                services.append(service)
                logger.info(f"Started service instance {i}: {service.instance_id}")

            # Wait for election to stabilize
            logger.info("Waiting for election to stabilize...")
            await asyncio.sleep(3)

            # Check that exactly one instance is active
            active_instances = [s for s in services if s.is_active]
            assert (
                len(active_instances) == 1
            ), f"Expected exactly 1 active instance, got {len(active_instances)}"

            leader = active_instances[0]
            logger.info(f"Leader elected: {leader.instance_id}")

            # Test that only the leader can process exclusive requests
            logger.info("Testing exclusive request handling...")

            # Give services a moment to register their RPC handlers
            await asyncio.sleep(1.0)

            # Make multiple RPC requests
            # Some may go to standby instances and return NOT_ACTIVE
            # This is expected behavior in sticky-active pattern
            from aegis_sdk.domain.models import RPCRequest

            active_responses = 0
            standby_responses = 0

            for i in range(10):  # Send more requests to test distribution
                try:
                    request = RPCRequest(
                        method="process_request",
                        params={"request_id": f"test-{i}"},
                        target="sticky-test-service",
                        timeout=2.0,
                    )
                    logger.info(f"Sending RPC request {i}")
                    rpc_response = await nats_adapter.call_rpc(request)
                except Exception as e:
                    logger.error(f"RPC call failed with exception: {e}")
                    raise

                # The RPC call itself should succeed
                assert rpc_response.success is True, f"RPC call {i} failed: {rpc_response.error}"

                # The result contains the ExclusiveRPCResponse as a dict
                exclusive_response = rpc_response.result

                if exclusive_response["success"]:
                    # Request was handled by active instance
                    active_responses += 1
                    handler_result = exclusive_response["result"]
                    assert handler_result["instance_id"] == leader.instance_id
                    logger.info(f"Request {i} processed by active instance")
                else:
                    # Request went to standby instance
                    standby_responses += 1
                    assert exclusive_response["error"] == "NOT_ACTIVE"
                    logger.info(f"Request {i} rejected by standby instance")

            # Verify we got both active and standby responses (load balancing is working)
            logger.info(
                f"Active responses: {active_responses}, Standby responses: {standby_responses}"
            )
            assert active_responses > 0, "Should have at least some active responses"
            assert (
                standby_responses > 0
            ), "Should have at least some standby responses (load balancing)"

            # Verify only the leader processed requests
            for service in services:
                if service.is_active:
                    assert (
                        service.process_count == active_responses
                    ), f"Active instance should have processed {active_responses} requests"
                else:
                    assert (
                        service.process_count == 0
                    ), "Standby instance should not have processed any requests"

        finally:
            # Clean up
            for service in services:
                if service.is_running:
                    await service.stop()
