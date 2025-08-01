"""Integration tests for MessageBusPort with NATS implementation."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from aegis_sdk.domain.models import Command, Event, RPCRequest
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.ports.message_bus import MessageBusPort


@pytest.fixture
def mock_nats_client():
    """Create a mock NATS client."""
    client = AsyncMock(spec=NATSClient)
    client.is_connected = True
    return client


@pytest.fixture
def mock_jetstream():
    """Create a mock JetStream context."""
    js = AsyncMock(spec=JetStreamContext)
    return js


@pytest_asyncio.fixture
async def nats_adapter(mock_nats_client, mock_jetstream):
    """Create a NATS adapter with mocked connections."""
    with patch("aegis_sdk.infrastructure.nats_adapter.nats") as mock_nats:
        # Mock the connect function to return our mock client
        mock_nats.connect = AsyncMock(return_value=mock_nats_client)
        mock_nats_client.jetstream.return_value = mock_jetstream

        # Mock stream creation
        mock_jetstream.stream_info.side_effect = Exception("Stream not found")
        mock_jetstream.add_stream = AsyncMock()

        adapter = NATSAdapter()
        await adapter.connect(["nats://localhost:4222"])

        yield adapter

        await adapter.disconnect()


class TestMessageBusIntegration:
    """Integration tests for MessageBusPort implementation."""

    @pytest.mark.asyncio
    async def test_adapter_implements_port_interface(self, nats_adapter):
        """Test that NATSAdapter properly implements MessageBusPort."""
        assert isinstance(nats_adapter, MessageBusPort)

        # Verify all required methods are present
        required_methods = [
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
        ]

        for method in required_methods:
            assert hasattr(nats_adapter, method)
            assert callable(getattr(nats_adapter, method))

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self):
        """Test complete connection lifecycle."""
        with patch("aegis_sdk.infrastructure.nats_adapter.nats") as mock_nats:
            mock_client = AsyncMock(spec=NATSClient)
            mock_client.is_connected = True
            mock_nats.connect = AsyncMock(return_value=mock_client)

            mock_js = AsyncMock(spec=JetStreamContext)
            mock_client.jetstream.return_value = mock_js
            mock_js.stream_info.side_effect = Exception("Stream not found")
            mock_js.add_stream = AsyncMock()

            adapter = NATSAdapter(pool_size=3)

            # Initially not connected
            assert not await adapter.is_connected()

            # Connect
            await adapter.connect(["nats://localhost:4222", "nats://localhost:4223"])
            assert await adapter.is_connected()

            # Verify connection pool
            assert len(adapter._connections) == 3
            assert adapter._js is not None

            # Disconnect
            await adapter.disconnect()
            assert not await adapter.is_connected()

    @pytest.mark.asyncio
    async def test_rpc_round_trip(self, nats_adapter):
        """Test complete RPC request/response cycle."""
        # Register RPC handler
        handler_called = False
        handler_params = None

        async def test_handler(params):
            nonlocal handler_called, handler_params
            handler_called = True
            handler_params = params
            return {"result": "success", "echo": params.get("message")}

        await nats_adapter.register_rpc_handler("test_service", "echo", test_handler)

        # Get the registered callback
        mock_nc = nats_adapter._connections[0]
        wrapper = mock_nc.subscribe.call_args[1]["cb"]

        # Simulate incoming RPC request
        mock_msg = Mock()
        mock_msg.data = b'{"message_id": "123", "method": "echo", "params": {"message": "hello"}}'
        mock_msg.respond = AsyncMock()

        # Process the request
        await wrapper(mock_msg)

        # Verify handler was called
        assert handler_called
        assert handler_params == {"message": "hello"}

        # Verify response was sent
        mock_msg.respond.assert_called_once()
        response_data = mock_msg.respond.call_args[0][0]
        assert b"success" in response_data

    @pytest.mark.asyncio
    async def test_event_pub_sub(self, nats_adapter):
        """Test event publishing and subscription."""
        # Track received events
        received_events = []

        async def event_handler(event):
            received_events.append(event)

        # Subscribe to events
        await nats_adapter.subscribe_event("events.user.created", event_handler)

        # Get the subscription callback
        mock_js = nats_adapter._js
        sub_wrapper = mock_js.subscribe.call_args[1]["cb"]

        # Publish an event
        event = Event(
            domain="user", event_type="created", payload={"user_id": "123", "name": "Test User"}
        )
        await nats_adapter.publish_event(event)

        # Simulate receiving the published event
        mock_msg = Mock()
        mock_msg.data = event.model_dump_json().encode()
        mock_msg.ack = AsyncMock()

        await sub_wrapper(mock_msg)

        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].domain == "user"
        assert received_events[0].event_type == "created"
        assert received_events[0].payload["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_command_with_progress(self, nats_adapter):
        """Test command execution with progress reporting."""
        # Track command execution
        command_received = None
        progress_reports = []

        async def command_handler(cmd, progress_reporter):
            nonlocal command_received
            command_received = cmd

            # Report progress
            await progress_reporter(25, "Starting")
            await asyncio.sleep(0.01)
            await progress_reporter(50, "Processing")
            await asyncio.sleep(0.01)
            await progress_reporter(100, "Complete")

            return {"status": "completed", "result": "success"}

        # Register command handler
        await nats_adapter.register_command_handler("worker", "process", command_handler)

        # Get the command handler wrapper
        mock_js = nats_adapter._js
        cmd_wrapper = mock_js.subscribe.call_args[1]["cb"]

        # Create and send command
        command = Command(target="worker", command="process", payload={"task": "test_task"})

        # Mock the command sending with progress tracking
        mock_nc = nats_adapter._connections[0]
        progress_callback = None
        completion_callback = None

        async def capture_callbacks(subject, cb=None, **kwargs):
            nonlocal progress_callback, completion_callback
            if "progress" in subject:
                progress_callback = cb
            elif "callback" in subject:
                completion_callback = cb
            sub_mock = AsyncMock()
            sub_mock.unsubscribe = AsyncMock()
            return sub_mock

        mock_nc.subscribe = capture_callbacks
        mock_js.publish = AsyncMock()

        # Start command in background
        send_task = asyncio.create_task(nats_adapter.send_command(command, track_progress=True))

        # Wait for subscriptions
        await asyncio.sleep(0.1)

        # Simulate command execution
        mock_msg = Mock()
        mock_msg.data = command.model_dump_json().encode()
        mock_msg.ack = AsyncMock()
        mock_nc.publish = AsyncMock()

        await cmd_wrapper(mock_msg)

        # Verify progress was reported
        assert mock_nc.publish.call_count >= 3  # Progress updates + completion

        # Simulate completion
        if completion_callback:
            completion_msg = Mock()
            completion_msg.data = (
                b'{"command_id": "'
                + command.message_id.encode()
                + b'", "status": "completed", "result": {"status": "completed", "result": "success"}}'
            )
            await completion_callback(completion_msg)

        # Get result
        result = await send_task
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_service_registration_flow(self, nats_adapter):
        """Test service registration and heartbeat flow."""
        mock_nc = nats_adapter._connections[0]
        mock_nc.publish = AsyncMock()

        # Register service
        await nats_adapter.register_service("test_service", "instance_001")

        # Verify registration was published
        mock_nc.publish.assert_called()
        reg_call = mock_nc.publish.call_args_list[0]
        assert "registry.register" in reg_call[0][0]

        # Send heartbeat
        await nats_adapter.send_heartbeat("test_service", "instance_001")

        # Verify heartbeat was published
        hb_call = mock_nc.publish.call_args_list[-1]
        assert "heartbeat.test_service" in hb_call[0][0]

        # Unregister service
        await nats_adapter.unregister_service("test_service", "instance_001")

        # Verify unregistration was published
        unreg_call = mock_nc.publish.call_args_list[-1]
        assert "registry.unregister" in unreg_call[0][0]

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, nats_adapter):
        """Test error handling and recovery mechanisms."""
        # Test RPC timeout
        request = RPCRequest(
            target="unavailable_service", method="test_method", params={}, timeout=0.1
        )

        mock_nc = nats_adapter._connections[0]
        mock_nc.request = AsyncMock(side_effect=asyncio.TimeoutError())

        response = await nats_adapter.call_rpc(request)
        assert not response.success
        assert "Timeout" in response.error

        # Test event publishing retry on JSON error
        mock_js = nats_adapter._js
        mock_js.publish.side_effect = [
            Exception("JSONDecodeError"),
            Mock(),  # Success on second attempt
        ]

        event = Event(domain="test", event_type="error_test", payload={})
        # Should not raise, retries internally
        await nats_adapter.publish_event(event)

        assert mock_js.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_msgpack_json_interoperability(self):
        """Test that msgpack and JSON serialization work together."""
        # Create two adapters with different serialization
        with patch("aegis_sdk.infrastructure.nats_adapter.nats") as mock_nats:
            mock_client = AsyncMock(spec=NATSClient)
            mock_client.is_connected = True
            mock_nats.connect = AsyncMock(return_value=mock_client)

            mock_js = AsyncMock(spec=JetStreamContext)
            mock_client.jetstream.return_value = mock_js
            mock_js.stream_info.side_effect = Exception("Stream not found")
            mock_js.add_stream = AsyncMock()

            msgpack_adapter = NATSAdapter(use_msgpack=True)
            json_adapter = NATSAdapter(use_msgpack=False)

            await msgpack_adapter.connect(["nats://localhost:4222"])
            await json_adapter.connect(["nats://localhost:4222"])

            # Register handler on msgpack adapter
            received_params = None

            async def handler(params):
                nonlocal received_params
                received_params = params
                return {"received": True}

            await msgpack_adapter.register_rpc_handler("test", "method", handler)
            wrapper = msgpack_adapter._connections[0].subscribe.call_args[1]["cb"]

            # Send JSON message to msgpack handler
            mock_msg = Mock()
            mock_msg.data = (
                b'{"message_id": "123", "method": "method", "params": {"test": "json_to_msgpack"}}'
            )
            mock_msg.respond = AsyncMock()

            await wrapper(mock_msg)

            # Verify it was handled correctly
            assert received_params == {"test": "json_to_msgpack"}

            await msgpack_adapter.disconnect()
            await json_adapter.disconnect()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, nats_adapter):
        """Test concurrent operations on the message bus."""
        # Register multiple handlers
        call_counts = {"rpc": 0, "events": 0, "commands": 0}

        async def rpc_handler(params):
            call_counts["rpc"] += 1
            await asyncio.sleep(0.01)
            return {"count": call_counts["rpc"]}

        async def event_handler(event):
            call_counts["events"] += 1
            await asyncio.sleep(0.01)

        async def command_handler(cmd, progress):
            call_counts["commands"] += 1
            await asyncio.sleep(0.01)
            return {"count": call_counts["commands"]}

        # Register all handlers
        await nats_adapter.register_rpc_handler("test", "concurrent", rpc_handler)
        await nats_adapter.subscribe_event("test.concurrent", event_handler)
        await nats_adapter.register_command_handler("test", "concurrent", command_handler)

        # Create multiple concurrent operations
        tasks = []

        # RPC calls
        for i in range(5):
            request = RPCRequest(target="test", method="concurrent", params={"i": i})
            tasks.append(nats_adapter.call_rpc(request))

        # Event publishes
        for i in range(5):
            event = Event(domain="test", event_type="concurrent", payload={"i": i})
            tasks.append(nats_adapter.publish_event(event))

        # Command sends
        for i in range(5):
            command = Command(target="test", command="concurrent", payload={"i": i})
            tasks.append(nats_adapter.send_command(command, track_progress=False))

        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions
        for result in results:
            assert not isinstance(result, Exception)
