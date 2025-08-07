"""Application use cases for Hello World service."""

from datetime import datetime, timezone

from ..domain.models import HelloRequest, HelloResponse, ServiceStatus
from ..ports.outbound import AuditLogPort, MetricsPort, NotificationPort


class HelloUseCase:
    """Application service for processing hello requests."""

    def __init__(
        self,
        metrics: MetricsPort | None = None,
        audit_log: AuditLogPort | None = None,
        notification: NotificationPort | None = None,
    ):
        """Initialize use case with optional dependencies."""
        self.metrics = metrics
        self.audit_log = audit_log
        self.notification = notification
        self.status = ServiceStatus(
            healthy=True,
            uptime_seconds=0,
            requests_processed=0,
            version="1.0.0",
        )
        self.start_time = datetime.now(timezone.utc)

    async def process_hello(self, request: HelloRequest) -> HelloResponse:
        """Process a hello request following business rules."""
        start_time = datetime.now(timezone.utc)

        # Log the incoming request
        if self.audit_log:
            await self.audit_log.log_request(request)

        # Record metrics
        if self.metrics:
            await self.metrics.record_request(request)

        # Apply business logic to generate greeting
        greeting = request.to_greeting()

        # Create response
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        response = HelloResponse(
            request_id=request.id,
            greeting=greeting,
            processing_time_ms=processing_time,
        )

        # Update status
        self.status.increment_requests()

        # Log the response
        if self.audit_log:
            await self.audit_log.log_response(response)

        # Record response time
        if self.metrics:
            await self.metrics.record_response_time(processing_time)

        # Send notification
        if self.notification:
            await self.notification.notify_greeting_sent(response)

        return response

    async def get_status(self) -> ServiceStatus:
        """Get current service status."""
        # Update uptime
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.status.uptime_seconds = uptime
        return self.status


class HealthCheckUseCase:
    """Use case for health checking."""

    def __init__(self, hello_use_case: HelloUseCase):
        """Initialize with hello use case for status."""
        self.hello_use_case = hello_use_case

    async def check_health(self) -> dict:
        """Perform health check and return status."""
        status = await self.hello_use_case.get_status()
        return {
            "status": "healthy" if status.healthy else "unhealthy",
            "uptime_seconds": status.uptime_seconds,
            "requests_processed": status.requests_processed,
            "last_request_at": status.last_request_at.isoformat()
            if status.last_request_at
            else None,
            "version": status.version,
        }
