"""Data Transfer Objects for Echo Service application layer.

DTOs define the data structures for communication between layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseDTO(BaseModel):
    """Base DTO class for all DTOs."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        validate_assignment=True,
    )


class EchoRequestDTO(BaseDTO):
    """DTO for echo request input."""

    message: str = Field(..., min_length=1, max_length=1000, description="Message to echo")
    mode: str = Field(default="simple", description="Echo mode")
    delay: float = Field(default=0.0, ge=0.0, le=10.0, description="Delay in seconds")
    transform_type: str | None = Field(default=None, description="Transformation type")
    priority: str = Field(default="normal", description="Message priority")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    request_id: str | None = Field(default=None, description="Request identifier")


class EchoResponseDTO(BaseDTO):
    """DTO for echo response output."""

    original: str = Field(..., description="Original message")
    echoed: str = Field(..., description="Processed message")
    mode: str = Field(..., description="Mode used")
    instance_id: str = Field(..., description="Instance that processed the request")
    processing_time_ms: float = Field(..., ge=0, description="Processing time")
    timestamp: datetime = Field(..., description="Response timestamp")
    sequence_number: int = Field(..., ge=0, description="Sequence number")
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None)
    correlation_id: str | None = Field(default=None)


class BatchEchoRequestDTO(BaseDTO):
    """DTO for batch echo request."""

    requests: list[EchoRequestDTO] = Field(
        ..., min_length=1, max_length=100, description="List of echo requests"
    )
    batch_id: str | None = Field(default=None, description="Batch identifier")
    priority: str = Field(default="normal", description="Batch priority")


class BatchEchoResponseDTO(BaseDTO):
    """DTO for batch echo response."""

    responses: list[EchoResponseDTO] = Field(..., description="List of echo responses")
    batch_id: str | None = Field(default=None)
    total_processing_time_ms: float = Field(..., ge=0)
    instance_id: str = Field(...)


class MetricsDTO(BaseDTO):
    """DTO for service metrics."""

    instance_id: str = Field(..., description="Instance identifier")
    total_requests: int = Field(..., ge=0, description="Total requests processed")
    successful_requests: int = Field(..., ge=0, description="Successful requests")
    failed_requests: int = Field(..., ge=0, description="Failed requests")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate percentage")
    average_latency_ms: float = Field(..., ge=0, description="Average latency")
    uptime_seconds: float = Field(..., ge=0, description="Service uptime")
    last_request_at: datetime | None = Field(default=None)
    mode_distribution: dict[str, int] = Field(default_factory=dict)
    priority_distribution: dict[str, int] = Field(default_factory=dict)


class HealthStatusDTO(BaseDTO):
    """DTO for health status."""

    status: str = Field(..., description="Health status (healthy/unhealthy/degraded)")
    instance_id: str = Field(..., description="Instance identifier")
    version: str = Field(..., description="Service version")
    checks: dict[str, bool] = Field(default_factory=dict, description="Health check results")
    metrics: dict[str, Any] | None = Field(default=None, description="Optional metrics")


class ServiceInfoDTO(BaseDTO):
    """DTO for service information."""

    service_name: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    instance_id: str = Field(..., description="Instance identifier")
    description: str = Field(..., description="Service description")
    owner: str = Field(..., description="Service owner")
    registration: dict[str, Any] | None = Field(default=None, description="Registration info")


class ServiceRegistrationDTO(BaseDTO):
    """DTO for service registration."""

    service_name: str = Field(..., description="Service name")
    owner: str = Field(..., description="Service owner")
    description: str = Field(..., description="Service description")
    version: str = Field(..., description="Service version")
    instance_id: str = Field(..., description="Instance identifier")
    nats_url: str = Field(..., description="NATS connection URL")


class RegistrationResponseDTO(BaseDTO):
    """DTO for registration response."""

    status: str = Field(..., description="Registration status")
    instance_id: str = Field(..., description="Instance identifier")
    service_name: str = Field(..., description="Service name")
    registered_at: datetime = Field(..., description="Registration timestamp")


class ErrorDTO(BaseDTO):
    """DTO for error responses."""

    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(default=None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now)
    instance_id: str | None = Field(default=None)


class PingResponseDTO(BaseDTO):
    """DTO for ping response."""

    status: str = Field(..., description="Ping status")
    instance_id: str = Field(..., description="Instance identifier")
    echo: str | None = Field(default=None, description="Echoed message if provided")


class ModeDistributionDTO(BaseDTO):
    """DTO for mode distribution data."""

    distribution: dict[str, int] = Field(..., description="Request count by mode")
    total_requests: int = Field(..., ge=0, description="Total requests")
    time_window: int | None = Field(default=None, description="Time window in seconds")


class PriorityDistributionDTO(BaseDTO):
    """DTO for priority distribution data."""

    distribution: dict[str, int] = Field(..., description="Request count by priority")
    total_requests: int = Field(..., ge=0, description="Total requests")
    time_window: int | None = Field(default=None, description="Time window in seconds")


class LatencyStatsDTO(BaseDTO):
    """DTO for latency statistics."""

    average_ms: float = Field(..., ge=0, description="Average latency")
    total_requests: int = Field(..., ge=0, description="Total requests")
    percentiles_requested: list[float] = Field(..., description="Requested percentiles")
    percentiles: dict[float, float] | None = Field(
        default=None, description="Calculated percentiles"
    )
    note: str | None = Field(default=None, description="Additional notes")
