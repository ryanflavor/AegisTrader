"""
Connection Manager for gateway connections
Handles connection lifecycle, reconnection, and heartbeat management
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from domain.gateway.events import (
    ConnectionAttempted,
    GatewayConnected,
    GatewayDisconnected,
    HeartbeatReceived,
    ReconnectionScheduled,
)
from domain.gateway.metrics import MetricsCollector
from domain.gateway.ports import GatewayPort
from domain.gateway.value_objects import ConnectionConfig, ConnectionState


class ConnectionHealthStatus(BaseModel):
    """Health status for connection"""

    is_healthy: bool
    state: ConnectionState
    uptime_seconds: float | None = None
    last_heartbeat: datetime | None = None
    connection_attempts: int = 0


class ConnectionStateData(BaseModel):
    """Persistent connection state data"""

    gateway_id: str
    connection_state: str
    last_successful_config: dict[str, Any] | None = None
    connection_attempts: int = 0
    last_heartbeat: datetime | None = None
    last_connection_time: datetime | None = None
    last_disconnection_time: datetime | None = None
    failure_count: int = 0


class ConnectionStatePersistence:
    """Handle persistence of connection state to NATS KV"""

    def __init__(self, kv_store: Any, gateway_id: str):
        """
        Initialize state persistence

        Args:
            kv_store: NATS KV store instance
            gateway_id: Gateway identifier for state key
        """
        self.kv_store = kv_store
        self.gateway_id = gateway_id
        self.state_key = f"gateway:state:{gateway_id}"

    async def save_state(self, state_data: ConnectionStateData) -> None:
        """
        Save connection state to KV store

        Args:
            state_data: State data to persist
        """
        try:
            # Convert to JSON-serializable dict
            state_dict = state_data.model_dump(mode="json")

            # Save to KV store
            await self.kv_store.put(
                key=self.state_key,
                value=json.dumps(state_dict).encode(),
                ttl=86400,  # 24 hour TTL
            )
        except Exception as e:
            # Log but don't fail on persistence errors
            print(f"Failed to persist connection state: {e}")

    async def load_state(self) -> ConnectionStateData | None:
        """
        Load connection state from KV store

        Returns:
            Restored state data or None if not found
        """
        try:
            # Get from KV store
            entry = await self.kv_store.get(self.state_key)
            if not entry or not entry.value:
                return None

            # Parse JSON
            state_dict = json.loads(entry.value.decode())

            # Convert to model
            return ConnectionStateData(**state_dict)

        except Exception as e:
            # Log but don't fail on load errors
            print(f"Failed to load connection state: {e}")
            return None

    async def delete_state(self) -> None:
        """
        Delete connection state from KV store
        """
        try:
            await self.kv_store.delete(self.state_key)
        except Exception:
            pass  # Ignore delete errors


class ConnectionManager:
    """
    Manages gateway connection lifecycle with automatic reconnection and state persistence
    """

    def __init__(
        self,
        adapter: GatewayPort,
        config: ConnectionConfig,
        kv_store: Any | None = None,
        gateway_id: str | None = None,
    ):
        """
        Initialize connection manager

        Args:
            adapter: Gateway port implementation
            config: Connection configuration
            kv_store: Optional NATS KV store for state persistence
            gateway_id: Optional gateway ID for state persistence
        """
        self.adapter = adapter
        self.config = config
        self.state = ConnectionState.DISCONNECTED

        # State persistence
        self.state_persistence = None
        if kv_store and gateway_id:
            self.state_persistence = ConnectionStatePersistence(kv_store, gateway_id)

        # Connection tracking
        self.connection_attempts = 0
        self.connected_at: datetime | None = None
        self.last_heartbeat_received: datetime | None = None
        self.last_heartbeat_sent: datetime | None = None

        # Use SDK's RetryPolicy instead of custom ExponentialBackoff
        from aegis_sdk.domain.value_objects import Duration, RetryPolicy

        self.retry_policy = RetryPolicy(
            max_retries=config.max_reconnect_attempts,
            initial_delay=Duration(seconds=config.reconnect_delay),
            backoff_multiplier=2.0,
            max_delay=Duration(seconds=60.0),
            jitter_factor=0.25,  # 25% jitter
        )
        self.current_retry_attempt = 0

        # Circuit breaker for connection resilience
        from domain.gateway.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout=30.0,
                failure_rate_threshold=0.5,
                sample_size=10,
            )
        )

        # Tasks
        self.heartbeat_task: asyncio.Task | None = None
        self.reconnect_task: asyncio.Task | None = None
        self._connection_lock = asyncio.Lock()

        # Event publishing (will be set by service)
        self.publish_event = None

        # Track last successful config for recovery
        self.last_successful_config: dict[str, Any] | None = None

        # Metrics collection
        self.metrics_collector = MetricsCollector()

    async def connect(self) -> None:
        """
        Connect to the gateway
        """
        async with self._connection_lock:
            if self.state == ConnectionState.CONNECTED:
                return

            if self.state == ConnectionState.CONNECTING:
                return  # Already connecting

            self.state = ConnectionState.CONNECTING
            self.connection_attempts += 1

            # Record metric
            self.metrics_collector.metrics.record_connection_attempt()

            # Publish connection attempt event
            if self.publish_event:
                await self.publish_event(
                    ConnectionAttempted(
                        gateway_id="",  # Will be set by service
                        attempt_number=self.connection_attempts,
                        gateway_type="",
                    )
                )

            try:
                # Attempt connection through circuit breaker
                await self.circuit_breaker.call(self.adapter.connect)

                # Connection successful
                self.state = ConnectionState.CONNECTED
                self.connected_at = datetime.now()
                self.current_retry_attempt = 0  # Reset retry counter on success

                # Record success metric
                self.metrics_collector.metrics.record_connection_success()

                # Save successful connection config
                self.last_successful_config = {
                    "timestamp": self.connected_at.isoformat(),
                    "config": self.config.model_dump(),
                }

                # Persist state after successful connection
                await self._persist_state()

                # Start heartbeat if configured
                if self.config.heartbeat_config.enabled:
                    self.heartbeat_task = asyncio.create_task(self.maintain_heartbeat())

                # Publish connected event
                if self.publish_event:
                    await self.publish_event(
                        GatewayConnected(
                            gateway_id="",
                            gateway_type="",
                        )
                    )

            except Exception as e:
                from domain.gateway.circuit_breaker import CircuitOpenError

                self.state = ConnectionState.DISCONNECTED

                # Record failure metric with error type
                error_type = "unknown"
                if isinstance(e, CircuitOpenError):
                    error_type = "circuit_breaker"
                elif "auth" in str(e).lower():
                    error_type = "auth"
                elif "network" in str(e).lower() or "connection" in str(e).lower():
                    error_type = "network"
                elif "timeout" in str(e).lower():
                    error_type = "timeout"

                self.metrics_collector.metrics.record_connection_failure(error_type)

                if isinstance(e, CircuitOpenError):
                    raise ConnectionError(f"Circuit breaker open: {e}")
                raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """
        Disconnect from the gateway
        """
        if self.state == ConnectionState.DISCONNECTED:
            return

        # Stop heartbeat
        self.stop_heartbeat()

        # Stop reconnection if active
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        # Disconnect adapter
        try:
            await self.adapter.disconnect()
        finally:
            self.state = ConnectionState.DISCONNECTED
            self.connected_at = None

            # Record disconnection metric
            self.metrics_collector.metrics.record_disconnection()

            # Persist disconnection state
            await self._persist_state()

            # Publish disconnected event
            if self.publish_event:
                await self.publish_event(
                    GatewayDisconnected(
                        gateway_id="",
                        gateway_type="",
                        reason="Manual disconnection",
                    )
                )

    async def reconnect(self) -> None:
        """
        Reconnect to the gateway
        """
        await self.disconnect()
        await self.connect()

    async def connect_with_retry(self) -> None:
        """
        Connect with automatic retry on failure using SDK's RetryPolicy
        """
        import random

        last_error = None
        self.current_retry_attempt = 0

        while self.current_retry_attempt < self.retry_policy.max_retries:
            try:
                await self.connect()
                self.current_retry_attempt = 0  # Reset on success
                return  # Success

            except Exception as e:
                last_error = e

                if self.current_retry_attempt >= self.retry_policy.max_retries - 1:
                    break

                # Calculate delay using SDK's retry policy
                delay_seconds = self.retry_policy.initial_delay.total_seconds()
                if self.current_retry_attempt > 0:
                    # Apply exponential backoff
                    delay_seconds = min(
                        delay_seconds
                        * (self.retry_policy.backoff_multiplier**self.current_retry_attempt),
                        self.retry_policy.max_delay.total_seconds(),
                    )

                    # Apply jitter
                    if self.retry_policy.jitter_factor > 0:
                        jitter_range = delay_seconds * self.retry_policy.jitter_factor
                        delay_seconds += random.uniform(-jitter_range, jitter_range)

                # Publish reconnection scheduled event
                if self.publish_event:
                    await self.publish_event(
                        ReconnectionScheduled(
                            gateway_id="",
                            next_attempt_in=int(delay_seconds),
                            attempt_number=self.current_retry_attempt + 1,
                        )
                    )

                # Wait before retry
                await asyncio.sleep(delay_seconds)
                self.current_retry_attempt += 1

        # Max attempts reached
        raise ConnectionError(f"Failed after {self.current_retry_attempt} attempts: {last_error}")

    async def maintain_heartbeat(self) -> None:
        """
        Maintain heartbeat with the gateway
        """
        while self.state == ConnectionState.CONNECTED:
            try:
                # Send heartbeat
                await self.adapter.send_heartbeat()
                self.last_heartbeat_sent = datetime.now()

                # Record heartbeat sent metric
                self.metrics_collector.metrics.record_heartbeat_sent()

                # Wait for interval
                await asyncio.sleep(self.config.heartbeat_config.interval)

                # Check for timeout
                if self.is_heartbeat_timeout():
                    # Heartbeat timeout, trigger reconnection
                    await self.handle_disconnection()
                    break

            except asyncio.CancelledError:
                break
            except Exception:
                # Heartbeat failed, trigger reconnection
                await self.handle_disconnection()
                break

    def handle_heartbeat_response(self) -> None:
        """
        Handle heartbeat response from gateway
        """
        self.last_heartbeat_received = datetime.now()

        # Calculate latency and record metric
        latency_ms = 0
        if self.last_heartbeat_sent:
            latency = (self.last_heartbeat_received - self.last_heartbeat_sent).total_seconds()
            latency_ms = int(latency * 1000)

        self.metrics_collector.metrics.record_heartbeat_received(latency_ms)

        # Persist heartbeat state
        if self.state_persistence:
            asyncio.create_task(self._persist_state())

        # Publish heartbeat received event
        if self.publish_event:
            latency_ms = None
            if self.last_heartbeat_sent:
                latency = (self.last_heartbeat_received - self.last_heartbeat_sent).total_seconds()
                latency_ms = int(latency * 1000)

            asyncio.create_task(
                self.publish_event(
                    HeartbeatReceived(
                        gateway_id="",
                        latency_ms=latency_ms,
                    )
                )
            )

    def is_heartbeat_timeout(self) -> bool:
        """
        Check if heartbeat has timed out

        Returns:
            True if heartbeat timeout, False otherwise
        """
        if not self.config.heartbeat_config.enabled:
            return False

        if self.last_heartbeat_received is None:
            # No heartbeat received yet, check against connection time
            if self.connected_at:
                time_since_connection = (datetime.now() - self.connected_at).total_seconds()
                return time_since_connection > self.config.heartbeat_config.timeout
            return False

        time_since_heartbeat = (datetime.now() - self.last_heartbeat_received).total_seconds()
        return time_since_heartbeat > self.config.heartbeat_config.timeout

    async def handle_disconnection(self) -> None:
        """
        Handle unexpected disconnection
        """
        if self.state != ConnectionState.CONNECTED:
            return

        self.state = ConnectionState.RECONNECTING

        # Stop heartbeat
        self.stop_heartbeat()

        # Publish disconnection event
        if self.publish_event:
            await self.publish_event(
                GatewayDisconnected(
                    gateway_id="",
                    gateway_type="",
                    reason="Connection lost",
                )
            )

        # Start reconnection task
        self.reconnect_task = asyncio.create_task(self.connect_with_retry())

    def stop_heartbeat(self) -> None:
        """Stop heartbeat task"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    def is_connected(self) -> bool:
        """
        Check if currently connected

        Returns:
            True if connected, False otherwise
        """
        return self.state == ConnectionState.CONNECTED and self.adapter.is_connected()

    def get_health_status(self) -> ConnectionHealthStatus:
        """
        Get connection health status

        Returns:
            ConnectionHealthStatus object
        """
        uptime = None
        if self.connected_at and self.state == ConnectionState.CONNECTED:
            uptime = (datetime.now() - self.connected_at).total_seconds()

        return ConnectionHealthStatus(
            is_healthy=self.is_connected() and not self.is_heartbeat_timeout(),
            state=self.state,
            uptime_seconds=uptime,
            last_heartbeat=self.last_heartbeat_received,
            connection_attempts=self.connection_attempts,
        )

    async def restore_state(self) -> bool:
        """
        Restore connection state from persistence

        Returns:
            True if state was restored, False otherwise
        """
        if not self.state_persistence:
            return False

        state_data = await self.state_persistence.load_state()
        if not state_data:
            return False

        # Restore relevant state
        self.connection_attempts = state_data.connection_attempts
        self.last_successful_config = state_data.last_successful_config

        if state_data.last_heartbeat:
            self.last_heartbeat_received = state_data.last_heartbeat

        return True

    async def _persist_state(self) -> None:
        """
        Persist current connection state
        """
        if not self.state_persistence:
            return

        state_data = ConnectionStateData(
            gateway_id=self.state_persistence.gateway_id,
            connection_state=self.state.value,
            last_successful_config=self.last_successful_config,
            connection_attempts=self.connection_attempts,
            last_heartbeat=self.last_heartbeat_received,
            last_connection_time=self.connected_at,
            last_disconnection_time=(
                datetime.now() if self.state == ConnectionState.DISCONNECTED else None
            ),
            failure_count=(
                self.circuit_breaker.stats.failure_count if hasattr(self, "circuit_breaker") else 0
            ),
        )

        await self.state_persistence.save_state(state_data)

    async def shutdown(self) -> None:
        """
        Gracefully shutdown connection manager
        """
        # Stop all tasks
        self.stop_heartbeat()

        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        # Disconnect
        await self.disconnect()

        # Clear persisted state on shutdown
        if self.state_persistence:
            await self.state_persistence.delete_state()

    def get_metrics(self) -> dict[str, Any]:
        """
        Get connection metrics

        Returns:
            Dictionary of current metrics
        """
        return self.metrics_collector.get_metrics().to_dict()
