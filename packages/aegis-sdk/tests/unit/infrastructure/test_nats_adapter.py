"""Unit tests for NATSAdapter."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from aegis_sdk.domain.models import RPCRequest, RPCResponse
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.serialization import serialize_to_json


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
