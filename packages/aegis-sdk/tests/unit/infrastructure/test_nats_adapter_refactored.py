"""Unit tests for refactored NATS adapter implementation."""

import json
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from nats.aio.client import Client as NATSClient

from aegis_sdk.domain.models import Event, RPCRequest, RPCResponse
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


class TestNATSAdapterConfiguration:
    """Tests for NATS adapter with configuration objects."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        adapter = NATSAdapter()
        assert adapter._config.pool_size == 1
        assert adapter._config.use_msgpack is True
        assert adapter._config.servers == ["nats://localhost:4222"]
        assert adapter._connections == []
        assert adapter._js is None
        assert adapter._service_name is None
        assert adapter._instance_id is None

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = NATSConnectionConfig(
            servers=["nats://server1:4222", "nats://server2:4222"],
            pool_size=3,
            use_msgpack=False,
            service_name="test-service",
            instance_id="instance-123",
            js_domain="test-domain",
        )
        adapter = NATSAdapter(config=config)

        assert adapter._config == config
        assert adapter._service_name == "test-service"
        assert adapter._instance_id == "instance-123"
        assert adapter._serializer is not None

    def test_service_identification_extraction(self):
        """Test extraction of service identification from config."""
        config = NATSConnectionConfig(
            service_name=ServiceName(value="my-service"),
            instance_id=InstanceId(value="my-instance"),
        )
        adapter = NATSAdapter(config=config)

        assert adapter._service_name == "my-service"
        assert adapter._instance_id == "my-instance"


class TestNATSAdapterConnection:
    """Tests for connection management with configuration."""

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    async def test_connect_with_config_servers(self, mock_connect):
        """Test connection uses servers from config."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_nc.jetstream.return_value = AsyncMock()
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig(
            servers=["nats://config-server:4222"],
            max_reconnect_attempts=5,
            reconnect_time_wait=1.0,
        )
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect()

        mock_connect.assert_called_once_with(
            servers=["nats://config-server:4222"],
            max_reconnect_attempts=5,
            reconnect_time_wait=1.0,
        )

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    async def test_connect_with_server_override(self, mock_connect):
        """Test connection with server override."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_nc.jetstream.return_value = AsyncMock()
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig(servers=["nats://config-server:4222"])
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect(["nats://override-server:4222"])

        # Should use override servers
        mock_connect.assert_called_once()
        call_args = mock_connect.call_args
        assert call_args[1]["servers"] == ["nats://override-server:4222"]

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    async def test_connect_with_pool(self, mock_connect):
        """Test connection creates pool based on config."""
        mock_connections = []
        for i in range(3):
            mock_nc = AsyncMock(spec=NATSClient)
            if i == 0:
                mock_nc.jetstream.return_value = AsyncMock()
            mock_connections.append(mock_nc)

        mock_connect.side_effect = mock_connections

        config = NATSConnectionConfig(pool_size=3)
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect()

        assert len(adapter._connections) == 3
        assert mock_connect.call_count == 3

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    async def test_connect_with_js_domain_from_config(self, mock_connect):
        """Test JetStream uses domain from config."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_js = AsyncMock()
        mock_nc.jetstream.return_value = mock_js
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig(js_domain="prod-domain")
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect()

        mock_nc.jetstream.assert_called_once_with(domain="prod-domain")

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    @patch.dict(os.environ, {"NATS_JS_DOMAIN": "env-domain"})
    async def test_connect_with_js_domain_from_env(self, mock_connect):
        """Test JetStream uses domain from environment when not in config."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_js = AsyncMock()
        mock_nc.jetstream.return_value = mock_js
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig()  # No JS domain in config
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect()

        mock_nc.jetstream.assert_called_once_with(domain="env-domain")

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    async def test_connect_without_jetstream(self, mock_connect):
        """Test connection without JetStream when disabled."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig(enable_jetstream=False)
        adapter = NATSAdapter(config=config)

        await adapter.connect()

        assert adapter._js is None
        mock_nc.jetstream.assert_not_called()

    @pytest.mark.asyncio
    @patch("aegis_sdk.infrastructure.nats_adapter.nats.connect")
    @patch("builtins.print")
    async def test_connect_logs_with_context(self, mock_print, mock_connect):
        """Test connection logs with LogContext."""
        mock_nc = AsyncMock(spec=NATSClient)
        mock_nc.jetstream.return_value = AsyncMock()
        mock_connect.return_value = mock_nc

        config = NATSConnectionConfig(
            service_name="test-service",
            instance_id="test-instance",
        )
        adapter = NATSAdapter(config=config)
        adapter._ensure_streams = AsyncMock()

        await adapter.connect()

        # Check that log message includes context
        mock_print.assert_called_once()
        log_message = mock_print.call_args[0][0]
        assert "Connected to NATS cluster" in log_message
        assert "service_name" in log_message
        assert "test-service" in log_message
        assert "instance_id" in log_message
        assert "test-instance" in log_message


class TestNATSAdapterSerialization:
    """Tests for serialization with factory."""

    @pytest.mark.asyncio
    async def test_rpc_uses_configured_serializer(self):
        """Test RPC uses serializer from factory."""
        config = NATSConnectionConfig(use_msgpack=True)
        adapter = NATSAdapter(config=config)

        # Mock connection and response
        mock_nc = AsyncMock()
        adapter._connections = [mock_nc]
        adapter._current_conn = 0

        # Create response message
        response = RPCResponse(
            correlation_id="test-123",
            success=True,
            result={"data": "value"},
        )

        # Mock the response with proper MessagePack data
        mock_response_msg = Mock()
        mock_response_msg.data = adapter._serializer.serialize(response)
        mock_nc.request.return_value = mock_response_msg

        # Make RPC call
        request = RPCRequest(
            method="testMethod",
            params={"param": "value"},
            target="service.method",
        )
        result = await adapter.call_rpc(request)

        assert result.success is True
        assert result.result == {"data": "value"}

        # Verify request was serialized with MessagePack
        call_args = mock_nc.request.call_args
        assert call_args[0][0] == "rpc.service.testMethod"
        # Data should be MessagePack bytes
        assert isinstance(call_args[0][1], bytes)

    @pytest.mark.asyncio
    async def test_event_publish_uses_serializer(self):
        """Test event publishing uses configured serializer."""
        config = NATSConnectionConfig(use_msgpack=False)  # Use JSON
        adapter = NATSAdapter(config=config)

        # Mock JetStream
        mock_js = AsyncMock()
        adapter._js = mock_js
        mock_js.publish.return_value = Mock(seq=123)

        # Publish event
        event = Event(
            domain="test",
            event_type="created",
            payload={"id": 123},
        )
        await adapter.publish_event(event)

        # Verify event was serialized with JSON
        call_args = mock_js.publish.call_args
        assert call_args[0][0] == "events.test.created"
        # Data should be JSON bytes
        data = call_args[0][1]
        assert isinstance(data, bytes)
        parsed = json.loads(data.decode())
        assert parsed["domain"] == "test"
        assert parsed["event_type"] == "created"


class TestNATSAdapterHeartbeat:
    """Tests for heartbeat with metrics snapshot."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_with_metrics_snapshot(self):
        """Test heartbeat sends MetricsSnapshot."""
        adapter = NATSAdapter()

        # Mock connection
        mock_nc = AsyncMock()
        adapter._connections = [mock_nc]

        # Mock metrics
        adapter._metrics.get_all = Mock(
            return_value={
                "uptime": 300.5,
                "counters": {"requests": 100},
                "gauges": {"connections": 5},
                "summaries": {},
            }
        )

        await adapter.send_heartbeat("test-service", "instance-123")

        # Verify heartbeat was sent
        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        assert call_args[0][0] == "internal.heartbeat.test-service"

        # Verify data includes metrics snapshot
        data = json.loads(call_args[0][1].decode())
        assert data["instance_id"] == "instance-123"
        assert "metrics" in data
        assert data["metrics"]["uptime_seconds"] == 300.5
        assert data["metrics"]["counters"] == {"requests": 100}
        assert data["metrics"]["gauges"] == {"connections": 5}


class TestNATSAdapterEventSubscription:
    """Tests for event subscription with modes."""

    @pytest.mark.asyncio
    async def test_subscribe_event_compete_mode_with_service(self):
        """Test event subscription in compete mode with service name."""
        config = NATSConnectionConfig(service_name="worker-service")
        adapter = NATSAdapter(config=config)

        # Mock connection and JetStream
        mock_nc = AsyncMock()
        mock_js = AsyncMock()
        adapter._connections = [mock_nc]
        adapter._js = mock_js
        adapter._current_conn = 0

        handler = AsyncMock()
        await adapter.subscribe_event("events.order.*", handler, mode="compete")

        # Should use core NATS with queue group for wildcards
        mock_nc.subscribe.assert_called_once()
        call_args = mock_nc.subscribe.call_args
        assert call_args[1]["queue"] == "worker-service"

    @pytest.mark.asyncio
    async def test_subscribe_event_broadcast_mode_with_instance(self):
        """Test event subscription in broadcast mode with instance ID."""
        config = NATSConnectionConfig(
            service_name="viewer-service",
            instance_id="viewer-123",
        )
        adapter = NATSAdapter(config=config)

        # Mock JetStream
        mock_js = AsyncMock()
        adapter._js = mock_js

        handler = AsyncMock()
        await adapter.subscribe_event(
            "events.order.created",
            handler,
            durable="order-viewer",
            mode="broadcast",
        )

        # Should use JetStream with unique durable per instance
        mock_js.subscribe.assert_called_once()
        call_args = mock_js.subscribe.call_args
        assert call_args[1]["durable"] == "order-viewer-viewer-123"
        assert "queue" not in call_args[1]
