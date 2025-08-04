"""Tests for metrics module."""

from unittest.mock import patch

import pytest

from aegis_sdk.application.metrics import Metrics, MetricsSummary, get_metrics
from aegis_sdk.domain.metrics_models import MetricsSnapshot, MetricsSummaryData


class TestMetricsSummary:
    """Test cases for MetricsSummary class."""

    def test_metrics_summary_initialization(self):
        """Test MetricsSummary initialization."""
        summary = MetricsSummary()
        assert summary.count == 0
        assert summary.total == 0.0
        assert summary.min == float("inf")
        assert summary.max == float("-inf")
        assert summary.values == []

    def test_add_single_value(self):
        """Test adding a single value."""
        summary = MetricsSummary()
        summary.add(10.5)

        assert summary.count == 1
        assert summary.total == 10.5
        assert summary.min == 10.5
        assert summary.max == 10.5
        assert summary.values == [10.5]
        assert summary.average == 10.5

    def test_add_multiple_values(self):
        """Test adding multiple values."""
        summary = MetricsSummary()
        values = [5.0, 10.0, 15.0, 20.0, 25.0]

        for value in values:
            summary.add(value)

        assert summary.count == 5
        assert summary.total == 75.0
        assert summary.min == 5.0
        assert summary.max == 25.0
        assert summary.values == values
        assert summary.average == 15.0

    def test_percentile_calculation(self):
        """Test percentile calculations."""
        summary = MetricsSummary()
        # Add values 1 through 100
        for i in range(1, 101):
            summary.add(float(i))

        assert summary.percentile(0) == 1.0
        assert summary.percentile(50) == 51.0  # 50th percentile of 1-100 is 51
        assert summary.percentile(90) == 91.0  # 90th percentile of 1-100 is 91
        assert summary.percentile(99) == 100.0  # 99th percentile of 1-100 is 100
        assert summary.percentile(100) == 100.0

    def test_percentile_empty_values(self):
        """Test percentile with no values."""
        summary = MetricsSummary()
        assert summary.percentile(50) == 0.0

    def test_percentile_single_value(self):
        """Test percentile with single value."""
        summary = MetricsSummary()
        summary.add(42.0)

        assert summary.percentile(0) == 42.0
        assert summary.percentile(50) == 42.0
        assert summary.percentile(100) == 42.0

    def test_to_pydantic(self):
        """Test conversion to Pydantic model."""
        summary = MetricsSummary()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]

        for value in values:
            summary.add(value)

        pydantic_model = summary.to_pydantic()

        assert isinstance(pydantic_model, MetricsSummaryData)
        assert pydantic_model.count == 5
        assert pydantic_model.average == 3.0
        assert pydantic_model.min == 1.0
        assert pydantic_model.max == 5.0
        assert pydantic_model.p50 == 3.0
        assert pydantic_model.p90 == 5.0
        assert pydantic_model.p99 == 5.0

    def test_to_pydantic_empty(self):
        """Test conversion to Pydantic model with no data."""
        summary = MetricsSummary()
        pydantic_model = summary.to_pydantic()

        assert pydantic_model.count == 0
        assert pydantic_model.average == 0.0
        assert pydantic_model.min == 0.0
        assert pydantic_model.max == 0.0
        assert pydantic_model.p50 == 0.0


class TestMetrics:
    """Test cases for Metrics class."""

    def test_metrics_initialization(self):
        """Test Metrics initialization."""
        metrics = Metrics()
        assert isinstance(metrics._counters, dict)
        assert isinstance(metrics._gauges, dict)
        assert isinstance(metrics._summaries, dict)
        assert metrics._start_time > 0

    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        metrics = Metrics()

        # Default increment
        metrics.increment("requests")
        assert metrics._counters["requests"] == 1

        # Increment again
        metrics.increment("requests")
        assert metrics._counters["requests"] == 2

        # Increment by custom value
        metrics.increment("errors", 5)
        assert metrics._counters["errors"] == 5

    def test_gauge_metric(self):
        """Test gauge metrics."""
        metrics = Metrics()

        metrics.gauge("temperature", 23.5)
        assert metrics._gauges["temperature"] == 23.5

        # Update gauge
        metrics.gauge("temperature", 24.0)
        assert metrics._gauges["temperature"] == 24.0

    def test_record_summary(self):
        """Test recording summary statistics."""
        metrics = Metrics()

        metrics.record("response_time", 100.0)
        metrics.record("response_time", 200.0)
        metrics.record("response_time", 150.0)

        summary = metrics._summaries["response_time"]
        assert summary.count == 3
        assert summary.average == 150.0

    def test_timer_context_manager(self):
        """Test timer context manager."""
        metrics = Metrics()

        with patch("time.time") as mock_time:
            # Mock time progression
            mock_time.side_effect = [0.0, 0.1]  # 100ms duration

            with metrics.timer("operation"):
                pass

        summary = metrics._summaries["operation"]
        assert summary.count == 1
        assert summary.values[0] == 100.0  # 100ms in milliseconds

    def test_get_snapshot(self):
        """Test getting metrics snapshot."""
        metrics = Metrics()

        # Add some metrics
        metrics.increment("requests", 10)
        metrics.gauge("active_connections", 5)
        metrics.record("latency", 50.0)
        metrics.record("latency", 100.0)

        with patch("time.time") as mock_time:
            mock_time.return_value = metrics._start_time + 60  # 60 seconds uptime
            snapshot = metrics.get_snapshot()

        assert isinstance(snapshot, MetricsSnapshot)
        assert snapshot.uptime_seconds == 60.0
        assert snapshot.counters["requests"] == 10
        assert snapshot.gauges["active_connections"] == 5
        assert "latency" in snapshot.summaries
        assert snapshot.summaries["latency"].count == 2
        assert snapshot.summaries["latency"].average == 75.0

    def test_get_all(self):
        """Test getting all metrics as dictionary."""
        metrics = Metrics()

        metrics.increment("test_counter")
        metrics.gauge("test_gauge", 42.0)

        all_metrics = metrics.get_all()

        assert isinstance(all_metrics, dict)
        assert "uptime_seconds" in all_metrics
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "summaries" in all_metrics
        assert all_metrics["counters"]["test_counter"] == 1
        assert all_metrics["gauges"]["test_gauge"] == 42.0

    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = Metrics()

        # Add some metrics
        metrics.increment("counter", 5)
        metrics.gauge("gauge", 10.0)
        metrics.record("summary", 15.0)

        # Reset
        metrics.reset()

        assert len(metrics._counters) == 0
        assert len(metrics._gauges) == 0
        assert len(metrics._summaries) == 0

    def test_multiple_summaries(self):
        """Test multiple independent summary metrics."""
        metrics = Metrics()

        # Record different metrics
        metrics.record("api_latency", 10.0)
        metrics.record("api_latency", 20.0)
        metrics.record("db_latency", 5.0)
        metrics.record("db_latency", 15.0)

        api_summary = metrics._summaries["api_latency"]
        db_summary = metrics._summaries["db_latency"]

        assert api_summary.average == 15.0
        assert db_summary.average == 10.0


class TestGlobalMetrics:
    """Test cases for global metrics instance."""

    def test_get_metrics_returns_singleton(self):
        """Test that get_metrics returns the same instance."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    def test_global_metrics_functionality(self):
        """Test that global metrics instance works correctly."""
        metrics = get_metrics()

        # Reset to ensure clean state
        metrics.reset()

        metrics.increment("global_counter")
        metrics.gauge("global_gauge", 99.9)

        snapshot = metrics.get_snapshot()
        assert snapshot.counters["global_counter"] == 1
        assert snapshot.gauges["global_gauge"] == 99.9


class TestMetricsIntegration:
    """Integration tests for metrics functionality."""

    @pytest.mark.asyncio
    async def test_metrics_in_async_context(self):
        """Test metrics work in async context."""
        metrics = Metrics()

        async def async_operation():
            with metrics.timer("async_op"):
                await asyncio.sleep(0.01)  # Small delay

        import asyncio

        await async_operation()

        summary = metrics._summaries["async_op"]
        assert summary.count == 1
        assert summary.values[0] >= 10.0  # At least 10ms

    def test_metrics_thread_safety_scenario(self):
        """Test basic thread safety scenario."""
        # Note: The current implementation uses defaultdict which has
        # some thread safety for basic operations, but a production
        # system might need explicit locking
        metrics = Metrics()

        # Simulate concurrent updates
        for _i in range(100):
            metrics.increment("concurrent_counter")

        assert metrics._counters["concurrent_counter"] == 100

    def test_large_number_of_metrics(self):
        """Test handling large number of different metrics."""
        metrics = Metrics()

        # Create many different metrics
        for i in range(1000):
            metrics.increment(f"counter_{i}")
            metrics.gauge(f"gauge_{i}", float(i))
            metrics.record(f"summary_{i}", float(i))

        snapshot = metrics.get_snapshot()
        assert len(snapshot.counters) == 1000
        assert len(snapshot.gauges) == 1000
        assert len(snapshot.summaries) == 1000
