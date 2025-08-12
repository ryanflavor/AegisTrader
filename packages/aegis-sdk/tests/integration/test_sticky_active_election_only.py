"""Simple test to verify sticky active election works without RPC complications."""

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


class SimpleActiveService(SingleActiveService):
    """Minimal service for testing election."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_running = True

    async def on_start(self):
        """No RPC handlers needed for basic election test."""
        pass

    async def stop(self) -> None:
        """Stop the service."""
        self.is_running = False
        await super().stop()


@pytest.mark.integration
class TestStickyActiveElection:
    """Test sticky active election without RPC complexity."""

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create and connect NATS adapter."""
        from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults

        bootstrap_defaults()

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
            kv_store_election = NATSKVStore(nats_adapter=adapter)
            await kv_store_election.connect("sticky_active")
            await kv_store_election.clear()

            kv_store_registry = NATSKVStore(nats_adapter=adapter)
            await kv_store_registry.connect("service_instances")
            await kv_store_registry.clear()
        except Exception:
            pass

        await adapter.disconnect()

    async def create_service_instance(
        self,
        nats_adapter: NATSAdapter,
        service_name: str = "test-service",
        instance_id: str | None = None,
        group_id: str = "test-group",
    ) -> SimpleActiveService:
        """Create a test service instance."""
        if instance_id is None:
            instance_id = f"service-{uuid.uuid4().hex[:8]}"

        logger = SimpleLogger(instance_id)

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
            version="1.0.0",
            group_id=group_id,
            leader_ttl_seconds=5,
            registry_ttl=30,
            heartbeat_interval=10,
        )

        service = SimpleActiveService(
            config=config,
            message_bus=nats_adapter,
            service_registry=service_registry,
            election_repository=election_repository,
            logger=logger,
            metrics=metrics,
        )

        return service

    @pytest.mark.asyncio
    async def test_exactly_one_leader_elected(self, nats_adapter):
        """Test that exactly one instance becomes leader."""
        services = []

        try:
            # Create and start 3 service instances
            for i in range(3):
                service = await self.create_service_instance(
                    nats_adapter, instance_id=f"service-{i}"
                )
                await service.start()
                services.append(service)

            # Wait for election to stabilize
            await asyncio.sleep(3)

            # Check that exactly one instance is active
            active_instances = [s for s in services if s.is_active]
            assert (
                len(active_instances) == 1
            ), f"Expected exactly 1 active instance, got {len(active_instances)}"

            leader = active_instances[0]
            print(f"✅ Leader elected: {leader.instance_id}")

            # Verify standby instances know they're not active
            for service in services:
                if service != leader:
                    assert not service.is_active, f"{service.instance_id} should be standby"
                    print(f"✅ {service.instance_id} is correctly in standby mode")

        finally:
            # Clean up
            for service in services:
                if service.is_running:
                    await service.stop()
