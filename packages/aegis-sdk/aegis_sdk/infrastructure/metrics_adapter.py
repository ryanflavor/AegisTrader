"""Metrics adapter - Concrete implementation of MetricsPort.

This adapter implements the MetricsPort interface using the existing
Metrics implementation, following the hexagonal architecture pattern.
"""

from contextlib import AbstractContextManager
from typing import Any

from ..application.metrics import Metrics, get_metrics
from ..ports.metrics import MetricsPort


class MetricsAdapter(MetricsPort):
    """Adapter that implements MetricsPort using the existing Metrics class."""

    def __init__(self, metrics: Metrics | None = None):
        """Initialize the metrics adapter.

        Args:
            metrics: Optional metrics instance. If not provided, uses the global instance.
        """
        self._metrics = metrics or get_metrics()

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self._metrics.increment(name, value)

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge metric."""
        self._metrics.gauge(name, value)

    def record(self, name: str, value: float) -> None:
        """Record a value for summary statistics."""
        self._metrics.record(name, value)

    def timer(self, name: str) -> AbstractContextManager[Any]:
        """Create a context manager for timing operations."""
        return self._metrics.timer(name)  # type: ignore[no-any-return]

    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        return self._metrics.get_all()

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.reset()
