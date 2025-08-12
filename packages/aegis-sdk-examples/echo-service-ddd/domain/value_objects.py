"""Value objects for Echo Service following DDD principles.

Value objects are immutable objects that are distinguished by their values rather than identity.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @classmethod
    def from_string(cls, value: str) -> EchoMode:
        """Create EchoMode from string value."""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid echo mode: {value}")

    def is_transformation_mode(self) -> bool:
        """Check if this mode transforms the message."""
        return self in [self.REVERSE, self.UPPERCASE, self.TRANSFORM]


class MessagePriority(str, Enum):
    """Message priority levels value object."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, value: str) -> MessagePriority:
        """Create MessagePriority from string value."""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid priority level: {value}")

    def is_urgent(self) -> bool:
        """Check if this priority level is urgent."""
        return self in [self.HIGH, self.CRITICAL]

    def get_weight(self) -> int:
        """Get numeric weight for priority (higher = more important)."""
        weights = {self.LOW: 1, self.NORMAL: 2, self.HIGH: 3, self.CRITICAL: 4}
        return weights[self]


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

    def get_major_version(self) -> int:
        """Extract major version number."""
        return int(self.version.split(".")[0])

    def get_minor_version(self) -> int:
        """Extract minor version number."""
        return int(self.version.split(".")[1])

    def get_patch_version(self) -> int:
        """Extract patch version number."""
        return int(self.version.split(".")[2])


class TransformationType(str, Enum):
    """Types of message transformations."""

    BASE64_ENCODE = "base64_encode"
    BASE64_DECODE = "base64_decode"
    ROT13 = "rot13"
    LEETSPEAK = "leetspeak"
    WORD_REVERSE = "word_reverse"
    CAPITALIZE_WORDS = "capitalize_words"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a transformation type is valid."""
        try:
            cls(value)
            return True
        except ValueError:
            return False


class HealthStatus(str, Enum):
    """Service health status value object."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def is_operational(self) -> bool:
        """Check if service is operational in this status."""
        return self in [self.HEALTHY, self.DEGRADED]


class InstanceIdentifier(BaseModel):
    """Value object for service instance identification."""

    model_config = ConfigDict(frozen=True, strict=True)

    instance_id: str = Field(
        ...,
        description="Unique instance identifier",
        min_length=1,
        max_length=128,
    )
    hostname: str | None = Field(
        default=None,
        description="Host where instance is running",
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Port number for the instance",
    )

    def get_full_identifier(self) -> str:
        """Get full instance identifier string."""
        if self.hostname and self.port:
            return f"{self.instance_id}@{self.hostname}:{self.port}"
        elif self.hostname:
            return f"{self.instance_id}@{self.hostname}"
        return self.instance_id


class ProcessingMetadata(BaseModel):
    """Value object for request/response processing metadata."""

    model_config = ConfigDict(frozen=True, strict=True)

    trace_id: str | None = Field(default=None, description="Distributed trace identifier")
    span_id: str | None = Field(default=None, description="Span identifier within trace")
    parent_span_id: str | None = Field(default=None, description="Parent span identifier")
    user_agent: str | None = Field(default=None, description="Client user agent")
    source_ip: str | None = Field(default=None, description="Source IP address")
    correlation_id: str | None = Field(default=None, description="Business correlation ID")

    def has_tracing_info(self) -> bool:
        """Check if tracing information is present."""
        return self.trace_id is not None and self.span_id is not None
