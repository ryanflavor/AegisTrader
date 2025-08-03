"""Domain models for AegisTrader Monitor API.

This module contains all domain entities and value objects with strict Pydantic v2
validation.
Domain models are free from any infrastructure dependencies.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ..utils.timezone import utc8_timestamp_factory


class HealthStatus(BaseModel):
    """Domain model representing the health status of the service."""

    model_config = ConfigDict(strict=True, frozen=True)

    status: Literal["healthy", "unhealthy", "degraded"] = Field(
        ..., description="Health status of the service"
    )
    service_name: str = Field(..., description="Service name", min_length=1)
    version: str = Field(..., description="Service version", pattern=r"^\d+\.\d+\.\d+$")
    nats_url: str = Field(..., description="NATS connection URL")
    timestamp: datetime = Field(
        default_factory=utc8_timestamp_factory, description="Status timestamp"
    )

    @field_validator("nats_url")
    @classmethod
    def validate_nats_url(cls, v: str) -> str:
        """Validate NATS URL format."""
        if not v.startswith(("nats://", "tls://")):
            raise ValueError("NATS URL must start with nats:// or tls://")
        return v


class ServiceError(BaseModel):
    """Domain model representing a service error."""

    model_config = ConfigDict(strict=True, frozen=True)

    detail: str = Field(..., description="Error message", min_length=1)
    error_code: str = Field(..., description="Error code", pattern=r"^[A-Z][A-Z0-9_]+$")
    timestamp: datetime = Field(
        default_factory=utc8_timestamp_factory, description="Error timestamp"
    )
    trace_id: str | None = Field(None, description="Trace ID for debugging")


class SystemStatus(BaseModel):
    """Domain model representing the overall system status."""

    model_config = ConfigDict(strict=True, frozen=True)

    timestamp: datetime = Field(..., description="Current server timestamp")
    uptime_seconds: float = Field(..., ge=0, description="Service uptime in seconds")
    environment: Literal["development", "staging", "production"] = Field(
        ..., description="Current environment"
    )
    connected_services: int = Field(default=0, ge=0, description="Number of connected services")
    deployment_version: str = Field(
        ..., description="Deployment version", pattern=r"^v\d+\.\d+\.\d+(-\w+)?$"
    )
    start_time: datetime = Field(..., description="Service start time")

    @field_validator("uptime_seconds")
    @classmethod
    def validate_uptime(cls, v: float, info: Any) -> float:
        """Validate uptime is consistent with timestamps."""
        # In Pydantic v2, use info.data to access other field values during validation
        if hasattr(info, "data") and info.data:
            timestamp = info.data.get("timestamp")
            start_time = info.data.get("start_time")
            if timestamp and start_time:
                expected_uptime = (timestamp - start_time).total_seconds()
                # Allow small discrepancy due to processing time
                if abs(v - expected_uptime) > 1.0:
                    raise ValueError("Uptime inconsistent with timestamp difference")
        return v


class ServiceConfiguration(BaseModel):
    """Domain model for service configuration."""

    model_config = ConfigDict(strict=True, frozen=True)

    nats_url: str = Field(..., description="NATS server URL")
    api_port: int = Field(..., ge=1, le=65535, description="API port number")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        ..., description="Logging level"
    )
    environment: Literal["development", "staging", "production"] = Field(
        ..., description="Deployment environment"
    )

    @field_validator("nats_url")
    @classmethod
    def validate_nats_url(cls, v: str) -> str:
        """Validate NATS URL format."""
        if not v.startswith(("nats://", "tls://")):
            raise ValueError("NATS URL must start with nats:// or tls://")
        return v


class DetailedHealthStatus(BaseModel):
    """Domain model for detailed health status with system metrics."""

    model_config = ConfigDict(strict=True, frozen=True)

    # Basic health info
    status: Literal["healthy", "unhealthy", "degraded"] = Field(
        ..., description="Health status of the service"
    )
    service_name: str = Field(..., description="Service name", min_length=1)
    version: str = Field(..., description="Service version", pattern=r"^\d+\.\d+\.\d+$")

    # System metrics
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(..., ge=0, le=100, description="Memory usage percentage")
    disk_usage_percent: float = Field(..., ge=0, le=100, description="Disk usage percentage")

    # Dependencies status
    nats_status: Literal["healthy", "unhealthy"] = Field(..., description="NATS connection status")
    nats_latency_ms: float = Field(..., ge=0, description="NATS latency in milliseconds")

    timestamp: datetime = Field(
        default_factory=utc8_timestamp_factory, description="Status timestamp"
    )


class ServiceDefinition(BaseModel):
    """Domain model representing a service definition in the registry."""

    model_config = ConfigDict(strict=True, frozen=True)

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
        description="Service version",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (UTC+8)",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (UTC+8)",
    )

    @field_validator("service_name")
    @classmethod
    def validate_service_name_format(cls, v: str) -> str:
        """Additional validation for service name format."""
        if "--" in v:
            raise ValueError("Service name cannot contain consecutive hyphens")
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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Handle ISO format with Z or timezone
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        raise ValueError(f"Invalid timestamp format: {v}")

    @field_validator("updated_at")
    @classmethod
    def validate_updated_after_created(cls, v: datetime, info: Any) -> datetime:
        """Validate updated_at is not before created_at."""
        if hasattr(info, "data") and info.data and "created_at" in info.data:
            created_at = info.data["created_at"]
            if v < created_at:
                raise ValueError("updated_at cannot be before created_at")
        return v

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat()

    def to_iso_dict(self) -> dict[str, Any]:
        """Convert to dictionary with ISO format timestamps."""
        data = self.model_dump()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data
