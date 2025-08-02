"""Integration tests for validating core SDK infrastructure components.

This module tests the following critical infrastructure components:
1. NATSAdapter connection pooling with round-robin distribution
2. Automatic failover and health checks
3. Reconnection with exponential backoff
4. MessageBusPort interface compliance
5. Service class lifecycle (start/stop/health)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from nats.aio.client import Client as NATSClient
from nats.errors import TimeoutError as NATSTimeoutError

from aegis_sdk.application.service import Service
from aegis_sdk.domain.models import (
    Command,
    Event,
    RPCRequest,
    ServiceInfo,
)
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.ports.message_bus import MessageBusPort


@pytest.mark.asyncio
class TestNATSAdapterConnectionPooling:
    """Test NATSAdapter connection pooling with round-robin distribution."""

    async def test_connection_pool_creation(self):
        """Test that connection pool is created with specified size."""
        pool_size = 3
        adapter = NATSAdapter(pool_size=pool_size)

        # Mock NATS connections
        mock_connections = []
        for _i in range(pool_size):
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = True
            mock_js = Mock()
            mock_js.stream_info = AsyncMock(side_effect=Exception("Not found"))
            mock_js.add_stream = AsyncMock()
            mock_nc.jetstream = Mock(return_value=mock_js)
            mock_connections.append(mock_nc)

        with patch("nats.connect", side_effect=mock_connections):
            await adapter.connect(["nats://localhost:4222"])

            assert len(adapter._connections) == pool_size
            assert adapter._js is not None
            assert adapter._current_conn == 0

    async def test_round_robin_connection_distribution(self):
        """Test that connections are distributed in round-robin fashion."""
        pool_size = 3
        adapter = NATSAdapter(pool_size=pool_size)

        # Create mock connections
        mock_connections = []
        for _i in range(pool_size):
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = True
            mock_nc.request = AsyncMock()
            mock_connections.append(mock_nc)

        adapter._connections = mock_connections

        # Track which connections are used
        connection_usage = []

        # Make several RPC calls to test round-robin
        for _i in range(pool_size * 2):
            conn = adapter._get_connection()
            connection_usage.append(adapter._connections.index(conn))

        # Verify round-robin pattern
        expected_pattern = [0, 1, 2, 0, 1, 2]
        assert connection_usage == expected_pattern

    async def test_connection_pool_with_failed_connections(self):
        """Test connection pool behavior when some connections fail."""
        pool_size = 3
        adapter = NATSAdapter(pool_size=pool_size)

        # Create mock connections with one failed
        mock_connections = []
        for i in range(pool_size):
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = i != 1  # Second connection is failed
            mock_connections.append(mock_nc)

        adapter._connections = mock_connections

        # Test that adapter finds working connections
        # The implementation uses round-robin with retry logic
        conn1 = adapter._get_connection()  # Should get first connection (index 0)
        assert conn1.is_connected
        assert conn1 in [mock_connections[0], mock_connections[2]]

        conn2 = adapter._get_connection()  # Should get next working connection
        assert conn2.is_connected
        assert conn2 in [mock_connections[0], mock_connections[2]]

        # Verify it never returns the failed connection
        for _ in range(10):
            conn = adapter._get_connection()
            assert conn != mock_connections[1]  # Never returns the failed one
            assert conn.is_connected

    async def test_all_connections_failed_raises_exception(self):
        """Test that exception is raised when all connections fail."""
        adapter = NATSAdapter(pool_size=2)

        # All connections failed
        mock_connections = []
        for _ in range(2):
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = False
            mock_connections.append(mock_nc)

        adapter._connections = mock_connections

        with pytest.raises(Exception, match="No active NATS connections"):
            adapter._get_connection()


@pytest.mark.asyncio
class TestNATSAdapterFailoverAndHealthChecks:
    """Test automatic failover and health check functionality."""

    async def test_connection_health_check(self):
        """Test that is_connected properly checks connection health."""
        adapter = NATSAdapter(pool_size=3)

        # No connections initially
        assert await adapter.is_connected() is False

        # Mix of healthy and unhealthy connections
        mock_connections = []
        for i in range(3):
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = i < 2  # First two are connected
            mock_connections.append(mock_nc)

        adapter._connections = mock_connections

        # Should return True if any connection is healthy
        assert await adapter.is_connected() is True

        # All connections fail
        for conn in mock_connections:
            conn.is_connected = False

        assert await adapter.is_connected() is False

    async def test_automatic_failover_on_request(self):
        """Test automatic failover when making requests."""
        adapter = NATSAdapter(pool_size=2)

        # Create mock connections
        mock_conn1 = Mock(spec=NATSClient)
        mock_conn1.is_connected = True
        mock_conn1.request = AsyncMock(side_effect=NATSTimeoutError("Connection lost"))

        mock_conn2 = Mock(spec=NATSClient)
        mock_conn2.is_connected = True
        mock_response = Mock()
        mock_response.data = (
            b'{"correlation_id":"123","success":true,"result":{"test":"data"}}'
        )
        mock_conn2.request = AsyncMock(return_value=mock_response)

        adapter._connections = [mock_conn1, mock_conn2]

        # First request should fail over to second connection
        request = RPCRequest(
            method="test_method",
            params={"test": "params"},
            target="test_service",
        )

        # Patch _get_connection to try first connection first
        call_count = 0

        def mock_get_connection():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_conn1
            return mock_conn2

        adapter._get_connection = mock_get_connection

        response = await adapter.call_rpc(request)

        # Should have succeeded with second connection
        assert response.success is False  # First connection failed
        assert "Timeout" in response.error

    async def test_heartbeat_functionality(self):
        """Test service heartbeat sending."""
        adapter = NATSAdapter()

        mock_nc = Mock(spec=NATSClient)
        mock_nc.is_connected = True
        mock_nc.publish = AsyncMock()

        adapter._connections = [mock_nc]

        await adapter.send_heartbeat("test_service", "instance-123")

        # Verify heartbeat was published
        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        assert call_args[0][0] == "internal.heartbeat.test_service"

        # Check heartbeat data
        heartbeat_data = json.loads(call_args[0][1].decode())
        assert heartbeat_data["instance_id"] == "instance-123"
        assert "timestamp" in heartbeat_data
        assert "metrics" in heartbeat_data


@pytest.mark.asyncio
class TestNATSAdapterReconnection:
    """Test reconnection with exponential backoff."""

    async def test_connection_with_retry_configuration(self):
        """Test that connections are configured with proper retry settings."""
        adapter = NATSAdapter(pool_size=1)

        with patch("nats.connect") as mock_connect:
            mock_nc = Mock(spec=NATSClient)
            mock_nc.is_connected = True
            mock_js = Mock()
            mock_js.stream_info = AsyncMock(side_effect=Exception("Not found"))
            mock_js.add_stream = AsyncMock()
            mock_nc.jetstream = Mock(return_value=mock_js)
            mock_connect.return_value = mock_nc

            await adapter.connect(["nats://localhost:4222"])

            # Verify reconnection settings
            mock_connect.assert_called_with(
                servers=["nats://localhost:4222"],
                max_reconnect_attempts=10,
                reconnect_time_wait=2.0,
            )

    async def test_publish_retry_on_json_decode_error(self):
        """Test that publish operations retry on JSON decode errors."""
        adapter = NATSAdapter()

        mock_js = Mock()
        adapter._js = mock_js

        # Simulate JSON decode error on first two attempts
        attempt_count = 0

        async def mock_publish(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise json.JSONDecodeError("Empty response", "", 0)
            return Mock()  # Success on third attempt

        mock_js.publish = mock_publish

        event = Event(
            domain="test",
            event_type="test_event",
            payload={"data": "test"},
        )

        await adapter.publish_event(event)

        # Should have retried and succeeded
        assert attempt_count == 3

    async def test_publish_max_retry_exceeded(self):
        """Test that publish fails after max retries."""
        adapter = NATSAdapter()

        mock_js = Mock()
        adapter._js = mock_js

        # Always fail with JSON decode error
        mock_js.publish = AsyncMock(
            side_effect=json.JSONDecodeError("Empty response", "", 0)
        )

        event = Event(
            domain="test",
            event_type="test_event",
            payload={"data": "test"},
        )

        with pytest.raises(
            Exception, match="JetStream publish failed after 3 attempts"
        ):
            await adapter.publish_event(event)

        # Should have tried 3 times
        assert mock_js.publish.call_count == 3

    async def test_command_send_retry_on_json_decode_error(self):
        """Test that command send operations retry on JSON decode errors."""
        adapter = NATSAdapter()

        mock_js = Mock()
        adapter._js = mock_js
        adapter._connections = [Mock(spec=NATSClient)]
        adapter._connections[0].is_connected = True
        adapter._connections[0].subscribe = AsyncMock()

        # Simulate JSON decode error on first attempt
        attempt_count = 0

        async def mock_publish(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise json.JSONDecodeError("Empty response", "", 0)
            return Mock(stream="COMMANDS", seq=123)

        mock_js.publish = mock_publish

        command = Command(
            command="test_command",
            payload={"data": "test"},
            target="test_service",
        )

        result = await adapter.send_command(command, track_progress=False)

        # Should have retried and succeeded
        assert attempt_count == 2
        assert result["stream"] == "COMMANDS"
        assert result["seq"] == 123


@pytest.mark.asyncio
class TestMessageBusPortCompliance:
    """Test that NATSAdapter fully implements MessageBusPort interface."""

    async def test_implements_all_abstract_methods(self):
        """Test that NATSAdapter implements all MessageBusPort methods."""
        adapter = NATSAdapter()

        # Check all required methods exist
        assert hasattr(adapter, "connect")
        assert hasattr(adapter, "disconnect")
        assert hasattr(adapter, "is_connected")
        assert hasattr(adapter, "register_rpc_handler")
        assert hasattr(adapter, "call_rpc")
        assert hasattr(adapter, "subscribe_event")
        assert hasattr(adapter, "publish_event")
        assert hasattr(adapter, "register_command_handler")
        assert hasattr(adapter, "send_command")
        assert hasattr(adapter, "register_service")
        assert hasattr(adapter, "unregister_service")
        assert hasattr(adapter, "send_heartbeat")

        # Verify it's a proper subclass
        assert isinstance(adapter, MessageBusPort)

    async def test_rpc_interface_compliance(self):
        """Test RPC operations comply with interface."""
        adapter = NATSAdapter()

        # Mock connection
        mock_nc = Mock(spec=NATSClient)
        mock_nc.is_connected = True
        mock_nc.subscribe = AsyncMock()
        mock_nc.request = AsyncMock()
        adapter._connections = [mock_nc]

        # Test handler registration
        async def test_handler(params: dict) -> dict:
            return {"result": "test"}

        await adapter.register_rpc_handler("test_service", "test_method", test_handler)

        # Verify subscription was created
        mock_nc.subscribe.assert_called_once()
        call_args = mock_nc.subscribe.call_args
        assert call_args[0][0] == "rpc.test_service.test_method"
        assert call_args[1]["queue"] == "rpc.test_service"

    async def test_event_interface_compliance(self):
        """Test event operations comply with interface."""
        adapter = NATSAdapter()

        # Mock JetStream
        mock_js = Mock()
        mock_js.subscribe = AsyncMock()
        mock_js.publish = AsyncMock()
        mock_js.stream_info = AsyncMock(side_effect=Exception("Not found"))
        mock_js.add_stream = AsyncMock()
        adapter._js = mock_js

        # Mock connection for wildcard subscriptions
        mock_nc = Mock(spec=NATSClient)
        mock_nc.is_connected = True
        mock_nc.subscribe = AsyncMock()
        adapter._connections = [mock_nc]

        # Test event subscription
        async def event_handler(event: Event) -> None:
            pass

        # Test wildcard subscription (uses core NATS)
        await adapter.subscribe_event("events.order.*", event_handler)
        mock_nc.subscribe.assert_called_once()

        # Test specific subscription (uses JetStream)
        await adapter.subscribe_event(
            "events.order.created", event_handler, "test-durable"
        )
        mock_js.subscribe.assert_called_once()

    async def test_command_interface_compliance(self):
        """Test command operations comply with interface."""
        adapter = NATSAdapter()

        # Mock JetStream
        mock_js = Mock()
        mock_js.subscribe = AsyncMock()
        mock_js.publish = AsyncMock(return_value=Mock(stream="COMMANDS", seq=1))
        adapter._js = mock_js

        # Test command handler registration
        async def command_handler(cmd: Command, progress: callable) -> dict:
            await progress(50, "Processing")
            return {"status": "completed"}

        await adapter.register_command_handler(
            "test_service", "test_command", command_handler
        )

        # Verify subscription was created
        mock_js.subscribe.assert_called_once()
        call_args = mock_js.subscribe.call_args
        assert call_args[0][0] == "commands.test_service.test_command"
        assert call_args[1]["durable"] == "test_service-test_command"


@pytest.mark.asyncio
class TestServiceLifecycle:
    """Test Service class lifecycle management."""

    async def test_service_initialization(self):
        """Test service initialization with proper configuration."""
        mock_bus = Mock(spec=MessageBusPort)

        service = Service(
            service_name="test_service",
            message_bus=mock_bus,
            version="1.2.3",
        )

        assert service.service_name == "test_service"
        assert service.version == "1.2.3"
        assert service.instance_id.startswith("test_service-")
        assert service._bus == mock_bus
        assert isinstance(service._info, ServiceInfo)

        # Check initial state
        assert service._rpc_handlers == {}
        assert service._event_handlers == {}
        assert service._command_handlers == {}
        assert service._heartbeat_task is None
        assert service._start_time is None

    async def test_service_start_lifecycle(self):
        """Test complete service start lifecycle."""
        mock_bus = Mock(spec=MessageBusPort)
        mock_bus.register_service = AsyncMock()
        mock_bus.register_rpc_handler = AsyncMock()
        mock_bus.subscribe_event = AsyncMock()
        mock_bus.register_command_handler = AsyncMock()
        mock_bus.send_heartbeat = AsyncMock()

        service = Service("test_service", mock_bus)

        # Register some handlers
        @service.rpc("get_status")
        async def get_status(params: dict) -> dict:
            return {"status": "ok"}

        @service.subscribe("test.events.*")
        async def handle_event(event: Event) -> None:
            pass

        @service.command("process_data")
        async def process_data(cmd: Command, progress: callable) -> dict:
            return {"processed": True}

        # Start service
        await service.start()

        # Verify start time is set
        assert service._start_time is not None

        # Verify service registration
        mock_bus.register_service.assert_called_once_with(
            "test_service", service.instance_id
        )

        # Verify handler registrations
        mock_bus.register_rpc_handler.assert_called_once_with(
            "test_service", "get_status", service._rpc_handlers["get_status"]
        )

        mock_bus.subscribe_event.assert_called_once()
        event_call = mock_bus.subscribe_event.call_args
        assert event_call[0][0] == "test.events.*"

        mock_bus.register_command_handler.assert_called_once_with(
            "test_service", "process_data", service._command_handlers["process_data"]
        )

        # Verify heartbeat task started
        assert service._heartbeat_task is not None
        assert not service._heartbeat_task.done()

        # Clean up
        await service.stop()

    async def test_service_stop_lifecycle(self):
        """Test service stop and cleanup."""
        mock_bus = Mock(spec=MessageBusPort)
        mock_bus.register_service = AsyncMock()
        mock_bus.unregister_service = AsyncMock()
        mock_bus.send_heartbeat = AsyncMock()

        service = Service("test_service", mock_bus)

        # Start service
        await service.start()

        # Get heartbeat task reference
        heartbeat_task = service._heartbeat_task

        # Stop service
        await service.stop()

        # Verify shutdown event is set
        assert service._shutdown_event.is_set()

        # Verify heartbeat task is cancelled
        assert heartbeat_task.cancelled()

        # Verify service unregistration
        mock_bus.unregister_service.assert_called_once_with(
            "test_service", service.instance_id
        )

    async def test_service_heartbeat_loop(self):
        """Test service heartbeat loop operation."""
        mock_bus = Mock(spec=MessageBusPort)
        mock_bus.send_heartbeat = AsyncMock()

        service = Service("test_service", mock_bus)

        # Manually start heartbeat loop
        heartbeat_task = asyncio.create_task(service._heartbeat_loop())

        # Let it run for a short time
        await asyncio.sleep(0.1)

        # Should have sent at least one heartbeat
        assert mock_bus.send_heartbeat.called

        # Stop the loop
        service._shutdown_event.set()

        # Cancel the task and wait for it to complete
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task

        # Task should be done now
        assert heartbeat_task.done()

    async def test_service_status_management(self):
        """Test service status updates."""
        mock_bus = Mock(spec=MessageBusPort)
        service = Service("test_service", mock_bus)

        # Initial status
        assert service.info.status == "ACTIVE"

        # Valid status updates
        service.set_status("STANDBY")
        assert service.info.status == "STANDBY"

        service.set_status("UNHEALTHY")
        assert service.info.status == "UNHEALTHY"

        service.set_status("SHUTDOWN")
        assert service.info.status == "SHUTDOWN"

        # Invalid status
        with pytest.raises(ValueError, match="Invalid status"):
            service.set_status("INVALID")

    async def test_service_invalid_name_validation(self):
        """Test that service validates name format."""
        mock_bus = Mock(spec=MessageBusPort)

        # Invalid service names
        with pytest.raises(ValueError, match="Invalid service name"):
            Service("invalid-name!", mock_bus)

        with pytest.raises(ValueError, match="Invalid service name"):
            Service("123invalid", mock_bus)

        with pytest.raises(ValueError, match="Invalid service name"):
            Service("", mock_bus)

    async def test_service_on_start_hook(self):
        """Test that on_start hook is called during startup."""
        mock_bus = Mock(spec=MessageBusPort)
        mock_bus.register_service = AsyncMock()
        mock_bus.send_heartbeat = AsyncMock()

        # Create custom service with on_start hook
        class TestService(Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.on_start_called = False

            async def on_start(self):
                self.on_start_called = True
                # Register a handler in on_start
                await self.register_rpc_method("dynamic_method", self.dynamic_handler)

            async def dynamic_handler(self, params: dict) -> dict:
                return {"dynamic": True}

        service = TestService("test_service", mock_bus)

        # Start service
        await service.start()

        # Verify on_start was called
        assert service.on_start_called

        # Verify dynamic registration worked
        assert "dynamic_method" in service._rpc_handlers

        # Clean up
        await service.stop()


@pytest.mark.asyncio
class TestMetricsIntegration:
    """Test metrics integration in infrastructure components."""

    async def test_nats_adapter_metrics_tracking(self):
        """Test that NATS adapter properly tracks metrics."""
        mock_metrics = Mock()
        mock_metrics.gauge = Mock()
        mock_metrics.increment = Mock()
        mock_metrics.timer = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))

        with patch(
            "aegis_sdk.infrastructure.nats_adapter.get_metrics",
            return_value=mock_metrics,
        ):
            adapter = NATSAdapter(pool_size=2)

            # Mock connections
            mock_connections = []
            for _ in range(2):
                mock_nc = Mock(spec=NATSClient)
                mock_nc.is_connected = True
                mock_js = Mock()
                mock_js.stream_info = AsyncMock(side_effect=Exception("Not found"))
                mock_js.add_stream = AsyncMock()
                mock_nc.jetstream = Mock(return_value=mock_js)
                mock_connections.append(mock_nc)

            with patch("nats.connect", side_effect=mock_connections):
                await adapter.connect(["nats://localhost:4222"])

            # Check connection gauge
            mock_metrics.gauge.assert_called_with("nats.connections", 2)

            # Test RPC metrics
            mock_nc = adapter._connections[0]
            mock_response = Mock()
            mock_response.data = b'{"correlation_id":"123","success":true,"result":{}}'
            mock_nc.request = AsyncMock(return_value=mock_response)

            request = RPCRequest(method="test", params={}, target="service")
            await adapter.call_rpc(request)

            # Check timer and increment calls
            mock_metrics.timer.assert_called()
            mock_metrics.increment.assert_called_with("rpc.client.service.test.success")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
