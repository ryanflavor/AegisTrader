"""Interface definitions for market-service."""

from abc import abstractmethod
from typing import Any, Protocol


class MessageBusPort(Protocol):
    """Message bus port interface."""

    @abstractmethod
    async def publish(self, topic: str, message: Any) -> None:
        """Publish message to topic."""
        ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Any) -> None:
        """Subscribe to topic."""
        ...


class CachePort(Protocol):
    """Cache port interface."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in cache with TTL."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        ...


class LoggerPort(Protocol):
    """Logger port interface."""

    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        ...

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        ...

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        ...


class MetricsPort(Protocol):
    """Metrics port interface."""

    @abstractmethod
    def increment(self, metric: str, value: int = 1, tags: dict = None) -> None:
        """Increment counter metric."""
        ...

    @abstractmethod
    def gauge(self, metric: str, value: float, tags: dict = None) -> None:
        """Set gauge metric."""
        ...

    @abstractmethod
    def histogram(self, metric: str, value: float, tags: dict = None) -> None:
        """Record histogram metric."""
        ...
