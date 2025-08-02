"""Contract tests for MessageBusPort implementations.

These tests define the contract that all MessageBusPort implementations
must satisfy, ensuring consistent behavior across different adapters.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import pytest

from aegis_sdk.domain.models import Command, Event
from aegis_sdk.ports.message_bus import MessageBusPort
from tests.builders import CommandBuilder, EventBuilder, RPCRequestBuilder


class MessageBusContractTest(ABC):
    """Abstract base class for MessageBusPort contract tests.

    Concrete test classes should inherit from this and implement
    the create_message_bus method to provide their specific implementation.
    """

    @abstractmethod
    async def create_message_bus(self) -> MessageBusPort:
        """Create a MessageBusPort implementation for testing.

        Returns:
            A configured MessageBusPort instance
        """
        ...

    @pytest.fixture
    async def message_bus(self) -> MessageBusPort:
        """Fixture that provides a MessageBusPort instance."""
        bus = await self.create_message_bus()
        yield bus
        await bus.disconnect()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, message_bus: MessageBusPort):
        """Test connection and disconnection."""
        # Should be connected after fixture setup
        assert await message_bus.is_connected()

        # Disconnect and verify
        await message_bus.disconnect()
        assert not await message_bus.is_connected()

        # Reconnect
        await message_bus.connect(["nats://localhost:4222"])
        assert await message_bus.is_connected()

    @pytest.mark.asyncio
    async def test_rpc_request_response(self, message_bus: MessageBusPort):
        """Test RPC request/response pattern."""
        received_params = None

        # Register handler
        async def test_handler(params: dict[str, Any]) -> dict[str, Any]:
            nonlocal received_params
            received_params = params
            return {"result": params.get("input", 0) * 2}

        await message_bus.register_rpc_handler("test_service", "multiply", test_handler)

        # Make RPC call
        request = (
            RPCRequestBuilder()
            .with_method("multiply")
            .with_target("test_service")
            .with_params(input=5)
            .build()
        )

        response = await message_bus.call_rpc(request)

        # Verify response
        assert response.success
        assert response.result == {"result": 10}
        assert received_params == {"input": 5}

    @pytest.mark.asyncio
    async def test_rpc_error_handling(self, message_bus: MessageBusPort):
        """Test RPC error handling."""

        # Register handler that raises an error
        async def error_handler(params: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("Test error")

        await message_bus.register_rpc_handler("test_service", "error_method", error_handler)

        # Make RPC call
        request = (
            RPCRequestBuilder().with_method("error_method").with_target("test_service").build()
        )

        response = await message_bus.call_rpc(request)

        # Verify error response
        assert not response.success
        assert response.error is not None
        assert "Test error" in response.error

    @pytest.mark.asyncio
    async def test_rpc_timeout(self, message_bus: MessageBusPort):
        """Test RPC timeout handling."""

        # Register slow handler
        async def slow_handler(params: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(2)
            return {"result": "too late"}

        await message_bus.register_rpc_handler("test_service", "slow_method", slow_handler)

        # Make RPC call with short timeout
        request = (
            RPCRequestBuilder()
            .with_method("slow_method")
            .with_target("test_service")
            .with_timeout(0.1)
            .build()
        )

        response = await message_bus.call_rpc(request)

        # Verify timeout response
        assert not response.success
        assert response.error is not None
        assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_event_publish_subscribe(self, message_bus: MessageBusPort):
        """Test event publishing and subscription."""
        received_events = []

        # Subscribe to events
        async def event_handler(event: Event) -> None:
            received_events.append(event)

        await message_bus.subscribe_event("test.*", event_handler)

        # Give subscription time to establish
        await asyncio.sleep(0.1)

        # Publish events
        event1 = EventBuilder().with_domain("test").with_type("created").build()
        event2 = EventBuilder().with_domain("test").with_type("updated").build()
        event3 = EventBuilder().with_domain("other").with_type("created").build()

        await message_bus.publish_event(event1)
        await message_bus.publish_event(event2)
        await message_bus.publish_event(event3)  # Should not be received

        # Wait for events to be processed
        await asyncio.sleep(0.2)

        # Verify only matching events were received
        assert len(received_events) == 2
        assert received_events[0].event_type == "created"
        assert received_events[1].event_type == "updated"

    @pytest.mark.asyncio
    async def test_command_send_and_handle(self, message_bus: MessageBusPort):
        """Test command sending and handling."""
        command_received = None

        # Register command handler
        async def command_handler(cmd: Command, progress_callback: Any) -> dict[str, Any]:
            nonlocal command_received
            command_received = cmd

            # Report progress
            await progress_callback(0.5, "halfway")
            await progress_callback(1.0, "completed")

            return {"result": "command processed"}

        await message_bus.register_command_handler("test_service", "process_data", command_handler)

        # Send command
        command = (
            CommandBuilder()
            .with_command("process_data")
            .with_target("test_service")
            .with_payload(data="test")
            .build()
        )

        result = await message_bus.send_command(command, track_progress=True)

        # Verify command was handled
        assert command_received is not None
        assert command_received.payload == {"data": "test"}
        assert result.get("result") == "command processed"

    @pytest.mark.asyncio
    async def test_service_registration(self, message_bus: MessageBusPort):
        """Test service registration and heartbeat."""
        # Register service
        await message_bus.register_service("test_service", "instance-123")

        # Send heartbeat
        await message_bus.send_heartbeat("test_service", "instance-123")

        # Unregister service
        await message_bus.unregister_service("test_service", "instance-123")

        # No exceptions should be raised
        assert True
