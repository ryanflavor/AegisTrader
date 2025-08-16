"""
Gateway dashboard configuration for monitoring visualization.

Defines the structure and layout of gateway monitoring dashboards
for tools like Grafana, Datadog, or custom monitoring UIs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VisualizationType(str, Enum):
    """Types of visualizations for metrics."""

    GAUGE = "gauge"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    HEATMAP = "heatmap"
    STAT = "stat"
    TABLE = "table"
    PIE_CHART = "pie_chart"
    HISTOGRAM = "histogram"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricPanel(BaseModel):
    """Configuration for a single metric panel."""

    model_config = ConfigDict(strict=True)

    title: str
    description: str
    metric_name: str
    visualization: VisualizationType
    unit: str | None = None
    thresholds: dict[str, float] | None = None
    refresh_interval_seconds: int = 30
    width: int = 6  # Grid width (1-12)
    height: int = 4  # Grid height


class AlertRule(BaseModel):
    """Alert rule configuration."""

    model_config = ConfigDict(strict=True)

    name: str
    description: str
    metric_name: str
    condition: str  # e.g., "> 100", "< 0.5", "== 0"
    threshold: float
    severity: AlertSeverity
    duration_seconds: int = 60  # How long condition must be true
    notification_channels: list[str] = Field(default_factory=list)


class DashboardSection(BaseModel):
    """Section of related panels in a dashboard."""

    model_config = ConfigDict(strict=True)

    title: str
    description: str
    panels: list[MetricPanel]
    collapsed: bool = False


class GatewayDashboardConfig(BaseModel):
    """Complete gateway dashboard configuration."""

    model_config = ConfigDict(strict=True)

    name: str = "Gateway Monitoring Dashboard"
    description: str = "Real-time monitoring of gateway connections and performance"
    refresh_interval_seconds: int = 10
    time_range_hours: int = 24
    sections: list[DashboardSection]
    alert_rules: list[AlertRule]


def create_default_dashboard_config() -> GatewayDashboardConfig:
    """
    Create default gateway dashboard configuration.

    Returns:
        Default dashboard configuration with all standard panels
    """
    # Connection Status Section
    connection_section = DashboardSection(
        title="Connection Status",
        description="Current gateway connection health and status",
        panels=[
            MetricPanel(
                title="Connection Status",
                description="Current connection state (1=Connected, 0=Disconnected)",
                metric_name="gateway_connection_status",
                visualization=VisualizationType.GAUGE,
                thresholds={"warning": 0.5, "critical": 0},
                width=3,
                height=3,
            ),
            MetricPanel(
                title="Circuit Breaker State",
                description="Circuit breaker state (0=Closed, 0.5=Half-Open, 1=Open)",
                metric_name="gateway_circuit_breaker_state",
                visualization=VisualizationType.GAUGE,
                thresholds={"warning": 0.5, "critical": 1},
                width=3,
                height=3,
            ),
            MetricPanel(
                title="Connection Success Rate",
                description="Percentage of successful connections",
                metric_name="gateway_connection_success_rate",
                visualization=VisualizationType.STAT,
                unit="%",
                thresholds={"warning": 95, "critical": 90},
                width=3,
                height=3,
            ),
            MetricPanel(
                title="Uptime",
                description="Current connection uptime",
                metric_name="gateway_uptime_seconds",
                visualization=VisualizationType.STAT,
                unit="seconds",
                width=3,
                height=3,
            ),
        ],
    )

    # Heartbeat Monitoring Section
    heartbeat_section = DashboardSection(
        title="Heartbeat Monitoring",
        description="Heartbeat health and latency metrics",
        panels=[
            MetricPanel(
                title="Heartbeat Latency",
                description="Current heartbeat round-trip latency",
                metric_name="gateway_heartbeat_latency_milliseconds",
                visualization=VisualizationType.LINE_CHART,
                unit="ms",
                thresholds={"warning": 100, "critical": 500},
                width=6,
                height=4,
            ),
            MetricPanel(
                title="Heartbeat Loss Rate",
                description="Percentage of lost heartbeats",
                metric_name="gateway_heartbeat_loss_rate",
                visualization=VisualizationType.STAT,
                unit="%",
                thresholds={"warning": 1, "critical": 5},
                width=3,
                height=4,
            ),
            MetricPanel(
                title="Heartbeat Histogram",
                description="Distribution of heartbeat latencies",
                metric_name="gateway_heartbeat_latency_milliseconds",
                visualization=VisualizationType.HISTOGRAM,
                unit="ms",
                width=3,
                height=4,
            ),
        ],
    )

    # Failover Metrics Section
    failover_section = DashboardSection(
        title="Failover Performance",
        description="High availability and failover metrics",
        panels=[
            MetricPanel(
                title="Failover Count",
                description="Total number of failovers",
                metric_name="gateway_failover_total",
                visualization=VisualizationType.STAT,
                width=3,
                height=3,
            ),
            MetricPanel(
                title="Failover Duration",
                description="Time taken for failover",
                metric_name="gateway_failover_duration_milliseconds",
                visualization=VisualizationType.LINE_CHART,
                unit="ms",
                thresholds={"warning": 1500, "critical": 2000},
                width=6,
                height=4,
            ),
            MetricPanel(
                title="Average Failover Time",
                description="Average failover duration",
                metric_name="gateway_failover_duration_milliseconds.avg",
                visualization=VisualizationType.GAUGE,
                unit="ms",
                thresholds={"warning": 1500, "critical": 2000},
                width=3,
                height=3,
            ),
        ],
    )

    # Connection Attempts Section
    connection_attempts_section = DashboardSection(
        title="Connection Attempts",
        description="Connection attempt statistics and errors",
        panels=[
            MetricPanel(
                title="Connection Attempts",
                description="Total connection attempts over time",
                metric_name="gateway_connection_attempts_total",
                visualization=VisualizationType.LINE_CHART,
                width=4,
                height=4,
            ),
            MetricPanel(
                title="Connection Successes",
                description="Successful connections over time",
                metric_name="gateway_connection_successes_total",
                visualization=VisualizationType.LINE_CHART,
                width=4,
                height=4,
            ),
            MetricPanel(
                title="Connection Failures",
                description="Failed connections over time",
                metric_name="gateway_connection_failures_total",
                visualization=VisualizationType.LINE_CHART,
                width=4,
                height=4,
            ),
        ],
    )

    # Error Analysis Section
    error_section = DashboardSection(
        title="Error Analysis",
        description="Breakdown of errors by type",
        panels=[
            MetricPanel(
                title="Error Distribution",
                description="Errors by type",
                metric_name="gateway_errors_*_total",
                visualization=VisualizationType.PIE_CHART,
                width=6,
                height=4,
            ),
            MetricPanel(
                title="Authentication Errors",
                description="Authentication failure count",
                metric_name="gateway_errors_auth_total",
                visualization=VisualizationType.STAT,
                width=3,
                height=2,
            ),
            MetricPanel(
                title="Network Errors",
                description="Network error count",
                metric_name="gateway_errors_network_total",
                visualization=VisualizationType.STAT,
                width=3,
                height=2,
            ),
            MetricPanel(
                title="Timeout Errors",
                description="Timeout error count",
                metric_name="gateway_errors_timeout_total",
                visualization=VisualizationType.STAT,
                width=3,
                height=2,
            ),
            MetricPanel(
                title="Circuit Breaker Opens",
                description="Circuit breaker activation count",
                metric_name="gateway_circuit_breaker_opens_total",
                visualization=VisualizationType.STAT,
                width=3,
                height=2,
            ),
        ],
    )

    # Message Flow Section
    message_section = DashboardSection(
        title="Message Flow",
        description="Gateway message processing metrics",
        panels=[
            MetricPanel(
                title="Messages Received",
                description="Messages received by type",
                metric_name="gateway_messages_received",
                visualization=VisualizationType.TABLE,
                width=6,
                height=4,
            ),
            MetricPanel(
                title="Message Rate",
                description="Messages per second",
                metric_name="gateway_messages_received.rate",
                visualization=VisualizationType.LINE_CHART,
                unit="msg/s",
                width=6,
                height=4,
            ),
        ],
    )

    # Define alert rules
    alert_rules = [
        AlertRule(
            name="Gateway Disconnected",
            description="Gateway connection lost",
            metric_name="gateway_connection_status",
            condition="== 0",
            threshold=0,
            severity=AlertSeverity.CRITICAL,
            duration_seconds=30,
            notification_channels=["slack", "email", "pagerduty"],
        ),
        AlertRule(
            name="Circuit Breaker Open",
            description="Circuit breaker has opened due to failures",
            metric_name="gateway_circuit_breaker_state",
            condition="== 1",
            threshold=1,
            severity=AlertSeverity.ERROR,
            duration_seconds=60,
            notification_channels=["slack", "email"],
        ),
        AlertRule(
            name="High Heartbeat Latency",
            description="Heartbeat latency exceeds threshold",
            metric_name="gateway_heartbeat_latency_milliseconds.avg",
            condition="> 500",
            threshold=500,
            severity=AlertSeverity.WARNING,
            duration_seconds=120,
            notification_channels=["slack"],
        ),
        AlertRule(
            name="Failover Time Exceeded",
            description="Failover took longer than 2 seconds",
            metric_name="gateway_failover_duration_milliseconds",
            condition="> 2000",
            threshold=2000,
            severity=AlertSeverity.ERROR,
            duration_seconds=0,  # Immediate alert
            notification_channels=["slack", "email"],
        ),
        AlertRule(
            name="Low Connection Success Rate",
            description="Connection success rate below 90%",
            metric_name="gateway_connection_success_rate",
            condition="< 90",
            threshold=90,
            severity=AlertSeverity.WARNING,
            duration_seconds=300,
            notification_channels=["slack"],
        ),
        AlertRule(
            name="High Heartbeat Loss",
            description="Heartbeat loss rate exceeds 5%",
            metric_name="gateway_heartbeat_loss_rate",
            condition="> 5",
            threshold=5,
            severity=AlertSeverity.WARNING,
            duration_seconds=180,
            notification_channels=["slack"],
        ),
        AlertRule(
            name="Excessive Authentication Failures",
            description="Too many authentication failures",
            metric_name="gateway_errors_auth_total.rate",
            condition="> 10",
            threshold=10,
            severity=AlertSeverity.ERROR,
            duration_seconds=60,
            notification_channels=["slack", "email"],
        ),
    ]

    return GatewayDashboardConfig(
        sections=[
            connection_section,
            heartbeat_section,
            failover_section,
            connection_attempts_section,
            error_section,
            message_section,
        ],
        alert_rules=alert_rules,
    )


def export_grafana_json(config: GatewayDashboardConfig) -> dict[str, Any]:
    """
    Export dashboard configuration as Grafana JSON.

    Args:
        config: Dashboard configuration

    Returns:
        Grafana-compatible dashboard JSON
    """
    panels = []
    panel_id = 1
    y_position = 0

    for section in config.sections:
        # Add section header
        panels.append(
            {
                "id": panel_id,
                "type": "row",
                "title": section.title,
                "collapsed": section.collapsed,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_position},
            }
        )
        panel_id += 1
        y_position += 1

        # Add panels in section
        x_position = 0
        max_height = 0

        for panel in section.panels:
            panel_config = {
                "id": panel_id,
                "type": _map_visualization_to_grafana(panel.visualization),
                "title": panel.title,
                "description": panel.description,
                "gridPos": {
                    "h": panel.height,
                    "w": panel.width,
                    "x": x_position,
                    "y": y_position,
                },
                "targets": [
                    {
                        "expr": panel.metric_name,
                        "refId": "A",
                    }
                ],
            }

            # Add thresholds if defined
            if panel.thresholds:
                panel_config["fieldConfig"] = {
                    "defaults": {
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": panel.thresholds.get("warning")},
                                {"color": "red", "value": panel.thresholds.get("critical")},
                            ],
                        },
                        "unit": panel.unit,
                    }
                }

            panels.append(panel_config)
            panel_id += 1
            x_position += panel.width
            max_height = max(max_height, panel.height)

            # Wrap to next row if needed
            if x_position >= 24:
                x_position = 0
                y_position += max_height
                max_height = 0

        y_position += max_height

    return {
        "dashboard": {
            "title": config.name,
            "description": config.description,
            "panels": panels,
            "refresh": f"{config.refresh_interval_seconds}s",
            "time": {
                "from": f"now-{config.time_range_hours}h",
                "to": "now",
            },
        },
    }


def _map_visualization_to_grafana(viz_type: VisualizationType) -> str:
    """Map visualization type to Grafana panel type."""
    mapping = {
        VisualizationType.GAUGE: "gauge",
        VisualizationType.LINE_CHART: "timeseries",
        VisualizationType.BAR_CHART: "barchart",
        VisualizationType.HEATMAP: "heatmap",
        VisualizationType.STAT: "stat",
        VisualizationType.TABLE: "table",
        VisualizationType.PIE_CHART: "piechart",
        VisualizationType.HISTOGRAM: "histogram",
    }
    return mapping.get(viz_type, "graph")
