"""Domain entities for Echo Service following DDD principles.

This module contains aggregate roots and entities that represent the core business concepts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .value_objects import EchoMode, MessagePriority, ServiceDefinitionInfo


class EchoRequest(BaseModel):
    """Entity representing an echo request.

    This is an aggregate root that encapsulates the request processing logic.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    message: str = Field(..., min_length=1, max_length=1000, description="Message to echo")
    mode: EchoMode | str = Field(default=EchoMode.SIMPLE, description="Echo operation mode")
    delay: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Delay in seconds for delayed mode"
    )
    transform_type: str | None = Field(
        default=None, description="Transformation type for transform mode"
    )
    priority: MessagePriority | str = Field(
        default=MessagePriority.NORMAL, description="Message priority"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    request_id: str | None = Field(default=None, description="Unique request identifier")

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v: str | EchoMode) -> EchoMode:
        """Convert string to EchoMode enum."""
        if isinstance(v, str):
            try:
                return EchoMode(v)
            except ValueError as e:
                raise ValueError(
                    f"Invalid mode: {v}. Must be one of {[m.value for m in EchoMode]}"
                ) from e
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: str | MessagePriority) -> MessagePriority:
        """Convert string to MessagePriority enum."""
        if isinstance(v, str):
            try:
                return MessagePriority(v)
            except ValueError as e:
                raise ValueError(
                    f"Invalid priority: {v}. Must be one of {[p.value for p in MessagePriority]}"
                ) from e
        return v

    def requires_delay(self) -> bool:
        """Check if request requires delay processing."""
        return self.mode == EchoMode.DELAYED and self.delay > 0

    def is_high_priority(self) -> bool:
        """Check if request has high or critical priority."""
        return self.priority in [MessagePriority.HIGH, MessagePriority.CRITICAL]


class EchoResponse(BaseModel):
    """Entity representing an echo response.

    Contains the processed message and related metadata.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    original: str = Field(..., description="Original message")
    echoed: str = Field(..., description="Echoed/processed message")
    mode: EchoMode = Field(..., description="Mode used for echo")
    instance_id: str = Field(..., description="Instance that handled the request")
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sequence_number: int = Field(default=0, ge=0, description="Request sequence number")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    request_id: str | None = Field(default=None, description="Original request identifier")

    def was_transformed(self) -> bool:
        """Check if the message was transformed from original."""
        return self.original != self.echoed


class ServiceMetrics(BaseModel):
    """Aggregate root for service metrics.

    Maintains the overall health and performance metrics of the service.
    """

    instance_id: str = Field(..., description="Service instance ID")
    total_requests: int = Field(default=0, ge=0, description="Total requests handled")
    successful_requests: int = Field(default=0, ge=0, description="Successful requests")
    failed_requests: int = Field(default=0, ge=0, description="Failed requests")
    average_latency_ms: float = Field(default=0.0, ge=0, description="Average latency")
    uptime_seconds: float = Field(default=0.0, ge=0, description="Service uptime")
    last_request_at: datetime | None = Field(default=None, description="Last request timestamp")
    mode_distribution: dict[EchoMode, int] = Field(
        default_factory=dict, description="Request distribution by mode"
    )
    priority_distribution: dict[MessagePriority, int] = Field(
        default_factory=dict, description="Request distribution by priority"
    )

    def record_request(
        self, mode: EchoMode, priority: MessagePriority, latency_ms: float, success: bool = True
    ) -> None:
        """Record a new request in metrics."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Update average latency
        if self.total_requests > 1:
            total_latency = self.average_latency_ms * (self.total_requests - 1) + latency_ms
            self.average_latency_ms = total_latency / self.total_requests
        else:
            self.average_latency_ms = latency_ms

        # Update distributions
        self.mode_distribution[mode] = self.mode_distribution.get(mode, 0) + 1
        self.priority_distribution[priority] = self.priority_distribution.get(priority, 0) + 1
        self.last_request_at = datetime.now(UTC)

    def get_success_rate(self) -> float:
        """Calculate the success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


class ServiceRegistration(BaseModel):
    """Aggregate root for service registration.

    Manages the service's registration with the monitoring system.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    definition: ServiceDefinitionInfo = Field(..., description="Service definition metadata")
    instance_id: str = Field(..., description="Unique instance identifier")
    nats_url: str = Field(..., description="NATS connection URL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = Field(default="active", description="Registration status")

    @field_validator("nats_url")
    @classmethod
    def validate_nats_url(cls, v: str) -> str:
        """Validate NATS URL format."""
        if not v.startswith(("nats://", "tls://")):
            raise ValueError("NATS URL must start with nats:// or tls://")
        if len(v) <= 7:  # Just protocol, no host
            raise ValueError("NATS URL must include host and port")
        return v

    def to_service_definition_dict(self) -> dict[str, Any]:
        """Convert to ServiceDefinition dict for monitor-api compatibility."""
        return {
            "service_name": self.definition.service_name,
            "owner": self.definition.owner,
            "description": self.definition.description,
            "version": self.definition.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if registration has expired based on TTL."""
        age_seconds = (datetime.now(UTC) - self.updated_at).total_seconds()
        return age_seconds > ttl_seconds


class BatchEchoRequest(BaseModel):
    """Entity for batch echo operations.

    Represents a collection of echo requests to be processed together.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    requests: list[EchoRequest] = Field(..., min_length=1, max_length=100)
    batch_id: str | None = Field(default=None, description="Unique batch identifier")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL)

    def get_total_delay(self) -> float:
        """Calculate total delay for all requests in batch."""
        return sum(req.delay for req in self.requests if req.mode == EchoMode.DELAYED)

    def get_modes_used(self) -> set[EchoMode]:
        """Get unique modes used in the batch."""
        return {req.mode for req in self.requests}
