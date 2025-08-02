"""Domain aggregates following Domain-Driven Design principles.

Aggregates are clusters of domain objects that can be treated as a single unit.
They enforce consistency boundaries and encapsulate business rules.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .models import ServiceInfo
from .value_objects import InstanceId, ServiceName


class ServiceStatus(str, Enum):
    """Service status enumeration."""

    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"
    UNHEALTHY = "UNHEALTHY"
    SHUTDOWN = "SHUTDOWN"


class ServiceLifecycleEvent(BaseModel):
    """Domain event for service lifecycle changes."""

    model_config = ConfigDict(frozen=True)

    service_name: ServiceName
    instance_id: InstanceId
    event_type: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class ServiceAggregate(BaseModel):
    """Service aggregate root that encapsulates service lifecycle.

    This aggregate ensures consistency of service state and enforces
    business rules around service lifecycle transitions.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow value objects
        validate_assignment=True,
    )

    # Identity
    service_name: ServiceName
    instance_id: InstanceId

    # State
    version: str = Field(default="1.0.0")
    status: ServiceStatus = Field(default=ServiceStatus.ACTIVE)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Domain events
    _events: list[ServiceLifecycleEvent] = []

    def __init__(self, **data):
        """Initialize aggregate and record creation event."""
        super().__init__(**data)
        self._record_event("service.registered")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy based on heartbeat."""
        time_since_heartbeat = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        return time_since_heartbeat < 30.0 and self.status != ServiceStatus.UNHEALTHY

    @computed_field  # type: ignore[prop-decorator]
    @property
    def uptime_seconds(self) -> float:
        """Calculate service uptime in seconds."""
        return (datetime.now(UTC) - self.registered_at).total_seconds()

    def heartbeat(self) -> None:
        """Record a heartbeat from the service.

        Business Rules:
        - Only active or standby services can send heartbeats
        - Automatically transitions unhealthy services back to their previous state
        """
        if self.status == ServiceStatus.SHUTDOWN:
            raise ValueError("Cannot send heartbeat from shutdown service")

        previous_status = self.status
        self.last_heartbeat = datetime.now(UTC)

        # Transition from unhealthy back to active
        if self.status == ServiceStatus.UNHEALTHY:
            self.status = ServiceStatus.ACTIVE
            self._record_event("service.recovered", {"previous_status": previous_status})

    def activate(self) -> None:
        """Activate the service.

        Business Rules:
        - Can only activate from STANDBY or UNHEALTHY states
        - Cannot activate a SHUTDOWN service
        """
        if self.status == ServiceStatus.ACTIVE:
            return  # Already active

        if self.status == ServiceStatus.SHUTDOWN:
            raise ValueError("Cannot activate a shutdown service")

        previous_status = self.status
        self.status = ServiceStatus.ACTIVE
        self._record_event("service.activated", {"previous_status": previous_status})

    def standby(self) -> None:
        """Put service in standby mode.

        Business Rules:
        - Can transition from ACTIVE or UNHEALTHY
        - Cannot transition from SHUTDOWN
        """
        if self.status == ServiceStatus.STANDBY:
            return  # Already in standby

        if self.status == ServiceStatus.SHUTDOWN:
            raise ValueError("Cannot put shutdown service in standby")

        previous_status = self.status
        self.status = ServiceStatus.STANDBY
        self._record_event("service.standby", {"previous_status": previous_status})

    def mark_unhealthy(self, reason: str) -> None:
        """Mark service as unhealthy.

        Business Rules:
        - Can mark any non-shutdown service as unhealthy
        - Records the reason for audit
        """
        if self.status == ServiceStatus.SHUTDOWN:
            raise ValueError("Cannot mark shutdown service as unhealthy")

        if self.status == ServiceStatus.UNHEALTHY:
            return  # Already unhealthy

        previous_status = self.status
        self.status = ServiceStatus.UNHEALTHY
        self._record_event(
            "service.unhealthy", {"previous_status": previous_status, "reason": reason}
        )

    def shutdown(self) -> None:
        """Shutdown the service.

        Business Rules:
        - This is a terminal state - cannot transition out
        - Records final state for audit
        """
        if self.status == ServiceStatus.SHUTDOWN:
            return  # Already shutdown

        previous_status = self.status
        self.status = ServiceStatus.SHUTDOWN
        self._record_event("service.shutdown", {"previous_status": previous_status})

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        """Update service metadata.

        Business Rules:
        - Cannot update metadata of shutdown services
        - Merges with existing metadata
        """
        if self.status == ServiceStatus.SHUTDOWN:
            raise ValueError("Cannot update metadata of shutdown service")

        old_metadata = self.metadata.copy()
        self.metadata.update(metadata)
        self._record_event(
            "service.metadata_updated",
            {"old_metadata": old_metadata, "new_metadata": self.metadata},
        )

    def to_service_info(self) -> ServiceInfo:
        """Convert to ServiceInfo model for external use."""
        return ServiceInfo(
            service_name=str(self.service_name),
            instance_id=str(self.instance_id),
            version=self.version,
            status=self.status.value,
            metadata=self.metadata.copy(),
            registered_at=self.registered_at.isoformat(),
            last_heartbeat=self.last_heartbeat.isoformat(),
        )

    def get_uncommitted_events(self) -> list[ServiceLifecycleEvent]:
        """Get all uncommitted domain events."""
        return self._events.copy()

    def mark_events_committed(self) -> None:
        """Mark all events as committed."""
        self._events.clear()

    def _record_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        """Record a domain event."""
        event = ServiceLifecycleEvent(
            service_name=self.service_name,
            instance_id=self.instance_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            details=details or {},
        )
        self._events.append(event)

    def __str__(self) -> str:
        """String representation."""
        return f"ServiceAggregate({self.service_name}/{self.instance_id} - {self.status.value})"
