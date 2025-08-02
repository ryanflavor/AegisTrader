"""Tests for the in-memory metrics implementation."""

import pytest
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics, get_metrics, set_metrics
from aegis_sdk.ports.metrics import MetricsPort


class TestInMemoryMetrics:
    """Test cases for InMemoryMetrics implementation."""

    def test_implements_metrics_port(self):
        """Test that InMemoryMetrics properly implements MetricsPort."""
        metrics = InMemoryMetrics()
        assert isinstance(metrics, MetricsPort)

    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        metrics = InMemoryMetrics()

        # Initial state
        all_metrics = metrics.get_all()
        assert all_metrics["counters"] == {}

        # Increment counter
        metrics.increment("requests.total")
        all_metrics = metrics.get_all()
        assert all_metrics["counters"]["requests.total"] == 1

        # Increment again
        metrics.increment("requests.total")
        all_metrics = metrics.get_all()
        assert all_metrics["counters"]["requests.total"] == 2

        # Increment by custom value
        metrics.increment("requests.total", 5)
        all_metrics = metrics.get_all()
        assert all_metrics["counters"]["requests.total"] == 7

    def test_multiple_counters(self):
        """Test multiple independent counters."""
        metrics = InMemoryMetrics()

        metrics.increment("api.calls")
        metrics.increment("api.errors", 2)
        metrics.increment("api.calls", 3)

        all_metrics = metrics.get_all()
        assert all_metrics["counters"]["api.calls"] == 4
        assert all_metrics["counters"]["api.errors"] == 2

    def test_gauge_metrics(self):
        """Test gauge metrics."""
        metrics = InMemoryMetrics()

        # Set gauge
        metrics.gauge("memory.usage", 75.5)
        all_metrics = metrics.get_all()
        assert all_metrics["gauges"]["memory.usage"] == 75.5

        # Update gauge
        metrics.gauge("memory.usage", 80.2)
        all_metrics = metrics.get_all()
        assert all_metrics["gauges"]["memory.usage"] == 80.2

        # Multiple gauges
        metrics.gauge("cpu.usage", 45.0)
        all_metrics = metrics.get_all()
        assert all_metrics["gauges"]["memory.usage"] == 80.2
        assert all_metrics["gauges"]["cpu.usage"] == 45.0

    def test_record_summary_metrics(self):
        """Test recording values for summary statistics."""
        metrics = InMemoryMetrics()

        # Record values
        metrics.record("latency", 100.0)
        metrics.record("latency", 200.0)
        metrics.record("latency", 150.0)

        all_metrics = metrics.get_all()
        summary = all_metrics["summaries"]["latency"]

        assert summary["count"] == 3
        assert summary["average"] == 150.0
        assert summary["min"] == 100.0
        assert summary["max"] == 200.0
        assert summary["p50"] == 150.0

    def test_timer_context_manager(self):
        """Test timer context manager."""
        metrics = InMemoryMetrics()

        # Use timer
        with metrics.timer("operation.duration"):
            # Simulate some work
            import time

            time.sleep(0.01)  # 10ms

        all_metrics = metrics.get_all()
        summary = all_metrics["summaries"]["operation.duration"]

        assert summary["count"] == 1
        assert summary["min"] >= 10.0  # At least 10ms
        assert summary["max"] >= 10.0

    def test_timer_with_exception(self):
        """Test timer records duration even with exception."""
        metrics = InMemoryMetrics()

        try:
            with metrics.timer("failed.operation"):
                import time

                time.sleep(0.01)
                raise ValueError("Test error")
        except ValueError:
            pass

        all_metrics = metrics.get_all()
        summary = all_metrics["summaries"]["failed.operation"]

        assert summary["count"] == 1
        assert summary["min"] >= 10.0

    def test_percentiles(self):
        """Test percentile calculations."""
        metrics = InMemoryMetrics()

        # Record values from 1 to 100
        for i in range(1, 101):
            metrics.record("test.metric", float(i))

        all_metrics = metrics.get_all()
        summary = all_metrics["summaries"]["test.metric"]

        assert summary["count"] == 100
        assert summary["p50"] == pytest.approx(50.0, abs=1.0)
        assert summary["p90"] == pytest.approx(90.0, abs=1.0)
        assert summary["p99"] == pytest.approx(99.0, abs=1.0)

    def test_reset_metrics(self):
        """Test resetting all metrics."""
        import time

        metrics = InMemoryMetrics()

        # Wait a tiny bit to ensure uptime > 0
        time.sleep(0.01)

        # Add some metrics
        metrics.increment("counter", 5)
        metrics.gauge("gauge", 10.0)
        metrics.record("summary", 100.0)

        # Verify they exist
        all_metrics = metrics.get_all()
        assert len(all_metrics["counters"]) > 0
        assert len(all_metrics["gauges"]) > 0
        assert len(all_metrics["summaries"]) > 0

        # Reset
        metrics.reset()

        # Verify cleared
        all_metrics = metrics.get_all()
        assert all_metrics["counters"] == {}
        assert all_metrics["gauges"] == {}
        assert all_metrics["summaries"] == {}

        # Uptime should not be reset
        assert all_metrics["uptime_seconds"] > 0

    def test_uptime_tracking(self):
        """Test that uptime is tracked correctly."""
        metrics = InMemoryMetrics()

        import time

        time.sleep(0.1)  # Wait 100ms

        all_metrics = metrics.get_all()
        assert all_metrics["uptime_seconds"] >= 0.1

    def test_empty_summary_handling(self):
        """Test handling of empty summaries."""
        metrics = InMemoryMetrics()

        # Don't record any values, just check the structure
        all_metrics = metrics.get_all()
        assert all_metrics["summaries"] == {}


class TestMetricsGlobalFunctions:
    """Test cases for global metrics functions."""

    def test_get_metrics_singleton(self):
        """Test that get_metrics returns singleton."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2
        assert isinstance(metrics1, MetricsPort)

    def test_set_metrics(self):
        """Test setting custom metrics implementation."""

        # Create a mock metrics implementation
        class MockMetrics(MetricsPort):
            def __init__(self):
                self.incremented = {}

            def increment(self, name: str, value: int = 1) -> None:
                self.incremented[name] = self.incremented.get(name, 0) + value

            def gauge(self, name: str, value: float) -> None:
                pass

            def record(self, name: str, value: float) -> None:
                pass

            def timer(self, name: str):
                from contextlib import contextmanager

                @contextmanager
                def _timer():
                    yield

                return _timer()

            def get_all(self) -> dict:
                return {"incremented": self.incremented}

            def reset(self) -> None:
                self.incremented.clear()

        # Set custom implementation
        mock_metrics = MockMetrics()
        set_metrics(mock_metrics)

        # Verify it's used
        metrics = get_metrics()
        assert metrics is mock_metrics

        # Test it works
        metrics.increment("test.counter")
        assert metrics.get_all()["incremented"]["test.counter"] == 1

        # Reset to default for other tests
        set_metrics(None)
