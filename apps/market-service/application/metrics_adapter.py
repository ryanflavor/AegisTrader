"""
Simplified Metrics Integration for Market Service.

This module extends SDK's Metrics class with domain-specific helpers,
following the Single Source of Truth principle by directly using SDK metrics
without unnecessary abstraction layers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from aegis_sdk.application.metrics import Metrics
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass


class MetricsReport(BaseModel):
    """Structured metrics report model."""

    model_config = ConfigDict(strict=True)

    timestamp: datetime
    gateway: dict[str, int | float]
    processing: dict[str, int | float]
    performance: dict[str, float]
    infrastructure: dict[str, Any]


class MarketServiceMetrics(Metrics):
    """
    Market Service metrics extending SDK's Metrics class.

    This class directly extends the SDK's Metrics implementation,
    adding only domain-specific helper methods without duplicating
    the core metrics functionality.
    """

    def __init__(self) -> None:
        """Initialize market service metrics."""
        super().__init__()
        self._metric_prefix = "market_service"

    # Domain-specific metric helpers

    def record_gateway_connected(self, gateway_id: str) -> None:
        """
        Record gateway connection event.

        Args:
            gateway_id: Gateway identifier
        """
        self.increment("gateway.connected")
        self.gauge(f"gateway.{gateway_id}.status", 1)

    def record_gateway_disconnected(self, gateway_id: str) -> None:
        """
        Record gateway disconnection event.

        Args:
            gateway_id: Gateway identifier
        """
        self.increment("gateway.disconnected")
        self.gauge(f"gateway.{gateway_id}.status", 0)

    def record_tick_processed(self, symbol: str, exchange: str) -> None:
        """
        Record tick processing.

        Args:
            symbol: Trading symbol
            exchange: Exchange name
        """
        self.increment("ticks.processed.total")
        self.increment(f"ticks.{exchange}.{symbol}")

    def record_subscription_created(self, symbol: str, exchange: str) -> None:
        """
        Record subscription creation.

        Args:
            symbol: Trading symbol
            exchange: Exchange name
        """
        self.increment("subscriptions.created")
        self.increment(f"subscriptions.{exchange}.{symbol}")

    def record_batch(self, metrics: list[tuple[str, str, float]]) -> None:
        """
        Record a batch of metrics.

        Args:
            metrics: List of (type, name, value) tuples
        """
        for metric_type, name, value in metrics:
            if metric_type == "counter":
                self.increment(name, int(value))
            elif metric_type == "gauge":
                self.gauge(name, value)
            elif metric_type == "timing":
                self.record(name, value)

    def increment_with_labels(self, name: str, labels: dict[str, str]) -> None:
        """
        Increment counter with labels.

        Args:
            name: Base metric name
            labels: Dictionary of labels
        """
        # Convert labels to metric name suffix
        label_suffix = ".".join(f"{k}_{v}" for k, v in sorted(labels.items()))
        full_name = f"{name}.{label_suffix}" if label_suffix else name
        self.increment(full_name)

    def get_metrics_report(self) -> MetricsReport:
        """
        Get aggregated metrics report.

        Returns:
            Structured metrics report
        """
        snapshot = self.get_snapshot()

        # Extract metrics from snapshot
        counters = snapshot.counters
        gauges = snapshot.gauges
        summaries = snapshot.summaries

        # Build domain-specific report
        gateway_metrics = {
            "connected": counters.get("gateway.connected", 0),
            "disconnected": counters.get("gateway.disconnected", 0),
            "active": gauges.get("active.gateways", 0),
        }

        processing_metrics = {
            "ticks_total": counters.get("ticks.processed.total", 0),
            "subscriptions_created": counters.get("subscriptions.created", 0),
        }

        performance_metrics = {}
        if "rpc.latency" in summaries:
            latency = summaries["rpc.latency"]
            performance_metrics = {
                "rpc_latency_avg": latency.average,
                "rpc_latency_p50": latency.p50,
                "rpc_latency_p90": latency.p90,
                "rpc_latency_p99": latency.p99,
            }

        return MetricsReport(
            timestamp=datetime.now(UTC),
            gateway=gateway_metrics,
            processing=processing_metrics,
            performance=performance_metrics,
            infrastructure={"uptime_seconds": snapshot.uptime_seconds},
        )

    def export_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        snapshot = self.get_snapshot()
        lines = []

        # Export counters
        for name, value in snapshot.counters.items():
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")

        # Export gauges
        for name, value in snapshot.gauges.items():
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")

        # Export summaries
        for name, summary in snapshot.summaries.items():
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} summary")
            lines.append(f"{metric_name}_count {summary.count}")
            lines.append(f"{metric_name}_sum {summary.count * summary.average}")

            # Add percentiles
            lines.append(f'{metric_name}{{quantile="0.50"}} {summary.p50}')
            lines.append(f'{metric_name}{{quantile="0.90"}} {summary.p90}')
            lines.append(f'{metric_name}{{quantile="0.99"}} {summary.p99}')

        return "\n".join(lines)

    def export_json_format(self) -> dict[str, Any]:
        """
        Export metrics in JSON format.

        Returns:
            JSON-compatible dictionary
        """
        snapshot = self.get_snapshot()
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "service": self._metric_prefix,
            "metrics": snapshot.model_dump(),
        }


# Backward compatibility alias and adapter
class SDKMetricsAdapter:
    """
    Backward compatibility adapter for code expecting the old interface.

    This adapter wraps MarketServiceMetrics to provide async methods
    for compatibility with existing code. It should be removed once
    all code is updated to use MarketServiceMetrics directly.
    """

    def __init__(self, sdk_metrics=None):
        """Initialize adapter with SDK metrics or create new MarketServiceMetrics."""
        if sdk_metrics is None or not isinstance(sdk_metrics, Metrics):
            # Create new MarketServiceMetrics instance
            self._metrics = MarketServiceMetrics()
        else:
            # Use provided metrics (for testing compatibility)
            self._metrics = sdk_metrics

    async def increment_counter(self, name: str, value: int = 1) -> None:
        """Async wrapper for increment (backward compatibility)."""
        try:
            self._metrics.increment(name, value)
        except Exception:
            pass

    async def set_gauge(self, name: str, value: float) -> None:
        """Async wrapper for gauge (backward compatibility)."""
        try:
            self._metrics.gauge(name, value)
        except Exception:
            pass

    async def record_timing(self, name: str, value: float) -> None:
        """Async wrapper for record (backward compatibility)."""
        try:
            self._metrics.record(name, value)
        except Exception:
            pass

    async def get_snapshot(self) -> dict[str, Any]:
        """Async wrapper for get_all (backward compatibility)."""
        try:
            return self._metrics.get_all()
        except Exception:
            return {"error": "Failed to retrieve metrics"}

    async def reset(self) -> None:
        """Async wrapper for reset (backward compatibility)."""
        try:
            self._metrics.reset()
        except Exception:
            pass

    async def record_gateway_connected(self, gateway_id: str) -> None:
        """Async wrapper for domain-specific method."""
        if hasattr(self._metrics, "record_gateway_connected"):
            self._metrics.record_gateway_connected(gateway_id)
        else:
            await self.increment_counter("gateway.connected")
            await self.set_gauge(f"gateway.{gateway_id}.status", 1)

    async def record_gateway_disconnected(self, gateway_id: str) -> None:
        """Async wrapper for domain-specific method."""
        if hasattr(self._metrics, "record_gateway_disconnected"):
            self._metrics.record_gateway_disconnected(gateway_id)
        else:
            await self.increment_counter("gateway.disconnected")
            await self.set_gauge(f"gateway.{gateway_id}.status", 0)

    async def record_tick_processed(self, symbol: str, exchange: str) -> None:
        """Async wrapper for domain-specific method."""
        if hasattr(self._metrics, "record_tick_processed"):
            self._metrics.record_tick_processed(symbol, exchange)
        else:
            await self.increment_counter("ticks.processed.total")
            await self.increment_counter(f"ticks.{exchange}.{symbol}")

    async def record_subscription_created(self, symbol: str, exchange: str) -> None:
        """Async wrapper for domain-specific method."""
        if hasattr(self._metrics, "record_subscription_created"):
            self._metrics.record_subscription_created(symbol, exchange)
        else:
            await self.increment_counter("subscriptions.created")
            await self.increment_counter(f"subscriptions.{exchange}.{symbol}")

    async def record_batch(self, metrics: list[tuple[str, str, float]]) -> None:
        """Async wrapper for batch recording."""
        if hasattr(self._metrics, "record_batch"):
            self._metrics.record_batch(metrics)
        else:
            for metric_type, name, value in metrics:
                if metric_type == "counter":
                    await self.increment_counter(name, int(value))
                elif metric_type == "gauge":
                    await self.set_gauge(name, value)
                elif metric_type == "timing":
                    await self.record_timing(name, value)

    async def increment_counter_with_labels(self, name: str, labels: dict[str, str]) -> None:
        """Async wrapper for labeled metrics."""
        if hasattr(self._metrics, "increment_with_labels"):
            self._metrics.increment_with_labels(name, labels)
        else:
            label_suffix = ".".join(f"{k}_{v}" for k, v in sorted(labels.items()))
            full_name = f"{name}.{label_suffix}" if label_suffix else name
            await self.increment_counter(full_name)

    async def get_metrics_report(self) -> dict[str, Any]:
        """Async wrapper for metrics report."""
        if hasattr(self._metrics, "get_metrics_report"):
            report = self._metrics.get_metrics_report()
            return report.model_dump() if hasattr(report, "model_dump") else report
        else:
            snapshot = await self.get_snapshot()
            counters = snapshot.get("counters", {})
            gauges = snapshot.get("gauges", {})
            summaries = snapshot.get("summaries", {})

            report = {
                "gateway": {
                    "connected": counters.get("gateway.connected", 0),
                    "disconnected": counters.get("gateway.disconnected", 0),
                    "active": gauges.get("active.gateways", 0),
                },
                "processing": {
                    "ticks_total": counters.get("ticks.processed.total", 0),
                    "subscriptions_created": counters.get("subscriptions.created", 0),
                },
                "performance": {},
                "infrastructure": {
                    "uptime_seconds": snapshot.get("uptime_seconds", 0),
                },
            }

            if "rpc.latency" in summaries:
                latency = summaries["rpc.latency"]
                report["performance"] = {
                    "rpc_latency_avg": latency.get("average", 0),
                    "rpc_latency_p50": latency.get("p50", 0),
                    "rpc_latency_p90": latency.get("p90", 0),
                    "rpc_latency_p99": latency.get("p99", 0),
                }

            return report

    async def export_prometheus_format(self) -> str:
        """Async wrapper for Prometheus export."""
        if hasattr(self._metrics, "export_prometheus_format"):
            return self._metrics.export_prometheus_format()
        else:
            snapshot = await self.get_snapshot()
            lines = []

            for name, value in snapshot.get("counters", {}).items():
                metric_name = name.replace(".", "_")
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {value}")

            for name, value in snapshot.get("gauges", {}).items():
                metric_name = name.replace(".", "_")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {value}")

            return "\n".join(lines)

    async def export_json_format(self) -> dict[str, Any]:
        """Async wrapper for JSON export."""
        if hasattr(self._metrics, "export_json_format"):
            return self._metrics.export_json_format()
        else:
            snapshot = await self.get_snapshot()
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "service": "market_service",
                "metrics": snapshot,
            }

    def timer(self, name: str):
        """Timer context manager (backward compatibility)."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def async_timer():
            with self._metrics.timer(name) as t:
                yield t

        return async_timer()
