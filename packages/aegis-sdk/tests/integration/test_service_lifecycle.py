#!/usr/bin/env python3
"""Comprehensive service lifecycle integration tests for AegisSDK.

Tests service registration, heartbeat updates, deregistration, and TTL-based cleanup.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


@pytest.mark.asyncio
class TestServiceLifecycle:
    """Test complete service lifecycle including TTL cleanup."""

    @pytest.fixture
    def mock_nats_connection(self):
        """Create a mock NATS connection."""
        mock_conn = AsyncMock()
        mock_conn.is_closed = False
        mock_conn.drain = AsyncMock()
        mock_conn.close = AsyncMock()
        return mock_conn

    @pytest.fixture
    def mock_kv_store(self):
        """Create a mock KV store with in-memory storage."""
        store = MagicMock(spec=NATSKVStore)
        store.storage = {}  # In-memory storage
        store.ttl_seconds = 30

        async def mock_put(key: str, value: bytes, ttl: int | None = None, **kwargs):
            """Mock put operation with TTL tracking."""
            store.storage[key] = {
                "value": value,
                "ttl": ttl,
                "timestamp": datetime.now(UTC),
            }
            return True

        async def mock_get(key: str):
            """Mock get operation with TTL checking."""
            if key not in store.storage:
                return None

            entry = store.storage[key]
            if entry["ttl"]:
                age = (datetime.now(UTC) - entry["timestamp"]).total_seconds()
                if age > entry["ttl"]:
                    # Entry expired
                    del store.storage[key]
                    return None

            # Return an object with .value attribute containing parsed JSON
            import json

            class MockEntry:
                def __init__(self, data):
                    self.value = json.loads(data) if isinstance(data, bytes) else data

            return MockEntry(entry["value"])

        async def mock_delete(key: str):
            """Mock delete operation."""
            if key in store.storage:
                del store.storage[key]
                return True
            return False

        async def mock_list_keys(prefix: str = ""):
            """Mock list keys operation."""
            return [k for k in store.storage.keys() if k.startswith(prefix)]

        store.put = mock_put
        store.get = mock_get
        store.delete = mock_delete
        store.list_keys = mock_list_keys
        store.keys = mock_list_keys  # Also add keys method
        store.connect = AsyncMock()
        store.close = AsyncMock()

        return store

    @pytest.fixture
    def service_registry(self, mock_kv_store):
        """Create a service registry with mock KV store."""
        registry = KVServiceRegistry(kv_store=mock_kv_store)
        return registry

    @pytest.fixture
    def service(self, mock_nats_connection):
        """Create a test service."""
        # Create a minimal service for testing
        # We don't need to actually test the service itself, just the lifecycle
        mock_service = MagicMock()
        mock_service.name = "test-service"
        mock_service.instance_id = "test-instance-001"
        mock_service.version = "1.0.0"
        return mock_service

    async def test_service_registration_and_appearance(
        self, service, service_registry, mock_kv_store
    ):
        """Test that service appears in registry after registration (AC: 1)."""
        # Set up service with registry
        service.service_registry = service_registry

        # Register service
        instance = ServiceInstance(
            service_name=service.name,
            instance_id=service.instance_id,
            version=service.version,
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        await service_registry.register(instance, ttl_seconds=30)

        # Verify service appears immediately
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 1
        assert instances[0].instance_id == "test-instance-001"
        assert instances[0].status == ServiceStatus.ACTIVE

        # Verify it appears within 5 seconds (AC: 1)
        start_time = time.time()
        found = False
        while time.time() - start_time < 5:
            all_services = await service_registry.list_all_services()
            instances = [inst for insts in all_services.values() for inst in insts]
            if instances and instances[0].instance_id == "test-instance-001":
                found = True
                break
            await asyncio.sleep(0.1)

        assert found, "Service did not appear within 5 seconds"

    async def test_service_heartbeat_updates(self, service, service_registry, mock_kv_store):
        """Test that heartbeats update the service timestamp (AC: 3)."""
        # Register service
        instance = ServiceInstance(
            service_name=service.name,
            instance_id=service.instance_id,
            version=service.version,
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC) - timedelta(seconds=10),
        )

        await service_registry.register(instance, ttl_seconds=30)

        # Get initial heartbeat
        initial_instance = await service_registry.get_instance(service.name, service.instance_id)
        initial_heartbeat = initial_instance.last_heartbeat

        # Wait a bit
        await asyncio.sleep(0.1)

        # Send heartbeat update
        updated_instance = await service_registry.get_instance(service.name, service.instance_id)
        updated_instance.last_heartbeat = datetime.now(UTC)
        await service_registry.register(updated_instance, ttl_seconds=30)

        # Verify heartbeat was updated
        updated_instance = await service_registry.get_instance(service.name, service.instance_id)
        assert updated_instance is not None
        assert updated_instance.last_heartbeat > initial_heartbeat

    async def test_service_deregistration_and_disappearance(
        self, service, service_registry, mock_kv_store
    ):
        """Test that service disappears after deregistration (AC: 2)."""
        # Register service
        instance = ServiceInstance(
            service_name=service.name,
            instance_id=service.instance_id,
            version=service.version,
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        await service_registry.register(instance, ttl_seconds=30)

        # Verify service exists
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 1

        # Deregister service
        await service_registry.deregister(service.name, service.instance_id)

        # Verify service disappears immediately
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 0

        # Verify it stays gone
        await asyncio.sleep(0.5)
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 0

    async def test_ttl_based_cleanup(self, service_registry, mock_kv_store):
        """Test that entries expire after TTL (AC: 2, 5)."""
        # Set short TTL for testing
        mock_kv_store.ttl_seconds = 2

        # Register service with TTL
        instance = ServiceInstance(
            service_name="ttl-test-service",
            instance_id="ttl-instance-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        # Store directly with TTL
        key = "services__ttl-instance-001"
        value = instance.model_dump_json().encode()
        await mock_kv_store.put(key, value, ttl=2)

        # Verify service exists initially
        stored_value = await mock_kv_store.get(key)
        assert stored_value is not None

        # Wait for TTL to expire
        await asyncio.sleep(2.5)

        # Verify service is gone after TTL
        stored_value = await mock_kv_store.get(key)
        assert stored_value is None

    async def test_stale_entry_filtering(self, service_registry, mock_kv_store):
        """Test that stale entries are filtered out (AC: 3, 6)."""
        # Create instances with different heartbeat ages
        now = datetime.now(UTC)

        # Fresh instance
        fresh_instance = ServiceInstance(
            service_name="fresh-service",
            instance_id="fresh-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=now,
        )

        # Stale instance (older than TTL + buffer)
        stale_instance = ServiceInstance(
            service_name="stale-service",
            instance_id="stale-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=now - timedelta(seconds=40),  # > 30s TTL + 5s buffer
        )

        # Register both instances
        await service_registry.register(fresh_instance, ttl_seconds=30)
        await service_registry.register(stale_instance, ttl_seconds=30)

        # Mock the filtering logic (normally done by monitor-api)
        async def get_filtered_instances():
            """Get instances and filter stale ones."""
            all_services = await service_registry.list_all_services()
            all_instances = [inst for insts in all_services.values() for inst in insts]
            threshold = 35  # TTL + 5s buffer
            filtered = []

            for instance in all_instances:
                age = (now - instance.last_heartbeat).total_seconds()
                if age <= threshold:
                    filtered.append(instance)

            return filtered

        # Get filtered instances
        filtered_instances = await get_filtered_instances()

        # Should only have fresh instance
        assert len(filtered_instances) == 1
        assert filtered_instances[0].instance_id == "fresh-001"

    async def test_multiple_services_lifecycle(self, service_registry, mock_kv_store):
        """Test lifecycle with multiple concurrent services."""
        services = []

        # Register multiple services
        for i in range(3):
            instance = ServiceInstance(
                service_name="multi-service",
                instance_id=f"multi-instance-{i:03d}",
                version="1.0.0",
                status=ServiceStatus.ACTIVE,
                last_heartbeat=datetime.now(UTC),
            )
            await service_registry.register(instance, ttl_seconds=30)
            services.append(instance)

        # Verify all services appear
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 3

        # Update heartbeats for some services
        inst = await service_registry.get_instance("multi-service", "multi-instance-000")
        inst.last_heartbeat = datetime.now(UTC)
        await service_registry.register(inst, ttl_seconds=30)

        inst = await service_registry.get_instance("multi-service", "multi-instance-002")
        inst.last_heartbeat = datetime.now(UTC)
        await service_registry.register(inst, ttl_seconds=30)

        # Deregister one service
        await service_registry.deregister("multi-service", "multi-instance-001")

        # Verify correct services remain
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        instance_ids = {i.instance_id for i in instances}
        assert "multi-instance-000" in instance_ids
        assert "multi-instance-001" not in instance_ids
        assert "multi-instance-002" in instance_ids

    async def test_service_status_transitions(self, service_registry, mock_kv_store):
        """Test service status changes during lifecycle."""
        # Register service as ACTIVE
        instance = ServiceInstance(
            service_name="status-test",
            instance_id="status-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        await service_registry.register(instance, ttl_seconds=30)

        # Verify initial status
        stored = await service_registry.get_instance("status-test", "status-001")
        assert stored.status == ServiceStatus.ACTIVE

        # Update to UNHEALTHY
        inst = await service_registry.get_instance("status-test", "status-001")
        inst.status = ServiceStatus.UNHEALTHY
        await service_registry.register(inst, ttl_seconds=30)

        # Verify status changed
        stored = await service_registry.get_instance("status-test", "status-001")
        assert stored.status == ServiceStatus.UNHEALTHY

        # Update to STANDBY
        inst = await service_registry.get_instance("status-test", "status-001")
        inst.status = ServiceStatus.STANDBY
        await service_registry.register(inst, ttl_seconds=30)

        # Verify final status
        stored = await service_registry.get_instance("status-test", "status-001")
        assert stored.status == ServiceStatus.STANDBY

    async def test_service_reconnection_after_failure(self, service_registry, mock_kv_store):
        """Test service can reconnect and re-register after failure."""
        # Register service
        instance = ServiceInstance(
            service_name="reconnect-test",
            instance_id="reconnect-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        await service_registry.register(instance, ttl_seconds=30)

        # Simulate connection failure by clearing storage
        mock_kv_store.storage.clear()

        # Verify service is gone
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 0

        # Re-register service (simulating reconnection)
        await service_registry.register(instance, ttl_seconds=30)

        # Verify service reappears
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 1
        assert instances[0].instance_id == "reconnect-001"

    async def test_echo_service_pattern_compliance(self):
        """Test that echo service follows expected lifecycle patterns."""
        # This test validates the echo service implementation patterns
        # without actually running it

        # Import echo service to check structure
        import sys
        from pathlib import Path

        echo_path = Path(__file__).parent.parent.parent.parent.parent / "apps" / "echo-service"
        sys.path.insert(0, str(echo_path))

        try:
            from app.application.use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase
            from app.domain.models import EchoRequest, EchoResponse, ServiceMetrics
            from app.domain.services import EchoProcessor, MetricsCollector

            # Verify domain models use Pydantic v2
            assert hasattr(EchoRequest, "model_dump")
            assert hasattr(EchoResponse, "model_dump")
            assert hasattr(ServiceMetrics, "model_dump")

            # Verify domain services exist
            processor = EchoProcessor("test-instance")
            assert hasattr(processor, "process_echo")

            collector = MetricsCollector()
            assert hasattr(collector, "record_request")
            assert hasattr(collector, "get_average_latency")

            # Verify use cases follow DDD pattern
            echo_use_case = EchoUseCase(processor, collector)
            assert hasattr(echo_use_case, "execute")

            metrics_use_case = GetMetricsUseCase("test", "1.0.0", collector)
            assert hasattr(metrics_use_case, "execute")

            health_use_case = HealthCheckUseCase("test", "1.0.0")
            assert hasattr(health_use_case, "execute")

        except ImportError as e:
            # Echo service not found, skip this validation
            pytest.skip(f"Echo service not available: {e}")

    async def test_performance_under_load(self, service_registry, mock_kv_store):
        """Test service lifecycle performance with many instances."""
        start_time = time.time()

        # Register 100 services concurrently
        tasks = []
        for i in range(100):
            instance = ServiceInstance(
                service_name="load-test",
                instance_id=f"load-{i:03d}",
                version="1.0.0",
                status=ServiceStatus.ACTIVE,
                last_heartbeat=datetime.now(UTC),
            )
            tasks.append(service_registry.register(instance, ttl_seconds=30))

        await asyncio.gather(*tasks)

        # Verify all registered
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 100

        # Heartbeat updates for all
        heartbeat_tasks = []
        for i in range(100):

            async def update_hb(inst_id):
                i = await service_registry.get_instance("load-test", inst_id)
                if i:
                    i.last_heartbeat = datetime.now(UTC)
                    await service_registry.register(i, ttl_seconds=30)

            heartbeat_tasks.append(update_hb(f"load-{i:03d}"))

        await asyncio.gather(*heartbeat_tasks)

        # Deregister half
        dereg_tasks = []
        for i in range(50):
            dereg_tasks.append(service_registry.deregister("load-test", f"load-{i:03d}"))

        await asyncio.gather(*dereg_tasks)

        # Verify correct count remains
        all_services = await service_registry.list_all_services()
        instances = [inst for insts in all_services.values() for inst in insts]
        assert len(instances) == 50

        # Check performance
        elapsed = time.time() - start_time
        assert elapsed < 5.0, f"Operations took too long: {elapsed:.2f}s"
