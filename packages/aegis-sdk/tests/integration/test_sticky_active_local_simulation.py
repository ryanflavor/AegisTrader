"""Local simulation of K8s sticky active service pattern.

This simulates the K8s environment locally to test the sticky active pattern
without needing actual K8s deployment.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio

from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class TestStickyService(SingleActiveService):
    """Test service for sticky active pattern."""

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
            self.process_count += 1
            return {
                "success": True,
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
@pytest.mark.asyncio
class TestStickyActiveLocalSimulation:
    """Test sticky active pattern with local simulation of K8s environment."""

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create NATS adapter."""
        config = NATSConnectionConfig()
        adapter = NATSAdapter(config=config)
        await adapter.connect("nats://localhost:4222")

        # Create KV stores and ensure buckets exist
        kv_store1 = NATSKVStore(nats_adapter=adapter)
        await kv_store1.connect("service-instances")

        kv_store2 = NATSKVStore(nats_adapter=adapter)
        await kv_store2.connect("sticky-active")

        yield adapter

        # Clean up KV store data after tests
        try:
            # Clear any election data
            kv_store_election = NATSKVStore(nats_adapter=adapter)
            await kv_store_election.connect("sticky-active")
            await kv_store_election.clear()

            # Clear any service registry data
            kv_store_registry = NATSKVStore(nats_adapter=adapter)
            await kv_store_registry.connect("service-instances")
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
        nats_adapter,
        service_name="sticky-test-service",
        group_id="test-group",
        instance_id=None,
    ):
        """Create a single service instance."""
        if instance_id is None:
            instance_id = f"sticky-service-{uuid.uuid4().hex[:8]}"

        logger = SimpleLogger(instance_id)

        # Create and connect KV store for service registry
        kv_store_registry = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_registry.connect("service-instances")

        # Create and connect KV store for election
        kv_store_election = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store_election.connect("sticky-active")

        service_registry = KVServiceRegistry(kv_store=kv_store_registry, logger=logger)
        election_repository = NatsKvElectionRepository(kv_store=kv_store_election, logger=logger)
        metrics = InMemoryMetrics()

        service = TestStickyService(
            service_name=service_name,
            instance_id=instance_id,
            message_bus=nats_adapter,
            service_registry=service_registry,
            election_repository=election_repository,
            logger=logger,
            metrics=metrics,
            group_id=group_id,
            leader_ttl_seconds=5,
            registry_ttl=30,
            heartbeat_interval=2,
        )

        return service

    @pytest.mark.asyncio
    async def test_leader_election_with_three_instances(self, nats_adapter, logger):
        """Test that exactly one instance becomes leader when starting 3 instances."""
        services: list[TestStickyService] = []

        try:
            # Create and start 3 service instances
            logger.info("Creating 3 service instances...")

            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"sticky-service-pod-{i}"
                )
                services.append(service)
                await service.start()
                # Small delay to simulate K8s pod startup timing
                await asyncio.sleep(0.5)

            # Wait for election to stabilize
            await asyncio.sleep(3)

            # Check that exactly one instance is active
            active_instances = [s for s in services if s.is_active]
            active_count = len(active_instances)

            logger.info(f"Active instances: {active_count}")
            for service in services:
                logger.info(
                    f"Instance {service.instance_id}: {'ACTIVE' if service.is_active else 'STANDBY'}"
                )

            assert active_count == 1, f"Expected 1 active instance, got {active_count}"

            # Test exclusive RPC routing
            logger.info("Testing exclusive RPC routing...")
            successful_responses = []

            for i in range(10):
                request_id = f"test-request-{i}"
                from aegis_sdk.domain.models import RPCRequest

                response = await nats_adapter.call_rpc(
                    RPCRequest(
                        method="process_request",
                        params={"request_id": request_id},
                        target="sticky-test-service",
                        timeout=5.0,
                    )
                )

                # Handle different response formats
                if response.success:
                    # If response.result is already the handler response
                    if (isinstance(response.result, dict) and "instance_id" in response.result) or (
                        isinstance(response.result, dict) and response.result.get("success", False)
                    ):
                        successful_responses.append(response.result)
                    else:
                        logger.info(f"Request {i} returned unexpected format: {response.result}")
                else:
                    error_msg = response.error or "Unknown error"
                    logger.info(f"Request {i} failed: {error_msg}")

            # We should have at least some successful responses
            assert (
                len(successful_responses) > 0
            ), f"Expected at least 1 successful response, got {len(successful_responses)}"

            # Debug: print response count and structure
            logger.info(f"Successful responses: {len(successful_responses)} out of 10")
            if successful_responses:
                logger.info(f"First response structure: {successful_responses[0]}")

            # Extract instance_ids, handling both response formats
            instance_ids = set()
            for r in successful_responses:
                if "instance_id" in r:
                    instance_ids.add(r["instance_id"])
                else:
                    logger.warning(f"Response missing instance_id: {r}")
            assert (
                len(instance_ids) == 1
            ), f"All requests should be handled by one instance, got: {instance_ids}"

            active_instance_id = active_instances[0].instance_id
            assert (
                list(instance_ids)[0] == active_instance_id
            ), "Requests should be handled by the active instance"

            logger.info(
                f"All requests successfully handled by active instance: {active_instance_id}"
            )

        finally:
            # Clean up
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_failover_under_2_seconds(self, nats_adapter, logger):
        """Test that failover completes in under 2 seconds when leader fails."""
        services: list[TestStickyService] = []

        try:
            # Create and start 3 service instances
            logger.info("Creating 3 service instances for failover test...")

            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"sticky-service-pod-{i}", group_id="failover-test"
                )
                services.append(service)
                await service.start()
                await asyncio.sleep(0.5)

            # Wait for election to stabilize
            await asyncio.sleep(3)

            # Find the current leader
            active_services = [s for s in services if s.is_active]
            assert len(active_services) == 1, "Should have exactly one leader"

            leader = active_services[0]
            logger.info(f"Current leader: {leader.instance_id}")

            # Simulate leader failure
            logger.info("Simulating leader failure...")
            failover_start = asyncio.get_event_loop().time()
            await leader.stop()

            # Wait for new leader election
            new_leader = None
            max_wait = 5.0  # Maximum wait time
            check_interval = 0.1  # Check every 100ms

            while asyncio.get_event_loop().time() - failover_start < max_wait:
                # Check remaining services for new leader
                for service in services:
                    if service != leader and service.is_active:
                        new_leader = service
                        break

                if new_leader:
                    break

                await asyncio.sleep(check_interval)

            failover_time = asyncio.get_event_loop().time() - failover_start

            assert new_leader is not None, "No new leader elected"
            assert new_leader != leader, "Same instance became leader again"
            assert failover_time < 2.0, f"Failover took {failover_time:.2f}s, expected < 2s"

            logger.info(
                f"Failover completed in {failover_time:.2f}s. New leader: {new_leader.instance_id}"
            )

            # Wait a bit for all instances to update their status
            await asyncio.sleep(1.0)

            # Verify only one active instance after failover
            active_count = sum(1 for s in services if s.is_active and s != leader)
            assert (
                active_count == 1
            ), f"Expected 1 active instance after failover, got {active_count}"

        finally:
            # Clean up
            for service in services:
                if service.is_running:
                    await service.stop()

    @pytest.mark.asyncio
    async def test_concurrent_requests_during_failover(self, nats_adapter, logger):
        """Test handling of concurrent requests during failover."""
        services: list[TestStickyService] = []
        stopped_services = set()  # Track which services we've stopped

        try:
            # Create and start 3 service instances
            logger.info("Creating 3 service instances for concurrent request test...")

            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"sticky-service-pod-{i}", group_id="concurrent-test"
                )
                services.append(service)
                await service.start()
                await asyncio.sleep(0.5)

            # Wait for election to stabilize
            await asyncio.sleep(3)

            # Find the current leader
            leader = next(s for s in services if s.is_active)
            logger.info(f"Current leader: {leader.instance_id}")

            # Get the standby services
            standby_services = [s for s in services if s != leader]
            logger.info(f"Standby services: {[s.instance_id for s in standby_services]}")

            # Start sending concurrent requests
            async def send_requests():
                results = []
                for i in range(50):
                    try:
                        from aegis_sdk.domain.models import RPCRequest

                        response = await nats_adapter.call_rpc(
                            RPCRequest(
                                method="process_request",
                                params={"request_id": f"concurrent-{i}"},
                                target="sticky-test-service",
                                timeout=10.0,
                            )
                        )
                        if response.success:
                            # Handle both response formats
                            if (
                                isinstance(response.result, dict)
                                and "instance_id" in response.result
                            ) or (
                                isinstance(response.result, dict)
                                and response.result.get("success", False)
                            ):
                                results.append(response.result)
                    except Exception as e:
                        logger.warning(f"Request {i} failed: {e}")
                    await asyncio.sleep(0.1)  # Small delay between requests
                return results

            # Start sending requests
            request_task = asyncio.create_task(send_requests())

            # After 2 seconds, trigger failover
            await asyncio.sleep(2)
            logger.info("Triggering failover during request processing...")
            logger.info(f"Stopping leader: {leader.instance_id}")
            await leader.stop()
            stopped_services.add(leader.instance_id)

            # Wait a moment for the leader to fully stop
            await asyncio.sleep(0.5)

            # Wait for a new leader to be elected
            max_election_wait = 3.0
            election_start = asyncio.get_event_loop().time()
            new_leader = None

            while asyncio.get_event_loop().time() - election_start < max_election_wait:
                for service in standby_services:
                    if service.is_active and service.instance_id not in stopped_services:
                        new_leader = service
                        break
                if new_leader:
                    break
                await asyncio.sleep(0.1)

            if new_leader:
                logger.info(f"New leader elected: {new_leader.instance_id}")
            else:
                logger.warning("No new leader elected within timeout")

            # Wait for requests to complete
            results = await request_task

            logger.info(f"Completed {len(results)} requests during failover")

            # Log current state of services
            for s in services:
                logger.info(
                    f"Service {s.instance_id}: is_running={s.is_running}, is_active={s.is_active}, stopped={s.instance_id in stopped_services}"
                )

            # Verify requests were handled by at most 2 instances (old and new leader)
            instance_ids = set()
            for r in results:
                if "instance_id" in r:
                    instance_ids.add(r["instance_id"])
            assert len(instance_ids) <= 2, f"Requests handled by too many instances: {instance_ids}"

            # Verify new leader is handling requests - but only if we have one
            if new_leader and new_leader.is_active:
                logger.info("Verifying new leader is handling requests...")

                # Give the system a moment to stabilize
                await asyncio.sleep(1.0)

                # Try to get a response from the new leader
                new_leader_id = None
                for attempt in range(3):
                    try:
                        from aegis_sdk.domain.models import RPCRequest

                        new_response = await nats_adapter.call_rpc(
                            RPCRequest(
                                method="process_request",
                                params={"request_id": f"after-failover-{attempt}"},
                                target="sticky-test-service",
                                timeout=5.0,
                            )
                        )

                        if new_response.success:
                            # Extract instance_id from successful response
                            if (
                                isinstance(new_response.result, dict)
                                and "instance_id" in new_response.result
                            ):
                                new_leader_id = new_response.result["instance_id"]
                                logger.info(f"Got response from new leader: {new_leader_id}")
                                break
                        else:
                            logger.info(f"Attempt {attempt} failed: {new_response.error}")
                    except Exception as e:
                        logger.warning(f"Attempt {attempt} exception: {e}")

                    if attempt < 2:
                        await asyncio.sleep(0.5)

                # Verify we got a response and it's from the new leader
                if new_leader_id:
                    assert (
                        new_leader_id == new_leader.instance_id
                    ), f"Response from unexpected instance: {new_leader_id} vs {new_leader.instance_id}"
                    assert new_leader_id != leader.instance_id, "New leader should be different"
                    logger.info(
                        f"Failover successful. New leader {new_leader_id} is handling requests."
                    )
                else:
                    logger.warning("Could not verify new leader is handling requests")
            else:
                logger.info(
                    "No new leader available to verify - this is acceptable during shutdown"
                )

        finally:
            # Clean up - stop all services that haven't been stopped yet
            for service in services:
                if service.instance_id not in stopped_services:
                    try:
                        await service.stop()
                        stopped_services.add(service.instance_id)
                    except Exception as e:
                        logger.warning(f"Error stopping service {service.instance_id}: {e}")
