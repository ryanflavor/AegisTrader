"""Domain models for AegisTrader Monitor API.

This module contains all domain entities and value objects with strict Pydantic v2
validation.
Domain models are free from any infrastructure dependencies.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        default_factory=datetime.now, description="Status timestamp"
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
        default_factory=datetime.now, description="Error timestamp"
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
    connected_services: int = Field(
        default=0, ge=0, description="Number of connected services"
    )
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
