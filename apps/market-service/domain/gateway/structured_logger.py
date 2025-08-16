"""
Structured logging for gateway connection events.

Provides JSON-formatted structured logging for all gateway events
to enable efficient log analysis and monitoring.

This extends the SDK's LoggerPort interface to provide domain-specific
structured logging while maintaining compatibility with the SDK.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aegis_sdk.ports.logger import LoggerPort
from pydantic import BaseModel, ConfigDict, Field


class LogLevel(str, Enum):
    """Log levels for structured logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    """Gateway event types for structured logging."""

    CONNECTION_ATTEMPT = "CONNECTION_ATTEMPT"
    CONNECTION_SUCCESS = "CONNECTION_SUCCESS"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    CONNECTION_LOST = "CONNECTION_LOST"
    AUTHENTICATION_START = "AUTHENTICATION_START"
    AUTHENTICATION_SUCCESS = "AUTHENTICATION_SUCCESS"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    HEARTBEAT_SENT = "HEARTBEAT_SENT"
    HEARTBEAT_RECEIVED = "HEARTBEAT_RECEIVED"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    FAILOVER_START = "FAILOVER_START"
    FAILOVER_COMPLETE = "FAILOVER_COMPLETE"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    CIRCUIT_BREAKER_HALF_OPEN = "CIRCUIT_BREAKER_HALF_OPEN"
    CIRCUIT_BREAKER_CLOSED = "CIRCUIT_BREAKER_CLOSED"
    RECONNECTION_ATTEMPT = "RECONNECTION_ATTEMPT"
    STATE_TRANSITION = "STATE_TRANSITION"


class StructuredLogEntry(BaseModel):
    """
    Structured log entry model for gateway events.

    All gateway events are logged in this consistent format
    for easy parsing and analysis.
    """

    model_config = ConfigDict(strict=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: LogLevel
    event_type: EventType
    gateway_id: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None
    correlation_id: str | None = None

    def to_json(self) -> str:
        """
        Convert log entry to JSON string.

        Returns:
            JSON-formatted log entry
        """
        data = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "event_type": self.event_type.value,
            "gateway_id": self.gateway_id,
            "message": self.message,
        }

        if self.details:
            data["details"] = self.details
        if self.error:
            data["error"] = self.error
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        if self.correlation_id:
            data["correlation_id"] = self.correlation_id

        return json.dumps(data, ensure_ascii=False)


class GatewayStructuredLogger(LoggerPort):
    """
    Structured logger for gateway connection events.

    Extends SDK's LoggerPort interface to provide domain-specific
    structured logging while maintaining SDK compatibility.
    Provides consistent, structured logging for all gateway
    events to enable monitoring, alerting, and debugging.
    """

    def __init__(self, gateway_id: str, logger: logging.Logger | None = None):
        """
        Initialize structured logger.

        Args:
            gateway_id: Unique identifier for the gateway
            logger: Optional logger instance, creates default if not provided
        """
        self.gateway_id = gateway_id
        self.logger = logger or logging.getLogger(f"gateway.{gateway_id}")
        self.logger.setLevel(logging.DEBUG)

        # Add JSON formatter if no handlers exist
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)

    # Implement LoggerPort interface methods
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        entry = StructuredLogEntry(
            level=LogLevel.DEBUG,
            event_type=EventType.STATE_TRANSITION,
            gateway_id=self.gateway_id,
            message=message,
            details=kwargs,
        )
        self.logger.debug(entry.to_json())

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.STATE_TRANSITION,
            gateway_id=self.gateway_id,
            message=message,
            details=kwargs,
        )
        self.logger.info(entry.to_json())

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        entry = StructuredLogEntry(
            level=LogLevel.WARNING,
            event_type=EventType.STATE_TRANSITION,
            gateway_id=self.gateway_id,
            message=message,
            details=kwargs,
        )
        self.logger.warning(entry.to_json())

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        entry = StructuredLogEntry(
            level=LogLevel.ERROR,
            event_type=EventType.CONNECTION_FAILURE,
            gateway_id=self.gateway_id,
            message=message,
            details=kwargs,
        )
        self.logger.error(entry.to_json())

    def exception(self, message: str, exc_info: Exception | None = None, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        entry = StructuredLogEntry(
            level=LogLevel.CRITICAL,
            event_type=EventType.CONNECTION_FAILURE,
            gateway_id=self.gateway_id,
            message=message,
            error=str(exc_info) if exc_info else None,
            details=kwargs,
        )
        self.logger.exception(entry.to_json(), exc_info=exc_info or True)

    def log_connection_attempt(self, details: dict[str, Any] | None = None) -> None:
        """
        Log connection attempt event.

        Args:
            details: Additional connection details
        """
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.CONNECTION_ATTEMPT,
            gateway_id=self.gateway_id,
            message="Attempting to connect to gateway",
            details=details or {},
        )
        self.logger.info(entry.to_json())

    def log_connection_success(
        self,
        duration_ms: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log successful connection event.

        Args:
            duration_ms: Time taken to establish connection
            details: Additional connection details
        """
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.CONNECTION_SUCCESS,
            gateway_id=self.gateway_id,
            message="Successfully connected to gateway",
            duration_ms=duration_ms,
            details=details or {},
        )
        self.logger.info(entry.to_json())

    def log_connection_failure(
        self,
        error: str,
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log connection failure event.

        Args:
            error: Error message or description
            duration_ms: Time spent attempting connection
            details: Additional failure details
        """
        entry = StructuredLogEntry(
            level=LogLevel.ERROR,
            event_type=EventType.CONNECTION_FAILURE,
            gateway_id=self.gateway_id,
            message="Failed to connect to gateway",
            error=error,
            duration_ms=duration_ms,
            details=details or {},
        )
        self.logger.error(entry.to_json())

    def log_authentication(
        self,
        success: bool,
        duration_ms: int | None = None,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log authentication event.

        Args:
            success: Whether authentication succeeded
            duration_ms: Time taken for authentication
            error: Error message if failed
            details: Additional authentication details
        """
        if success:
            entry = StructuredLogEntry(
                level=LogLevel.INFO,
                event_type=EventType.AUTHENTICATION_SUCCESS,
                gateway_id=self.gateway_id,
                message="Authentication successful",
                duration_ms=duration_ms,
                details=details or {},
            )
            self.logger.info(entry.to_json())
        else:
            entry = StructuredLogEntry(
                level=LogLevel.ERROR,
                event_type=EventType.AUTHENTICATION_FAILURE,
                gateway_id=self.gateway_id,
                message="Authentication failed",
                error=error or "Unknown authentication error",
                duration_ms=duration_ms,
                details=details or {},
            )
            self.logger.error(entry.to_json())

    def log_heartbeat(
        self,
        sent: bool,
        latency_ms: int | None = None,
        timeout: bool = False,
    ) -> None:
        """
        Log heartbeat event.

        Args:
            sent: True if heartbeat sent, False if received
            latency_ms: Round-trip latency for received heartbeats
            timeout: True if heartbeat timeout occurred
        """
        if timeout:
            entry = StructuredLogEntry(
                level=LogLevel.WARNING,
                event_type=EventType.HEARTBEAT_TIMEOUT,
                gateway_id=self.gateway_id,
                message="Heartbeat timeout detected",
            )
            self.logger.warning(entry.to_json())
        elif sent:
            entry = StructuredLogEntry(
                level=LogLevel.DEBUG,
                event_type=EventType.HEARTBEAT_SENT,
                gateway_id=self.gateway_id,
                message="Heartbeat sent",
            )
            self.logger.debug(entry.to_json())
        else:
            entry = StructuredLogEntry(
                level=LogLevel.DEBUG,
                event_type=EventType.HEARTBEAT_RECEIVED,
                gateway_id=self.gateway_id,
                message="Heartbeat received",
                details={"latency_ms": latency_ms} if latency_ms else {},
            )
            self.logger.debug(entry.to_json())

    def log_failover(
        self,
        start: bool,
        duration_ms: int | None = None,
        from_instance: str | None = None,
        to_instance: str | None = None,
    ) -> None:
        """
        Log failover event.

        Args:
            start: True if failover starting, False if complete
            duration_ms: Time taken for failover
            from_instance: Previous active instance
            to_instance: New active instance
        """
        if start:
            entry = StructuredLogEntry(
                level=LogLevel.WARNING,
                event_type=EventType.FAILOVER_START,
                gateway_id=self.gateway_id,
                message="Failover initiated",
                details=(
                    {
                        "from_instance": from_instance,
                        "to_instance": to_instance,
                    }
                    if from_instance or to_instance
                    else {}
                ),
            )
            self.logger.warning(entry.to_json())
        else:
            entry = StructuredLogEntry(
                level=LogLevel.INFO,
                event_type=EventType.FAILOVER_COMPLETE,
                gateway_id=self.gateway_id,
                message="Failover completed",
                duration_ms=duration_ms,
                details=(
                    {
                        "from_instance": from_instance,
                        "to_instance": to_instance,
                    }
                    if from_instance or to_instance
                    else {}
                ),
            )
            self.logger.info(entry.to_json())

    def log_circuit_breaker_state(
        self,
        state: str,
        reason: str | None = None,
        failure_count: int | None = None,
    ) -> None:
        """
        Log circuit breaker state change.

        Args:
            state: New circuit breaker state
            reason: Reason for state change
            failure_count: Number of failures that triggered change
        """
        event_map = {
            "OPEN": EventType.CIRCUIT_BREAKER_OPEN,
            "HALF_OPEN": EventType.CIRCUIT_BREAKER_HALF_OPEN,
            "CLOSED": EventType.CIRCUIT_BREAKER_CLOSED,
        }

        level_map = {
            "OPEN": LogLevel.ERROR,
            "HALF_OPEN": LogLevel.WARNING,
            "CLOSED": LogLevel.INFO,
        }

        entry = StructuredLogEntry(
            level=level_map.get(state, LogLevel.INFO),
            event_type=event_map.get(state, EventType.STATE_TRANSITION),
            gateway_id=self.gateway_id,
            message=f"Circuit breaker state changed to {state}",
            details=(
                {
                    "state": state,
                    "reason": reason,
                    "failure_count": failure_count,
                }
                if reason or failure_count
                else {"state": state}
            ),
        )

        if state == "OPEN":
            self.logger.error(entry.to_json())
        elif state == "HALF_OPEN":
            self.logger.warning(entry.to_json())
        else:
            self.logger.info(entry.to_json())

    def log_state_transition(
        self,
        from_state: str,
        to_state: str,
        trigger: str | None = None,
    ) -> None:
        """
        Log connection state transition.

        Args:
            from_state: Previous connection state
            to_state: New connection state
            trigger: What triggered the transition
        """
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.STATE_TRANSITION,
            gateway_id=self.gateway_id,
            message=f"Connection state transition: {from_state} → {to_state}",
            details=(
                {
                    "from_state": from_state,
                    "to_state": to_state,
                    "trigger": trigger,
                }
                if trigger
                else {"from_state": from_state, "to_state": to_state}
            ),
        )
        self.logger.info(entry.to_json())

    def log_reconnection_attempt(
        self,
        attempt_number: int,
        max_attempts: int,
        wait_time_ms: int | None = None,
    ) -> None:
        """
        Log reconnection attempt.

        Args:
            attempt_number: Current attempt number
            max_attempts: Maximum number of attempts
            wait_time_ms: Time to wait before next attempt
        """
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.RECONNECTION_ATTEMPT,
            gateway_id=self.gateway_id,
            message=f"Reconnection attempt {attempt_number}/{max_attempts}",
            details=(
                {
                    "attempt_number": attempt_number,
                    "max_attempts": max_attempts,
                    "wait_time_ms": wait_time_ms,
                }
                if wait_time_ms
                else {
                    "attempt_number": attempt_number,
                    "max_attempts": max_attempts,
                }
            ),
        )
        self.logger.info(entry.to_json())

    def log_error(
        self,
        message: str,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log generic error event.

        Args:
            message: Error message
            error: Error description
            details: Additional error details
        """
        entry = StructuredLogEntry(
            level=LogLevel.ERROR,
            event_type=EventType.CONNECTION_FAILURE,
            gateway_id=self.gateway_id,
            message=message,
            error=error,
            details=details or {},
        )
        self.logger.error(entry.to_json())
