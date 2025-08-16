"""
Unit tests for gateway structured logging.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from domain.gateway.structured_logger import (
    EventType,
    GatewayStructuredLogger,
    LogLevel,
    StructuredLogEntry,
)


class TestStructuredLogEntry:
    """Test suite for StructuredLogEntry model."""

    def test_log_entry_creation(self):
        """Test creating a structured log entry."""
        entry = StructuredLogEntry(
            level=LogLevel.INFO,
            event_type=EventType.CONNECTION_SUCCESS,
            gateway_id="ctp-gateway-1",
            message="Connection established",
            details={"broker": "9999", "address": "tcp://test:10130"},
            duration_ms=1500,
            correlation_id="conn-123",
        )

        assert entry.level == LogLevel.INFO
        assert entry.event_type == EventType.CONNECTION_SUCCESS
        assert entry.gateway_id == "ctp-gateway-1"
        assert entry.message == "Connection established"
        assert entry.details["broker"] == "9999"
        assert entry.duration_ms == 1500
        assert entry.correlation_id == "conn-123"

    def test_log_entry_to_json(self):
        """Test converting log entry to JSON."""
        entry = StructuredLogEntry(
            level=LogLevel.ERROR,
            event_type=EventType.CONNECTION_FAILURE,
            gateway_id="ctp-gateway-1",
            message="Connection failed",
            error="Network timeout",
            duration_ms=5000,
        )

        json_str = entry.to_json()
        data = json.loads(json_str)

        assert data["level"] == "ERROR"
        assert data["event_type"] == "CONNECTION_FAILURE"
        assert data["gateway_id"] == "ctp-gateway-1"
        assert data["message"] == "Connection failed"
        assert data["error"] == "Network timeout"
        assert data["duration_ms"] == 5000
        assert "timestamp" in data

    def test_log_entry_minimal(self):
        """Test creating minimal log entry."""
        entry = StructuredLogEntry(
            level=LogLevel.DEBUG,
            event_type=EventType.HEARTBEAT_SENT,
            gateway_id="test-gateway",
            message="Heartbeat sent",
        )

        json_str = entry.to_json()
        data = json.loads(json_str)

        assert data["level"] == "DEBUG"
        assert data["event_type"] == "HEARTBEAT_SENT"
        assert "error" not in data
        assert "duration_ms" not in data
        assert "correlation_id" not in data


class TestGatewayStructuredLogger:
    """Test suite for GatewayStructuredLogger."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        mock = MagicMock(spec=logging.Logger)
        mock.handlers = [MagicMock()]  # Simulate existing handler
        return mock

    @pytest.fixture
    def structured_logger(self, mock_logger):
        """Create structured logger with mock."""
        return GatewayStructuredLogger("test-gateway", logger=mock_logger)

    def test_log_connection_attempt(self, structured_logger, mock_logger):
        """Test logging connection attempt."""
        structured_logger.log_connection_attempt({"broker": "9999"})

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "CONNECTION_ATTEMPT"
        assert log_data["message"] == "Attempting to connect to gateway"
        assert log_data["details"]["broker"] == "9999"

    def test_log_connection_success(self, structured_logger, mock_logger):
        """Test logging connection success."""
        structured_logger.log_connection_success(
            duration_ms=1200,
            details={"address": "tcp://test:10130"},
        )

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "CONNECTION_SUCCESS"
        assert log_data["message"] == "Successfully connected to gateway"
        assert log_data["duration_ms"] == 1200
        assert log_data["details"]["address"] == "tcp://test:10130"

    def test_log_connection_failure(self, structured_logger, mock_logger):
        """Test logging connection failure."""
        structured_logger.log_connection_failure(
            error="Authentication failed",
            duration_ms=3000,
            details={"error_code": "-3"},
        )

        mock_logger.error.assert_called_once()
        log_data = json.loads(mock_logger.error.call_args[0][0])

        assert log_data["level"] == "ERROR"
        assert log_data["event_type"] == "CONNECTION_FAILURE"
        assert log_data["message"] == "Failed to connect to gateway"
        assert log_data["error"] == "Authentication failed"
        assert log_data["duration_ms"] == 3000
        assert log_data["details"]["error_code"] == "-3"

    def test_log_authentication_success(self, structured_logger, mock_logger):
        """Test logging successful authentication."""
        structured_logger.log_authentication(
            success=True,
            duration_ms=500,
            details={"user": "test_user"},
        )

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "AUTHENTICATION_SUCCESS"
        assert log_data["message"] == "Authentication successful"
        assert log_data["duration_ms"] == 500

    def test_log_authentication_failure(self, structured_logger, mock_logger):
        """Test logging authentication failure."""
        structured_logger.log_authentication(
            success=False,
            error="Invalid credentials",
            duration_ms=200,
        )

        mock_logger.error.assert_called_once()
        log_data = json.loads(mock_logger.error.call_args[0][0])

        assert log_data["level"] == "ERROR"
        assert log_data["event_type"] == "AUTHENTICATION_FAILURE"
        assert log_data["message"] == "Authentication failed"
        assert log_data["error"] == "Invalid credentials"

    def test_log_heartbeat_sent(self, structured_logger, mock_logger):
        """Test logging heartbeat sent."""
        structured_logger.log_heartbeat(sent=True)

        mock_logger.debug.assert_called_once()
        log_data = json.loads(mock_logger.debug.call_args[0][0])

        assert log_data["level"] == "DEBUG"
        assert log_data["event_type"] == "HEARTBEAT_SENT"
        assert log_data["message"] == "Heartbeat sent"

    def test_log_heartbeat_received(self, structured_logger, mock_logger):
        """Test logging heartbeat received."""
        structured_logger.log_heartbeat(sent=False, latency_ms=25)

        mock_logger.debug.assert_called_once()
        log_data = json.loads(mock_logger.debug.call_args[0][0])

        assert log_data["level"] == "DEBUG"
        assert log_data["event_type"] == "HEARTBEAT_RECEIVED"
        assert log_data["message"] == "Heartbeat received"
        assert log_data["details"]["latency_ms"] == 25

    def test_log_heartbeat_timeout(self, structured_logger, mock_logger):
        """Test logging heartbeat timeout."""
        structured_logger.log_heartbeat(sent=False, timeout=True)

        mock_logger.warning.assert_called_once()
        log_data = json.loads(mock_logger.warning.call_args[0][0])

        assert log_data["level"] == "WARNING"
        assert log_data["event_type"] == "HEARTBEAT_TIMEOUT"
        assert log_data["message"] == "Heartbeat timeout detected"

    def test_log_failover_start(self, structured_logger, mock_logger):
        """Test logging failover start."""
        structured_logger.log_failover(
            start=True,
            from_instance="instance-1",
            to_instance="instance-2",
        )

        mock_logger.warning.assert_called_once()
        log_data = json.loads(mock_logger.warning.call_args[0][0])

        assert log_data["level"] == "WARNING"
        assert log_data["event_type"] == "FAILOVER_START"
        assert log_data["message"] == "Failover initiated"
        assert log_data["details"]["from_instance"] == "instance-1"
        assert log_data["details"]["to_instance"] == "instance-2"

    def test_log_failover_complete(self, structured_logger, mock_logger):
        """Test logging failover completion."""
        structured_logger.log_failover(
            start=False,
            duration_ms=1800,
            to_instance="instance-2",
        )

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "FAILOVER_COMPLETE"
        assert log_data["message"] == "Failover completed"
        assert log_data["duration_ms"] == 1800

    def test_log_circuit_breaker_states(self, structured_logger, mock_logger):
        """Test logging circuit breaker state changes."""
        # Test OPEN state
        structured_logger.log_circuit_breaker_state(
            "OPEN",
            reason="Too many failures",
            failure_count=5,
        )

        mock_logger.error.assert_called_once()
        log_data = json.loads(mock_logger.error.call_args[0][0])
        assert log_data["level"] == "ERROR"
        assert log_data["event_type"] == "CIRCUIT_BREAKER_OPEN"
        assert "Too many failures" in log_data["details"]["reason"]
        assert log_data["details"]["failure_count"] == 5

        # Test HALF_OPEN state
        mock_logger.reset_mock()
        structured_logger.log_circuit_breaker_state("HALF_OPEN")

        mock_logger.warning.assert_called_once()
        log_data = json.loads(mock_logger.warning.call_args[0][0])
        assert log_data["level"] == "WARNING"
        assert log_data["event_type"] == "CIRCUIT_BREAKER_HALF_OPEN"

        # Test CLOSED state
        mock_logger.reset_mock()
        structured_logger.log_circuit_breaker_state("CLOSED")

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])
        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "CIRCUIT_BREAKER_CLOSED"

    def test_log_state_transition(self, structured_logger, mock_logger):
        """Test logging state transitions."""
        structured_logger.log_state_transition(
            from_state="DISCONNECTED",
            to_state="CONNECTING",
            trigger="user_request",
        )

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "STATE_TRANSITION"
        assert "DISCONNECTED → CONNECTING" in log_data["message"]
        assert log_data["details"]["trigger"] == "user_request"

    def test_log_reconnection_attempt(self, structured_logger, mock_logger):
        """Test logging reconnection attempts."""
        structured_logger.log_reconnection_attempt(
            attempt_number=3,
            max_attempts=10,
            wait_time_ms=5000,
        )

        mock_logger.info.assert_called_once()
        log_data = json.loads(mock_logger.info.call_args[0][0])

        assert log_data["level"] == "INFO"
        assert log_data["event_type"] == "RECONNECTION_ATTEMPT"
        assert "3/10" in log_data["message"]
        assert log_data["details"]["attempt_number"] == 3
        assert log_data["details"]["max_attempts"] == 10
        assert log_data["details"]["wait_time_ms"] == 5000

    def test_log_error(self, structured_logger, mock_logger):
        """Test logging generic errors."""
        structured_logger.log_error(
            message="Unexpected error occurred",
            error="NullPointerException",
            details={"stack_trace": "..."},
        )

        mock_logger.error.assert_called_once()
        log_data = json.loads(mock_logger.error.call_args[0][0])

        assert log_data["level"] == "ERROR"
        assert log_data["event_type"] == "CONNECTION_FAILURE"
        assert log_data["message"] == "Unexpected error occurred"
        assert log_data["error"] == "NullPointerException"
        assert "stack_trace" in log_data["details"]

    def test_logger_without_handlers(self):
        """Test logger creation without existing handlers."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock(spec=logging.Logger)
            mock_logger.handlers = []  # No handlers
            mock_get_logger.return_value = mock_logger

            logger = GatewayStructuredLogger("test-gateway")

            # Should add a handler
            mock_logger.addHandler.assert_called_once()
            assert mock_logger.setLevel.called
