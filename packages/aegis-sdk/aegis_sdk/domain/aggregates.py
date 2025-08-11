"""Domain aggregates following Domain-Driven Design principles.

Aggregates are clusters of domain objects that can be treated as a single unit.
They enforce consistency boundaries and encapsulate business rules.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import ServiceInfo
from .value_objects import (
    InstanceId,
    ServiceName,
)


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

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy based on heartbeat."""
        time_since_heartbeat = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        return time_since_heartbeat < 30.0 and self.status != ServiceStatus.UNHEALTHY

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


class StickyActiveElectionState(str, Enum):
    """Sticky active election state enumeration."""

    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"
    ELECTING = "ELECTING"


class StickyActiveElectionEvent(BaseModel):
    """Domain event for sticky active election changes."""

    model_config = ConfigDict(frozen=True)

    service_name: ServiceName
    instance_id: InstanceId
    group_id: str
    event_type: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class StickyActiveElection(BaseModel):
    """Aggregate root for sticky active election management.

    This aggregate encapsulates the business logic for leader election
    in a sticky single-active pattern using NATS KV Store.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )

    # Identity
    service_name: ServiceName
    instance_id: InstanceId
    group_id: str = Field(default="default", description="Service group identifier")

    # State
    status: StickyActiveElectionState = Field(default=StickyActiveElectionState.STANDBY)
    leader_instance_id: InstanceId | None = Field(default=None)
    last_leader_heartbeat: datetime | None = Field(default=None)

    # Configuration
    leader_ttl_seconds: int = Field(default=5, ge=1, le=300)
    heartbeat_interval_seconds: int = Field(default=2, ge=1, le=60)
    election_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_election_attempt: datetime | None = Field(default=None)
    became_leader_at: datetime | None = Field(default=None)

    # Domain events
    _events: list[StickyActiveElectionEvent] = []

    def __init__(self, **data):
        """Initialize aggregate and validate configuration."""
        super().__init__(**data)
        self._validate_timing_configuration()
        self._record_event("election.initialized")

    def _validate_timing_configuration(self) -> None:
        """Validate timing configuration consistency."""
        if self.heartbeat_interval_seconds >= self.leader_ttl_seconds:
            raise ValueError("Heartbeat interval must be less than leader TTL")
        if self.election_timeout_seconds <= self.leader_ttl_seconds:
            raise ValueError("Election timeout should be greater than leader TTL")

    @property
    def is_leader(self) -> bool:
        """Check if this instance is the current leader."""
        return (
            self.status == StickyActiveElectionState.ACTIVE
            and self.leader_instance_id == self.instance_id
        )

    @property
    def is_electing(self) -> bool:
        """Check if currently in election process."""
        return self.status == StickyActiveElectionState.ELECTING

    @property
    def leader_key(self) -> str:
        """Get the NATS KV Store key for leader election."""
        return f"sticky-active.{self.service_name.value}.{self.group_id}.leader"

    def start_election(self) -> None:
        """Start the election process.

        Business Rules:
        - Can only start election from STANDBY state
        - Cannot start if already ACTIVE
        - Records election attempt timestamp
        """
        if self.status == StickyActiveElectionState.ACTIVE:
            raise ValueError("Cannot start election when already active")

        if self.status == StickyActiveElectionState.ELECTING:  # noqa: SIM102
            # Check if election timeout has passed
            # Note: Can't easily combine with outer if due to complex condition
            if (
                self.last_election_attempt
                and (datetime.now(UTC) - self.last_election_attempt).total_seconds()
                < self.election_timeout_seconds
            ):
                raise ValueError("Election already in progress")

        previous_status = self.status
        self.status = StickyActiveElectionState.ELECTING
        self.last_election_attempt = datetime.now(UTC)
        self._record_event(
            "election.started",
            {"previous_status": previous_status, "attempt_time": self.last_election_attempt},
        )

    def win_election(self) -> None:
        """Mark this instance as having won the election.

        Business Rules:
        - Must be in ELECTING state
        - Sets leader instance ID to self
        - Transitions to ACTIVE state
        """
        if self.status != StickyActiveElectionState.ELECTING:
            raise ValueError("Can only win election from ELECTING state")

        self.status = StickyActiveElectionState.ACTIVE
        self.leader_instance_id = self.instance_id
        self.became_leader_at = datetime.now(UTC)
        self.last_leader_heartbeat = self.became_leader_at
        self._record_event(
            "election.won",
            {
                "instance_id": str(self.instance_id),
                "became_leader_at": self.became_leader_at,
            },
        )

    def lose_election(self, winner_instance_id: InstanceId) -> None:
        """Mark this instance as having lost the election.

        Business Rules:
        - Must be in ELECTING state
        - Records the winner's instance ID
        - Transitions to STANDBY state
        """
        if self.status != StickyActiveElectionState.ELECTING:
            raise ValueError("Can only lose election from ELECTING state")

        self.status = StickyActiveElectionState.STANDBY
        self.leader_instance_id = winner_instance_id
        self.last_leader_heartbeat = datetime.now(UTC)
        self._record_event(
            "election.lost",
            {
                "winner_instance_id": str(winner_instance_id),
                "own_instance_id": str(self.instance_id),
            },
        )

    def update_leader_heartbeat(self) -> None:
        """Update the leader's heartbeat timestamp.

        Business Rules:
        - Only the active leader can update heartbeat
        - Updates last heartbeat timestamp
        """
        if not self.is_leader:
            raise ValueError("Only the leader can update heartbeat")

        self.last_leader_heartbeat = datetime.now(UTC)
        self._record_event("leader.heartbeat_updated")

    def observe_leader_heartbeat(self, leader_instance_id: InstanceId) -> None:
        """Observe a heartbeat from the current leader.

        Business Rules:
        - Used by standby instances to track leader health
        - Updates leader instance ID and heartbeat timestamp
        """
        if self.status == StickyActiveElectionState.ACTIVE and self.is_leader:
            raise ValueError("Active leader cannot observe other leader's heartbeat")

        self.leader_instance_id = leader_instance_id
        self.last_leader_heartbeat = datetime.now(UTC)

    def detect_leader_failure(self) -> bool:
        """Check if the leader has failed based on heartbeat.

        Returns:
            True if leader is considered failed, False otherwise
        """
        if self.is_leader:
            return False  # Leader doesn't detect its own failure

        if not self.last_leader_heartbeat:
            return True  # No leader heartbeat ever received

        elapsed = (datetime.now(UTC) - self.last_leader_heartbeat).total_seconds()
        return elapsed > self.leader_ttl_seconds

    def step_down(self, reason: str) -> None:
        """Step down from leadership.

        Business Rules:
        - Can only step down if currently ACTIVE
        - Transitions to STANDBY state
        - Clears leader instance ID
        """
        if self.status != StickyActiveElectionState.ACTIVE:
            raise ValueError("Can only step down from ACTIVE state")

        previous_leader = self.leader_instance_id
        self.status = StickyActiveElectionState.STANDBY
        self.leader_instance_id = None
        self.became_leader_at = None
        self._record_event(
            "leader.stepped_down",
            {
                "previous_leader": str(previous_leader) if previous_leader else None,
                "reason": reason,
            },
        )

    def handle_leader_expired(self) -> None:
        """Handle detection of expired leader.

        Business Rules:
        - Transitions standby instances to prepare for new election
        - Records the event for audit
        """
        if self.is_leader:
            raise ValueError("Leader cannot handle its own expiration")

        old_leader = self.leader_instance_id
        self.leader_instance_id = None
        self.last_leader_heartbeat = None

        self._record_event(
            "leader.expired",
            {
                "expired_leader": str(old_leader) if old_leader else None,
                "detected_at": datetime.now(UTC),
            },
        )

    def get_uncommitted_events(self) -> list[StickyActiveElectionEvent]:
        """Get all uncommitted domain events."""
        return self._events.copy()

    def mark_events_committed(self) -> None:
        """Mark all events as committed."""
        self._events.clear()

    def _record_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        """Record a domain event."""
        event = StickyActiveElectionEvent(
            service_name=self.service_name,
            instance_id=self.instance_id,
            group_id=self.group_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            details=details or {},
        )
        self._events.append(event)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"StickyActiveElection({self.service_name}/{self.instance_id} "
            f"in group '{self.group_id}' - {self.status.value})"
        )
