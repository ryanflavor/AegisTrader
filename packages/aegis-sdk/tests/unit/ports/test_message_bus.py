"""Tests for message bus port interface."""

from abc import ABC
from unittest.mock import AsyncMock

import pytest

from aegis_sdk.domain.models import Command, Event, RPCRequest, RPCResponse
from aegis_sdk.ports.message_bus import MessageBusPort


class TestMessageBusPort:
    """Test cases for MessageBusPort interface."""

    def test_message_bus_port_is_abstract(self):
        """Test that MessageBusPort is an abstract base class."""
        assert issubclass(MessageBusPort, ABC)

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            MessageBusPort()

    def test_message_bus_port_defines_interface(self):
        """Test that MessageBusPort defines all required methods."""
        # Check all abstract methods are defined
        abstract_methods = {
            "connect",
            "disconnect",
            "is_connected",
            "register_rpc_handler",
            "call_rpc",
            "subscribe_event",
            "publish_event",
            "register_command_handler",
            "send_command",
            "register_service",
            "unregister_service",
            "send_heartbeat",
        }

        # Get all abstract methods from the class
        actual_abstract_methods = {
            name
            for name, method in MessageBusPort.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert abstract_methods == actual_abstract_methods

    def test_message_bus_port_method_signatures(self):
        """Test that port methods have correct signatures."""
        # Test connect method
        connect_method = MessageBusPort.connect
        assert connect_method.__name__ == "connect"
        # Check it's async
        assert hasattr(connect_method, "__isabstractmethod__")

        # Test RPC methods
        register_rpc = MessageBusPort.register_rpc_handler
        assert register_rpc.__name__ == "register_rpc_handler"

        call_rpc = MessageBusPort.call_rpc
        assert call_rpc.__name__ == "call_rpc"

        # Test Event methods
        subscribe = MessageBusPort.subscribe_event
        assert subscribe.__name__ == "subscribe_event"

        publish = MessageBusPort.publish_event
        assert publish.__name__ == "publish_event"

        # Test Command methods
        register_cmd = MessageBusPort.register_command_handler
        assert register_cmd.__name__ == "register_command_handler"

        send_cmd = MessageBusPort.send_command
        assert send_cmd.__name__ == "send_command"


class TestMessageBusPortImplementation:
    """Test cases for MessageBusPort implementation contract."""

    @pytest.fixture
    def mock_implementation(self):
        """Create a mock implementation of MessageBusPort."""

        class MockMessageBus(MessageBusPort):
            def __init__(self):
                self.connected = False
                self.servers = []
                self.rpc_handlers = {}
                self.event_handlers = {}
                self.command_handlers = {}

            async def connect(self, servers: list[str]) -> None:
                self.servers = servers
                self.connected = True

            async def disconnect(self) -> None:
                self.connected = False
                self.servers = []

            async def is_connected(self) -> bool:
                return self.connected

            async def register_rpc_handler(
                self, service: str, method: str, handler
            ) -> None:
                key = f"{service}.{method}"
                self.rpc_handlers[key] = handler

            async def call_rpc(self, request: RPCRequest) -> RPCResponse:
                return RPCResponse(
                    correlation_id=request.message_id,
                    success=True,
                    result={"test": "response"},
                )

            async def subscribe_event(
                self, pattern: str, handler, durable: str | None = None
            ) -> None:
                self.event_handlers[pattern] = handler

            async def publish_event(self, event: Event) -> None:
                pass

            async def register_command_handler(
                self, service: str, command: str, handler
            ) -> None:
                key = f"{service}.{command}"
                self.command_handlers[key] = handler

            async def send_command(
                self, command: Command, track_progress: bool = True
            ) -> dict:
                return {"command_id": command.message_id, "status": "sent"}

            async def register_service(
                self, service_name: str, instance_id: str
            ) -> None:
                pass

            async def unregister_service(
                self, service_name: str, instance_id: str
            ) -> None:
                pass

            async def send_heartbeat(self, service_name: str, instance_id: str) -> None:
                pass

        return MockMessageBus()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, mock_implementation):
        """Test connection lifecycle methods."""
        # Initially not connected
        assert await mock_implementation.is_connected() is False

        # Connect
        servers = ["nats://localhost:4222"]
        await mock_implementation.connect(servers)
        assert await mock_implementation.is_connected() is True
        assert mock_implementation.servers == servers

        # Disconnect
        await mock_implementation.disconnect()
        assert await mock_implementation.is_connected() is False
        assert mock_implementation.servers == []

    @pytest.mark.asyncio
    async def test_rpc_operations(self, mock_implementation):
        """Test RPC registration and calling."""
        # Register handler
        handler = AsyncMock(return_value={"user_id": 123})
        await mock_implementation.register_rpc_handler(
            "user-service", "get_user", handler
        )
        assert "user-service.get_user" in mock_implementation.rpc_handlers

        # Call RPC
        request = RPCRequest(
            method="get_user", params={"id": 123}, target="user-service"
        )
        response = await mock_implementation.call_rpc(request)

        assert isinstance(response, RPCResponse)
        assert response.success is True
        assert response.correlation_id == request.message_id

    @pytest.mark.asyncio
    async def test_event_operations(self, mock_implementation):
        """Test event subscription and publishing."""
        # Subscribe to events
        handler = AsyncMock()
        await mock_implementation.subscribe_event(
            "order.*", handler, durable="test-durable"
        )
        assert "order.*" in mock_implementation.event_handlers

        # Publish event
        event = Event(domain="order", event_type="created", payload={"order_id": "123"})
        await mock_implementation.publish_event(event)
        # No assertion needed - just checking it doesn't raise

    @pytest.mark.asyncio
    async def test_command_operations(self, mock_implementation):
        """Test command registration and sending."""
        # Register command handler
        handler = AsyncMock()
        await mock_implementation.register_command_handler("worker", "process", handler)
        assert "worker.process" in mock_implementation.command_handlers

        # Send command
        command = Command(
            command="process", target="worker", payload={"task_id": "456"}
        )
        result = await mock_implementation.send_command(command, track_progress=True)

        assert isinstance(result, dict)
        assert result["command_id"] == command.message_id
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_service_registration(self, mock_implementation):
        """Test service registration operations."""
        # These methods should not raise
        await mock_implementation.register_service("test-service", "instance-1")
        await mock_implementation.send_heartbeat("test-service", "instance-1")
        await mock_implementation.unregister_service("test-service", "instance-1")


class TestMessageBusPortContract:
    """Test that implementations must follow the port contract."""

    def test_implementation_must_override_all_methods(self):
        """Test that incomplete implementations raise TypeError."""

        # Create incomplete implementation
        class IncompleteMessageBus(MessageBusPort):
            async def connect(self, servers: list[str]) -> None:
                pass

            # Missing other methods

        # Should not be able to instantiate
        with pytest.raises(TypeError) as exc_info:
            IncompleteMessageBus()

        error_msg = str(exc_info.value)
        assert "Can't instantiate abstract class" in error_msg

    def test_implementation_method_signatures_must_match(self):
        """Test that implementations must match method signatures."""
        # This is more of a documentation test - Python doesn't enforce
        # signature matching for abstract methods at runtime, but type
        # checkers like mypy will catch these issues

        class BadImplementation(MessageBusPort):
            # Wrong signature - missing servers parameter
            async def connect(self) -> None:  # type: ignore
                pass

            async def disconnect(self) -> None:
                pass

            async def is_connected(self) -> bool:
                return False

            # Wrong signature - missing service parameter
            async def register_rpc_handler(self, method: str, handler) -> None:  # type: ignore
                pass

            async def call_rpc(self, request: RPCRequest) -> RPCResponse:
                return RPCResponse()

            async def subscribe_event(
                self, pattern: str, handler, durable: str | None = None
            ) -> None:
                pass

            async def publish_event(self, event: Event) -> None:
                pass

            async def register_command_handler(
                self, service: str, command: str, handler
            ) -> None:
                pass

            async def send_command(
                self, command: Command, track_progress: bool = True
            ) -> dict:
                return {}

            async def register_service(
                self, service_name: str, instance_id: str
            ) -> None:
                pass

            async def unregister_service(
                self, service_name: str, instance_id: str
            ) -> None:
                pass

            async def send_heartbeat(self, service_name: str, instance_id: str) -> None:
                pass

        # Can instantiate (Python doesn't check signatures at runtime)
        # but type checkers would catch this
        bad_impl = BadImplementation()
        assert isinstance(bad_impl, MessageBusPort)
