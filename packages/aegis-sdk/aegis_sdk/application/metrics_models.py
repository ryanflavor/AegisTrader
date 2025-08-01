"""Pydantic models for metrics data."""

from pydantic import BaseModel, ConfigDict, Field


class MetricsSummaryData(BaseModel):
    """Summary statistics for a metric."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    count: int = Field(default=0, ge=0, description="Number of values recorded")
    average: float = Field(default=0.0, description="Average value")
    min: float = Field(default=0.0, description="Minimum value")
    max: float = Field(default=0.0, description="Maximum value")
    p50: float = Field(default=0.0, description="50th percentile (median)")
    p90: float = Field(default=0.0, description="90th percentile")
    p99: float = Field(default=0.0, description="99th percentile")


class MetricsSnapshot(BaseModel):
    """Complete metrics snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    uptime_seconds: float = Field(ge=0, description="Service uptime in seconds")
    counters: dict[str, int] = Field(
        default_factory=dict, description="Counter metrics"
    )
    gauges: dict[str, float] = Field(default_factory=dict, description="Gauge metrics")
    summaries: dict[str, MetricsSummaryData] = Field(
        default_factory=dict, description="Summary statistics"
    )
