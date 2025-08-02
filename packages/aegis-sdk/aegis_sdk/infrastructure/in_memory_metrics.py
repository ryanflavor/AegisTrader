"""In-memory metrics implementation following hexagonal architecture.

This is a pure infrastructure implementation that doesn't depend on
application or domain layers, only on the metrics port interface.
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any

from ..ports.metrics import MetricsPort


class MetricsSummary:
    """Summary statistics for a metric."""

    def __init__(self):
        """Initialize metrics summary."""
        self.count: int = 0
        self.total: float = 0.0
        self.min: float = float("inf")
        self.max: float = float("-inf")
        self.values: list[float] = []

    def add(self, value: float) -> None:
        """Add a value to the summary."""
        self.count += 1
        self.total += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.values.append(value)

    @property
    def average(self) -> float:
        """Calculate average value."""
        return self.total / self.count if self.count > 0 else 0.0

    def percentile(self, p: float) -> float:
        """Calculate percentile (0-100)."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        index = int((p / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary format."""
        return {
            "count": self.count,
            "average": round(self.average, 2),
            "min": round(self.min, 2) if self.count > 0 else 0,
            "max": round(self.max, 2) if self.count > 0 else 0,
            "p50": round(self.percentile(50), 2),
            "p90": round(self.percentile(90), 2),
            "p99": round(self.percentile(99), 2),
        }


class InMemoryMetrics(MetricsPort):
    """In-memory implementation of the MetricsPort.

    This is a pure infrastructure implementation that stores metrics
    in memory without any dependencies on application or domain layers.
    """

    def __init__(self):
        """Initialize in-memory metrics collector."""
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._summaries: dict[str, MetricsSummary] = defaultdict(MetricsSummary)
        self._start_time = time.time()

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[name] += value

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge metric."""
        self._gauges[name] = value

    def record(self, name: str, value: float) -> None:
        """Record a value for summary statistics."""
        self._summaries[name].add(value)

    @contextmanager
    def timer(self, name: str):
        """Context manager for timing operations."""
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.record(name, duration_ms)

    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        uptime = time.time() - self._start_time

        return {
            "uptime_seconds": round(uptime, 2),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "summaries": {name: summary.to_dict() for name, summary in self._summaries.items()},
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._summaries.clear()
        # Don't reset start time


# Global instance for convenience (can be replaced with DI)
_global_metrics: MetricsPort | None = None


def get_metrics() -> MetricsPort:
    """Get the global metrics instance.

    This is a convenience function for cases where dependency injection
    is not feasible. In production code, prefer passing MetricsPort
    instances through constructors.
    """
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = InMemoryMetrics()
    return _global_metrics


def set_metrics(metrics: MetricsPort) -> None:
    """Set the global metrics instance.

    This allows replacing the default in-memory implementation
    with other implementations (e.g., Prometheus, StatsD).
    """
    global _global_metrics
    _global_metrics = metrics
