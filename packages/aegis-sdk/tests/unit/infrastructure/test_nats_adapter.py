"""Unit tests for NATSAdapter."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from aegis_sdk.domain.metrics_models import MetricsSnapshot
from aegis_sdk.domain.models import Command, Event, RPCRequest, RPCResponse
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.serialization import (
    SerializationError,
    serialize_to_json,
    serialize_to_msgpack,
)


class TestNATSAdapterInit:
    """Test NATSAdapter initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        adapter = NATSAdapter()

        assert adapter._config is not None
        assert isinstance(adapter._config, NATSConnectionConfig)
        assert adapter._connections == []
        assert adapter._js is None
        assert adapter._current_conn == 0
        assert adapter._metrics is not None
        assert adapter._serializer is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = NATSConnectionConfig(servers=["nats://custom:4222"], pool_size=3, use_msgpack=True)
        adapter = NATSAdapter(config=config)

        assert adapter._config == config
        assert adapter._connections == []

    def test_init_with_metrics(self):
        """Test initialization with custom metrics."""
        mock_metrics = MagicMock()
        adapter = NATSAdapter(metrics=mock_metrics)

        assert adapter._metrics == mock_metrics

    def test_init_extracts_service_identification(self):
        """Test service name and instance ID extraction from config."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")
        config = NATSConnectionConfig(service_name=service_name, instance_id=instance_id)
        adapter = NATSAdapter(config=config)

        assert adapter._service_name == "test-service"
        assert adapter._instance_id == "instance-123"


class TestNATSAdapterConnection:
    """Test NATSAdapter connection management."""

    @pytest.fixture
    def mock_nats_module(self):
        """Mock the nats module."""
        with patch("aegis_sdk.infrastructure.nats_adapter.nats") as mock:
            yield mock

    @pytest.fixture
    def adapter(self):
        """Create adapter with test config."""
        config = NATSConnectionConfig(pool_size=2, enable_jetstream=True)
        return NATSAdapter(config=config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, mock_nats_module):
        """Test successful connection."""
        # Mock NATS connections
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_nats_module.connect = AsyncMock(side_effect=[mock_conn1, mock_conn2])

        # Mock JetStream
        mock_js = AsyncMock()
        mock_conn1.jetstream.return_value = mock_js

        # Mock ensure_streams
        with patch.object(adapter, "_ensure_streams", new_callable=AsyncMock) as mock_ensure:
            # Mock metrics
            adapter._metrics = MagicMock()

            await adapter.connect()

            # Verify connections created
            assert len(adapter._connections) == 2
            assert adapter._connections[0] == mock_conn1
            assert adapter._connections[1] == mock_conn2

            # Verify JetStream initialized
            assert adapter._js == mock_js

            # Verify ensure_streams called
            mock_ensure.assert_called_once()

            # Verify metrics updated
            adapter._metrics.gauge.assert_called_with("nats.connections", 2)

    @pytest.mark.asyncio
    async def test_connect_with_servers_override(self, adapter, mock_nats_module):
        """Test connection with servers override."""
        mock_conn = MagicMock()
        mock_nats_module.connect = AsyncMock(return_value=mock_conn)

        # Mock JetStream
        mock_js = AsyncMock()
        mock_conn.jetstream.return_value = mock_js

        # Mock ensure_streams
        with patch.object(adapter, "_ensure_streams", new_callable=AsyncMock):
            servers = ["nats://override:4222"]
            await adapter.connect(servers)

            # Verify connect called with override servers
            assert mock_nats_module.connect.call_count == 2
            # Verify servers parameter was used
            for call_args in mock_nats_module.connect.call_args_list:
                assert call_args[1]["servers"] == servers

    @pytest.mark.asyncio
    async def test_connect_with_js_domain(self, adapter, mock_nats_module):
        """Test connection with JetStream domain."""
        mock_conn = MagicMock()
        mock_nats_module.connect = AsyncMock(return_value=mock_conn)
        mock_js = MagicMock()
        mock_conn.jetstream.return_value = mock_js

        adapter._config.js_domain = "test-domain"

        with patch.object(adapter, "_ensure_streams", new_callable=AsyncMock):
            await adapter.connect()

            # Verify JetStream initialized with domain
            mock_conn.jetstream.assert_called_with(domain="test-domain")

    @pytest.mark.asyncio
    async def test_connect_with_env_js_domain(self, adapter, mock_nats_module):
        """Test connection with JetStream domain from environment."""
        mock_conn = MagicMock()
        mock_nats_module.connect = AsyncMock(return_value=mock_conn)
        mock_js = MagicMock()
        mock_conn.jetstream.return_value = mock_js

        with patch.dict(os.environ, {"NATS_JS_DOMAIN": "env-domain"}):
            with patch.object(adapter, "_ensure_streams", new_callable=AsyncMock):
                await adapter.connect()

                # Verify JetStream initialized with env domain
                mock_conn.jetstream.assert_called_with(domain="env-domain")

    @pytest.mark.asyncio
    async def test_connect_without_jetstream(self, mock_nats_module):
        """Test connection without JetStream."""
        config = NATSConnectionConfig(enable_jetstream=False)
        adapter = NATSAdapter(config=config)

        mock_conn = MagicMock()
        mock_nats_module.connect = AsyncMock(return_value=mock_conn)

        await adapter.connect()

        assert adapter._js is None
        mock_conn.jetstream.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnection."""
        # Setup mock connections
        mock_conn1 = MagicMock()
        mock_conn1.is_connected = True
        mock_conn1.close = AsyncMock()

        mock_conn2 = MagicMock()
        mock_conn2.is_connected = False  # Already disconnected
        mock_conn2.close = AsyncMock()

        adapter._connections = [mock_conn1, mock_conn2]

        # Mock metrics
        adapter._metrics = MagicMock()

        await adapter.disconnect()

        # Verify close called only on connected clients
        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_not_called()

        # Verify connections cleared
        assert adapter._connections == []
        adapter._metrics.gauge.assert_called_with("nats.connections", 0)

    @pytest.mark.asyncio
    async def test_is_connected(self, adapter):
        """Test connection status check."""
        # No connections
        assert await adapter.is_connected() is False

        # With disconnected connections
        mock_conn1 = MagicMock()
        mock_conn1.is_connected = False
        mock_conn2 = MagicMock()
        mock_conn2.is_connected = False
        adapter._connections = [mock_conn1, mock_conn2]

        assert await adapter.is_connected() is False

        # With at least one connected
        mock_conn1.is_connected = True
        assert await adapter.is_connected() is True


class TestNATSAdapterConnectionPool:
    """Test connection pool management."""

    @pytest.fixture
    def adapter_with_connections(self):
        """Create adapter with mock connections."""
        adapter = NATSAdapter()

        # Mock connections
        conn1 = MagicMock()
        conn1.is_connected = True
        conn2 = MagicMock()
        conn2.is_connected = True
        conn3 = MagicMock()
        conn3.is_connected = False

        adapter._connections = [conn1, conn2, conn3]
        adapter._current_conn = 0

        return adapter

    def test_get_connection_round_robin(self, adapter_with_connections):
        """Test round-robin connection selection."""
        adapter = adapter_with_connections

        # First call should return first connected connection
        conn = adapter._get_connection()
        assert conn.is_connected is True  # Verify it's a connected mock
        assert adapter._current_conn == 1

        # Second call should return second connected connection
        conn = adapter._get_connection()
        assert conn.is_connected is True  # Verify it's a connected mock
        assert adapter._current_conn == 2

        # Third call should skip disconnected connection and wrap around
        conn = adapter._get_connection()
        assert conn.is_connected is True  # Should be connected
        assert adapter._current_conn == 1

    def test_get_connection_no_connections(self):
        """Test getting connection when none exist."""
        adapter = NATSAdapter()

        with pytest.raises(Exception, match="Not connected to NATS"):
            adapter._get_connection()

    def test_get_connection_all_disconnected(self, adapter_with_connections):
        """Test getting connection when all are disconnected."""
        adapter = adapter_with_connections

        # Disconnect all
        for conn in adapter._connections:
            conn.is_connected = False

        with pytest.raises(Exception, match="No active NATS connections"):
            adapter._get_connection()


class TestNATSAdapterStreams:
    """Test JetStream stream management."""

    @pytest.fixture
    def adapter_with_js(self):
        """Create adapter with mock JetStream."""
        adapter = NATSAdapter()
        adapter._js = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_ensure_streams_success(self, adapter_with_js):
        """Test successful stream creation."""
        adapter = adapter_with_js
        mock_js = adapter._js

        # Mock stream_info to raise exception (stream doesn't exist)
        mock_js.stream_info = AsyncMock(
            side_effect=[Exception("not found"), Exception("not found")]
        )
        mock_js.add_stream = AsyncMock()

        await adapter._ensure_streams()

        # Verify streams checked
        expected_calls = [call("EVENTS"), call("COMMANDS")]
        mock_js.stream_info.assert_has_calls(expected_calls)

        # Verify add_stream called for both
        assert mock_js.add_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_ensure_streams_already_exist(self, adapter_with_js):
        """Test when streams already exist."""
        adapter = adapter_with_js
        mock_js = adapter._js

        # Mock stream_info to succeed (streams exist)
        mock_js.stream_info = AsyncMock(return_value=MagicMock())

        await adapter._ensure_streams()

        # Verify no streams created
        mock_js.add_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_streams_no_jetstream(self):
        """Test when JetStream is not initialized."""
        adapter = NATSAdapter()
        adapter._js = None

        # Should not raise error
        await adapter._ensure_streams()


class TestNATSAdapterRPC:
    """Test RPC functionality."""

    @pytest.fixture
    def adapter_with_connection(self):
        """Create adapter with mock connection."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        adapter._connections = [mock_conn]
        return adapter

    @pytest.mark.asyncio
    async def test_register_rpc_handler(self, adapter_with_connection):
        """Test RPC handler registration."""
        adapter = adapter_with_connection
        handler = AsyncMock(return_value={"result": "success"})

        # Make subscribe async
        mock_conn = adapter._connections[0]
        mock_conn.subscribe = AsyncMock()

        await adapter.register_rpc_handler("test-service", "test-method", handler)

        # Verify subscription created
        mock_conn.subscribe.assert_called_once()

        # Check call signature - subscribe(subject, queue=queue_group, cb=wrapper)
        call_args = mock_conn.subscribe.call_args
        # First positional argument is subject
        assert "rpc.test-service.test-method" in call_args[0][0]  # Subject pattern
        # Check keyword arguments
        assert call_args[1]["queue"] == "rpc.test-service"

    @pytest.mark.asyncio
    async def test_call_rpc_success(self, adapter_with_connection):
        """Test successful RPC call."""
        adapter = adapter_with_connection
        mock_conn = adapter._connections[0]

        # Mock response
        response = RPCResponse(correlation_id="123", success=True, result={"data": "test"})
        mock_response_msg = MagicMock()
        mock_response_msg.data = serialize_to_json(response)
        mock_conn.request = AsyncMock(return_value=mock_response_msg)

        # Make RPC call
        request = RPCRequest(method="test", target="service", params={})
        result = await adapter.call_rpc(request)

        # Verify request made
        mock_conn.request.assert_called_once()

        # Verify result
        assert result.success is True
        assert result.result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_call_rpc_timeout(self, adapter_with_connection):
        """Test RPC call timeout."""
        adapter = adapter_with_connection
        mock_conn = adapter._connections[0]

        # Mock timeout
        mock_conn.request = AsyncMock(side_effect=TimeoutError())

        # Make RPC call
        request = RPCRequest(method="test", timeout=1.0)
        result = await adapter.call_rpc(request)

        # Verify timeout response
        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_call_rpc_error(self, adapter_with_connection):
        """Test RPC call with general error."""
        adapter = adapter_with_connection
        mock_conn = adapter._connections[0]

        # Mock error
        mock_conn.request = AsyncMock(side_effect=Exception("Connection error"))

        # Make RPC call
        request = RPCRequest(method="test")
        result = await adapter.call_rpc(request)

        # Verify error response
        assert result.success is False
        assert "Connection error" in result.error


class TestNATSAdapterEvents:
    """Test event publishing and subscription."""

    @pytest.fixture
    def adapter_with_js(self):
        """Create adapter with mock JetStream."""
        adapter = NATSAdapter()
        adapter._js = AsyncMock()
        adapter._metrics = MagicMock()
        return adapter

    @pytest.fixture
    def adapter_with_connection(self):
        """Create adapter with mock connection."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.subscribe = AsyncMock()  # Make subscribe async
        adapter._connections = [mock_conn]
        adapter._js = AsyncMock()
        adapter._metrics = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_publish_event_success(self, adapter_with_js):
        """Test successful event publishing."""
        adapter = adapter_with_js
        event = Event(
            domain="test",
            event_type="created",
            payload={"id": 123},
        )

        await adapter.publish_event(event)

        # Verify JetStream publish called
        adapter._js.publish.assert_called_once()
        call_args = adapter._js.publish.call_args
        assert "events.test.created" in call_args[0]
        adapter._metrics.increment.assert_called_with("events.published.test.created")

    @pytest.mark.asyncio
    async def test_publish_event_with_retry(self, adapter_with_js):
        """Test event publishing with retry on JSON decode error."""
        adapter = adapter_with_js
        # Mock JSON decode error on first two attempts, then success
        adapter._js.publish = AsyncMock(
            side_effect=[
                json.JSONDecodeError("test", "doc", 0),
                json.JSONDecodeError("test", "doc", 0),
                None,
            ]
        )

        event = Event(domain="test", event_type="created", payload={})

        await adapter.publish_event(event)

        # Should have retried 3 times
        assert adapter._js.publish.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_event_max_retries_exceeded(self, adapter_with_js):
        """Test event publishing fails after max retries."""
        adapter = adapter_with_js
        # Mock JSON decode error on all attempts
        adapter._js.publish = AsyncMock(side_effect=json.JSONDecodeError("test", "doc", 0))

        event = Event(domain="test", event_type="created", payload={})

        with pytest.raises(Exception, match="JetStream publish failed after 3 attempts"):
            await adapter.publish_event(event)

        adapter._metrics.increment.assert_called_with("events.publish.json_errors")

    @pytest.mark.asyncio
    async def test_publish_event_no_jetstream(self):
        """Test event publishing without JetStream."""
        adapter = NATSAdapter()
        adapter._js = None

        event = Event(domain="test", event_type="created", payload={})

        with pytest.raises(Exception, match="JetStream not initialized"):
            await adapter.publish_event(event)

    @pytest.mark.asyncio
    async def test_subscribe_event_compete_mode(self, adapter_with_connection):
        """Test event subscription in compete mode."""
        adapter = adapter_with_connection
        adapter._service_name = "test-service"
        handler = AsyncMock()

        await adapter.subscribe_event("events.test.*", handler, mode="compete")

        # Verify subscription with queue group for wildcards
        mock_conn = adapter._connections[0]
        mock_conn.subscribe.assert_called_once()
        call_args = mock_conn.subscribe.call_args
        assert call_args[1]["queue"] == "test-service"

    @pytest.mark.asyncio
    async def test_subscribe_event_broadcast_mode(self, adapter_with_connection):
        """Test event subscription in broadcast mode."""
        adapter = adapter_with_connection
        adapter._instance_id = "instance-123"
        handler = AsyncMock()

        # Test with specific subject (no wildcards)
        await adapter.subscribe_event(
            "events.test.created", handler, mode="broadcast", durable="test-durable"
        )

        # Verify JetStream subscription with unique durable
        adapter._js.subscribe.assert_called_once()
        call_args = adapter._js.subscribe.call_args
        assert call_args[1]["durable"] == "test-durable-instance-123"
        assert "queue" not in call_args[1]

    @pytest.mark.asyncio
    async def test_subscribe_event_invalid_mode(self, adapter_with_js):
        """Test event subscription with invalid mode."""
        adapter = adapter_with_js
        handler = AsyncMock()

        with pytest.raises(ValueError, match="Invalid mode: invalid"):
            await adapter.subscribe_event("events.*", handler, mode="invalid")

    @pytest.mark.asyncio
    async def test_subscribe_event_no_jetstream(self):
        """Test event subscription without JetStream."""
        adapter = NATSAdapter()
        adapter._js = None
        handler = AsyncMock()

        with pytest.raises(Exception, match="JetStream not initialized"):
            await adapter.subscribe_event("events.*", handler)

    @pytest.mark.asyncio
    async def test_event_handler_wrapper_success(self, adapter_with_connection):
        """Test event handler wrapper processing."""
        adapter = adapter_with_connection
        handler = AsyncMock()

        # Subscribe and get the wrapper
        await adapter.subscribe_event("events.test.*", handler, mode="compete")
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message with event data
        event = Event(domain="test", event_type="created", payload={"id": 1})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(event)
        mock_msg.ack = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify handler called and message acked
        handler.assert_called_once()
        mock_msg.ack.assert_called_once()
        adapter._metrics.increment.assert_called_with("events.processed.test.created")

    @pytest.mark.asyncio
    async def test_event_handler_wrapper_error(self, adapter_with_connection):
        """Test event handler wrapper error handling."""
        adapter = adapter_with_connection
        handler = AsyncMock(side_effect=Exception("Handler error"))

        # Subscribe and get the wrapper
        await adapter.subscribe_event("events.test.*", handler, mode="compete")
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message
        event = Event(domain="test", event_type="created", payload={})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(event)
        mock_msg.nak = AsyncMock()

        # Process message - should handle error
        await wrapper(mock_msg)

        # Verify error handling
        mock_msg.nak.assert_called_once()
        adapter._metrics.increment.assert_called_with("events.errors")


class TestNATSAdapterCommands:
    """Test command sending and handling."""

    @pytest.fixture
    def adapter_with_js(self):
        """Create adapter with mock JetStream."""
        adapter = NATSAdapter()
        adapter._js = AsyncMock()
        adapter._metrics = MagicMock()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        adapter._connections = [mock_conn]
        return adapter

    @pytest.mark.asyncio
    async def test_register_command_handler(self, adapter_with_js):
        """Test command handler registration."""
        adapter = adapter_with_js
        handler = AsyncMock(return_value={"result": "success"})

        await adapter.register_command_handler("test-service", "process", handler)

        # Verify JetStream subscription
        adapter._js.subscribe.assert_called_once()
        call_args = adapter._js.subscribe.call_args
        assert "commands.test-service.process" in call_args[0]
        assert call_args[1]["durable"] == "test-service-process"
        assert call_args[1]["manual_ack"] is True

    @pytest.mark.asyncio
    async def test_register_command_handler_no_jetstream(self):
        """Test command handler registration without JetStream."""
        adapter = NATSAdapter()
        adapter._js = None
        handler = AsyncMock()

        with pytest.raises(Exception, match="JetStream not initialized"):
            await adapter.register_command_handler("service", "cmd", handler)

    @pytest.mark.asyncio
    async def test_command_handler_wrapper_success(self, adapter_with_js):
        """Test command handler wrapper processing."""
        adapter = adapter_with_js
        handler = AsyncMock(return_value={"status": "completed"})

        # Register and get the wrapper
        await adapter.register_command_handler("service", "process", handler)
        wrapper = adapter._js.subscribe.call_args[1]["cb"]

        # Create mock message with command
        cmd = Command(
            command="process",
            target="service",
            payload={"data": "test"},
        )
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(cmd)
        mock_msg.ack = AsyncMock()

        # Mock connection for progress reporting
        adapter._connections[0].publish = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify handler called and completion sent
        handler.assert_called_once()
        # Verify progress callback was passed
        assert callable(handler.call_args[0][1])
        mock_msg.ack.assert_called_once()
        adapter._metrics.increment.assert_called_with("commands.processed.service.process")

        # Verify completion message sent
        adapter._connections[0].publish.assert_called()
        publish_call = adapter._connections[0].publish.call_args
        assert "commands.callback" in publish_call[0][0]

    @pytest.mark.asyncio
    async def test_command_handler_wrapper_error(self, adapter_with_js):
        """Test command handler wrapper error handling."""
        adapter = adapter_with_js
        handler = AsyncMock(side_effect=Exception("Command failed"))

        # Register and get the wrapper
        await adapter.register_command_handler("service", "process", handler)
        wrapper = adapter._js.subscribe.call_args[1]["cb"]

        # Create mock message
        cmd = Command(command="process", target="service", payload={})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(cmd)
        mock_msg.nak = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify error handling
        mock_msg.nak.assert_called_once()
        adapter._metrics.increment.assert_called_with("commands.errors")

    @pytest.mark.asyncio
    async def test_send_command_with_progress(self, adapter_with_js):
        """Test sending command with progress tracking."""
        adapter = adapter_with_js
        mock_conn = adapter._connections[0]
        mock_conn.subscribe = AsyncMock()
        mock_conn.publish = AsyncMock()

        # Mock JetStream publish with ACK
        mock_ack = MagicMock()
        mock_ack.stream = "COMMANDS"
        mock_ack.seq = 123
        adapter._js.publish = AsyncMock(return_value=mock_ack)

        command = Command(
            command="process",
            target="service",
            payload={"data": "test"},
            timeout=5.0,
        )

        # Setup completion handler to be triggered
        completion_data = {
            "command_id": command.message_id,
            "status": "completed",
            "result": {"ok": True},
        }

        async def trigger_completion():
            # Wait a bit then call the completion handler
            await asyncio.sleep(0.1)
            # Get the completion handler from subscribe calls
            for call_args in mock_conn.subscribe.call_args_list:
                if "commands.callback" in str(call_args[0]):
                    handler = call_args[1]["cb"]
                    mock_msg = MagicMock()
                    mock_msg.data = json.dumps(completion_data).encode()
                    await handler(mock_msg)
                    break

        # Start completion trigger in background
        asyncio.create_task(trigger_completion())

        # Send command
        result = await adapter.send_command(command, track_progress=True)

        # Verify subscriptions created for progress and completion
        assert mock_conn.subscribe.call_count == 2
        # Verify result
        assert result["status"] == "completed"
        assert result["result"] == {"ok": True}

    @pytest.mark.asyncio
    async def test_send_command_without_progress(self, adapter_with_js):
        """Test sending command without progress tracking."""
        adapter = adapter_with_js

        # Mock JetStream publish with ACK
        mock_ack = MagicMock()
        mock_ack.stream = "COMMANDS"
        mock_ack.seq = 456
        adapter._js.publish = AsyncMock(return_value=mock_ack)

        command = Command(command="process", target="service", payload={})

        result = await adapter.send_command(command, track_progress=False)

        # Verify immediate return with ACK info
        assert result["stream"] == "COMMANDS"
        assert result["seq"] == 456
        assert result["command_id"] == command.message_id

    @pytest.mark.asyncio
    async def test_send_command_timeout(self, adapter_with_js):
        """Test command sending with timeout."""
        adapter = adapter_with_js
        mock_conn = adapter._connections[0]
        mock_conn.subscribe = AsyncMock()

        # Mock JetStream publish
        adapter._js.publish = AsyncMock(return_value=MagicMock(stream="COMMANDS", seq=1))

        command = Command(command="process", target="service", payload={}, timeout=0.1)

        # Don't trigger completion - let it timeout
        result = await adapter.send_command(command, track_progress=True)

        # Should return timeout error
        assert result["error"] == "Command timeout"

    @pytest.mark.asyncio
    async def test_send_command_no_jetstream(self):
        """Test sending command without JetStream."""
        adapter = NATSAdapter()
        adapter._js = None

        command = Command(command="process", payload={})

        with pytest.raises(Exception, match="JetStream not initialized"):
            await adapter.send_command(command)

    @pytest.mark.asyncio
    async def test_send_command_with_retry(self, adapter_with_js):
        """Test command sending with retry on JSON decode error."""
        adapter = adapter_with_js
        # Mock JSON decode error on first attempt, then success
        mock_ack = MagicMock(stream="COMMANDS", seq=789)
        adapter._js.publish = AsyncMock(
            side_effect=[json.JSONDecodeError("test", "doc", 0), mock_ack]
        )

        command = Command(command="process", target="service", payload={})

        result = await adapter.send_command(command, track_progress=False)

        # Should have retried and succeeded
        assert adapter._js.publish.call_count == 2
        assert result["seq"] == 789


class TestNATSAdapterServiceRegistry:
    """Test service registration functionality."""

    @pytest.fixture
    def adapter_with_connection(self):
        """Create adapter with mock connection."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.publish = AsyncMock()
        adapter._connections = [mock_conn]
        adapter._metrics = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_register_service(self, adapter_with_connection):
        """Test service registration."""
        adapter = adapter_with_connection

        await adapter.register_service("test-service", "instance-123")

        # Verify registration message published
        mock_conn = adapter._connections[0]
        mock_conn.publish.assert_called_once()
        call_args = mock_conn.publish.call_args
        assert "registry.register" in call_args[0][0]

        # Verify registration data
        data = json.loads(call_args[0][1].decode())
        assert data["service_name"] == "test-service"
        assert data["instance_id"] == "instance-123"
        assert "timestamp" in data

        # Verify service info stored
        assert adapter._service_name == "test-service"
        assert adapter._instance_id == "instance-123"

        # Verify metrics
        adapter._metrics.increment.assert_called_with("services.registered")

    @pytest.mark.asyncio
    async def test_unregister_service(self, adapter_with_connection):
        """Test service unregistration."""
        adapter = adapter_with_connection

        await adapter.unregister_service("test-service", "instance-123")

        # Verify unregistration message published
        mock_conn = adapter._connections[0]
        mock_conn.publish.assert_called_once()
        call_args = mock_conn.publish.call_args
        assert "registry.unregister" in call_args[0][0]

        # Verify unregistration data
        data = json.loads(call_args[0][1].decode())
        assert data["service_name"] == "test-service"
        assert data["instance_id"] == "instance-123"

        # Verify metrics
        adapter._metrics.increment.assert_called_with("services.unregistered")

    @pytest.mark.asyncio
    async def test_send_heartbeat(self, adapter_with_connection):
        """Test sending service heartbeat."""
        adapter = adapter_with_connection

        # Mock metrics with MetricsSnapshot
        from aegis_sdk.domain.metrics_models import MetricsSummaryData

        metrics_snapshot = MetricsSnapshot(
            uptime_seconds=100.0,
            counters={"requests": 50},
            gauges={"connections": 5},
            summaries={"latency": MetricsSummaryData(average=10.5, count=100)},
        )
        adapter._metrics.get_all = MagicMock(return_value=metrics_snapshot)

        await adapter.send_heartbeat("test-service", "instance-123")

        # Verify heartbeat message published
        mock_conn = adapter._connections[0]
        mock_conn.publish.assert_called_once()
        call_args = mock_conn.publish.call_args
        assert "heartbeat.test-service" in call_args[0][0]

        # Verify heartbeat data
        data = json.loads(call_args[0][1].decode())
        assert data["instance_id"] == "instance-123"
        assert "timestamp" in data
        assert "metrics" in data
        assert data["metrics"]["uptime_seconds"] == 100.0

        # Verify metrics
        adapter._metrics.increment.assert_called_with("heartbeats.sent")

    @pytest.mark.asyncio
    async def test_send_heartbeat_legacy_metrics(self, adapter_with_connection):
        """Test sending heartbeat with legacy metrics format."""
        adapter = adapter_with_connection

        # Mock metrics with legacy dict format
        legacy_metrics = {
            "uptime": 200.0,
            "counters": {"calls": 100},
            "gauges": {"memory": 1024},
            "summaries": {"response_time": {"p99": 50}},
        }
        adapter._metrics.get_all = MagicMock(return_value=legacy_metrics)

        await adapter.send_heartbeat("test-service", "instance-123")

        # Verify heartbeat sent with converted metrics
        mock_conn = adapter._connections[0]
        data = json.loads(mock_conn.publish.call_args[0][1].decode())
        assert data["metrics"]["uptime_seconds"] == 200.0


class TestNATSAdapterRPCHandlerWrapper:
    """Test RPC handler wrapper functionality."""

    @pytest.fixture
    def adapter_with_connection(self):
        """Create adapter with mock connection."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.subscribe = AsyncMock()
        adapter._connections = [mock_conn]
        adapter._metrics = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_rpc_handler_wrapper_success(self, adapter_with_connection):
        """Test RPC handler wrapper with successful execution."""
        adapter = adapter_with_connection
        handler = AsyncMock(return_value={"result": "success"})

        # Register handler and get wrapper
        await adapter.register_rpc_handler("service", "method", handler)
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message
        request = RPCRequest(method="method", params={"test": "data"})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(request)
        mock_msg.respond = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify handler called
        handler.assert_called_once_with({"test": "data"})

        # Verify response sent
        mock_msg.respond.assert_called_once()
        response_data = mock_msg.respond.call_args[0][0]
        # Response should be serialized
        assert isinstance(response_data, bytes)

        # Verify metrics
        adapter._metrics.increment.assert_called_with("rpc.service.method.success")

    @pytest.mark.asyncio
    async def test_rpc_handler_wrapper_with_msgpack(self, adapter_with_connection):
        """Test RPC handler wrapper with MessagePack data."""
        adapter = adapter_with_connection
        adapter._config.use_msgpack = True
        adapter._serializer = MagicMock()
        adapter._serializer.serialize = MagicMock(return_value=b"response")
        handler = AsyncMock(return_value={"result": "ok"})

        # Register handler and get wrapper
        await adapter.register_rpc_handler("service", "method", handler)
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message with MessagePack data
        request = RPCRequest(method="method", params={"data": "test"})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_msgpack(request)
        mock_msg.respond = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify handler called
        handler.assert_called_once()
        # Verify response sent
        mock_msg.respond.assert_called_once_with(b"response")

    @pytest.mark.asyncio
    async def test_rpc_handler_wrapper_serialization_error(self, adapter_with_connection):
        """Test RPC handler wrapper with serialization error fallback."""
        adapter = adapter_with_connection
        handler = AsyncMock(return_value={"result": "ok"})

        # Register handler and get wrapper
        await adapter.register_rpc_handler("service", "method", handler)
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message with invalid data that causes SerializationError
        mock_msg = MagicMock()
        # First attempt to deserialize will fail, fallback to JSON
        request_data = {"method": "method", "params": {}, "message_id": "123"}
        mock_msg.data = json.dumps(request_data).encode()
        mock_msg.respond = AsyncMock()

        # Mock detect_and_deserialize to raise SerializationError
        with patch("aegis_sdk.infrastructure.nats_adapter.detect_and_deserialize") as mock_detect:
            mock_detect.side_effect = SerializationError("Invalid format")

            # Process message
            await wrapper(mock_msg)

            # Handler should still be called after fallback
            handler.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_rpc_handler_wrapper_error(self, adapter_with_connection):
        """Test RPC handler wrapper with handler error."""
        adapter = adapter_with_connection
        handler = AsyncMock(side_effect=Exception("Handler failed"))

        # Register handler and get wrapper
        await adapter.register_rpc_handler("service", "method", handler)
        wrapper = adapter._connections[0].subscribe.call_args[1]["cb"]

        # Create mock message
        request = RPCRequest(method="method", params={})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(request)
        mock_msg.respond = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify error response sent
        mock_msg.respond.assert_called_once()
        # Verify metrics
        adapter._metrics.increment.assert_called_with("rpc.service.method.error")


class TestNATSAdapterIntegration:
    """Test integration scenarios."""

    def test_serializer_configuration(self):
        """Test serializer is configured based on config."""
        # JSON serializer (default)
        config = NATSConnectionConfig(use_msgpack=False)
        adapter = NATSAdapter(config=config)
        assert adapter._serializer is not None

        # MessagePack serializer
        config = NATSConnectionConfig(use_msgpack=True)
        adapter = NATSAdapter(config=config)
        assert adapter._serializer is not None

    def test_metrics_integration(self):
        """Test metrics are properly tracked."""
        mock_metrics = MagicMock()
        adapter = NATSAdapter(metrics=mock_metrics)

        # Connection metrics
        mock_metrics.gauge.reset_mock()
        asyncio.run(adapter.disconnect())
        mock_metrics.gauge.assert_called_with("nats.connections", 0)

    @pytest.mark.asyncio
    async def test_full_rpc_flow(self):
        """Test complete RPC flow with mocked components."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.subscribe = AsyncMock()
        mock_conn.request = AsyncMock()
        adapter._connections = [mock_conn]

        # Register handler
        handler = AsyncMock(return_value={"status": "ok"})
        await adapter.register_rpc_handler("test", "ping", handler)

        # Verify handler registration
        mock_conn.subscribe.assert_called_once()

        # Make RPC call
        response = RPCResponse(correlation_id="123", success=True, result={"status": "ok"})
        mock_response_msg = MagicMock()
        mock_response_msg.data = serialize_to_json(response)
        mock_conn.request.return_value = mock_response_msg

        request = RPCRequest(method="ping", target="test")
        result = await adapter.call_rpc(request)

        assert result.success is True
        assert result.result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_progress_reporter_in_command_handler(self):
        """Test progress reporter functionality in command handler."""
        adapter = NATSAdapter()
        adapter._js = AsyncMock()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.publish = AsyncMock()
        adapter._connections = [mock_conn]
        adapter._metrics = MagicMock()

        # Track progress reports
        progress_reports = []

        async def test_handler(cmd, report_progress):
            # Report progress
            await report_progress(25, "starting")
            progress_reports.append(25)
            await report_progress(50, "halfway")
            progress_reports.append(50)
            await report_progress(100, "done")
            progress_reports.append(100)
            return {"completed": True}

        # Register handler and get wrapper
        await adapter.register_command_handler("service", "process", test_handler)
        wrapper = adapter._js.subscribe.call_args[1]["cb"]

        # Create mock message
        cmd = Command(command="process", target="service", payload={})
        mock_msg = MagicMock()
        mock_msg.data = serialize_to_json(cmd)
        mock_msg.ack = AsyncMock()

        # Process message
        await wrapper(mock_msg)

        # Verify progress reports were sent
        assert progress_reports == [25, 50, 100]
        # Should have 3 progress reports + 1 completion
        assert mock_conn.publish.call_count == 4

    @pytest.mark.asyncio
    async def test_call_rpc_with_different_target_formats(self):
        """Test RPC call with different target format parsing."""
        adapter = NATSAdapter()
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.request = AsyncMock()
        adapter._connections = [mock_conn]
        adapter._metrics = MagicMock()

        # Mock response
        response = RPCResponse(correlation_id="123", success=True, result={})
        mock_response_msg = MagicMock()
        mock_response_msg.data = serialize_to_json(response)
        mock_conn.request.return_value = mock_response_msg

        # Test with dotted target
        request = RPCRequest(method="test", target="service.component")
        await adapter.call_rpc(request)
        assert "rpc.service.test" in mock_conn.request.call_args[0][0]

        # Test with simple target
        request = RPCRequest(method="test", target="simple")
        await adapter.call_rpc(request)
        assert "rpc.simple.test" in mock_conn.request.call_args[0][0]

        # Test with no target
        request = RPCRequest(method="test", target=None)
        await adapter.call_rpc(request)
        assert "rpc.unknown.test" in mock_conn.request.call_args[0][0]
