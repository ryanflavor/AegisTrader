"""
Gateway metrics for monitoring connection health and performance.

Provides comprehensive metrics collection with SDK integration for
monitoring gateway connections, heartbeats, failovers, and circuit breaker states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from application.metrics_adapter import SDKMetricsAdapter


@dataclass
class GatewayMetrics:
    """
    Comprehensive metrics for gateway monitoring
    """

    # Connection metrics
    connection_attempts: int = 0
    connection_successes: int = 0
    connection_failures: int = 0
    current_connection_state: str = "DISCONNECTED"

    # Heartbeat metrics
    heartbeat_sent_count: int = 0
    heartbeat_received_count: int = 0
    heartbeat_latencies_ms: list[int] = field(default_factory=list)
    last_heartbeat_latency_ms: int | None = None
    avg_heartbeat_latency_ms: float | None = None
    max_heartbeat_latency_ms: int | None = None

    # Failover metrics
    failover_count: int = 0
    failover_durations_ms: list[int] = field(default_factory=list)
    last_failover_duration_ms: int | None = None
    avg_failover_duration_ms: float | None = None

    # Connection stability metrics
    uptime_seconds: float = 0
    last_connection_time: datetime | None = None
    last_disconnection_time: datetime | None = None
    connection_uptime_percentage: float = 0.0

    # Circuit breaker metrics
    circuit_breaker_opens: int = 0
    circuit_breaker_half_opens: int = 0
    circuit_breaker_closes: int = 0
    current_circuit_state: str = "CLOSED"

    # Error metrics by type
    auth_errors: int = 0
    network_errors: int = 0
    timeout_errors: int = 0
    unknown_errors: int = 0

    def record_connection_attempt(self) -> None:
        """Record a connection attempt"""
        self.connection_attempts += 1

    def record_connection_success(self) -> None:
        """Record a successful connection"""
        self.connection_successes += 1
        self.current_connection_state = "CONNECTED"
        self.last_connection_time = datetime.now()

    def record_connection_failure(self, error_type: str = "unknown") -> None:
        """
        Record a connection failure

        Args:
            error_type: Type of error (auth, network, timeout, unknown)
        """
        self.connection_failures += 1
        self.current_connection_state = "DISCONNECTED"

        # Track error by type
        if error_type == "auth":
            self.auth_errors += 1
        elif error_type == "network":
            self.network_errors += 1
        elif error_type == "timeout":
            self.timeout_errors += 1
        else:
            self.unknown_errors += 1

    def record_heartbeat_sent(self) -> None:
        """Record a heartbeat sent"""
        self.heartbeat_sent_count += 1

    def record_heartbeat_received(self, latency_ms: int) -> None:
        """
        Record a heartbeat received with latency

        Args:
            latency_ms: Heartbeat round-trip latency in milliseconds
        """
        self.heartbeat_received_count += 1
        self.heartbeat_latencies_ms.append(latency_ms)
        self.last_heartbeat_latency_ms = latency_ms

        # Update statistics
        if self.heartbeat_latencies_ms:
            self.avg_heartbeat_latency_ms = sum(self.heartbeat_latencies_ms) / len(
                self.heartbeat_latencies_ms
            )
            self.max_heartbeat_latency_ms = max(self.heartbeat_latencies_ms)

        # Keep only last 100 samples to avoid memory growth
        if len(self.heartbeat_latencies_ms) > 100:
            self.heartbeat_latencies_ms = self.heartbeat_latencies_ms[-100:]

    def record_failover(self, duration_ms: int) -> None:
        """
        Record a failover event

        Args:
            duration_ms: Time taken for failover in milliseconds
        """
        self.failover_count += 1
        self.failover_durations_ms.append(duration_ms)
        self.last_failover_duration_ms = duration_ms

        # Update average
        if self.failover_durations_ms:
            self.avg_failover_duration_ms = sum(self.failover_durations_ms) / len(
                self.failover_durations_ms
            )

        # Keep only last 10 failovers
        if len(self.failover_durations_ms) > 10:
            self.failover_durations_ms = self.failover_durations_ms[-10:]

    def record_disconnection(self) -> None:
        """Record a disconnection event"""
        self.current_connection_state = "DISCONNECTED"
        self.last_disconnection_time = datetime.now()

    def update_uptime(self) -> None:
        """Update uptime metrics"""
        if self.last_connection_time and self.current_connection_state == "CONNECTED":
            self.uptime_seconds = (datetime.now() - self.last_connection_time).total_seconds()

    def record_circuit_breaker_state_change(self, new_state: str) -> None:
        """
        Record circuit breaker state change

        Args:
            new_state: New circuit breaker state (OPEN, HALF_OPEN, CLOSED)
        """
        self.current_circuit_state = new_state

        if new_state == "OPEN":
            self.circuit_breaker_opens += 1
        elif new_state == "HALF_OPEN":
            self.circuit_breaker_half_opens += 1
        elif new_state == "CLOSED":
            self.circuit_breaker_closes += 1

    def get_connection_success_rate(self) -> float:
        """
        Calculate connection success rate

        Returns:
            Success rate as percentage (0-100)
        """
        if self.connection_attempts == 0:
            return 0.0
        return (self.connection_successes / self.connection_attempts) * 100

    def get_heartbeat_loss_rate(self) -> float:
        """
        Calculate heartbeat loss rate

        Returns:
            Loss rate as percentage (0-100)
        """
        if self.heartbeat_sent_count == 0:
            return 0.0
        loss_count = self.heartbeat_sent_count - self.heartbeat_received_count
        return (loss_count / self.heartbeat_sent_count) * 100

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metrics to dictionary for reporting

        Returns:
            Dictionary of all metrics
        """
        return {
            # Connection metrics
            "connection_attempts": self.connection_attempts,
            "connection_successes": self.connection_successes,
            "connection_failures": self.connection_failures,
            "connection_success_rate": self.get_connection_success_rate(),
            "current_connection_state": self.current_connection_state,
            # Heartbeat metrics
            "heartbeat_sent_count": self.heartbeat_sent_count,
            "heartbeat_received_count": self.heartbeat_received_count,
            "heartbeat_loss_rate": self.get_heartbeat_loss_rate(),
            "last_heartbeat_latency_ms": self.last_heartbeat_latency_ms,
            "avg_heartbeat_latency_ms": self.avg_heartbeat_latency_ms,
            "max_heartbeat_latency_ms": self.max_heartbeat_latency_ms,
            # Failover metrics
            "failover_count": self.failover_count,
            "last_failover_duration_ms": self.last_failover_duration_ms,
            "avg_failover_duration_ms": self.avg_failover_duration_ms,
            # Stability metrics
            "uptime_seconds": self.uptime_seconds,
            "last_connection_time": (
                self.last_connection_time.isoformat() if self.last_connection_time else None
            ),
            "last_disconnection_time": (
                self.last_disconnection_time.isoformat() if self.last_disconnection_time else None
            ),
            # Circuit breaker metrics
            "circuit_breaker_opens": self.circuit_breaker_opens,
            "circuit_breaker_half_opens": self.circuit_breaker_half_opens,
            "circuit_breaker_closes": self.circuit_breaker_closes,
            "current_circuit_state": self.current_circuit_state,
            # Error breakdown
            "auth_errors": self.auth_errors,
            "network_errors": self.network_errors,
            "timeout_errors": self.timeout_errors,
            "unknown_errors": self.unknown_errors,
        }


class MetricsCollector:
    """
    Collects and aggregates gateway metrics with SDK integration.

    This class bridges the domain-specific GatewayMetrics with the SDK's
    metrics infrastructure, providing proper Gauge, Histogram, and Counter
    metrics for monitoring.
    """

    def __init__(self, sdk_metrics: SDKMetricsAdapter | None = None):
        """
        Initialize metrics collector.

        Args:
            sdk_metrics: Optional SDK metrics adapter for metric export
        """
        self.metrics = GatewayMetrics()
        self.start_time = datetime.now()
        self.sdk_metrics = sdk_metrics

    def get_metrics(self) -> GatewayMetrics:
        """
        Get current metrics

        Returns:
            Current gateway metrics
        """
        # Update uptime before returning
        self.metrics.update_uptime()

        # Export to SDK metrics if available
        if self.sdk_metrics:
            self._export_to_sdk_metrics()

        return self.metrics

    async def record_connection_attempt(self) -> None:
        """Record a connection attempt with SDK metrics."""
        self.metrics.record_connection_attempt()
        if self.sdk_metrics:
            await self.sdk_metrics.increment_counter("gateway.connection.attempts")

    async def record_connection_success(self) -> None:
        """Record a successful connection with SDK metrics."""
        self.metrics.record_connection_success()
        if self.sdk_metrics:
            await self.sdk_metrics.increment_counter("gateway.connection.successes")
            await self.sdk_metrics.set_gauge("gateway.connection.status", 1.0)

    async def record_connection_failure(self, error_type: str = "unknown") -> None:
        """
        Record a connection failure with SDK metrics.

        Args:
            error_type: Type of error (auth, network, timeout, circuit_breaker, unknown)
        """
        self.metrics.record_connection_failure(error_type)
        if self.sdk_metrics:
            await self.sdk_metrics.increment_counter("gateway.connection.failures")
            await self.sdk_metrics.increment_counter_with_labels(
                "gateway.errors", {"type": error_type}
            )
            await self.sdk_metrics.set_gauge("gateway.connection.status", 0.0)

    async def record_heartbeat_latency(self, latency_ms: int) -> None:
        """
        Record heartbeat latency with SDK histogram.

        Args:
            latency_ms: Heartbeat round-trip latency in milliseconds
        """
        self.metrics.record_heartbeat_received(latency_ms)
        if self.sdk_metrics:
            await self.sdk_metrics.record_timing("gateway.heartbeat.latency_ms", float(latency_ms))

    async def record_failover_duration(self, duration_ms: int) -> None:
        """
        Record failover duration with SDK histogram.

        Args:
            duration_ms: Time taken for failover in milliseconds
        """
        self.metrics.record_failover(duration_ms)
        if self.sdk_metrics:
            await self.sdk_metrics.record_timing("gateway.failover.duration_ms", float(duration_ms))
            await self.sdk_metrics.increment_counter("gateway.failover.count")

    async def record_circuit_breaker_state(self, state: str) -> None:
        """
        Record circuit breaker state change.

        Args:
            state: Circuit breaker state (OPEN, HALF_OPEN, CLOSED)
        """
        self.metrics.record_circuit_breaker_state_change(state)
        if self.sdk_metrics:
            # Map states to numeric values for gauge
            state_values = {"CLOSED": 0.0, "HALF_OPEN": 0.5, "OPEN": 1.0}
            await self.sdk_metrics.set_gauge(
                "gateway.circuit_breaker.state", state_values.get(state, -1.0)
            )
            await self.sdk_metrics.increment_counter(
                f"gateway.circuit_breaker.{state.lower()}_count"
            )

    async def record_message_received(self, message_type: str) -> None:
        """
        Record message received from gateway.

        Args:
            message_type: Type of message received
        """
        if self.sdk_metrics:
            await self.sdk_metrics.increment_counter_with_labels(
                "gateway.messages.received", {"type": message_type}
            )

    def _export_to_sdk_metrics(self) -> None:
        """
        Export current metrics to SDK metrics system.

        This method is called internally to push gauge values
        to the SDK metrics infrastructure.
        """
        if not self.sdk_metrics:
            return

        # Export gauge metrics asynchronously would require async context
        # For now, these are exported when individual events occur

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state"""
        self.metrics = GatewayMetrics()
        self.start_time = datetime.now()

    def get_runtime_seconds(self) -> float:
        """
        Get total runtime in seconds

        Returns:
            Seconds since metrics collector was started
        """
        return (datetime.now() - self.start_time).total_seconds()

    async def export_metrics_snapshot(self) -> dict[str, Any]:
        """
        Export comprehensive metrics snapshot.

        Returns:
            Dictionary containing all current metrics with proper types
        """
        metrics = self.get_metrics()

        # Structure metrics according to Prometheus conventions
        snapshot = {
            # Gauges
            "gauges": {
                "gateway_connection_status": (
                    1.0 if metrics.current_connection_state == "CONNECTED" else 0.0
                ),
                "gateway_circuit_breaker_state": self._map_circuit_state_to_value(
                    metrics.current_circuit_state
                ),
                "gateway_uptime_seconds": metrics.uptime_seconds,
                "gateway_connection_success_rate": metrics.get_connection_success_rate(),
                "gateway_heartbeat_loss_rate": metrics.get_heartbeat_loss_rate(),
            },
            # Counters
            "counters": {
                "gateway_connection_attempts_total": metrics.connection_attempts,
                "gateway_connection_successes_total": metrics.connection_successes,
                "gateway_connection_failures_total": metrics.connection_failures,
                "gateway_heartbeat_sent_total": metrics.heartbeat_sent_count,
                "gateway_heartbeat_received_total": metrics.heartbeat_received_count,
                "gateway_failover_total": metrics.failover_count,
                "gateway_circuit_breaker_opens_total": metrics.circuit_breaker_opens,
                "gateway_circuit_breaker_closes_total": metrics.circuit_breaker_closes,
                "gateway_errors_auth_total": metrics.auth_errors,
                "gateway_errors_network_total": metrics.network_errors,
                "gateway_errors_timeout_total": metrics.timeout_errors,
            },
            # Histograms (represented as summary statistics)
            "histograms": {
                "gateway_heartbeat_latency_milliseconds": {
                    "count": len(metrics.heartbeat_latencies_ms),
                    "sum": (
                        sum(metrics.heartbeat_latencies_ms) if metrics.heartbeat_latencies_ms else 0
                    ),
                    "avg": metrics.avg_heartbeat_latency_ms or 0,
                    "max": metrics.max_heartbeat_latency_ms or 0,
                    "last": metrics.last_heartbeat_latency_ms or 0,
                },
                "gateway_failover_duration_milliseconds": {
                    "count": len(metrics.failover_durations_ms),
                    "sum": (
                        sum(metrics.failover_durations_ms) if metrics.failover_durations_ms else 0
                    ),
                    "avg": metrics.avg_failover_duration_ms or 0,
                    "last": metrics.last_failover_duration_ms or 0,
                },
            },
            # Metadata
            "metadata": {
                "collector_runtime_seconds": self.get_runtime_seconds(),
                "last_connection_time": (
                    metrics.last_connection_time.isoformat()
                    if metrics.last_connection_time
                    else None
                ),
                "last_disconnection_time": (
                    metrics.last_disconnection_time.isoformat()
                    if metrics.last_disconnection_time
                    else None
                ),
            },
        }

        return snapshot

    def _map_circuit_state_to_value(self, state: str) -> float:
        """
        Map circuit breaker state to numeric value.

        Args:
            state: Circuit breaker state string

        Returns:
            Numeric representation (0.0=CLOSED, 0.5=HALF_OPEN, 1.0=OPEN)
        """
        state_map = {
            "CLOSED": 0.0,
            "HALF_OPEN": 0.5,
            "OPEN": 1.0,
        }
        return state_map.get(state, -1.0)
