"""
Tests for gateway metrics collection
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from domain.gateway.connection_manager import ConnectionManager
from domain.gateway.metrics import GatewayMetrics, MetricsCollector
from domain.gateway.value_objects import ConnectionConfig, HeartbeatConfig


class TestGatewayMetrics:
    """Test gateway metrics functionality"""

    def test_record_connection_attempt(self):
        """Test recording connection attempts"""
        metrics = GatewayMetrics()

        metrics.record_connection_attempt()
        metrics.record_connection_attempt()

        assert metrics.connection_attempts == 2

    def test_record_connection_success(self):
        """Test recording successful connections"""
        metrics = GatewayMetrics()

        metrics.record_connection_success()

        assert metrics.connection_successes == 1
        assert metrics.current_connection_state == "CONNECTED"
        assert metrics.last_connection_time is not None

    def test_record_connection_failure(self):
        """Test recording connection failures"""
        metrics = GatewayMetrics()

        metrics.record_connection_failure("auth")
        metrics.record_connection_failure("network")
        metrics.record_connection_failure("timeout")
        metrics.record_connection_failure("unknown")

        assert metrics.connection_failures == 4
        assert metrics.auth_errors == 1
        assert metrics.network_errors == 1
        assert metrics.timeout_errors == 1
        assert metrics.unknown_errors == 1
        assert metrics.current_connection_state == "DISCONNECTED"

    def test_record_heartbeat_sent(self):
        """Test recording heartbeat sent"""
        metrics = GatewayMetrics()

        metrics.record_heartbeat_sent()
        metrics.record_heartbeat_sent()

        assert metrics.heartbeat_sent_count == 2

    def test_record_heartbeat_received(self):
        """Test recording heartbeat received with latency"""
        metrics = GatewayMetrics()

        metrics.record_heartbeat_received(50)
        metrics.record_heartbeat_received(100)
        metrics.record_heartbeat_received(75)

        assert metrics.heartbeat_received_count == 3
        assert metrics.last_heartbeat_latency_ms == 75
        assert metrics.avg_heartbeat_latency_ms == 75.0
        assert metrics.max_heartbeat_latency_ms == 100
        assert len(metrics.heartbeat_latencies_ms) == 3

    def test_heartbeat_latency_buffer_limit(self):
        """Test heartbeat latency buffer is limited to 100 samples"""
        metrics = GatewayMetrics()

        # Add 150 samples
        for i in range(150):
            metrics.record_heartbeat_received(i)

        # Should only keep last 100
        assert len(metrics.heartbeat_latencies_ms) == 100
        assert metrics.heartbeat_latencies_ms[0] == 50  # First 50 should be dropped
        assert metrics.heartbeat_latencies_ms[-1] == 149  # Last should be 149

    def test_record_failover(self):
        """Test recording failover events"""
        metrics = GatewayMetrics()

        metrics.record_failover(1500)
        metrics.record_failover(2000)

        assert metrics.failover_count == 2
        assert metrics.last_failover_duration_ms == 2000
        assert metrics.avg_failover_duration_ms == 1750.0
        assert len(metrics.failover_durations_ms) == 2

    def test_failover_buffer_limit(self):
        """Test failover buffer is limited to 10 samples"""
        metrics = GatewayMetrics()

        # Add 15 failovers
        for i in range(15):
            metrics.record_failover(i * 100)

        # Should only keep last 10
        assert len(metrics.failover_durations_ms) == 10
        assert metrics.failover_durations_ms[0] == 500  # First 5 should be dropped

    def test_record_disconnection(self):
        """Test recording disconnection"""
        metrics = GatewayMetrics()

        metrics.record_disconnection()

        assert metrics.current_connection_state == "DISCONNECTED"
        assert metrics.last_disconnection_time is not None

    def test_record_circuit_breaker_state_changes(self):
        """Test recording circuit breaker state changes"""
        metrics = GatewayMetrics()

        metrics.record_circuit_breaker_state_change("OPEN")
        metrics.record_circuit_breaker_state_change("HALF_OPEN")
        metrics.record_circuit_breaker_state_change("CLOSED")
        metrics.record_circuit_breaker_state_change("OPEN")

        assert metrics.circuit_breaker_opens == 2
        assert metrics.circuit_breaker_half_opens == 1
        assert metrics.circuit_breaker_closes == 1
        assert metrics.current_circuit_state == "OPEN"

    def test_get_connection_success_rate(self):
        """Test connection success rate calculation"""
        metrics = GatewayMetrics()

        # No attempts
        assert metrics.get_connection_success_rate() == 0.0

        # Some successes and failures
        metrics.connection_attempts = 10
        metrics.connection_successes = 7
        assert metrics.get_connection_success_rate() == 70.0

        # All successful
        metrics.connection_attempts = 5
        metrics.connection_successes = 5
        assert metrics.get_connection_success_rate() == 100.0

    def test_get_heartbeat_loss_rate(self):
        """Test heartbeat loss rate calculation"""
        metrics = GatewayMetrics()

        # No heartbeats sent
        assert metrics.get_heartbeat_loss_rate() == 0.0

        # Some lost heartbeats
        metrics.heartbeat_sent_count = 100
        metrics.heartbeat_received_count = 95
        assert metrics.get_heartbeat_loss_rate() == 5.0

        # No loss
        metrics.heartbeat_sent_count = 50
        metrics.heartbeat_received_count = 50
        assert metrics.get_heartbeat_loss_rate() == 0.0

    def test_update_uptime(self):
        """Test uptime calculation"""
        metrics = GatewayMetrics()

        # Not connected
        metrics.update_uptime()
        assert metrics.uptime_seconds == 0

        # Connected
        metrics.current_connection_state = "CONNECTED"
        metrics.last_connection_time = datetime.now()

        import time

        time.sleep(0.1)  # Wait a bit

        metrics.update_uptime()
        assert metrics.uptime_seconds > 0

    def test_to_dict(self):
        """Test converting metrics to dictionary"""
        metrics = GatewayMetrics()

        # Set some values
        metrics.record_connection_attempt()
        metrics.record_connection_success()
        metrics.record_heartbeat_sent()
        metrics.record_heartbeat_received(50)

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result["connection_attempts"] == 1
        assert result["connection_successes"] == 1
        assert result["heartbeat_sent_count"] == 1
        assert result["heartbeat_received_count"] == 1
        assert result["last_heartbeat_latency_ms"] == 50
        assert "connection_success_rate" in result
        assert "heartbeat_loss_rate" in result


class TestMetricsCollector:
    """Test metrics collector functionality"""

    def test_get_metrics(self):
        """Test getting metrics from collector"""
        collector = MetricsCollector()

        collector.metrics.record_connection_attempt()
        collector.metrics.record_connection_success()

        metrics = collector.get_metrics()

        assert metrics.connection_attempts == 1
        assert metrics.connection_successes == 1

    def test_reset_metrics(self):
        """Test resetting metrics"""
        collector = MetricsCollector()

        # Add some metrics
        collector.metrics.record_connection_attempt()
        collector.metrics.record_connection_success()

        # Reset
        collector.reset_metrics()

        metrics = collector.get_metrics()
        assert metrics.connection_attempts == 0
        assert metrics.connection_successes == 0

    def test_get_runtime_seconds(self):
        """Test getting runtime"""
        collector = MetricsCollector()

        import time

        time.sleep(0.1)  # Wait a bit

        runtime = collector.get_runtime_seconds()
        assert runtime > 0


class TestConnectionManagerWithMetrics:
    """Test ConnectionManager metrics integration"""

    @pytest.fixture
    def mock_adapter(self):
        """Mock gateway adapter"""
        adapter = AsyncMock()
        adapter.connect = AsyncMock()
        adapter.disconnect = AsyncMock()
        adapter.send_heartbeat = AsyncMock()
        adapter.is_connected = lambda: True
        return adapter

    @pytest.fixture
    def connection_config(self):
        """Connection configuration"""
        return ConnectionConfig(
            heartbeat_config=HeartbeatConfig(enabled=False),
            reconnect_delay=1,
            max_reconnect_attempts=3,
        )

    async def test_connect_records_metrics(self, mock_adapter, connection_config):
        """Test that connect records metrics"""
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
        )

        await manager.connect()

        metrics = manager.get_metrics()
        assert metrics["connection_attempts"] == 1
        assert metrics["connection_successes"] == 1
        assert metrics["current_connection_state"] == "CONNECTED"

    async def test_connect_failure_records_metrics(self, mock_adapter, connection_config):
        """Test that connection failure records metrics"""
        mock_adapter.connect.side_effect = Exception("Network error")

        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
        )

        with pytest.raises(ConnectionError):
            await manager.connect()

        metrics = manager.get_metrics()
        assert metrics["connection_attempts"] == 1
        assert metrics["connection_failures"] == 1
        assert metrics["network_errors"] == 1
        assert metrics["current_connection_state"] == "DISCONNECTED"

    async def test_disconnect_records_metrics(self, mock_adapter, connection_config):
        """Test that disconnect records metrics"""
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
        )

        await manager.connect()
        await manager.disconnect()

        metrics = manager.get_metrics()
        assert metrics["current_connection_state"] == "DISCONNECTED"

    async def test_heartbeat_metrics(self, mock_adapter, connection_config):
        """Test heartbeat metrics recording"""
        # Enable heartbeat for this test
        config = ConnectionConfig(
            heartbeat_config=HeartbeatConfig(enabled=True, interval=1, timeout=3),
            reconnect_delay=1,
            max_reconnect_attempts=3,
        )

        manager = ConnectionManager(
            adapter=mock_adapter,
            config=config,
        )

        await manager.connect()

        # Simulate sending heartbeat
        await manager.adapter.send_heartbeat()
        manager.last_heartbeat_sent = datetime.now()
        manager.metrics_collector.metrics.record_heartbeat_sent()

        # Simulate receiving heartbeat response
        manager.handle_heartbeat_response()

        metrics = manager.get_metrics()
        assert metrics["heartbeat_sent_count"] == 1
        assert metrics["heartbeat_received_count"] == 1
        assert metrics["last_heartbeat_latency_ms"] >= 0
