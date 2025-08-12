"""Queries for Echo Service application layer.

Queries represent requests for information that don't change system state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Query(BaseModel):
    """Base query class for all queries."""

    correlation_id: str | None = Field(default=None, description="Correlation ID for tracking")


class GetMetricsQuery(Query):
    """Query to retrieve service metrics."""

    detailed: bool = Field(default=False, description="Include detailed metrics")


class GetHealthQuery(Query):
    """Query to get service health status."""

    include_dependencies: bool = Field(default=True, description="Include dependency health checks")
    include_metrics: bool = Field(default=True, description="Include metrics in health status")


class GetServiceInfoQuery(Query):
    """Query to get service information."""

    include_registration: bool = Field(default=True, description="Include registration status")
    include_version: bool = Field(default=True, description="Include version information")


class GetModeDistributionQuery(Query):
    """Query to get request distribution by mode."""

    time_window_seconds: int | None = Field(
        default=None, description="Time window for distribution (if supported)"
    )


class GetPriorityDistributionQuery(Query):
    """Query to get request distribution by priority."""

    time_window_seconds: int | None = Field(
        default=None, description="Time window for distribution (if supported)"
    )


class GetLatencyStatsQuery(Query):
    """Query to get latency statistics."""

    percentiles: list[float] = Field(default=[50, 95, 99], description="Percentiles to calculate")


class PingQuery(Query):
    """Simple ping query for connectivity testing."""

    echo_message: str | None = Field(default=None, description="Optional message to echo back")
