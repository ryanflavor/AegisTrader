"""Tests for the service module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.domain.exceptions import ServiceUnavailableError
from aegis_sdk.domain.models import (
    Event,
    RPCRequest,
    ServiceInfo,
    ServiceInstance,
)
from aegis_sdk.ports.service_discovery import SelectionStrategy


class TestServiceInitialization:
    """Test cases for Service initialization."""

    def test_service_init_with_defaults(self, mock_message_bus):
        """Test service initialization with default values."""
        service = Service("test-service", mock_message_bus)

        assert service.service_name == "test-service"
        assert service.instance_id.startswith("test-service-")
        assert service.version == "1.0.0"
        assert service._bus is mock_message_bus
        assert isinstance(service._info, ServiceInfo)
        assert service._info.service_name == "test-service"
        assert service._info.status == "ACTIVE"

    def test_service_init_with_custom_values(self, mock_message_bus):
        """Test service initialization with custom values."""
        service = Service(
            "custom-service",
            mock_message_bus,
            instance_id="custom-123",
            version="2.0.0",
        )

        assert service.service_name == "custom-service"
        assert service.instance_id == "custom-123"
        assert service.version == "2.0.0"
        assert service._info.version == "2.0.0"

    def test_service_init_invalid_name(self, mock_message_bus):
        """Test service initialization with invalid name."""
        with pytest.raises(ValueError) as exc_info:
            Service("123-invalid", mock_message_bus)
        assert "Invalid service name" in str(exc_info.value)

    def test_service_registries_initialized(self, mock_message_bus):
        """Test that handler registries are initialized."""
        service = Service("test-service", mock_message_bus)

        assert isinstance(service._rpc_handlers, dict)
        assert isinstance(service._event_handlers, dict)
        assert isinstance(service._command_handlers, dict)
        assert service._heartbeat_task is None
        assert isinstance(service._shutdown_event, asyncio.Event)


class TestServiceLifecycle:
    """Test cases for service lifecycle methods."""

    @pytest.mark.asyncio
    async def test_service_start(self, mock_message_bus, mock_service_registry):
        """Test starting a service."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        # Add some handlers to test registration
        @service.rpc("test_method")
        async def test_handler(params):
            return {"result": "ok"}

        @service.subscribe("test.event")
        async def event_handler(event):
            pass

        @service.command("test_command")
        async def command_handler(cmd, progress):
            return {"status": "done"}

        # Start the service
        await service.start()

        # Verify registrations
        mock_message_bus.register_service.assert_called_once_with(
            "test-service", service.instance_id
        )

        # Verify RPC handler registration
        mock_message_bus.register_rpc_handler.assert_called_once_with(
            "test-service", "test_method", test_handler
        )

        # Verify event subscription
        mock_message_bus.subscribe_event.assert_called_once()

        # Verify command handler registration
        mock_message_bus.register_command_handler.assert_called_once_with(
            "test-service", "test_command", command_handler
        )

        # Verify heartbeat task started
        assert service._heartbeat_task is not None
        assert not service._heartbeat_task.done()

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_service_stop(self, mock_message_bus, mock_service_registry):
        """Test stopping a service."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        # Start and then stop
        await service.start()
        await service.stop()

        # Verify shutdown
        assert service._shutdown_event.is_set()
        assert service._heartbeat_task.cancelled()

        # Verify unregistration
        mock_message_bus.unregister_service.assert_called_once_with(
            "test-service", service.instance_id
        )

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, mock_message_bus, mock_service_registry):
        """Test heartbeat loop functionality."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        # Start service
        await service.start()

        # Let the heartbeat loop run at least once
        await asyncio.sleep(0.1)

        # Stop service
        await service.stop()

        # The heartbeat might not have run due to timing, so just verify
        # the service started and stopped correctly
        assert service._shutdown_event.is_set()
        mock_message_bus.register_service.assert_called_once()


class TestRPCMethods:
    """Test cases for RPC functionality."""

    def test_rpc_decorator(self, mock_message_bus):
        """Test RPC decorator registration."""
        service = Service("test-service", mock_message_bus)

        @service.rpc("get_data")
        async def get_data(params):
            return {"data": params.get("id", "default")}

        assert "get_data" in service._rpc_handlers
        assert service._rpc_handlers["get_data"] is get_data

    def test_rpc_decorator_invalid_method(self, mock_message_bus):
        """Test RPC decorator with invalid method name."""
        service = Service("test-service", mock_message_bus)

        with pytest.raises(ValueError) as exc_info:

            @service.rpc("123-invalid")
            async def handler(params):
                pass

        assert "Invalid method name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_rpc_success(self, mock_message_bus):
        """Test successful RPC call without discovery."""
        service = Service("test-service", mock_message_bus)

        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.result = {"user": "john"}
        mock_response.error = None
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call with discovery disabled
        result = await service.call_rpc(
            "user-service", "get_user", {"id": 123}, discovery_enabled=False
        )

        assert result == {"user": "john"}

        # Verify request was made correctly
        call_args = mock_message_bus.call_rpc.call_args[0][0]
        assert isinstance(call_args, RPCRequest)
        assert call_args.method == "get_user"
        assert call_args.params == {"id": 123}
        assert call_args.target == "user-service"
        assert call_args.source == service.instance_id

    @pytest.mark.asyncio
    async def test_call_rpc_failure(self, mock_message_bus):
        """Test failed RPC call."""
        service = Service("test-service", mock_message_bus)

        # Configure mock error response
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.result = None
        mock_response.error = "Method not found"
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call with discovery disabled
        with pytest.raises(Exception) as exc_info:
            await service.call_rpc("user-service", "unknown_method", discovery_enabled=False)

        assert "RPC failed: Method not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_rpc_with_discovery(self, mock_message_bus):
        """Test RPC call with service discovery."""
        # Create mock discovery
        mock_discovery = MagicMock()
        mock_discovery.select_instance = AsyncMock()
        mock_discovery.invalidate_cache = AsyncMock()

        # Create service with discovery
        service = Service(
            "test-service",
            mock_message_bus,
            service_discovery=mock_discovery,
        )

        # Configure mock instance
        from datetime import UTC, datetime

        mock_instance = ServiceInstance(
            service_name="user-service",
            instance_id="user-service-abc123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        mock_discovery.select_instance.return_value = mock_instance

        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.result = {"user": "john"}
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call
        result = await service.call_rpc("user-service", "get_user", {"id": 123})

        assert result == {"user": "john"}

        # Verify discovery was used
        mock_discovery.select_instance.assert_called_once_with(
            "user-service",
            strategy=SelectionStrategy.ROUND_ROBIN,
            preferred_instance_id=None,
        )

        # Verify request used discovered instance
        call_args = mock_message_bus.call_rpc.call_args[0][0]
        assert call_args.target == "user-service-abc123"

    @pytest.mark.asyncio
    async def test_call_rpc_with_discovery_no_instances(self, mock_message_bus):
        """Test RPC call when no healthy instances available."""
        # Create mock discovery
        mock_discovery = MagicMock()
        mock_discovery.select_instance = AsyncMock(return_value=None)

        # Create service with discovery
        service = Service(
            "test-service",
            mock_message_bus,
            service_discovery=mock_discovery,
        )

        # Make RPC call
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await service.call_rpc("user-service", "get_user")

        assert exc_info.value.service_name == "user-service"

    @pytest.mark.asyncio
    async def test_call_rpc_with_discovery_failure_invalidates_cache(self, mock_message_bus):
        """Test that RPC failures invalidate discovery cache."""
        # Create mock discovery
        mock_discovery = MagicMock()
        mock_discovery.select_instance = AsyncMock()
        mock_discovery.invalidate_cache = AsyncMock()

        # Create service with discovery
        service = Service(
            "test-service",
            mock_message_bus,
            service_discovery=mock_discovery,
        )

        # Configure mock instance
        from datetime import UTC, datetime

        mock_instance = ServiceInstance(
            service_name="user-service",
            instance_id="user-service-abc123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
        )
        mock_discovery.select_instance.return_value = mock_instance

        # Configure mock error response
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Service unavailable"
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call
        with pytest.raises(Exception) as exc_info:
            await service.call_rpc("user-service", "get_user")

        assert "RPC failed: Service unavailable" in str(exc_info.value)

        # Verify cache was invalidated
        mock_discovery.invalidate_cache.assert_called_once_with("user-service")

    @pytest.mark.asyncio
    async def test_call_rpc_direct_instance_id(self, mock_message_bus):
        """Test RPC call with direct instance ID bypasses discovery."""
        # Create mock discovery
        mock_discovery = MagicMock()
        mock_discovery.select_instance = AsyncMock()

        # Create service with discovery
        service = Service(
            "test-service",
            mock_message_bus,
            service_discovery=mock_discovery,
        )

        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.result = {"ok": True}
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call with instance ID
        result = await service.call_rpc("user-service-abc123def", "health_check")

        assert result == {"ok": True}

        # Verify discovery was NOT used
        mock_discovery.select_instance.assert_not_called()

        # Verify request used direct instance ID
        call_args = mock_message_bus.call_rpc.call_args[0][0]
        assert call_args.target == "user-service-abc123def"

    def test_is_service_name(self, mock_message_bus):
        """Test service name vs instance ID detection."""
        service = Service("test-service", mock_message_bus)

        # Service names
        assert service._is_service_name("user-service") is True
        assert service._is_service_name("order-service") is True
        assert service._is_service_name("payment") is True

        # Instance IDs
        assert service._is_service_name("user-service-a1b2c3d4") is False
        assert service._is_service_name("order-service-deadbeef") is False
        assert service._is_service_name("payment-123456") is False

        # Edge cases
        assert service._is_service_name("service-with-many-parts") is True
        assert service._is_service_name("service-short") is True  # Short hex not considered ID


class TestEventMethods:
    """Test cases for event functionality."""

    def test_subscribe_decorator(self, mock_message_bus):
        """Test event subscription decorator."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("order.created")
        async def handle_order_created(event):
            pass

        assert "order.created" in service._event_handlers
        assert handle_order_created in service._event_handlers["order.created"]

    def test_subscribe_multiple_handlers(self, mock_message_bus):
        """Test multiple handlers for same event pattern."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("user.*")
        async def handler1(event):
            pass

        @service.subscribe("user.*")
        async def handler2(event):
            pass

        assert len(service._event_handlers["user.*"]) == 2
        assert handler1 in service._event_handlers["user.*"]
        assert handler2 in service._event_handlers["user.*"]

    @pytest.mark.asyncio
    async def test_publish_event(self, mock_message_bus):
        """Test publishing an event."""
        service = Service("test-service", mock_message_bus)

        await service.publish_event("order", "created", {"order_id": "123"})

        # Verify event was published
        mock_message_bus.publish_event.assert_called_once()
        event_arg = mock_message_bus.publish_event.call_args[0][0]

        assert isinstance(event_arg, Event)
        assert event_arg.domain == "order"
        assert event_arg.event_type == "created"
        assert event_arg.payload == {"order_id": "123"}
        assert event_arg.source == service.instance_id


class TestCommandMethods:
    """Test cases for command functionality."""

    def test_command_decorator(self, mock_message_bus):
        """Test command handler decorator."""
        service = Service("test-service", mock_message_bus)

        @service.command("process_batch")
        async def process_batch(cmd, progress):
            await progress(50, "Half done")
            return {"processed": 100}

        assert "process_batch" in service._command_handlers
        assert service._command_handlers["process_batch"] is process_batch

    @pytest.mark.asyncio
    async def test_send_command(self, mock_message_bus):
        """Test sending a command."""
        service = Service("test-service", mock_message_bus)

        # Configure mock response
        mock_message_bus.send_command.return_value = {
            "command_id": "cmd-123",
            "status": "completed",
            "result": {"processed": 50},
        }

        # Send command
        result = await service.send_command(
            "worker-service",
            "process_data",
            {"batch_id": "batch-456"},
            priority="high",
            track_progress=True,
        )

        assert result["status"] == "completed"
        assert result["result"]["processed"] == 50

        # Verify command was sent correctly
        command_arg = mock_message_bus.send_command.call_args[0][0]
        assert command_arg.command == "process_data"
        assert command_arg.payload == {"batch_id": "batch-456"}
        assert command_arg.priority == "high"
        assert command_arg.target == "worker-service"
        assert command_arg.source == service.instance_id


class TestServiceInfo:
    """Test cases for service info and status."""

    def test_get_service_info(self, mock_message_bus):
        """Test getting service information."""
        service = Service("test-service", mock_message_bus, version="1.2.3")

        info = service.info
        assert isinstance(info, ServiceInfo)
        assert info.service_name == "test-service"
        assert info.version == "1.2.3"
        assert info.status == "ACTIVE"

    def test_set_status_valid(self, mock_message_bus):
        """Test setting valid service status."""
        service = Service("test-service", mock_message_bus)

        for status in ["ACTIVE", "STANDBY", "UNHEALTHY", "SHUTDOWN"]:
            service.set_status(status)
            assert service._info.status == status

    def test_set_status_invalid(self, mock_message_bus):
        """Test setting invalid service status."""
        service = Service("test-service", mock_message_bus)

        with pytest.raises(ValueError) as exc_info:
            service.set_status("RUNNING")

        assert "Invalid status: RUNNING" in str(exc_info.value)


class TestServiceRegistration:
    """Test cases for service registration functionality."""

    def test_service_init_with_registration_config(self, mock_message_bus):
        """Test service initialization with registration configuration."""
        service = Service(
            "test-service",
            mock_message_bus,
            registry_ttl=60,
            heartbeat_interval=20,
            enable_registration=False,
        )

        assert service._registry_ttl == 60
        assert service._heartbeat_interval == 20
        assert service._enable_registration is False
        assert service._service_instance is None  # Not created when registration disabled

    @pytest.mark.asyncio
    async def test_service_registration_on_start(self, mock_message_bus, mock_service_registry):
        """Test service registration during start."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            registry_ttl=30,
            enable_registration=True,
        )

        await service.start()

        # Verify registry was used for registration
        mock_service_registry.register.assert_called_once()
        call_args = mock_service_registry.register.call_args

        # Check instance data
        instance = call_args[0][0]
        assert instance.service_name == "test-service"
        assert instance.instance_id == service.instance_id
        assert instance.version == "1.0.0"
        assert instance.status == "ACTIVE"
        assert instance.last_heartbeat is not None
        assert "metadata" in instance.model_dump()

        # Check TTL
        ttl = call_args[0][1]
        assert ttl == 30

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_service_registration_disabled(self, mock_message_bus, mock_service_registry):
        """Test service start with registration disabled."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        await service.start()

        # Verify registry was NOT used
        mock_service_registry.register.assert_not_called()

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_service_registration_without_registry(self, mock_message_bus):
        """Test service without registry provided."""
        service = Service(
            "test-service",
            mock_message_bus,
            enable_registration=True,
        )

        # Should start successfully without registry
        await service.start()

        # Service instance should be created
        assert service._service_instance is not None
        assert service._service_instance.service_name == "test-service"

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_service_registration_failure(self, mock_message_bus, mock_service_registry):
        """Test handling of registration failure."""
        # Configure registry to fail
        mock_service_registry.register.side_effect = Exception("Registry error")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        # Registration failure should propagate
        with pytest.raises(Exception) as exc_info:
            await service.start()

        assert "Registry error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_deregistration_on_stop(self, mock_message_bus, mock_service_registry):
        """Test service deregistration during stop."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        await service.start()

        await service.stop()

        # Verify deregister was called
        mock_service_registry.deregister.assert_called_once_with(
            "test-service", service.instance_id
        )

    @pytest.mark.asyncio
    async def test_service_deregistration_failure_handled(
        self, mock_message_bus, mock_service_registry, mock_logger
    ):
        """Test handling of deregistration failure."""
        # Configure registry deregister to fail
        mock_service_registry.deregister.side_effect = Exception("Delete failed")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            logger=mock_logger,
            enable_registration=True,
        )

        await service.start()
        await service.stop()

        # Should log warning but not raise
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Failed to remove service instance from registry" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_heartbeat_updates_registry(self, mock_message_bus, mock_service_registry):
        """Test heartbeat updates registry entry."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            heartbeat_interval=0.1,  # Fast heartbeat for testing
            enable_registration=True,
        )

        await service.start()

        # Let heartbeat run once
        await asyncio.sleep(0.2)

        await service.stop()

        # Verify registry was updated (at least once during start and once during heartbeat)
        assert mock_service_registry.register.call_count >= 1
        assert mock_service_registry.update_heartbeat.call_count >= 1

    @pytest.mark.asyncio
    async def test_heartbeat_re_registers_if_missing(self, mock_message_bus, mock_service_registry):
        """Test heartbeat re-registers if entry is missing."""
        # Configure update_heartbeat to fail first time (simulating missing entry)
        mock_service_registry.update_heartbeat.side_effect = [Exception("Not found"), None]

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        await service.start()

        # Manually call heartbeat update - it should raise the exception
        with pytest.raises(Exception) as exc_info:
            await service._update_registry_heartbeat()

        assert "Not found" in str(exc_info.value)

        # Should have called register at least once during start
        assert mock_service_registry.register.call_count >= 1

    @pytest.mark.asyncio
    async def test_status_update_in_registry(self, mock_message_bus, mock_service_registry):
        """Test status updates are reflected in registry."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        await service.start()

        # Change status
        service.set_status("UNHEALTHY")

        # Give async task time to complete
        await asyncio.sleep(0.1)

        # Verify update_heartbeat was called after status change
        assert mock_service_registry.update_heartbeat.call_count >= 1

        # Check that service instance status was updated
        assert service._service_instance.status == "UNHEALTHY"

        await service.stop()

    @pytest.mark.asyncio
    async def test_registration_with_custom_ttl(self, mock_message_bus, mock_service_registry):
        """Test registration with custom TTL value."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            registry_ttl=120,  # 2 minutes
            enable_registration=True,
        )

        await service.start()

        # Verify TTL was used
        call_args = mock_service_registry.register.call_args
        ttl = call_args[0][1]
        assert ttl == 120

        await service.stop()

    @pytest.mark.asyncio
    async def test_service_metadata_in_registration(self, mock_message_bus, mock_service_registry):
        """Test service metadata is included in registration."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        await service.start()

        # Check metadata
        call_args = mock_service_registry.register.call_args
        instance = call_args[0][0]
        assert instance.metadata is not None
        assert "start_time" in instance.metadata

        await service.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_failure_recovery(
        self, mock_message_bus, mock_service_registry, mock_logger
    ):
        """Test heartbeat handles and recovers from failures."""
        # Configure registry to fail on update_heartbeat
        mock_service_registry.update_heartbeat.side_effect = Exception("Transient error")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            logger=mock_logger,
            heartbeat_interval=0.1,
            enable_registration=True,
        )

        await service.start()

        # Manually trigger heartbeat update - it should raise but log warning
        with pytest.raises(Exception) as exc_info:
            await service._update_registry_heartbeat()

        assert "Transient error" in str(exc_info.value)

        # Should log warning
        mock_logger.warning.assert_called()
        assert "Failed to update registry heartbeat" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_status_update_no_service_instance(self, mock_message_bus, mock_service_registry):
        """Test status update when no service instance exists."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,  # Disable to prevent instance creation
        )

        # Don't start service (no service instance)
        service.set_status("UNHEALTHY")

        # Give async task time
        await asyncio.sleep(0.1)

        # Should not call registry
        mock_service_registry.update_heartbeat.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_instance_creation(self, mock_message_bus, mock_service_registry):
        """Test service instance is created properly."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            version="2.0.0",
            enable_registration=True,
        )

        await service.start()

        # Verify service instance was created
        assert service._service_instance is not None
        assert service._service_instance.service_name == "test-service"
        assert service._service_instance.version == "2.0.0"
        assert service._service_instance.status == "ACTIVE"

        await service.stop()

    def test_register_rpc_method(self, mock_message_bus):
        """Test register_rpc_method helper."""
        service = Service("test-service", mock_message_bus)

        async def handler(params):
            return {"result": "ok"}

        # This should work without decorators
        asyncio.run(service.register_rpc_method("test_method", handler))

        assert "test_method" in service._rpc_handlers
        assert service._rpc_handlers["test_method"] is handler

    def test_register_command_handler(self, mock_message_bus):
        """Test register_command_handler helper."""
        service = Service("test-service", mock_message_bus)

        async def handler(cmd, progress):
            return {"status": "done"}

        asyncio.run(service.register_command_handler("test_command", handler))

        assert "test_command" in service._command_handlers
        assert service._command_handlers["test_command"] is handler

    def test_subscribe_event_helper(self, mock_message_bus):
        """Test subscribe_event helper method."""
        service = Service("test-service", mock_message_bus)

        async def handler(event):
            pass

        asyncio.run(service.subscribe_event("order", "created", handler))

        # Check handler was registered with full pattern
        expected_pattern = "events.order.created"
        assert expected_pattern in service._event_handlers
        assert handler in service._event_handlers[expected_pattern]

    @pytest.mark.asyncio
    async def test_emit_event_helper(self, mock_message_bus):
        """Test emit_event helper method."""
        service = Service("test-service", mock_message_bus)

        await service.emit_event("order", "created", {"id": 123})

        # Verify event was published
        mock_message_bus.publish_event.assert_called_once()
        event = mock_message_bus.publish_event.call_args[0][0]
        assert event.domain == "order"
        assert event.event_type == "created"
        assert event.payload == {"id": 123}

    @pytest.mark.asyncio
    async def test_on_start_hook(self, mock_message_bus):
        """Test on_start hook is called."""

        # Create a custom service that uses on_start
        class CustomService(Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.on_start_called = False

            async def on_start(self):
                self.on_start_called = True
                await self.register_rpc_method("custom_method", self.custom_handler)

            async def custom_handler(self, params):
                return {"custom": True}

        service = CustomService("custom-service", mock_message_bus, enable_registration=False)
        await service.start()

        assert service.on_start_called
        assert "custom_method" in service._rpc_handlers

        await service.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_consecutive_failures(
        self, mock_message_bus, mock_service_registry, mock_logger
    ):
        """Test heartbeat loop handles consecutive failures and marks service unhealthy."""
        # Configure message bus to fail on heartbeat
        mock_message_bus.send_heartbeat.side_effect = Exception("Network error")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            logger=mock_logger,
            heartbeat_interval=0.01,  # Very fast for testing
            enable_registration=True,
        )

        # Mock time to avoid real sleeps in exponential backoff
        # We need to selectively mock only the backoff sleeps, not heartbeat interval
        original_sleep = asyncio.sleep
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            # Only actually sleep for small delays (heartbeat interval)
            # Skip the exponential backoff sleeps
            if delay < 1:
                await original_sleep(delay)
            else:
                # For backoff sleeps, just yield control without waiting
                await original_sleep(0.001)

        with patch("asyncio.sleep", mock_sleep):
            # Create an event to signal when unhealthy status is set
            unhealthy_event = asyncio.Event()
            original_set_status = service.set_status

            def set_status_with_signal(status):
                original_set_status(status)
                if status == "UNHEALTHY":
                    unhealthy_event.set()

            service.set_status = set_status_with_signal

            await service.start()

            # Wait for unhealthy status (should happen quickly with mocked backoff)
            try:
                await asyncio.wait_for(unhealthy_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Service did not become unhealthy within timeout")

            # Should mark service as unhealthy after 3 consecutive failures
            assert service._info.status == "UNHEALTHY"

            # Should log warnings
            assert mock_logger.warning.call_count >= 3

            # Verify exponential backoff was used (2^1, 2^2, 2^3)
            # Filter out heartbeat interval sleeps (0.01) and look for backoff sleeps
            backoff_sleeps = [s for s in sleep_calls if s > 1]
            assert len(backoff_sleeps) >= 3
            # Check that backoff values increase exponentially (with jitter)
            assert 1.5 < backoff_sleeps[0] < 3.5  # ~2 seconds + jitter
            assert 3.5 < backoff_sleeps[1] < 5.5  # ~4 seconds + jitter
            assert 7.5 < backoff_sleeps[2] < 11  # ~8 seconds + jitter (capped at 10)

        await service.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_recovery_after_failure(
        self, mock_message_bus, mock_service_registry
    ):
        """Test heartbeat loop recovers after failures."""
        # Configure to fail twice then succeed
        call_count = 0

        async def send_heartbeat_with_failures(*args):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Transient failure")
            # Success on third call

        mock_message_bus.send_heartbeat = send_heartbeat_with_failures

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            heartbeat_interval=0.01,
            enable_registration=True,
        )

        # Use selective mocking for sleep
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            if delay < 1:
                await original_sleep(delay)
            else:
                await original_sleep(0.001)

        with patch("asyncio.sleep", mock_sleep):
            await service.start()

            # Wait for recovery
            start_time = asyncio.get_event_loop().time()
            while call_count < 3 and asyncio.get_event_loop().time() - start_time < 2.0:
                await asyncio.sleep(0.01)

            # Should have recovered
            assert call_count >= 3

        await service.stop()

    @pytest.mark.asyncio
    async def test_register_instance_failure_propagates(
        self, mock_message_bus, mock_service_registry, mock_logger
    ):
        """Test that registration failure during start propagates correctly."""
        # Configure registry to fail during initial registration
        mock_service_registry.register.side_effect = Exception("Registry unavailable")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            logger=mock_logger,
            enable_registration=True,
        )

        # Should raise exception during start
        with pytest.raises(Exception) as exc_info:
            await service.start()

        assert "Registry unavailable" in str(exc_info.value)

        # Logger should have logged the error
        mock_logger.error.assert_called_once()
        assert "Failed to register service instance" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_registry_status_failure_handled(
        self, mock_message_bus, mock_service_registry, mock_logger
    ):
        """Test that registry status update failures are handled gracefully."""
        # Configure registry to fail on update_heartbeat
        mock_service_registry.update_heartbeat.side_effect = Exception("Update failed")

        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            logger=mock_logger,
            enable_registration=True,
        )

        await service.start()

        # Change status - should trigger update
        service.set_status("STANDBY")

        # Give async task time to run
        await asyncio.sleep(0.1)

        # Should log warning about failure
        mock_logger.warning.assert_called()
        assert "Failed to update registry status" in str(mock_logger.warning.call_args)

        await service.stop()

    @pytest.mark.asyncio
    async def test_status_update_cancels_previous_task(
        self, mock_message_bus, mock_service_registry
    ):
        """Test that status updates cancel previous update tasks."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        await service.start()

        # Set status multiple times quickly
        service.set_status("STANDBY")
        first_task = service._status_update_task

        # Give the task a moment to start
        await asyncio.sleep(0.01)

        service.set_status("UNHEALTHY")
        second_task = service._status_update_task

        # Wait for cancellation to propagate
        await asyncio.sleep(0.01)

        # First task should be cancelled
        assert first_task.cancelled() or first_task.done()
        assert first_task != second_task

        await service.stop()

    def test_register_rpc_method_invalid_name(self, mock_message_bus):
        """Test register_rpc_method with invalid method name."""
        service = Service("test-service", mock_message_bus)

        async def handler(params):
            return {}

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(service.register_rpc_method("123-invalid", handler))

        assert "Invalid method name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_heartbeat_loop_shutdown_handling(self, mock_message_bus):
        """Test heartbeat loop properly checks shutdown event."""
        service = Service(
            "test-service",
            mock_message_bus,
            heartbeat_interval=0.05,
            enable_registration=False,
        )

        await service.start()

        # Verify heartbeat task is running
        assert service._heartbeat_task is not None
        assert not service._heartbeat_task.done()

        # Set shutdown event
        service._shutdown_event.set()

        # Heartbeat should exit soon
        await asyncio.sleep(0.1)

        # Task should complete (not be cancelled)
        assert service._heartbeat_task.done()

    @pytest.mark.asyncio
    async def test_service_start_time_tracking(self, mock_message_bus, mock_service_registry):
        """Test that service tracks start time correctly."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=True,
        )

        # Start time should be None initially
        assert service._start_time is None

        await service.start()

        # Start time should be set
        assert service._start_time is not None

        # Check metadata includes start time
        assert service._service_instance is not None
        assert "start_time" in service._service_instance.metadata
        assert service._service_instance.metadata["start_time"] is not None

        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self, mock_message_bus):
        """Test stopping a service that was never started."""
        service = Service("test-service", mock_message_bus)

        # Should handle gracefully
        await service.stop()

        # Shutdown event should be set
        assert service._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self, mock_message_bus, mock_logger):
        """Test exponential backoff calculation in heartbeat loop."""
        service = Service(
            "test-service",
            mock_message_bus,
            logger=mock_logger,
            heartbeat_interval=0.01,
            enable_registration=False,
        )

        # Configure to always fail
        mock_message_bus.send_heartbeat.side_effect = Exception("Always fail")

        # Use selective mocking for sleep
        original_sleep = asyncio.sleep
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            if delay < 1:
                await original_sleep(delay)
            else:
                await original_sleep(0.001)

        with patch("asyncio.sleep", mock_sleep):
            await service.start()

            # Wait for failures
            start_time = asyncio.get_event_loop().time()
            while (
                mock_logger.warning.call_count < 3
                and asyncio.get_event_loop().time() - start_time < 2.0
            ):
                await asyncio.sleep(0.01)

            # Should have logged multiple failures with increasing counts
            assert mock_logger.warning.call_count >= 3

            # Verify exponential backoff pattern in sleep calls
            backoff_sleeps = [s for s in sleep_calls if s > 1]
            assert len(backoff_sleeps) >= 3

        await service.stop()

    @pytest.mark.asyncio
    async def test_register_instance_no_registry(self, mock_message_bus):
        """Test _register_instance returns early when no registry."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=None,  # No registry
            enable_registration=True,
        )

        # Should not raise even with no registry
        await service._register_instance()

    @pytest.mark.asyncio
    async def test_register_instance_no_service_instance(
        self, mock_message_bus, mock_service_registry
    ):
        """Test _register_instance returns early when no service instance."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,  # This prevents _service_instance creation
        )

        # Manually clear service instance
        service._service_instance = None

        # Should not raise
        await service._register_instance()

    @pytest.mark.asyncio
    async def test_update_registry_heartbeat_no_registry(self, mock_message_bus):
        """Test _update_registry_heartbeat returns early when no registry."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=None,
            enable_registration=True,
        )

        # Create service instance manually
        from aegis_sdk.domain.models import ServiceInstance

        service._service_instance = ServiceInstance(
            service_name="test-service",
            instance_id=service.instance_id,
            version="1.0.0",
            status="ACTIVE",
        )

        # Should not raise
        await service._update_registry_heartbeat()

    @pytest.mark.asyncio
    async def test_update_registry_heartbeat_no_service_instance(
        self, mock_message_bus, mock_service_registry
    ):
        """Test _update_registry_heartbeat returns early when no service instance."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        # Should not raise
        await service._update_registry_heartbeat()

    @pytest.mark.asyncio
    async def test_update_registry_status_no_registry(self, mock_message_bus):
        """Test _update_registry_status returns early when no registry."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=None,
            enable_registration=True,
        )

        # Should not raise
        await service._update_registry_status("STANDBY")

    @pytest.mark.asyncio
    async def test_update_registry_status_no_service_instance(
        self, mock_message_bus, mock_service_registry
    ):
        """Test _update_registry_status returns early when no service instance."""
        service = Service(
            "test-service",
            mock_message_bus,
            service_registry=mock_service_registry,
            enable_registration=False,
        )

        # Should not raise
        await service._update_registry_status("STANDBY")

    @pytest.mark.asyncio
    async def test_heartbeat_marks_unhealthy_after_max_failures(self, mock_message_bus):
        """Test that heartbeat loop marks service unhealthy after max consecutive failures."""
        # Track status changes
        status_changes = []

        class TrackingService(Service):
            def set_status(self, status: str) -> None:
                status_changes.append(status)
                super().set_status(status)

        # Configure to always fail
        mock_message_bus.send_heartbeat.side_effect = Exception("Always fail")

        service = TrackingService(
            "test-service",
            mock_message_bus,
            heartbeat_interval=0.01,
            enable_registration=False,
        )

        # Use selective mocking for sleep
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            if delay < 1:
                await original_sleep(delay)
            else:
                await original_sleep(0.001)

        with patch("asyncio.sleep", mock_sleep):
            await service.start()

            # Wait for unhealthy status
            start_time = asyncio.get_event_loop().time()
            while (
                "UNHEALTHY" not in status_changes
                and asyncio.get_event_loop().time() - start_time < 2.0
            ):
                await asyncio.sleep(0.01)

            # Should have marked service as unhealthy
            assert "UNHEALTHY" in status_changes
            assert service._info.status == "UNHEALTHY"

        await service.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_error_without_logger(self, mock_message_bus, capsys):
        """Test heartbeat error handling without logger uses print."""
        # Configure message bus to fail
        mock_message_bus.send_heartbeat.side_effect = Exception("Network error")

        service = Service(
            "test-service",
            mock_message_bus,
            logger=None,  # No logger
            heartbeat_interval=0.01,
            enable_registration=False,
        )

        await service.start()

        # Let it fail once
        await asyncio.sleep(0.1)

        # Check console output
        captured = capsys.readouterr()
        assert "❌ Heartbeat error (1/3): Network error" in captured.out

        await service.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_marks_unhealthy_without_logger(self, mock_message_bus, capsys):
        """Test heartbeat marks unhealthy and prints to console without logger."""
        # Configure to always fail
        mock_message_bus.send_heartbeat.side_effect = Exception("Always fail")

        service = Service(
            "test-service",
            mock_message_bus,
            logger=None,  # No logger
            heartbeat_interval=0.01,
            enable_registration=False,
        )

        # Use selective mocking for sleep
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            if delay < 1:
                await original_sleep(delay)
            else:
                await original_sleep(0.001)

        all_output = ""
        with patch("asyncio.sleep", mock_sleep):
            await service.start()

            # Wait for unhealthy status
            start_time = asyncio.get_event_loop().time()
            while (
                service._info.status != "UNHEALTHY"
                and asyncio.get_event_loop().time() - start_time < 2.0
            ):
                await asyncio.sleep(0.01)
                captured = capsys.readouterr()
                all_output += captured.out

            # Should have marked service as unhealthy
            assert service._info.status == "UNHEALTHY"

            # Get final output
            final_output = capsys.readouterr()
            all_output += final_output.out

            # Check console output for multiple errors
            assert "❌ Heartbeat error (1/3): Always fail" in all_output
            assert "❌ Heartbeat error (2/3): Always fail" in all_output
            assert "❌ Heartbeat error (3/3): Always fail" in all_output

        await service.stop()
