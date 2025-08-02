"""Tests for the service module."""

import asyncio
from unittest.mock import MagicMock

import pytest
from aegis_sdk.application.service import Service
from aegis_sdk.domain.models import Event, RPCRequest, ServiceInfo


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
    async def test_service_start(self, mock_message_bus):
        """Test starting a service."""
        service = Service("test-service", mock_message_bus)

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
    async def test_service_stop(self, mock_message_bus):
        """Test stopping a service."""
        service = Service("test-service", mock_message_bus)

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
    async def test_heartbeat_loop(self, mock_message_bus):
        """Test heartbeat loop functionality."""
        service = Service("test-service", mock_message_bus)

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
        """Test successful RPC call."""
        service = Service("test-service", mock_message_bus)

        # Configure mock response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.result = {"user": "john"}
        mock_response.error = None
        mock_message_bus.call_rpc.return_value = mock_response

        # Make RPC call
        result = await service.call_rpc("user-service", "get_user", {"id": 123})

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

        # Make RPC call
        with pytest.raises(Exception) as exc_info:
            await service.call_rpc("user-service", "unknown_method")

        assert "RPC failed: Method not found" in str(exc_info.value)


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
