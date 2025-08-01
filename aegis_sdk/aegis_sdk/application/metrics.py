"""Simple metrics collection for monitoring."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsSummary:
    """Summary of collected metrics."""

    count: int = 0
    total: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    values: list[float] = field(default_factory=list)

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


class Metrics:
    """Simple metrics collector."""

    def __init__(self):
        """Initialize metrics collector."""
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

    def timer(self, name: str):
        """Context manager for timing operations."""

        class Timer:
            def __init__(self, metrics: Metrics, metric_name: str):
                self.metrics = metrics
                self.name = metric_name
                self.start = 0.0

            def __enter__(self):
                self.start = time.time()
                return self

            def __exit__(self, *args):
                duration_ms = (time.time() - self.start) * 1000
                self.metrics.record(self.name, duration_ms)

        return Timer(self, name)

    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        uptime = time.time() - self._start_time

        return {
            "uptime_seconds": round(uptime, 2),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "summaries": {
                name: {
                    "count": summary.count,
                    "average": round(summary.average, 2),
                    "min": round(summary.min, 2) if summary.count > 0 else 0,
                    "max": round(summary.max, 2) if summary.count > 0 else 0,
                    "p50": round(summary.percentile(50), 2),
                    "p90": round(summary.percentile(90), 2),
                    "p99": round(summary.percentile(99), 2),
                }
                for name, summary in self._summaries.items()
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._summaries.clear()


# Global metrics instance
_global_metrics = Metrics()


def get_metrics() -> Metrics:
    """Get the global metrics instance."""
    return _global_metrics
