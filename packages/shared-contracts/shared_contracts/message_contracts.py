"""Message format contracts for AegisTrader services.

This module defines the technical message format contracts,
NOT business domain models. Business models should be defined
within each service's own domain.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class EventMetadata(TypedDict, total=False):
    """Standard metadata fields for events."""

    correlation_id: str
    causation_id: str
    user_id: str
    session_id: str
    request_id: str
    trace_id: str
    span_id: str


class BaseEventContract(BaseModel):
    """Base contract for all events in the system."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(
        ..., description="Event type following pattern: events.{domain}.{action}"
    )
    timestamp: datetime = Field(..., description="Event timestamp in UTC")
    source_service: str = Field(..., description="Service that emitted the event")
    source_instance: str = Field(..., description="Service instance ID that emitted the event")
    version: str = Field("1.0", description="Event schema version")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")
    payload: dict[str, Any] = Field(..., description="Event-specific payload data")


class RPCRequestContract(BaseModel):
    """Standard RPC request format."""

    method: str = Field(..., description="RPC method name")
    params: dict[str, Any] = Field(default_factory=dict, description="Method parameters")
    timeout: int | None = Field(None, description="Request timeout in milliseconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Request metadata")


class RPCResponseContract(BaseModel):
    """Standard RPC response format."""

    result: dict[str, Any] | None = Field(None, description="Success result data")
    error: dict[str, Any] | None = Field(None, description="Error information if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class ServiceHealthContract(BaseModel):
    """Standard health check response format."""

    status: str = Field(..., description="Service health status: healthy, unhealthy, degraded")
    service: str = Field(..., description="Service name")
    instance: str = Field(..., description="Service instance ID")
    version: str = Field(..., description="Service version")
    uptime: float = Field(..., description="Service uptime in seconds")
    checks: dict[str, bool] = Field(default_factory=dict, description="Individual health checks")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Current metrics snapshot")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ServiceMetricsContract(BaseModel):
    """Standard metrics response format."""

    service: str = Field(..., description="Service name")
    instance: str = Field(..., description="Service instance ID")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    counters: dict[str, int] = Field(default_factory=dict, description="Counter metrics")
    gauges: dict[str, float] = Field(default_factory=dict, description="Gauge metrics")
    histograms: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Histogram metrics"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
