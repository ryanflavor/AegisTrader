"""Application use cases for Echo Service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

# Python 3.10 compatibility
UTC = UTC

from ..domain.models import EchoRequest, EchoResponse, HealthCheck, ServiceMetrics
from ..domain.services import EchoProcessor, MetricsCollector

logger = logging.getLogger(__name__)


class EchoUseCase:
    """Use case for handling echo requests."""

    def __init__(self, processor: EchoProcessor, metrics: MetricsCollector):
        """Initialize echo use case.

        Args:
            processor: Echo processor domain service
            metrics: Metrics collector
        """
        self.processor = processor
        self.metrics = metrics

    async def execute(self, request: EchoRequest) -> EchoResponse:
        """Execute echo request.

        Args:
            request: Echo request to process

        Returns:
            Echo response
        """
        try:
            # Process the echo request
            response = await self.processor.process_echo(request)

            # Record metrics
            self.metrics.record_request(
                mode=request.mode,
                latency_ms=response.processing_time_ms,
                success=True,
            )

            logger.info(
                f"Processed echo request: mode={request.mode}, "
                f"latency={response.processing_time_ms:.2f}ms"
            )

            return response

        except Exception as e:
            # Record failure
            self.metrics.record_request(mode=request.mode, latency_ms=0.0, success=False)

            logger.error(f"Failed to process echo request: {e}")
            raise


class GetMetricsUseCase:
    """Use case for retrieving service metrics."""

    def __init__(self, instance_id: str, version: str, metrics: MetricsCollector):
        """Initialize metrics use case.

        Args:
            instance_id: Service instance ID
            version: Service version
            metrics: Metrics collector
        """
        self.instance_id = instance_id
        self.version = version
        self.metrics = metrics
        self.last_request_time: datetime | None = None

    async def execute(self) -> ServiceMetrics:
        """Get current service metrics.

        Returns:
            Service metrics
        """
        return ServiceMetrics(
            instance_id=self.instance_id,
            total_requests=self.metrics.total_requests,
            successful_requests=self.metrics.successful_requests,
            failed_requests=self.metrics.failed_requests,
            average_latency_ms=self.metrics.get_average_latency(),
            uptime_seconds=self.metrics.get_uptime_seconds(),
            last_request_at=self.last_request_time,
            mode_distribution=dict(self.metrics.mode_counts),
        )

    def update_last_request_time(self) -> None:
        """Update the last request timestamp."""
        self.last_request_time = datetime.now(UTC)


class HealthCheckUseCase:
    """Use case for health checking."""

    def __init__(self, instance_id: str, version: str):
        """Initialize health check use case.

        Args:
            instance_id: Service instance ID
            version: Service version
        """
        self.instance_id = instance_id
        self.version = version
        self.nats_connected = False

    async def execute(self) -> HealthCheck:
        """Perform health check.

        Returns:
            Health check result
        """
        checks = {
            "nats": self.nats_connected,
            "processor": True,  # Always healthy if we can respond
            "memory": self._check_memory(),
        }

        # Determine overall status
        if all(checks.values()):
            status = "healthy"
        elif checks["nats"]:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthCheck(
            status=status,
            instance_id=self.instance_id,
            version=self.version,
            checks=checks,
        )

    def set_nats_status(self, connected: bool) -> None:
        """Update NATS connection status.

        Args:
            connected: Whether NATS is connected
        """
        self.nats_connected = connected

    def _check_memory(self) -> bool:
        """Check memory usage is within limits."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            # Alert if using more than 256MB
            return memory_mb < 256
        except ImportError:
            # psutil not available, assume healthy
            return True
        except Exception:
            return False
