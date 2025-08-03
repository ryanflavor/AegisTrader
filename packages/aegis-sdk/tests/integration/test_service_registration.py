"""Integration tests for service registration with NATS KV Store."""

import asyncio
import os

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

# Skip if integration tests are disabled
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "").lower() == "true",
    reason="Integration tests disabled",
)


@pytest.mark.asyncio
class TestServiceRegistrationIntegration:
    """Integration tests for service registration with real NATS."""

    async def test_service_registration_full_flow(self):
        """Test complete service registration flow with NATS."""
        # Use K8s environment URL if available, otherwise use localhost
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        # Create NATS adapter
        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        # Create KV store
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        # Create service with registration enabled
        service = Service(
            "test-service",
            adapter,
            service_registry=registry,
            registry_ttl=30,
            heartbeat_interval=5,
            enable_registration=True,
        )

        try:
            # Start service (should register)
            await service.start()

            # Verify registration through registry
            instance = await registry.get_instance("test-service", service.instance_id)

            assert instance is not None
            assert instance.service_name == "test-service"
            assert instance.instance_id == service.instance_id
            assert instance.status == "ACTIVE"
            assert instance.version == "1.0.0"
            assert instance.is_healthy()

            # Test status update
            service.set_status("UNHEALTHY")
            await asyncio.sleep(0.5)  # Give time for async update

            # Verify status was updated
            updated_instance = await registry.get_instance("test-service", service.instance_id)
            assert updated_instance.status == "UNHEALTHY"
            assert not updated_instance.is_healthy()

            # Stop service (should deregister)
            await service.stop()

            # Verify deregistration
            final_instance = await registry.get_instance("test-service", service.instance_id)
            assert final_instance is None

        finally:
            # Cleanup
            if hasattr(service, "_heartbeat_task") and service._heartbeat_task:
                service._heartbeat_task.cancel()
            await adapter.disconnect()

    async def test_multiple_service_instances(self):
        """Test multiple instances of same service can register."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        # Create shared NATS adapter
        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        # Create shared KV store
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        # Create two service instances
        service1 = Service(
            "multi-service",
            adapter,
            service_registry=registry,
            instance_id="multi-service-instance1",
            enable_registration=True,
        )

        service2 = Service(
            "multi-service",
            adapter,
            service_registry=registry,
            instance_id="multi-service-instance2",
            enable_registration=True,
        )

        try:
            # Start both services
            await service1.start()
            await service2.start()

            # Verify both are registered through registry
            instances = await registry.list_instances("multi-service")

            assert len(instances) >= 2
            instance_ids = [inst.instance_id for inst in instances]
            assert "multi-service-instance1" in instance_ids
            assert "multi-service-instance2" in instance_ids

            # Verify each instance individually
            instance1 = await registry.get_instance("multi-service", "multi-service-instance1")
            instance2 = await registry.get_instance("multi-service", "multi-service-instance2")

            assert instance1 is not None
            assert instance2 is not None
            assert instance1.instance_id == "multi-service-instance1"
            assert instance2.instance_id == "multi-service-instance2"

        finally:
            # Cleanup
            await service1.stop()
            await service2.stop()
            await adapter.disconnect()

    async def test_ttl_expiration(self):
        """Test that service registration expires after TTL."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        # Use a separate bucket for TTL testing to avoid conflicts
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry-ttl-test", enable_ttl=True)  # Enable TTL support

        # Create registry
        registry = KVServiceRegistry(kv_store)

        service = Service(
            "ttl-test-service",
            adapter,
            service_registry=registry,
            registry_ttl=5,  # 5 seconds TTL
            heartbeat_interval=10,  # Longer than TTL to test expiration
            enable_registration=True,
        )

        try:
            # Start service
            await service.start()

            # Verify initial registration
            instance = await registry.get_instance("ttl-test-service", service.instance_id)
            assert instance is not None

            # Stop heartbeat to simulate failure
            if service._heartbeat_task:
                service._heartbeat_task.cancel()

            # Wait for TTL to expire (add buffer)
            await asyncio.sleep(7)

            # Verify entry has expired
            expired_instance = await registry.get_instance("ttl-test-service", service.instance_id)
            assert expired_instance is None

        finally:
            # Cleanup
            await service.stop()
            await adapter.disconnect()

    async def test_heartbeat_keeps_registration_alive(self):
        """Test that heartbeat prevents TTL expiration."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        # Use a separate bucket for TTL testing to avoid conflicts
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry-ttl-test", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        service = Service(
            "heartbeat-test-service",
            adapter,
            service_registry=registry,
            registry_ttl=5,  # 5 seconds TTL
            heartbeat_interval=2,  # Heartbeat every 2 seconds
            enable_registration=True,
        )

        try:
            # Start service
            await service.start()

            # Verify initial registration
            initial_instance = await registry.get_instance(
                "heartbeat-test-service", service.instance_id
            )
            assert initial_instance is not None
            initial_heartbeat = initial_instance.last_heartbeat

            # Wait longer than TTL but less than heartbeat cycles
            await asyncio.sleep(8)

            # Verify entry still exists (heartbeat kept it alive)
            current_instance = await registry.get_instance(
                "heartbeat-test-service", service.instance_id
            )
            assert current_instance is not None
            assert current_instance.last_heartbeat != initial_heartbeat

        finally:
            # Cleanup
            await service.stop()
            await adapter.disconnect()

    async def test_re_registration_on_lost_entry(self):
        """Test service re-registers if KV entry is lost."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        service = Service(
            "reregister-test-service",
            adapter,
            service_registry=registry,
            heartbeat_interval=2,
            enable_registration=True,
        )

        try:
            # Start service
            await service.start()

            # Verify initial registration
            instance = await registry.get_instance("reregister-test-service", service.instance_id)
            assert instance is not None

            # Manually delete the entry (simulate loss)
            await registry.deregister("reregister-test-service", service.instance_id)

            # Wait for heartbeat to detect and re-register
            await asyncio.sleep(3)

            # Verify re-registration
            new_instance = await registry.get_instance(
                "reregister-test-service", service.instance_id
            )
            assert new_instance is not None
            assert new_instance.service_name == "reregister-test-service"

        finally:
            # Cleanup
            await service.stop()
            await adapter.disconnect()

    async def test_concurrent_heartbeat_updates(self):
        """Test concurrent heartbeat updates don't cause issues."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        service = Service(
            "concurrent-test-service",
            adapter,
            service_registry=registry,
            heartbeat_interval=0.5,  # Fast heartbeat
            enable_registration=True,
        )

        try:
            # Start service
            await service.start()

            # Trigger multiple concurrent status updates
            tasks = []
            statuses = ["ACTIVE", "UNHEALTHY", "STANDBY", "ACTIVE"]
            for status in statuses:
                service.set_status(status)
                tasks.append(asyncio.create_task(asyncio.sleep(0.1)))

            await asyncio.gather(*tasks)

            # Verify final state is consistent
            final_instance = await registry.get_instance(
                "concurrent-test-service", service.instance_id
            )
            assert final_instance is not None
            assert final_instance.status in statuses

        finally:
            # Cleanup
            await service.stop()
            await adapter.disconnect()

    async def test_service_discovery_pattern(self):
        """Test service discovery using key prefix pattern."""
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

        adapter = NATSAdapter()
        await adapter.connect([nats_url])

        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("service-registry", enable_ttl=True)

        # Create registry
        registry = KVServiceRegistry(kv_store)

        # Create services with different names
        services = []
        service_names = ["discovery-service-a", "discovery-service-b", "other-service"]

        try:
            for name in service_names:
                service = Service(
                    name,
                    adapter,
                    service_registry=registry,
                    enable_registration=True,
                )
                await service.start()
                services.append(service)

            # Discover all services using registry
            all_services = await registry.list_all_services()

            # Check discovery services
            discovery_services = [
                name for name in all_services if name.startswith("discovery-service")
            ]

            assert len(discovery_services) == 2
            assert "discovery-service-a" in discovery_services
            assert "discovery-service-b" in discovery_services
            assert "other-service" in all_services

        finally:
            # Cleanup
            for service in services:
                await service.stop()
            await adapter.disconnect()
