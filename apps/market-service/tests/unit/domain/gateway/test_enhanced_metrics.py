"""
Unit tests for enhanced gateway metrics with SDK integration.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from application.metrics_adapter import SDKMetricsAdapter
from domain.gateway.metrics import MetricsCollector


class TestEnhancedMetricsCollector:
    """Test suite for enhanced MetricsCollector with SDK integration."""

    @pytest.fixture
    def mock_sdk_metrics(self):
        """Create a mock SDK metrics adapter."""
        mock = AsyncMock(spec=SDKMetricsAdapter)
        mock.increment_counter = AsyncMock()
        mock.set_gauge = AsyncMock()
        mock.record_timing = AsyncMock()
        mock.increment_counter_with_labels = AsyncMock()
        return mock

    @pytest.fixture
    def metrics_collector(self, mock_sdk_metrics):
        """Create metrics collector with mock SDK metrics."""
        return MetricsCollector(sdk_metrics=mock_sdk_metrics)

    @pytest.mark.asyncio
    async def test_record_connection_attempt_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test connection attempt recording with SDK metrics."""
        await metrics_collector.record_connection_attempt()

        assert metrics_collector.metrics.connection_attempts == 1
        mock_sdk_metrics.increment_counter.assert_called_once_with("gateway.connection.attempts")

    @pytest.mark.asyncio
    async def test_record_connection_success_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test connection success recording with SDK metrics."""
        await metrics_collector.record_connection_success()

        assert metrics_collector.metrics.connection_successes == 1
        assert metrics_collector.metrics.current_connection_state == "CONNECTED"

        mock_sdk_metrics.increment_counter.assert_called_once_with("gateway.connection.successes")
        mock_sdk_metrics.set_gauge.assert_called_once_with("gateway.connection.status", 1.0)

    @pytest.mark.asyncio
    async def test_record_connection_failure_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test connection failure recording with SDK metrics and error types."""
        await metrics_collector.record_connection_failure("network")

        assert metrics_collector.metrics.connection_failures == 1
        assert metrics_collector.metrics.network_errors == 1
        assert metrics_collector.metrics.current_connection_state == "DISCONNECTED"

        mock_sdk_metrics.increment_counter.assert_called_with("gateway.connection.failures")
        mock_sdk_metrics.increment_counter_with_labels.assert_called_with(
            "gateway.errors", {"type": "network"}
        )
        mock_sdk_metrics.set_gauge.assert_called_with("gateway.connection.status", 0.0)

    @pytest.mark.asyncio
    async def test_record_heartbeat_latency_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test heartbeat latency recording with SDK histogram."""
        await metrics_collector.record_heartbeat_latency(50)

        assert metrics_collector.metrics.heartbeat_received_count == 1
        assert metrics_collector.metrics.last_heartbeat_latency_ms == 50

        mock_sdk_metrics.record_timing.assert_called_once_with("gateway.heartbeat.latency_ms", 50.0)

    @pytest.mark.asyncio
    async def test_record_failover_duration_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test failover duration recording with SDK metrics."""
        await metrics_collector.record_failover_duration(1500)

        assert metrics_collector.metrics.failover_count == 1
        assert metrics_collector.metrics.last_failover_duration_ms == 1500

        mock_sdk_metrics.record_timing.assert_called_once_with(
            "gateway.failover.duration_ms", 1500.0
        )
        mock_sdk_metrics.increment_counter.assert_called_once_with("gateway.failover.count")

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_state_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test circuit breaker state recording with SDK metrics."""
        # Test CLOSED state
        await metrics_collector.record_circuit_breaker_state("CLOSED")
        assert metrics_collector.metrics.current_circuit_state == "CLOSED"
        assert metrics_collector.metrics.circuit_breaker_closes == 1
        mock_sdk_metrics.set_gauge.assert_called_with("gateway.circuit_breaker.state", 0.0)
        mock_sdk_metrics.increment_counter.assert_called_with(
            "gateway.circuit_breaker.closed_count"
        )

        # Test HALF_OPEN state
        await metrics_collector.record_circuit_breaker_state("HALF_OPEN")
        assert metrics_collector.metrics.current_circuit_state == "HALF_OPEN"
        assert metrics_collector.metrics.circuit_breaker_half_opens == 1
        mock_sdk_metrics.set_gauge.assert_called_with("gateway.circuit_breaker.state", 0.5)
        mock_sdk_metrics.increment_counter.assert_called_with(
            "gateway.circuit_breaker.half_open_count"
        )

        # Test OPEN state
        await metrics_collector.record_circuit_breaker_state("OPEN")
        assert metrics_collector.metrics.current_circuit_state == "OPEN"
        assert metrics_collector.metrics.circuit_breaker_opens == 1
        mock_sdk_metrics.set_gauge.assert_called_with("gateway.circuit_breaker.state", 1.0)
        mock_sdk_metrics.increment_counter.assert_called_with("gateway.circuit_breaker.open_count")

    @pytest.mark.asyncio
    async def test_record_message_received_with_sdk(self, metrics_collector, mock_sdk_metrics):
        """Test message received recording with SDK metrics."""
        await metrics_collector.record_message_received("tick")

        mock_sdk_metrics.increment_counter_with_labels.assert_called_once_with(
            "gateway.messages.received", {"type": "tick"}
        )

    @pytest.mark.asyncio
    async def test_export_metrics_snapshot(self, metrics_collector):
        """Test comprehensive metrics snapshot export."""
        # Simulate some metrics
        metrics_collector.metrics.connection_attempts = 10
        metrics_collector.metrics.connection_successes = 8
        metrics_collector.metrics.connection_failures = 2
        metrics_collector.metrics.current_connection_state = "CONNECTED"
        metrics_collector.metrics.heartbeat_sent_count = 100
        metrics_collector.metrics.heartbeat_received_count = 98
        metrics_collector.metrics.heartbeat_latencies_ms = [10, 20, 30, 40, 50]
        metrics_collector.metrics.avg_heartbeat_latency_ms = 30.0  # Set the calculated average
        metrics_collector.metrics.max_heartbeat_latency_ms = 50
        metrics_collector.metrics.last_heartbeat_latency_ms = 50
        metrics_collector.metrics.failover_count = 2
        metrics_collector.metrics.failover_durations_ms = [1000, 1500]
        metrics_collector.metrics.avg_failover_duration_ms = 1250.0  # Set the calculated average
        metrics_collector.metrics.last_failover_duration_ms = 1500

        snapshot = await metrics_collector.export_metrics_snapshot()

        # Verify gauges
        assert snapshot["gauges"]["gateway_connection_status"] == 1.0
        assert snapshot["gauges"]["gateway_connection_success_rate"] == 80.0
        assert snapshot["gauges"]["gateway_heartbeat_loss_rate"] == 2.0

        # Verify counters
        assert snapshot["counters"]["gateway_connection_attempts_total"] == 10
        assert snapshot["counters"]["gateway_connection_successes_total"] == 8
        assert snapshot["counters"]["gateway_connection_failures_total"] == 2
        assert snapshot["counters"]["gateway_heartbeat_sent_total"] == 100
        assert snapshot["counters"]["gateway_heartbeat_received_total"] == 98
        assert snapshot["counters"]["gateway_failover_total"] == 2

        # Verify histograms
        heartbeat_hist = snapshot["histograms"]["gateway_heartbeat_latency_milliseconds"]
        assert heartbeat_hist["count"] == 5
        assert heartbeat_hist["sum"] == 150
        assert heartbeat_hist["avg"] == 30
        assert heartbeat_hist["max"] == 50
        assert heartbeat_hist["last"] == 50

        failover_hist = snapshot["histograms"]["gateway_failover_duration_milliseconds"]
        assert failover_hist["count"] == 2
        assert failover_hist["sum"] == 2500
        assert failover_hist["avg"] == 1250
        assert failover_hist["last"] == 1500

    @pytest.mark.asyncio
    async def test_metrics_without_sdk(self):
        """Test metrics collector works without SDK metrics."""
        collector = MetricsCollector(sdk_metrics=None)

        # Should not raise any errors
        await collector.record_connection_attempt()
        await collector.record_connection_success()
        await collector.record_connection_failure("network")
        await collector.record_heartbeat_latency(50)
        await collector.record_failover_duration(1500)
        await collector.record_circuit_breaker_state("OPEN")
        await collector.record_message_received("tick")

        # Verify internal metrics still work
        assert collector.metrics.connection_attempts == 1
        assert collector.metrics.connection_successes == 1
        assert collector.metrics.connection_failures == 1
        assert collector.metrics.network_errors == 1

    def test_circuit_state_mapping(self, metrics_collector):
        """Test circuit breaker state to numeric value mapping."""
        assert metrics_collector._map_circuit_state_to_value("CLOSED") == 0.0
        assert metrics_collector._map_circuit_state_to_value("HALF_OPEN") == 0.5
        assert metrics_collector._map_circuit_state_to_value("OPEN") == 1.0
        assert metrics_collector._map_circuit_state_to_value("UNKNOWN") == -1.0

    @pytest.mark.asyncio
    async def test_error_type_categorization(self, metrics_collector, mock_sdk_metrics):
        """Test different error types are properly categorized."""
        error_types = ["auth", "network", "timeout", "circuit_breaker", "unknown"]

        for error_type in error_types:
            await metrics_collector.record_connection_failure(error_type)

        metrics = metrics_collector.metrics
        assert metrics.auth_errors == 1
        assert metrics.network_errors == 1
        assert metrics.timeout_errors == 1
        assert metrics.unknown_errors == 2  # circuit_breaker and unknown both map to unknown

        # Verify SDK calls
        assert mock_sdk_metrics.increment_counter_with_labels.call_count == 5
        for error_type in error_types:
            mock_sdk_metrics.increment_counter_with_labels.assert_any_call(
                "gateway.errors", {"type": error_type}
            )

    def test_runtime_calculation(self, metrics_collector):
        """Test runtime seconds calculation."""
        with patch("domain.gateway.metrics.datetime") as mock_datetime:
            start_time = datetime(2024, 1, 1, 12, 0, 0)
            current_time = datetime(2024, 1, 1, 12, 5, 30)

            metrics_collector.start_time = start_time
            mock_datetime.now.return_value = current_time

            runtime = metrics_collector.get_runtime_seconds()
            assert runtime == 330.0  # 5 minutes 30 seconds
