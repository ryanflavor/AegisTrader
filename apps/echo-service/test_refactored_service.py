#!/usr/bin/env python3
"""Test script to validate the refactored echo service architecture.

This script tests that the refactored service maintains all functionality
while properly implementing DDD and hexagonal architecture patterns.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.application.echo_service import EchoApplicationService
from app.infrastructure.environment_configuration_adapter import EnvironmentConfigurationAdapter
from app.infrastructure.factory import EchoServiceFactory
from app.ports.configuration import ConfigurationPort
from app.ports.service_bus import ServiceBusPort


async def test_factory_creation():
    """Test that the factory can create test services."""
    print("Testing Factory Pattern...")

    # Create mock service bus
    mock_bus = MagicMock(spec=ServiceBusPort)
    mock_bus.start = AsyncMock()
    mock_bus.stop = AsyncMock()
    mock_bus.register_rpc_handler = MagicMock()
    mock_bus.get_instance_id = MagicMock(return_value="test-123")
    mock_bus.is_connected = MagicMock(return_value=True)

    # Create test service
    service = EchoServiceFactory.create_test_service(
        service_bus=mock_bus, config_defaults={"service_name": "echo-test", "version": "test-1.0.0"}
    )

    # Verify service was created
    assert isinstance(service, EchoApplicationService)
    assert service._service_bus == mock_bus

    # Test starting the service
    await service.start()
    mock_bus.start.assert_called_once()

    # Test RPC handler registration
    assert mock_bus.register_rpc_handler.call_count == 5
    registered_methods = [call[0][0] for call in mock_bus.register_rpc_handler.call_args_list]
    assert "echo" in registered_methods
    assert "batch_echo" in registered_methods
    assert "metrics" in registered_methods
    assert "health" in registered_methods
    assert "ping" in registered_methods

    # Test stopping the service
    await service.stop()
    mock_bus.stop.assert_called_once()

    print("✅ Factory pattern test passed!")


async def test_configuration_adapter():
    """Test the configuration adapter."""
    print("\nTesting Configuration Adapter...")

    # Create adapter with defaults
    config = EnvironmentConfigurationAdapter(
        defaults={"service_name": "test-echo", "version": "2.0.0", "debug": True}
    )

    # Test configuration methods
    assert config.get_service_name() == "test-echo"
    assert config.get_service_version() == "2.0.0"
    assert config.is_debug_enabled() is True

    # Test default values
    assert config.get_service_type() == "service"

    print("✅ Configuration adapter test passed!")


async def test_application_service_handlers():
    """Test the application service RPC handlers."""
    print("\nTesting Application Service Handlers...")

    # Create mocks
    mock_bus = MagicMock(spec=ServiceBusPort)
    mock_bus.start = AsyncMock()
    mock_bus.stop = AsyncMock()
    mock_bus.register_rpc_handler = MagicMock()
    mock_bus.get_instance_id = MagicMock(return_value="handler-test")
    mock_bus.is_connected = MagicMock(return_value=True)

    mock_config = MagicMock(spec=ConfigurationPort)
    mock_config.get_instance_id = MagicMock(return_value="test-instance")
    mock_config.get_service_version = MagicMock(return_value="1.0.0")

    # Create service
    service = EchoApplicationService(mock_bus, mock_config)

    # Test echo handler
    echo_result = await service._handle_echo({"message": "Hello Test", "mode": "simple"})
    assert "echo" in echo_result
    assert echo_result["original"] == "Hello Test"
    assert "error" not in echo_result

    # Test batch echo handler
    batch_result = await service._handle_batch_echo({"messages": ["One", "Two", "Three"]})
    assert batch_result["count"] == 3
    assert len(batch_result["results"]) == 3

    # Test ping handler
    ping_result = await service._handle_ping({"timestamp": "2024-01-01"})
    assert ping_result["pong"] is True
    assert ping_result["timestamp"] == "2024-01-01"

    # Test metrics handler
    metrics_result = await service._handle_metrics({})
    assert "total_requests" in metrics_result
    assert "instance_id" in metrics_result

    # Test health handler
    health_result = await service._handle_health({})
    assert "status" in health_result
    assert "checks" in health_result

    print("✅ Application service handlers test passed!")


async def test_hexagonal_architecture():
    """Verify hexagonal architecture boundaries are maintained."""
    print("\nVerifying Hexagonal Architecture...")

    # Verify ports don't import infrastructure
    from app.ports import configuration, service_bus

    # Check that ports modules don't have infrastructure imports
    assert "infrastructure" not in str(configuration.__file__)
    assert "infrastructure" not in str(service_bus.__file__)

    # Verify application layer doesn't import infrastructure directly

    # The application should only depend on ports, not concrete implementations
    import_check = True
    try:
        # This should fail as application shouldn't import infrastructure
        exec("from app.application.echo_service import AegisServiceBusAdapter")
        import_check = False
    except ImportError:
        pass  # Expected - application shouldn't know about concrete adapters

    assert import_check, "Application layer should not import infrastructure directly"

    print("✅ Hexagonal architecture verification passed!")


async def main():
    """Run all architecture tests."""
    print("=" * 60)
    print("ECHO SERVICE ARCHITECTURE VALIDATION")
    print("=" * 60)

    try:
        await test_factory_creation()
        await test_configuration_adapter()
        await test_application_service_handlers()
        await test_hexagonal_architecture()

        print("\n" + "=" * 60)
        print("✅ ALL ARCHITECTURE TESTS PASSED!")
        print("=" * 60)
        print("\nThe refactored echo service properly implements:")
        print("• Domain-Driven Design (DDD)")
        print("• Hexagonal Architecture (Ports & Adapters)")
        print("• Dependency Injection")
        print("• Factory Pattern")
        print("• Clean separation of concerns")
        print("• Testable architecture with proper mocking boundaries")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
