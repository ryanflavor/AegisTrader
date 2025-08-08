"""Integration test for service registration with monitor-api.

This test validates that the echo-service properly registers
both ServiceDefinition and ServiceInstance entries.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.application.echo_service import EchoApplicationService
from app.infrastructure.kv_service_registry_adapter import KVServiceRegistryAdapter
from app.ports.configuration import ConfigurationPort
from app.ports.service_bus import ServiceBusPort


class MockConfiguration(ConfigurationPort):
    """Mock configuration for testing."""

    def get_service_name(self) -> str:
        return "echo-service"

    def get_instance_id(self) -> str:
        return "echo-service-test-123"

    def get_service_version(self) -> str:
        return "1.0.0"

    def get_service_type(self) -> str:
        return "service"

    def get_nats_url(self) -> str | None:
        return "nats://localhost:4222"

    def is_debug_enabled(self) -> bool:
        return False

    def is_kubernetes_environment(self) -> bool:
        return False

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return default


@pytest.mark.asyncio
async def test_service_registration_on_startup():
    """Test that service registers definition and instance on startup."""
    # Create mocks
    mock_service_bus = AsyncMock(spec=ServiceBusPort)
    mock_service_bus.is_connected.return_value = True
    mock_service_bus.get_instance_id.return_value = "echo-service-test-123"

    mock_kv_store = AsyncMock()
    mock_kv_store.get.return_value = None  # No existing definition
    mock_kv_store.put = AsyncMock()

    # Create real registry adapter with mock KV store
    service_registry = KVServiceRegistryAdapter(mock_kv_store)

    # Create configuration
    configuration = MockConfiguration()

    # Create application service
    service = EchoApplicationService(
        service_bus=mock_service_bus,
        configuration=configuration,
        service_registry=service_registry,
    )

    # Start the service
    await service.start()

    # Verify service definition was registered
    assert mock_kv_store.put.call_count >= 1

    # Find the service definition registration call
    service_def_call = None
    instance_call = None

    for call in mock_kv_store.put.call_args_list:
        key = call[1]["key"]
        if key == "echo-service":
            service_def_call = call
        elif key.startswith("service-instances__echo-service__"):
            instance_call = call

    # Verify service definition was registered correctly
    assert service_def_call is not None, "Service definition was not registered"
    service_def = service_def_call[1]["value"]
    assert service_def["service_name"] == "echo-service"
    assert service_def["owner"] == "Platform Team"
    assert service_def["description"] == "Echo service for testing and demonstration"
    assert service_def["version"] == "1.0.0"
    assert "created_at" in service_def
    assert "updated_at" in service_def

    # Verify instance was registered correctly
    assert instance_call is not None, "Service instance was not registered"
    instance_data = instance_call[1]["value"]
    assert instance_data["serviceName"] == "echo-service"
    assert instance_data["instanceId"] == "echo-service-test-123"
    assert instance_data["version"] == "1.0.0"
    assert instance_data["status"] == "ACTIVE"
    assert "lastHeartbeat" in instance_data

    # Clean up
    await service.stop()


@pytest.mark.asyncio
async def test_service_deregistration_on_stop():
    """Test that service deregisters instance on stop."""
    # Create mocks
    mock_service_bus = AsyncMock(spec=ServiceBusPort)
    mock_service_bus.is_connected.return_value = True
    mock_service_bus.get_instance_id.return_value = "echo-service-test-123"

    mock_kv_store = AsyncMock()
    mock_kv_store.get.return_value = {"service_name": "echo-service"}  # Existing definition
    mock_kv_store.put = AsyncMock()
    mock_kv_store.delete = AsyncMock(return_value=True)

    # Create real registry adapter with mock KV store
    service_registry = KVServiceRegistryAdapter(mock_kv_store)

    # Create configuration
    configuration = MockConfiguration()

    # Create application service
    service = EchoApplicationService(
        service_bus=mock_service_bus,
        configuration=configuration,
        service_registry=service_registry,
    )

    # Start and stop the service
    await service.start()
    await service.stop()

    # Verify instance was deregistered
    mock_kv_store.delete.assert_called_once()
    delete_key = mock_kv_store.delete.call_args[0][0]
    assert delete_key == "service-instances__echo-service__echo-service-test-123"


@pytest.mark.asyncio
async def test_service_continues_without_registry():
    """Test that service continues to work even if registry is unavailable."""
    # Create mocks
    mock_service_bus = AsyncMock(spec=ServiceBusPort)
    mock_service_bus.is_connected.return_value = True
    mock_service_bus.get_instance_id.return_value = "echo-service-test-123"

    # Create configuration
    configuration = MockConfiguration()

    # Create application service without registry
    service = EchoApplicationService(
        service_bus=mock_service_bus,
        configuration=configuration,
        service_registry=None,  # No registry available
    )

    # Start the service - should not raise
    await service.start()

    # Service should be functional
    result = await service._handle_ping({"timestamp": "2024-01-01T00:00:00"})
    assert result["pong"] is True
    assert result["instance_id"] == "echo-service-test-123"

    # Stop the service - should not raise
    await service.stop()


@pytest.mark.asyncio
async def test_heartbeat_updates_instance():
    """Test that heartbeat updates instance registration."""
    # Create mocks
    mock_kv_store = AsyncMock()
    mock_kv_store.get.return_value = {"instanceId": "echo-service-test-123"}  # Instance exists
    mock_kv_store.put = AsyncMock()

    # Create registry adapter
    service_registry = KVServiceRegistryAdapter(mock_kv_store)

    # Update heartbeat
    await service_registry.update_instance_heartbeat(
        service_name="echo-service",
        instance_id="echo-service-test-123",
        instance_data={
            "serviceName": "echo-service",
            "instanceId": "echo-service-test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
        },
        ttl_seconds=30,
    )

    # Verify heartbeat was updated
    mock_kv_store.put.assert_called_once()
    updated_data = mock_kv_store.put.call_args[1]["value"]
    assert "lastHeartbeat" in updated_data
    assert updated_data["status"] == "ACTIVE"
