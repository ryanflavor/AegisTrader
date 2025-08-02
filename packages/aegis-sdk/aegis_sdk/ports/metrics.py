"""Metrics port - Abstract interface for metrics collection.

This port defines the contract for metrics collection in the hexagonal architecture.
It allows the domain and application layers to collect metrics without depending
on specific metrics implementation details.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any


class MetricsPort(ABC):
    """Abstract interface for metrics collection.

    This port decouples the domain and application layers from specific
    metrics implementations, following the Dependency Inversion Principle.
    """

    @abstractmethod
    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: The metric name (e.g., "rpc.service.method.success")
            value: The increment value (default: 1)
        """
        ...

    @abstractmethod
    def gauge(self, name: str, value: float) -> None:
        """Set a gauge metric.

        Args:
            name: The metric name (e.g., "nats.connections")
            value: The gauge value
        """
        ...

    @abstractmethod
    def record(self, name: str, value: float) -> None:
        """Record a value for summary statistics.

        Args:
            name: The metric name (e.g., "rpc.latency_ms")
            value: The value to record
        """
        ...

    @abstractmethod
    def timer(self, name: str) -> AbstractContextManager[Any]:
        """Create a context manager for timing operations.

        Args:
            name: The metric name for the timer

        Returns:
            A context manager that records the operation duration
        """
        ...

    @abstractmethod
    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary containing all collected metrics
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset all metrics."""
        ...
