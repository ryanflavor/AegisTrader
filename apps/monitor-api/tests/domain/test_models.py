"""Tests for domain models.

These tests ensure that domain models have proper validation
and follow Pydantic v2 strict mode requirements.
"""

from datetime import datetime

import pytest
from app.domain.models import (
    HealthStatus,
    ServiceConfiguration,
    ServiceError,
    SystemStatus,
)
from pydantic import ValidationError


class TestHealthStatus:
    """Test cases for HealthStatus model."""

    def test_valid_health_status(self):
        """Test creating a valid health status."""
        # Arrange
        status_data = {
            "status": "healthy",
            "service_name": "test-service",
            "version": "1.0.0",
            "nats_url": "nats://localhost:4222",
        }

        # Act
        health_status = HealthStatus(**status_data)

        # Assert
        assert health_status.status == "healthy"
        assert health_status.service_name == "test-service"
        assert health_status.version == "1.0.0"
        assert health_status.nats_url == "nats://localhost:4222"
        assert isinstance(health_status.timestamp, datetime)

    def test_invalid_status_value(self):
        """Test that invalid status values are rejected."""
        # Arrange
        status_data = {
            "status": "invalid",
            "service_name": "test-service",
            "version": "1.0.0",
            "nats_url": "nats://localhost:4222",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(**status_data)

        errors = exc_info.value.errors()
        assert any("literal_error" in str(error) for error in errors)

    def test_invalid_nats_url(self):
        """Test that invalid NATS URLs are rejected."""
        # Arrange
        status_data = {
            "status": "healthy",
            "service_name": "test-service",
            "version": "1.0.0",
            "nats_url": "http://localhost:4222",  # Wrong protocol
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(**status_data)

        errors = exc_info.value.errors()
        assert any(
            "NATS URL must start with nats:// or tls://" in str(error)
            for error in errors
        )

    def test_invalid_version_format(self):
        """Test that invalid version formats are rejected."""
        # Arrange
        status_data = {
            "status": "healthy",
            "service_name": "test-service",
            "version": "1.0",  # Missing patch version
            "nats_url": "nats://localhost:4222",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(**status_data)

        errors = exc_info.value.errors()
        assert any("string_pattern_mismatch" in str(error) for error in errors)

    def test_model_is_immutable(self):
        """Test that the model is frozen (immutable)."""
        # Arrange
        health_status = HealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            nats_url="nats://localhost:4222",
        )

        # Act & Assert
        with pytest.raises(ValidationError):
            health_status.status = "unhealthy"


class TestServiceError:
    """Test cases for ServiceError model."""

    def test_valid_service_error(self):
        """Test creating a valid service error."""
        # Arrange
        error_data = {
            "detail": "Something went wrong",
            "error_code": "SERVICE_ERROR",
            "trace_id": "123e4567-e89b-12d3-a456-426614174000",
        }

        # Act
        error = ServiceError(**error_data)

        # Assert
        assert error.detail == "Something went wrong"
        assert error.error_code == "SERVICE_ERROR"
        assert error.trace_id == "123e4567-e89b-12d3-a456-426614174000"
        assert isinstance(error.timestamp, datetime)

    def test_invalid_error_code_format(self):
        """Test that invalid error code formats are rejected."""
        # Arrange
        error_data = {
            "detail": "Something went wrong",
            "error_code": "invalid-code",  # Should be UPPER_SNAKE_CASE
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ServiceError(**error_data)

        errors = exc_info.value.errors()
        assert any("string_pattern_mismatch" in str(error) for error in errors)

    def test_empty_detail_rejected(self):
        """Test that empty error details are rejected."""
        # Arrange
        error_data = {
            "detail": "",
            "error_code": "SERVICE_ERROR",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ServiceError(**error_data)

        errors = exc_info.value.errors()
        assert any("at least 1 character" in str(error) for error in errors)


class TestSystemStatus:
    """Test cases for SystemStatus model."""

    def test_valid_system_status(self):
        """Test creating a valid system status."""
        # Arrange
        now = datetime.now()
        start_time = datetime.now()
        uptime = 3600.0  # 1 hour

        status_data = {
            "timestamp": now,
            "uptime_seconds": uptime,
            "environment": "development",
            "connected_services": 5,
            "deployment_version": "v1.0.0-beta",
            "start_time": start_time,
        }

        # Act
        status = SystemStatus(**status_data)

        # Assert
        assert status.timestamp == now
        assert status.uptime_seconds == uptime
        assert status.environment == "development"
        assert status.connected_services == 5
        assert status.deployment_version == "v1.0.0-beta"

    def test_negative_uptime_rejected(self):
        """Test that negative uptime values are rejected."""
        # Arrange
        status_data = {
            "timestamp": datetime.now(),
            "uptime_seconds": -100.0,
            "environment": "development",
            "deployment_version": "v1.0.0",
            "start_time": datetime.now(),
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SystemStatus(**status_data)

        errors = exc_info.value.errors()
        assert any("greater_than_equal" in str(error) for error in errors)

    def test_invalid_deployment_version_format(self):
        """Test that invalid deployment version formats are rejected."""
        # Arrange
        status_data = {
            "timestamp": datetime.now(),
            "uptime_seconds": 100.0,
            "environment": "development",
            "deployment_version": "1.0.0",  # Missing 'v' prefix
            "start_time": datetime.now(),
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            SystemStatus(**status_data)

        errors = exc_info.value.errors()
        assert any("string_pattern_mismatch" in str(error) for error in errors)


class TestServiceConfiguration:
    """Test cases for ServiceConfiguration model."""

    def test_valid_configuration(self):
        """Test creating a valid service configuration."""
        # Arrange
        config_data = {
            "nats_url": "nats://localhost:4222",
            "api_port": 8080,
            "log_level": "INFO",
            "environment": "development",
        }

        # Act
        config = ServiceConfiguration(**config_data)

        # Assert
        assert config.nats_url == "nats://localhost:4222"
        assert config.api_port == 8080
        assert config.log_level == "INFO"
        assert config.environment == "development"

    def test_invalid_port_range(self):
        """Test that invalid port numbers are rejected."""
        # Arrange
        config_data = {
            "nats_url": "nats://localhost:4222",
            "api_port": 70000,  # Out of valid range
            "log_level": "INFO",
            "environment": "development",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(**config_data)

        errors = exc_info.value.errors()
        assert any("less_than_equal" in str(error) for error in errors)

    def test_tls_nats_url_accepted(self):
        """Test that TLS NATS URLs are accepted."""
        # Arrange
        config_data = {
            "nats_url": "tls://secure-nats:4222",
            "api_port": 8080,
            "log_level": "INFO",
            "environment": "production",
        }

        # Act
        config = ServiceConfiguration(**config_data)

        # Assert
        assert config.nats_url == "tls://secure-nats:4222"
