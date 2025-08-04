"""
Example fix for service discovery integration test following TDD and hexagonal architecture.

This demonstrates how to refactor the test to use the new Service API with proper
port abstractions instead of direct infrastructure dependencies.
"""

import asyncio

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.infrastructure import (
    BasicServiceDiscovery,
    KVServiceRegistry,
    NATSAdapter,
    NATSKVStore,
)
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class TestServiceDiscoveryK8sIntegrationFixed:
    """Fixed version following hexagonal architecture."""

    @pytest.fixture
    async def infrastructure_setup(self):
        """Set up infrastructure adapters."""
        # Create NATS adapter (infrastructure layer)
        nats_adapter = NATSAdapter()
        await nats_adapter.connect(["nats://localhost:4222"])

        # Create KV store (infrastructure layer)
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test-service-discovery-k8s")
        await kv_store.clear()

        yield {
            "nats_adapter": nats_adapter,
            "kv_store": kv_store,
        }

        # Cleanup
        await kv_store.clear()
        await kv_store.disconnect()
        await nats_adapter.disconnect()

    @pytest.fixture
    async def port_implementations(self, infrastructure_setup):
        """Create port implementations from infrastructure."""
        nats_adapter = infrastructure_setup["nats_adapter"]
        kv_store = infrastructure_setup["kv_store"]

        # Create port implementations
        message_bus = nats_adapter  # NATSAdapter implements MessageBusPort
        service_registry = KVServiceRegistry(kv_store)
        service_discovery = BasicServiceDiscovery(service_registry)
        logger = SimpleLogger()

        return {
            "message_bus": message_bus,
            "service_registry": service_registry,
            "service_discovery": service_discovery,
            "logger": logger,
        }

    @pytest.fixture
    async def test_service_a_fixed(self, port_implementations):
        """Create test service A using proper port abstractions."""
        instances = []

        for i in range(3):
            # Create service with port abstractions (not infrastructure)
            service = Service(
                service_name="test-service-a",  # Changed from 'name'
                message_bus=port_implementations["message_bus"],  # Port, not adapter
                version="1.0.0",
                service_registry=port_implementations["service_registry"],  # Explicit registry
                service_discovery=port_implementations["service_discovery"],  # Explicit discovery
                logger=port_implementations["logger"],
                instance_id=f"service-a-{i + 1}",  # Explicit instance ID
            )

            # Add RPC handler
            @service.rpc("echo")
            async def echo_handler(params, _service=service):
                return {
                    "message": params.get("message"),
                    "instance": _service.instance_id,  # Use public property
                }

            await service.start()
            instances.append(service)

        yield instances

        # Cleanup
        for service in instances:
            await service.stop()

    async def test_full_discovery_flow_fixed(
        self,
        port_implementations,
        test_service_a_fixed,
    ):
        """Test discovery using port abstractions."""
        discovery = port_implementations["service_discovery"]

        # Wait for services to register
        await asyncio.sleep(1.0)

        # Discover service A instances
        instances_a = await discovery.discover_instances("test-service-a")
        assert len(instances_a) == 3
        assert all(i.service_name == "test-service-a" for i in instances_a)
        assert all(i.status == "ACTIVE" for i in instances_a)

        # Test selection strategies
        instance = await discovery.select_instance("test-service-a", strategy="round_robin")
        assert instance is not None
        assert instance.service_name == "test-service-a"


# Alternative approach using dependency injection pattern
class ServiceBuilder:
    """Builder pattern for creating services in tests."""

    def __init__(self, port_implementations: dict):
        self.ports = port_implementations
        self.instance_counter = 0

    def build_service(
        self,
        service_name: str,
        version: str = "1.0.0",
        instance_id: str | None = None,
    ) -> Service:
        """Build a service with all required dependencies."""
        if not instance_id:
            self.instance_counter += 1
            instance_id = f"{service_name}-{self.instance_counter}"

        return Service(
            service_name=service_name,
            message_bus=self.ports["message_bus"],
            version=version,
            service_registry=self.ports["service_registry"],
            service_discovery=self.ports["service_discovery"],
            logger=self.ports["logger"],
            instance_id=instance_id,
        )


# Example of how to update the old test fixture
def migrate_old_service_creation():
    """Migration guide from old to new API."""

    # OLD WAY (infrastructure coupling):
    """
    service = Service(
        name="test-service",
        adapter=nats_adapter,      # ❌ Infrastructure
        kv_store=kv_store,         # ❌ Infrastructure
        logger=logger,
        metrics=metrics,
    )
    """

    # NEW WAY (port abstraction):
    """
    # Step 1: Create port implementations
    message_bus = nats_adapter  # Adapter implements port
    service_registry = KVServiceRegistry(kv_store)
    service_discovery = BasicServiceDiscovery(service_registry)

    # Step 2: Create service with ports
    service = Service(
        service_name="test-service",
        message_bus=message_bus,        # ✅ Port abstraction
        service_registry=service_registry,    # ✅ Port abstraction
        service_discovery=service_discovery,  # ✅ Port abstraction
        logger=logger,
    )
    """
    pass
