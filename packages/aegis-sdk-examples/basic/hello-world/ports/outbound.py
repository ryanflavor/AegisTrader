"""Outbound ports (interfaces) for Hello World service."""

from abc import ABC, abstractmethod
from typing import Protocol

from ..domain.models import HelloRequest, HelloResponse


class MetricsPort(Protocol):
    """Port for metrics collection."""

    async def record_request(self, request: HelloRequest) -> None:
        """Record a request for metrics."""
        ...

    async def record_response_time(self, time_ms: float) -> None:
        """Record response time."""
        ...


class AuditLogPort(ABC):
    """Abstract port for audit logging."""

    @abstractmethod
    async def log_request(self, request: HelloRequest) -> None:
        """Log an incoming request."""
        pass

    @abstractmethod
    async def log_response(self, response: HelloResponse) -> None:
        """Log an outgoing response."""
        pass


class NotificationPort(Protocol):
    """Port for sending notifications."""

    async def notify_greeting_sent(self, response: HelloResponse) -> None:
        """Notify that a greeting was sent."""
        ...
