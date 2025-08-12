"""Domain events for Echo Service following DDD principles.

Domain events represent significant business occurrences that have happened in the past.
They are immutable and used for event-driven communication.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .value_objects import EchoMode, HealthStatus, MessagePriority


class DomainEvent(BaseModel):
    """Base class for all domain events.

    All events are immutable and contain metadata about when and where they occurred.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of the event")
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When the event occurred"
    )
    aggregate_id: str = Field(..., description="ID of the aggregate that generated the event")
    version: int = Field(default=1, description="Event version for schema evolution")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")


class EchoRequestReceived(DomainEvent):
    """Event raised when an echo request is received."""

    event_type: str = Field(default="echo.request.received")
    request_id: str = Field(..., description="Unique request identifier")
    message: str = Field(..., description="The message to echo")
    mode: EchoMode = Field(..., description="Echo mode requested")
    priority: MessagePriority = Field(..., description="Request priority")
    instance_id: str = Field(..., description="Instance handling the request")


class EchoRequestProcessed(DomainEvent):
    """Event raised when an echo request has been successfully processed."""

    event_type: str = Field(default="echo.request.processed")
    request_id: str = Field(..., description="Unique request identifier")
    original_message: str = Field(..., description="Original message")
    echoed_message: str = Field(..., description="Processed message")
    mode: EchoMode = Field(..., description="Echo mode used")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    instance_id: str = Field(..., description="Instance that processed the request")


class EchoRequestFailed(DomainEvent):
    """Event raised when an echo request processing fails."""

    event_type: str = Field(default="echo.request.failed")
    request_id: str = Field(..., description="Unique request identifier")
    error_message: str = Field(..., description="Error description")
    error_code: str | None = Field(default=None, description="Error code if applicable")
    mode: EchoMode = Field(..., description="Echo mode that was attempted")
    instance_id: str = Field(..., description="Instance where failure occurred")


class BatchEchoRequestReceived(DomainEvent):
    """Event raised when a batch of echo requests is received."""

    event_type: str = Field(default="echo.batch.received")
    batch_id: str = Field(..., description="Unique batch identifier")
    request_count: int = Field(..., description="Number of requests in batch")
    modes_used: list[str] = Field(..., description="List of modes in the batch")
    instance_id: str = Field(..., description="Instance handling the batch")


class BatchEchoRequestCompleted(DomainEvent):
    """Event raised when a batch of echo requests has been processed."""

    event_type: str = Field(default="echo.batch.completed")
    batch_id: str = Field(..., description="Unique batch identifier")
    total_requests: int = Field(..., description="Total requests in batch")
    successful_requests: int = Field(..., description="Number of successful requests")
    failed_requests: int = Field(..., description="Number of failed requests")
    total_processing_time_ms: float = Field(..., description="Total processing time")
    instance_id: str = Field(..., description="Instance that processed the batch")


class ServiceRegistered(DomainEvent):
    """Event raised when a service instance is registered."""

    event_type: str = Field(default="service.registered")
    instance_id: str = Field(..., description="Service instance identifier")
    service_name: str = Field(..., description="Name of the service")
    version: str = Field(..., description="Service version")
    nats_url: str = Field(..., description="NATS connection URL")


class ServiceDeregistered(DomainEvent):
    """Event raised when a service instance is deregistered."""

    event_type: str = Field(default="service.deregistered")
    instance_id: str = Field(..., description="Service instance identifier")
    reason: str = Field(..., description="Reason for deregistration")


class ServiceHealthChanged(DomainEvent):
    """Event raised when service health status changes."""

    event_type: str = Field(default="service.health.changed")
    instance_id: str = Field(..., description="Service instance identifier")
    previous_status: HealthStatus = Field(..., description="Previous health status")
    current_status: HealthStatus = Field(..., description="Current health status")
    checks_passed: list[str] = Field(default_factory=list, description="Health checks that passed")
    checks_failed: list[str] = Field(default_factory=list, description="Health checks that failed")


class MetricsSnapshotTaken(DomainEvent):
    """Event raised when a metrics snapshot is taken."""

    event_type: str = Field(default="metrics.snapshot.taken")
    instance_id: str = Field(..., description="Service instance identifier")
    total_requests: int = Field(..., description="Total requests processed")
    success_rate: float = Field(..., description="Success rate percentage")
    average_latency_ms: float = Field(..., description="Average latency")
    uptime_seconds: float = Field(..., description="Service uptime")


class HighPriorityRequestReceived(DomainEvent):
    """Event raised when a high-priority request is received."""

    event_type: str = Field(default="request.high_priority.received")
    request_id: str = Field(..., description="Request identifier")
    priority: MessagePriority = Field(..., description="Request priority level")
    message: str = Field(..., description="Request message")
    instance_id: str = Field(..., description="Instance handling the request")


class RequestRateLimitExceeded(DomainEvent):
    """Event raised when request rate limit is exceeded."""

    event_type: str = Field(default="request.rate_limit.exceeded")
    instance_id: str = Field(..., description="Service instance identifier")
    current_rate: float = Field(..., description="Current request rate")
    limit_rate: float = Field(..., description="Maximum allowed rate")
    client_id: str | None = Field(default=None, description="Client identifier if available")


class TransformationFailed(DomainEvent):
    """Event raised when a message transformation fails."""

    event_type: str = Field(default="transformation.failed")
    request_id: str = Field(..., description="Request identifier")
    transformation_type: str = Field(..., description="Type of transformation attempted")
    error_message: str = Field(..., description="Error description")
    fallback_used: bool = Field(..., description="Whether fallback was used")
    instance_id: str = Field(..., description="Instance where failure occurred")


class ServiceConfigurationChanged(DomainEvent):
    """Event raised when service configuration is updated."""

    event_type: str = Field(default="service.configuration.changed")
    instance_id: str = Field(..., description="Service instance identifier")
    configuration_key: str = Field(..., description="Configuration key that changed")
    previous_value: Any = Field(..., description="Previous configuration value")
    new_value: Any = Field(..., description="New configuration value")


class PerformanceDegradationDetected(DomainEvent):
    """Event raised when performance degradation is detected."""

    event_type: str = Field(default="performance.degradation.detected")
    instance_id: str = Field(..., description="Service instance identifier")
    metric_type: str = Field(..., description="Type of metric showing degradation")
    threshold_value: float = Field(..., description="Threshold that was exceeded")
    actual_value: float = Field(..., description="Actual measured value")
    duration_seconds: float = Field(..., description="Duration of degradation")


class DomainEventPublisher:
    """Publisher for domain events.

    Handles the publication and distribution of domain events.
    """

    def __init__(self):
        """Initialize the event publisher."""
        self._handlers: dict[str, list] = {}
        self._event_store: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event.

        Args:
            event: The domain event to publish
        """
        # Store event
        self._event_store.append(event)

        # Notify handlers
        event_type = event.event_type
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                handler(event)

    def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: The type of event to subscribe to
            handler: The handler function to call when event occurs
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def get_events(
        self, aggregate_id: str | None = None, event_type: str | None = None, limit: int = 100
    ) -> list[DomainEvent]:
        """Get stored events with optional filtering.

        Args:
            aggregate_id: Filter by aggregate ID
            event_type: Filter by event type
            limit: Maximum number of events to return

        Returns:
            List of domain events
        """
        events = self._event_store

        if aggregate_id:
            events = [e for e in events if e.aggregate_id == aggregate_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:] if len(events) > limit else events
