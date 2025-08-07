"""Domain models for Echo Service using Pydantic v2."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EchoMode(str, Enum):
    """Echo operation modes."""

    SIMPLE = "simple"
    DELAYED = "delayed"
    TRANSFORM = "transform"
    BATCH = "batch"


class MessagePriority(str, Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EchoRequest(BaseModel):
    """Domain model for echo request."""

    message: str = Field(..., min_length=1, max_length=1000, description="Message to echo")
    mode: EchoMode = Field(default=EchoMode.SIMPLE, description="Echo operation mode")
    delay_seconds: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Delay in seconds for delayed mode"
    )
    transform_type: str | None = Field(
        default=None, description="Transformation type for transform mode"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL, description="Message priority"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("delay_seconds")
    @classmethod
    def validate_delay_for_mode(cls, v: float, info) -> float:
        """Validate delay is only used in delayed mode."""
        # In Pydantic v2, we use info.data to access other fields
        mode = info.data.get("mode") if hasattr(info, "data") else EchoMode.SIMPLE
        if v > 0 and mode != EchoMode.DELAYED:
            raise ValueError("delay_seconds can only be set in DELAYED mode")
        return v


class EchoResponse(BaseModel):
    """Domain model for echo response."""

    echo: str = Field(..., description="Echoed message")
    original: str = Field(..., description="Original message")
    mode: EchoMode = Field(..., description="Mode used for echo")
    instance_id: str = Field(..., description="Instance that handled the request")
    sequence_number: int = Field(..., ge=0, description="Request sequence number")
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
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
