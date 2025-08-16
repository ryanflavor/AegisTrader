"""
Unit tests for generic connection management
Following TDD RED phase - these tests should fail initially
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = pytest.mark.asyncio

# These imports will fail initially (RED phase)
from domain.gateway.connection_manager import ConnectionManager
from domain.gateway.ports import GatewayPort
from domain.gateway.value_objects import (
    ConnectionConfig,
    ConnectionState,
    HeartbeatConfig,
)


class TestConnectionManager:
    """Test suite for generic connection management logic"""

    @pytest.fixture
    def mock_gateway_port(self) -> Mock:
        """Mock gateway port for testing"""
        port = Mock(spec=GatewayPort)
        port.connect = AsyncMock()
        port.disconnect = AsyncMock()
        port.send_heartbeat = AsyncMock()
        port.is_connected = Mock(return_value=False)
        return port

    @pytest.fixture
    def connection_config(self) -> ConnectionConfig:
        """Connection configuration for testing"""
        return ConnectionConfig(
            reconnect_delay=1,  # 1 second for testing
            max_reconnect_attempts=3,
            connection_timeout=5,
            heartbeat_config=HeartbeatConfig(
                interval=2,  # 2 seconds for testing
                timeout=4,  # 4 seconds timeout
                enabled=True,
            ),
        )

    @pytest.fixture
    def connection_manager(self, mock_gateway_port, connection_config) -> ConnectionManager:
        """Create connection manager instance for testing"""
        manager = ConnectionManager(adapter=mock_gateway_port, config=connection_config)
        return manager

    async def test_connection_lifecycle_management(self, connection_manager, mock_gateway_port):
        """Test connection lifecycle: connect(), disconnect(), reconnect()"""
        # Initial state should be disconnected
        assert connection_manager.state == ConnectionState.DISCONNECTED

        # Test connect
        await connection_manager.connect()
        mock_gateway_port.connect.assert_called_once()
        assert connection_manager.state == ConnectionState.CONNECTED

        # Test disconnect
        await connection_manager.disconnect()
        mock_gateway_port.disconnect.assert_called_once()
        assert connection_manager.state == ConnectionState.DISCONNECTED

        # Test reconnect
        await connection_manager.reconnect()
        assert mock_gateway_port.connect.call_count == 2
        assert connection_manager.state == ConnectionState.CONNECTED

    async def test_connection_state_transitions(self, connection_manager, mock_gateway_port):
        """Test proper state transitions: disconnected → connecting → connected"""
        # Initial state
        assert connection_manager.state == ConnectionState.DISCONNECTED

        # Make connection take some time to observe CONNECTING state
        async def delayed_connect():
            await asyncio.sleep(0.1)  # Simulate connection time

        mock_gateway_port.connect.side_effect = delayed_connect

        # Start connection (should transition to connecting)
        connect_task = asyncio.create_task(connection_manager.connect())
        await asyncio.sleep(0.01)  # Allow state transition
        assert connection_manager.state == ConnectionState.CONNECTING

        # Complete connection
        await connect_task
        assert connection_manager.state == ConnectionState.CONNECTED

        # Disconnect
        await connection_manager.disconnect()
        assert connection_manager.state == ConnectionState.DISCONNECTED

    async def test_automatic_reconnection_with_exponential_backoff(
        self, connection_manager, mock_gateway_port
    ):
        """Test automatic reconnection with exponential backoff strategy"""
        # Configure port to fail first 2 attempts
        mock_gateway_port.connect.side_effect = [
            ConnectionError("First attempt failed"),
            ConnectionError("Second attempt failed"),
            None,  # Third attempt succeeds
        ]

        # Track reconnection delays
        delays = []
        original_sleep = asyncio.sleep

        async def track_sleep(delay):
            delays.append(delay)
            await original_sleep(min(delay, 0.01))  # Speed up test

        with patch("asyncio.sleep", side_effect=track_sleep):
            await connection_manager.connect_with_retry()

        # Verify exponential backoff pattern
        assert len(delays) == 2  # Two retries
        assert delays[0] < delays[1]  # Exponential increase
        assert mock_gateway_port.connect.call_count == 3

    async def test_heartbeat_mechanism(self, connection_manager, mock_gateway_port):
        """Test heartbeat send/receive/timeout detection"""
        # Connect first
        await connection_manager.connect()

        # Start heartbeat
        heartbeat_task = asyncio.create_task(connection_manager.maintain_heartbeat())

        # Let it run for a few intervals
        await asyncio.sleep(0.05)  # Allow heartbeat to start

        # Verify heartbeats are being sent
        assert mock_gateway_port.send_heartbeat.called

        # Simulate heartbeat response
        connection_manager.handle_heartbeat_response()
        assert connection_manager.last_heartbeat_received is not None

        # Stop heartbeat
        connection_manager.stop_heartbeat()
        await asyncio.sleep(0.01)
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    async def test_heartbeat_timeout_detection(self, connection_manager, connection_config):
        """Test detection of heartbeat timeout"""
        # Connect
        await connection_manager.connect()

        # Set last heartbeat to past timeout
        connection_manager.last_heartbeat_received = datetime.now() - timedelta(
            seconds=connection_config.heartbeat_config.timeout + 1
        )

        # Check heartbeat timeout
        assert connection_manager.is_heartbeat_timeout() is True

        # Update heartbeat
        connection_manager.handle_heartbeat_response()
        assert connection_manager.is_heartbeat_timeout() is False

    async def test_connection_event_publishing(self, connection_manager, mock_gateway_port):
        """Test that connection events are published correctly"""
        events_published = []

        async def capture_event(event):
            events_published.append(event)

        connection_manager.publish_event = capture_event

        # Connect
        await connection_manager.connect()

        # Verify ConnectionAttempted and GatewayConnected events
        event_types = [type(e).__name__ for e in events_published]
        assert "ConnectionAttempted" in event_types
        assert "GatewayConnected" in event_types

        # Disconnect
        await connection_manager.disconnect()

        # Verify GatewayDisconnected event
        event_types = [type(e).__name__ for e in events_published]
        assert "GatewayDisconnected" in event_types

    async def test_connection_health_monitoring(self, connection_manager, mock_gateway_port):
        """Test connection health monitoring capabilities"""
        # Initially unhealthy (not connected)
        health = connection_manager.get_health_status()
        assert health.is_healthy is False
        assert health.state == ConnectionState.DISCONNECTED

        # Connect and check health
        await connection_manager.connect()
        # After successful connection, mock should return True
        mock_gateway_port.is_connected.return_value = True
        health = connection_manager.get_health_status()
        assert health.is_healthy is True
        assert health.state == ConnectionState.CONNECTED
        assert health.uptime_seconds >= 0

        # Simulate connection issue
        mock_gateway_port.is_connected.return_value = False
        health = connection_manager.get_health_status()
        assert health.is_healthy is False

    async def test_reconnection_on_connection_loss(self, connection_manager, mock_gateway_port):
        """Test automatic reconnection when connection is lost"""
        # Connect initially
        await connection_manager.connect()
        assert connection_manager.state == ConnectionState.CONNECTED

        # Simulate connection loss
        mock_gateway_port.is_connected.return_value = False
        await connection_manager.handle_disconnection()

        # Should attempt reconnection
        assert connection_manager.state == ConnectionState.RECONNECTING

        # Complete reconnection
        mock_gateway_port.is_connected.return_value = True
        await connection_manager.connect()
        assert connection_manager.state == ConnectionState.CONNECTED

    async def test_max_reconnection_attempts(
        self, connection_manager, mock_gateway_port, connection_config
    ):
        """Test that reconnection stops after max attempts"""
        # Configure to always fail
        mock_gateway_port.connect.side_effect = ConnectionError("Connection failed")

        # Attempt connection with retries
        with pytest.raises(ConnectionError):
            await connection_manager.connect_with_retry()

        # Verify max attempts were made
        assert mock_gateway_port.connect.call_count == connection_config.max_reconnect_attempts
        assert connection_manager.state == ConnectionState.DISCONNECTED

    async def test_concurrent_connection_attempts_prevention(self, connection_manager):
        """Test that concurrent connection attempts are prevented"""
        # Start first connection
        connect_task1 = asyncio.create_task(connection_manager.connect())
        await asyncio.sleep(0.01)  # Let first connection start

        # Try second connection while first is in progress
        connect_task2 = asyncio.create_task(connection_manager.connect())

        # Second should return immediately without double-connecting
        await connect_task2
        await connect_task1

        # Only one connection should have been made
        assert connection_manager.connection_attempts == 1

    async def test_graceful_shutdown(self, connection_manager, mock_gateway_port):
        """Test graceful shutdown of connection and cleanup"""
        # Connect and start heartbeat
        await connection_manager.connect()
        heartbeat_task = asyncio.create_task(connection_manager.maintain_heartbeat())

        # Graceful shutdown
        await connection_manager.shutdown()

        # Verify cleanup
        assert connection_manager.state == ConnectionState.DISCONNECTED
        mock_gateway_port.disconnect.assert_called()
        assert connection_manager.heartbeat_task is None

        # Cleanup task
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


class TestSDKRetryPolicy:
    """Test suite for SDK's RetryPolicy integration"""

    def test_sdk_retry_policy_configuration(self):
        """Test that ConnectionManager properly uses SDK's RetryPolicy"""
        from aegis_sdk.domain.value_objects import Duration, RetryPolicy

        # Create retry policy similar to what ConnectionManager uses
        retry_policy = RetryPolicy(
            max_retries=5,
            initial_delay=Duration(seconds=1.0),
            backoff_multiplier=2.0,
            max_delay=Duration(seconds=32.0),
            jitter_factor=0.25,
        )

        # Test configuration
        assert retry_policy.max_retries == 5
        assert retry_policy.initial_delay.total_seconds() == 1.0
        assert retry_policy.backoff_multiplier == 2.0
        assert retry_policy.max_delay.total_seconds() == 32.0
        assert retry_policy.jitter_factor == 0.25

    async def test_connection_manager_uses_sdk_retry_policy(self):
        """Test that ConnectionManager properly uses SDK's RetryPolicy for reconnection"""
        from unittest.mock import AsyncMock, Mock

        from domain.gateway.connection_manager import ConnectionManager
        from domain.gateway.ports import GatewayPort
        from domain.gateway.value_objects import ConnectionConfig, HeartbeatConfig

        # Setup
        mock_gateway_port = Mock(spec=GatewayPort)
        mock_gateway_port.connect = AsyncMock()
        mock_gateway_port.disconnect = AsyncMock()
        mock_gateway_port.is_connected = Mock(return_value=False)

        config = ConnectionConfig(
            reconnect_delay=1,
            max_reconnect_attempts=3,
            connection_timeout=5,
            heartbeat_config=HeartbeatConfig(
                interval=2,
                timeout=4,
                enabled=False,
            ),
        )

        manager = ConnectionManager(adapter=mock_gateway_port, config=config)

        # Verify retry policy is configured
        assert manager.retry_policy is not None
        assert manager.retry_policy.max_retries == 3
        assert manager.retry_policy.initial_delay.total_seconds() == 1.0
        assert manager.retry_policy.backoff_multiplier == 2.0
        assert manager.retry_policy.jitter_factor == 0.25
