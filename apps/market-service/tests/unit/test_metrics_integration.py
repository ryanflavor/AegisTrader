"""
Unit tests for SDK metrics integration.

Tests that market-service properly uses the SDK's metrics capabilities
instead of duplicating them.
"""

from unittest.mock import MagicMock

import pytest
from aegis_sdk.application.metrics import Metrics

from application.metrics_adapter import SDKMetricsAdapter


@pytest.mark.asyncio
class TestSDKMetricsIntegration:
    """Test suite for SDK metrics integration."""

    @pytest.fixture
    def mock_sdk_metrics(self):
        """Create a mock SDK metrics instance that properly inherits from Metrics."""
        # Create a mock that passes isinstance check
        metrics = MagicMock(spec=Metrics)
        metrics.increment = MagicMock()
        metrics.gauge = MagicMock()
        metrics.record = MagicMock()
        metrics.timer = MagicMock()
        metrics.get_all = MagicMock(
            return_value={
                "counters": {"test.counter": 10},
                "gauges": {"test.gauge": 5.5},
                "summaries": {},
            }
        )
        metrics.reset = MagicMock()
        return metrics

    @pytest.fixture
    def metrics_adapter(self, mock_sdk_metrics):
        """Create metrics adapter with mock SDK metrics."""
        return SDKMetricsAdapter(mock_sdk_metrics)

    async def test_increment_counter(self, metrics_adapter, mock_sdk_metrics):
        """Test incrementing a counter metric."""
        await metrics_adapter.increment_counter("gateway.connect.attempts")
        mock_sdk_metrics.increment.assert_called_once_with("gateway.connect.attempts", 1)

        await metrics_adapter.increment_counter("gateway.connect.success", 5)
        mock_sdk_metrics.increment.assert_called_with("gateway.connect.success", 5)

    async def test_set_gauge(self, metrics_adapter, mock_sdk_metrics):
        """Test setting a gauge metric."""
        await metrics_adapter.set_gauge("active.gateways", 3)
        mock_sdk_metrics.gauge.assert_called_once_with("active.gateways", 3)

    async def test_record_timing(self, metrics_adapter, mock_sdk_metrics):
        """Test recording timing metrics."""
        await metrics_adapter.record_timing("rpc.latency", 15.5)
        mock_sdk_metrics.record.assert_called_once_with("rpc.latency", 15.5)

    async def test_timer_context_manager(self, metrics_adapter, mock_sdk_metrics):
        """Test timer context manager."""
        mock_timer = MagicMock()
        mock_timer.__enter__ = MagicMock(return_value=mock_timer)
        mock_timer.__exit__ = MagicMock(return_value=None)
        mock_sdk_metrics.timer.return_value = mock_timer

        async with metrics_adapter.timer("operation.duration"):
            pass

        mock_sdk_metrics.timer.assert_called_once_with("operation.duration")
        mock_timer.__enter__.assert_called_once()
        mock_timer.__exit__.assert_called_once()

    async def test_get_metrics_snapshot(self, metrics_adapter, mock_sdk_metrics):
        """Test getting metrics snapshot."""
        snapshot = await metrics_adapter.get_snapshot()

        mock_sdk_metrics.get_all.assert_called_once()
        assert snapshot["counters"]["test.counter"] == 10
        assert snapshot["gauges"]["test.gauge"] == 5.5

    async def test_reset_metrics(self, metrics_adapter, mock_sdk_metrics):
        """Test resetting metrics."""
        await metrics_adapter.reset()
        mock_sdk_metrics.reset.assert_called_once()

    async def test_domain_specific_metrics(self, metrics_adapter, mock_sdk_metrics):
        """Test domain-specific metric helpers."""
        # Test gateway metrics
        await metrics_adapter.record_gateway_connected("ctp-gateway")
        assert mock_sdk_metrics.increment.call_args_list[-1] == (("gateway.connected", 1), {})
        assert mock_sdk_metrics.gauge.call_args_list[-1] == (("gateway.ctp-gateway.status", 1), {})

        await metrics_adapter.record_gateway_disconnected("ctp-gateway")
        assert mock_sdk_metrics.increment.call_args_list[-1] == (("gateway.disconnected", 1), {})
        assert mock_sdk_metrics.gauge.call_args_list[-1] == (("gateway.ctp-gateway.status", 0), {})

        # Test tick processing metrics - checks both calls were made
        await metrics_adapter.record_tick_processed("AAPL", "NASDAQ")
        increment_calls = [call[0] for call in mock_sdk_metrics.increment.call_args_list[-2:]]
        assert ("ticks.processed.total", 1) in increment_calls
        assert ("ticks.NASDAQ.AAPL", 1) in increment_calls

        # Test subscription metrics - checks both calls were made
        await metrics_adapter.record_subscription_created("AAPL", "NASDAQ")
        increment_calls = [call[0] for call in mock_sdk_metrics.increment.call_args_list[-2:]]
        assert ("subscriptions.created", 1) in increment_calls
        assert ("subscriptions.NASDAQ.AAPL", 1) in increment_calls

    async def test_error_handling(self, metrics_adapter, mock_sdk_metrics):
        """Test error handling in metrics operations."""
        # Simulate SDK metrics error
        mock_sdk_metrics.increment.side_effect = Exception("Metrics error")

        # Should not raise exception
        await metrics_adapter.increment_counter("test.counter")

        # Should log error (in real implementation)
        mock_sdk_metrics.increment.assert_called_once()

    async def test_batch_metrics_recording(self, metrics_adapter, mock_sdk_metrics):
        """Test batch recording of metrics."""
        metrics_batch = [
            ("counter", "test.counter1", 1),
            ("counter", "test.counter2", 2),
            ("gauge", "test.gauge1", 3.5),
            ("timing", "test.timing1", 10.5),
        ]

        await metrics_adapter.record_batch(metrics_batch)

        assert mock_sdk_metrics.increment.call_count == 2
        mock_sdk_metrics.increment.assert_any_call("test.counter1", 1)
        mock_sdk_metrics.increment.assert_any_call("test.counter2", 2)
        mock_sdk_metrics.gauge.assert_called_once_with("test.gauge1", 3.5)
        mock_sdk_metrics.record.assert_called_once_with("test.timing1", 10.5)

    async def test_metrics_with_labels(self, metrics_adapter, mock_sdk_metrics):
        """Test metrics with labels/tags."""
        await metrics_adapter.increment_counter_with_labels(
            "rpc.calls", {"service": "market-service", "method": "connect_gateway"}
        )

        # Should create a labeled metric name (labels are sorted alphabetically)
        mock_sdk_metrics.increment.assert_called_with(
            "rpc.calls.method_connect_gateway.service_market-service", 1
        )

    async def test_metrics_aggregation(self, metrics_adapter, mock_sdk_metrics):
        """Test metrics aggregation for reporting."""
        mock_sdk_metrics.get_all.return_value = {
            "counters": {
                "gateway.connected": 5,
                "gateway.disconnected": 2,
                "ticks.processed.total": 1000,
            },
            "gauges": {"active.gateways": 3, "memory.usage": 256.5},
            "summaries": {
                "rpc.latency": {
                    "count": 100,
                    "average": 15.5,
                    "min": 5.0,
                    "max": 50.0,
                    "p50": 14.0,
                    "p90": 25.0,
                    "p99": 45.0,
                }
            },
        }

        report = await metrics_adapter.get_metrics_report()

        assert report["gateway"]["connected"] == 5
        assert report["gateway"]["disconnected"] == 2
        assert report["gateway"]["active"] == 3
        assert report["processing"]["ticks_total"] == 1000
        assert report["performance"]["rpc_latency_avg"] == 15.5
        assert report["performance"]["rpc_latency_p99"] == 45.0

    async def test_metrics_export_format(self, metrics_adapter, mock_sdk_metrics):
        """Test exporting metrics in various formats."""
        # Set up mock data for export test
        mock_sdk_metrics.get_all.return_value = {
            "counters": {"gateway.connected": 5},
            "gauges": {"test.gauge": 5.5},
            "summaries": {},
        }

        # Test Prometheus format
        prometheus_metrics = await metrics_adapter.export_prometheus_format()
        assert "# TYPE gateway_connected counter" in prometheus_metrics
        assert "gateway_connected 5" in prometheus_metrics

        # Test JSON format
        json_metrics = await metrics_adapter.export_json_format()
        assert isinstance(json_metrics, dict)
        assert "timestamp" in json_metrics
        assert "metrics" in json_metrics
