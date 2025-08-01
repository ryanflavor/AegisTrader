"""Domain models using Pydantic for validation."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Message(BaseModel):
    """Base message model with trace context."""

    model_config = ConfigDict(
        extra="forbid",  # This prevents extra fields
        str_strip_whitespace=True,
        strict=True,  # Enforce strict type checking
        validate_assignment=True,  # Validate on assignment
        json_schema_extra={
            "example": {
                "message_id": "123e4567-e89b-12d3-a456-426614174000",
                "trace_id": "987fcdeb-51a2-43f1-9012-345678901234",
                "timestamp": "2025-01-01T00:00:00Z",
                "source": "order-service",
                "target": "payment-service",
            }
        },
    )

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = Field(default=None)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str | None = Field(default=None)
    target: str | None = Field(default=None)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is in ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO timestamp format: {v}") from e
        return v


class RPCRequest(Message):
    """RPC request model."""

    method: str = Field(..., min_length=1, description="RPC method name")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Method parameters"
    )
    timeout: float = Field(default=5.0, gt=0, description="Request timeout in seconds")

    @field_validator("method", mode="before")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate method name format."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Method name cannot be empty")
        return v


class RPCResponse(Message):
    """RPC response model."""

    success: bool = Field(default=True, description="Whether the request succeeded")
    result: Any | None = Field(default=None, description="Response data if successful")
    error: str | None = Field(default=None, description="Error message if failed")

    @model_validator(mode="after")
    def validate_error_consistency(self) -> "RPCResponse":
        """Ensure error is consistent with success status."""
        if self.success and self.error is not None:
            raise ValueError("Error must be None when success is True")
        if not self.success and self.error is None:
            raise ValueError("Error message required when success is False")
        return self


class Event(Message):
    """Domain event model."""

    domain: str = Field(..., min_length=1, description="Event domain")
    event_type: str = Field(..., min_length=1, description="Event type")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    version: str = Field(default="1.0", description="Event schema version")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (semantic versioning)."""
        import re

        if not re.match(r"^\d+\.\d+(\.\d+)?$", v):
            raise ValueError(
                f"Invalid version format: {v}. Use semantic versioning (e.g., 1.0.0)"
            )
        return v


class Command(Message):
    """Command model for async processing."""

    command: str = Field(..., min_length=1, description="Command name")
    payload: dict[str, Any] = Field(default_factory=dict, description="Command payload")
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|critical)$",
        description="Command priority",
    )
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    timeout: float = Field(
        default=300.0, gt=0, description="Command timeout in seconds"
    )

    @field_validator("command", mode="before")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Validate command name format."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Command name cannot be empty")
        return v


class ServiceInfo(BaseModel):
    """Service instance information."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, strict=True, validate_assignment=True
    )

    service_name: str = Field(..., min_length=1, description="Service name")
    instance_id: str = Field(..., min_length=1, description="Instance identifier")
    version: str = Field(default="1.0.0", description="Service version")
    status: str = Field(
        default="ACTIVE",
        pattern="^(ACTIVE|STANDBY|UNHEALTHY|SHUTDOWN)$",
        description="Service status",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Service metadata"
    )
    registered_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Registration timestamp",
    )
    last_heartbeat: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Last heartbeat timestamp",
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (semantic versioning)."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(
                f"Invalid version format: {v}. Use semantic versioning (e.g., 1.0.0)"
            )
        return v

    @field_validator("registered_at", "last_heartbeat")
    @classmethod
    def validate_timestamps(cls, v: str) -> str:
        """Validate timestamp is in ISO format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO timestamp format: {v}") from e
        return v
