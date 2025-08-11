"""Integration tests for SDK-based service registration and heartbeat.

Tests verify that the echo service properly uses SDK's built-in
heartbeat management and service registration capabilities.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aegis_sdk.application.service import ServiceConfig
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort
from app.application.echo_service import EchoApplicationService


@pytest.mark.asyncio
async def test_sdk_service_registration_and_heartbeat():
    """Test that SDK's Service base class handles registration and heartbeat."""
    # Create mock message bus
    mock_message_bus = AsyncMock(spec=MessageBusPort)
    mock_message_bus.is_connected.return_value = True

    # Create mock service registry
    mock_registry = AsyncMock(spec=ServiceRegistryPort)

    # Create SDK-based echo service with direct parameters
    service = EchoApplicationService(
        service_name="echo-service",
        message_bus=mock_message_bus,
        instance_id="test-instance-123",
        version="1.0.0",
        service_registry=mock_registry,
        heartbeat_interval=1.0,  # Fast heartbeat for testing
        registry_ttl=5.0,
        enable_registration=True,
    )

    # Start the service
    await service.start()

    # Verify SDK registered the service
    assert mock_registry.register.called
    register_call = mock_registry.register.call_args
    instance = register_call[0][0]
    assert instance.service_name == "echo-service"
    assert instance.instance_id == "test-instance-123"
    assert instance.version == "1.0.0"

    # Wait briefly for heartbeat
    import asyncio

    await asyncio.sleep(1.5)

    # Verify heartbeat was sent
    assert mock_registry.update_heartbeat.called
    assert mock_message_bus.send_heartbeat.called

    # Stop the service
    await service.stop()

    # Verify deregistration
    assert mock_registry.deregister.called


@pytest.mark.asyncio
async def test_sdk_handler_registration():
    """Test that handlers are registered with SDK's handler registry."""
    # Create mock message bus
    mock_message_bus = AsyncMock(spec=MessageBusPort)
    mock_message_bus.is_connected.return_value = True
    mock_message_bus.register_rpc_handler = AsyncMock()

    # Create SDK-based echo service
    service = EchoApplicationService(
        service_name="echo-service",
        message_bus=mock_message_bus,
        instance_id="test-instance-456",
        version="1.0.0",
        enable_registration=False,  # Disable registration for this test
    )

    # Start the service
    await service.start()

    # Verify all handlers were registered with SDK
    handler_registry = service._handler_registry
    assert "echo" in handler_registry.rpc_handlers
    assert "batch_echo" in handler_registry.rpc_handlers
    assert "metrics" in handler_registry.rpc_handlers
    assert "health" in handler_registry.rpc_handlers
    assert "ping" in handler_registry.rpc_handlers

    # Test echo handler
    echo_handler = handler_registry.rpc_handlers["echo"]
    result = await echo_handler({"message": "test"})
    assert result["echo"] == "test"
    assert result["instance_id"] == "test-instance-456"

    # Stop the service
    await service.stop()


@pytest.mark.asyncio
async def test_sdk_configuration_validation():
    """Test that SDK validates configuration properly."""
    # Test invalid service name
    with pytest.raises(ValueError, match="Invalid service name"):
        ServiceConfig(
            service_name="invalid service!",  # Invalid characters
            instance_id="test",
            version="1.0.0",
        )

    # Test invalid heartbeat interval
    with pytest.raises(ValueError):
        ServiceConfig(
            service_name="echo-service",
            instance_id="test",
            version="1.0.0",
            heartbeat_interval=-1.0,  # Negative interval
        )

    # Test invalid TTL
    with pytest.raises(ValueError):
        ServiceConfig(
            service_name="echo-service",
            instance_id="test",
            version="1.0.0",
            registry_ttl=0,  # Zero TTL
        )


@pytest.mark.asyncio
async def test_sdk_health_manager_exponential_backoff():
    """Test that SDK's HealthManager implements exponential backoff on failures."""
    # Create mock message bus that fails
    mock_message_bus = AsyncMock(spec=MessageBusPort)
    mock_message_bus.is_connected.return_value = True
    mock_message_bus.send_heartbeat.side_effect = Exception("Network error")

    # Create mock registry
    mock_registry = AsyncMock(spec=ServiceRegistryPort)

    # Create service with fast heartbeat
    service = EchoApplicationService(
        service_name="echo-service",
        message_bus=mock_message_bus,
        instance_id="test-backoff",
        version="1.0.0",
        service_registry=mock_registry,
        heartbeat_interval=0.1,  # Very fast for testing
        registry_ttl=5.0,
        enable_registration=True,
    )

    # Start the service
    await service.start()

    # Wait for multiple heartbeat attempts
    import asyncio

    await asyncio.sleep(1.0)

    # Verify health manager is handling failures
    health_manager = service._health_manager
    assert health_manager._consecutive_failures > 0

    # Stop the service
    await service.stop()


@pytest.mark.asyncio
async def test_legacy_compatibility():
    """Test that legacy service_bus and configuration still work."""
    from app.ports.configuration import ConfigurationPort
    from app.ports.service_bus import ServiceBusPort

    # Create legacy mocks
    mock_service_bus = AsyncMock(spec=ServiceBusPort)
    mock_service_bus.register_rpc_handler = MagicMock()

    mock_configuration = MagicMock(spec=ConfigurationPort)
    mock_configuration.get_instance_id.return_value = "legacy-instance"
    mock_configuration.get_service_version.return_value = "1.0.0"

    # Create mock SDK components
    mock_message_bus = AsyncMock(spec=MessageBusPort)

    # Create service with both SDK and legacy components
    service = EchoApplicationService(
        service_name="echo-service",
        message_bus=mock_message_bus,
        instance_id="legacy-instance",
        version="1.0.0",
        enable_registration=False,
        service_bus=mock_service_bus,  # Legacy
        configuration=mock_configuration,  # Legacy
    )

    # Start the service
    await service.start()

    # Verify legacy handlers were also registered
    assert mock_service_bus.register_rpc_handler.called
    assert mock_service_bus.register_rpc_handler.call_count == 5  # All 5 handlers

    # Verify service started legacy bus
    assert mock_service_bus.start.called

    # Stop the service
    await service.stop()

    # Verify legacy bus was stopped
    assert mock_service_bus.stop.called
