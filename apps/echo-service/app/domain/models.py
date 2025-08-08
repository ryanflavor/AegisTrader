"""Domain models for Echo Service using Pydantic v2.

This module contains all domain entities and value objects with strict Pydantic v2
validation, following DDD principles and hexagonal architecture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Python 3.10 compatibility - UTC was added in Python 3.11
UTC = UTC


class EchoMode(str, Enum):
    """Echo operation modes value object.

    Defines the different processing modes for echo operations.
    """

    SIMPLE = "simple"  # Return message as-is
    REVERSE = "reverse"  # Reverse the message
    UPPERCASE = "uppercase"  # Convert to uppercase
    DELAYED = "delayed"  # Return after a delay
    TRANSFORM = "transform"  # Apply custom transformation
    BATCH = "batch"  # Process multiple messages


class MessagePriority(str, Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EchoRequest(BaseModel):
    """Value object representing an echo request.

    Immutable request model with strict validation.
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


class EchoResponse(BaseModel):
    """Value object representing an echo response.

    Immutable response model with processing metadata.
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


class ServiceMetrics(BaseModel):
    """Domain model for service metrics."""

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


class HealthCheck(BaseModel):
    """Domain model for health check."""

    status: str = Field(..., description="Health status")
    instance_id: str = Field(..., description="Instance ID")
    version: str = Field(..., description="Service version")
    checks: dict[str, bool] = Field(default_factory=dict, description="Health check results")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ServiceDefinitionInfo(BaseModel):
    """Value object representing service definition information.

    Contains the core metadata for service registration with monitor-api.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    service_name: str = Field(
        ...,
        description="Unique service identifier",
        pattern=r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$",
        min_length=3,
        max_length=64,
    )
    owner: str = Field(
        ...,
        description="Service owner or team",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Service description",
        min_length=1,
        max_length=500,
    )
    version: str = Field(
        ...,
        description="Service semantic version",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    @field_validator("service_name")
    @classmethod
    def validate_service_name_format(cls, v: str) -> str:
        """Additional validation for service name format."""
        if "--" in v:
            raise ValueError("Service name cannot contain consecutive hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Service name cannot start or end with hyphen")
        return v

    @field_validator("version")
    @classmethod
    def validate_semantic_version(cls, v: str) -> str:
        """Validate semantic version format."""
        parts = v.split(".")
        for part in parts:
            if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
                raise ValueError("Version parts must be numeric without leading zeros")
        return v


class ServiceRegistrationData(BaseModel):
    """Aggregate root for service registration.

    Combines service definition with runtime registration data.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    definition: ServiceDefinitionInfo = Field(..., description="Service definition metadata")
    instance_id: str = Field(..., description="Unique instance identifier")
    nats_url: str = Field(..., description="NATS connection URL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

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
        """Convert to ServiceDefinition dict for monitor-api compatibility.

        Returns a dictionary that matches the monitor-api ServiceDefinition model.
        """
        return {
            "service_name": self.definition.service_name,
            "owner": self.definition.owner,
            "description": self.definition.description,
            "version": self.definition.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
