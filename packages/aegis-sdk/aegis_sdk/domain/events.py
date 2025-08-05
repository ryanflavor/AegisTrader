"""Domain events for service lifecycle and state changes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Base class for domain events.

    Domain events represent something that has happened in the domain.
    They are immutable facts that can be used for auditing, integration,
    and event sourcing.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_assignment=True,
    )

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event identifier",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event occurred",
    )
    aggregate_id: str = Field(
        ...,
        description="ID of the aggregate that emitted this event",
    )
    aggregate_type: str = Field(
        ...,
        description="Type of the aggregate",
    )
    event_type: str = Field(
        ...,
        description="Type of the event",
    )
    event_version: str = Field(
        default="1.0",
        description="Version of the event schema",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event metadata",
    )


class ServiceRegisteredEvent(DomainEvent):
    """Event emitted when a service instance is registered."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    version: str = Field(..., description="Service version")
    initial_status: str = Field(..., description="Initial service status")
    ttl_seconds: int = Field(..., description="Registration TTL in seconds")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ServiceRegistered"
        data["aggregate_type"] = "ServiceInstance"
        super().__init__(**data)


class ServiceDeregisteredEvent(DomainEvent):
    """Event emitted when a service instance is deregistered."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    reason: str = Field(..., description="Reason for deregistration")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ServiceDeregistered"
        data["aggregate_type"] = "ServiceInstance"
        super().__init__(**data)


class ServiceStatusChangedEvent(DomainEvent):
    """Event emitted when a service instance status changes."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    old_status: str = Field(..., description="Previous status")
    new_status: str = Field(..., description="New status")
    reason: str | None = Field(None, description="Reason for status change")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ServiceStatusChanged"
        data["aggregate_type"] = "ServiceInstance"
        super().__init__(**data)


class ServiceHeartbeatMissedEvent(DomainEvent):
    """Event emitted when a service misses heartbeats."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    last_heartbeat: datetime = Field(..., description="Last known heartbeat")
    missed_count: int = Field(..., description="Number of missed heartbeats")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ServiceHeartbeatMissed"
        data["aggregate_type"] = "ServiceInstance"
        super().__init__(**data)


class LeaderElectedEvent(DomainEvent):
    """Event emitted when a new leader is elected."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier of the new leader")
    group_id: str = Field(..., description="Service group identifier")
    previous_leader_id: str | None = Field(None, description="Previous leader instance ID")
    elected_at: datetime = Field(..., description="Timestamp of election")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "LeaderElected"
        data["aggregate_type"] = "StickyActiveElection"
        super().__init__(**data)


class LeaderLostEvent(DomainEvent):
    """Event emitted when leadership is lost."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier that lost leadership")
    group_id: str = Field(..., description="Service group identifier")
    reason: str = Field(..., description="Reason for leadership loss")
    lost_at: datetime = Field(..., description="Timestamp of leadership loss")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "LeaderLost"
        data["aggregate_type"] = "StickyActiveElection"
        super().__init__(**data)


class ElectionStartedEvent(DomainEvent):
    """Event emitted when an election starts."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier starting the election")
    group_id: str = Field(..., description="Service group identifier")
    reason: str = Field(..., description="Reason for starting election")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ElectionStarted"
        data["aggregate_type"] = "StickyActiveElection"
        super().__init__(**data)


class ElectionFailedEvent(DomainEvent):
    """Event emitted when an election fails."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier that failed election")
    group_id: str = Field(..., description="Service group identifier")
    reason: str = Field(..., description="Reason for election failure")
    retry_after_seconds: int | None = Field(None, description="Seconds before retry")

    def __init__(self, **data: Any) -> None:
        """Initialize with proper event type."""
        data["event_type"] = "ElectionFailed"
        data["aggregate_type"] = "StickyActiveElection"
        super().__init__(**data)
