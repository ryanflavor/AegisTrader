"""Infrastructure adapters implementing the ports."""

from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.ports.logger import Logger

from ..domain.models import HelloRequest, HelloResponse
from ..ports.outbound import AuditLogPort, MetricsPort, NotificationPort


class SimpleMetricsAdapter:
    """Simple in-memory metrics adapter."""

    def __init__(self):
        """Initialize metrics storage."""
        self.request_count = 0
        self.total_response_time = 0.0
        self.response_times: list[float] = []

    async def record_request(self, request: HelloRequest) -> None:
        """Record a request for metrics."""
        self.request_count += 1

    async def record_response_time(self, time_ms: float) -> None:
        """Record response time."""
        self.response_times.append(time_ms)
        self.total_response_time += time_ms

    def get_average_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return self.total_response_time / len(self.response_times)


class LoggerAuditAdapter(AuditLogPort):
    """Audit adapter using logger."""

    def __init__(self, logger: Logger | None = None):
        """Initialize with logger."""
        self.logger = logger or SimpleLogger()

    async def log_request(self, request: HelloRequest) -> None:
        """Log an incoming request."""
        await self.logger.info(
            "Received hello request",
            {
                "request_id": str(request.id),
                "name": request.name,
                "style": request.greeting_style,
            },
        )

    async def log_response(self, response: HelloResponse) -> None:
        """Log an outgoing response."""
        await self.logger.info(
            "Sent hello response",
            {
                "request_id": str(response.request_id),
                "message": response.greeting.message,
                "processing_time_ms": response.processing_time_ms,
            },
        )


class ConsoleNotificationAdapter:
    """Simple console notification adapter."""

    async def notify_greeting_sent(self, response: HelloResponse) -> None:
        """Print notification to console."""
        print(f"🔔 Greeting sent for request {response.request_id}")
        print(f"   Message: {response.greeting.message}")


class NATSNotificationAdapter:
    """NATS-based notification adapter."""

    def __init__(self, nats_client):
        """Initialize with NATS client."""
        self.nats = nats_client

    async def notify_greeting_sent(self, response: HelloResponse) -> None:
        """Publish notification to NATS."""
        await self.nats.publish("hello.notifications", response.model_dump_json().encode())


# Factory functions for creating adapters
def create_metrics_adapter() -> MetricsPort:
    """Create a metrics adapter."""
    return SimpleMetricsAdapter()


def create_audit_adapter(logger: Logger | None = None) -> AuditLogPort:
    """Create an audit log adapter."""
    return LoggerAuditAdapter(logger)


def create_notification_adapter(use_nats: bool = False, nats_client=None) -> NotificationPort:
    """Create a notification adapter."""
    if use_nats and nats_client:
        return NATSNotificationAdapter(nats_client)
    return ConsoleNotificationAdapter()
