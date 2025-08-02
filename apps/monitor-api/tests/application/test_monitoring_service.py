"""Tests for the monitoring application service.

These tests verify the business logic orchestration without
depending on infrastructure implementations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.monitoring_service import MonitoringService
from app.domain.exceptions import (
    HealthCheckFailedException,
    ServiceUnavailableException,
)
from app.domain.models import HealthStatus, SystemStatus
from app.ports.configuration import ConfigurationPort
from app.ports.monitoring import MonitoringPort


@pytest.fixture
def mock_monitoring_port() -> AsyncMock:
    """Create a mock monitoring port for testing."""
    return AsyncMock(spec=MonitoringPort)


@pytest.fixture
def mock_configuration_port() -> Mock:
    """Create a mock configuration port for testing."""
    return Mock(spec=ConfigurationPort)


@pytest.fixture
def monitoring_service(
    mock_monitoring_port: AsyncMock, mock_configuration_port: Mock
) -> MonitoringService:
    """Create a monitoring service with mocked dependencies."""
    return MonitoringService(mock_monitoring_port, mock_configuration_port)


class TestMonitoringService:
    """Test cases for MonitoringService."""

    @pytest.mark.asyncio
    async def test_get_health_status_success(self, monitoring_service, mock_monitoring_port):
        """Test successfully getting health status."""
        # Arrange
        expected_health = HealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            nats_url="nats://localhost:4222",
        )
        mock_monitoring_port.check_health.return_value = expected_health

        # Act
        result = await monitoring_service.get_health_status()

        # Assert
        assert result == expected_health
        mock_monitoring_port.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_health_status_failure(self, monitoring_service, mock_monitoring_port):
        """Test handling health check failures."""
        # Arrange
        mock_monitoring_port.check_health.side_effect = Exception("Connection failed")

        # Act & Assert
        with pytest.raises(HealthCheckFailedException) as exc_info:
            await monitoring_service.get_health_status()

        assert "Failed to check health: Connection failed" in str(exc_info.value)
        assert exc_info.value.error_code == "HEALTH_CHECK_FAILED"

    @pytest.mark.asyncio
    async def test_get_system_status_success(self, monitoring_service, mock_monitoring_port):
        """Test successfully getting system status."""
        # Arrange
        now = datetime.now()
        expected_status = SystemStatus(
            timestamp=now,
            uptime_seconds=3600.0,
            environment="development",
            connected_services=5,
            deployment_version="v1.0.0",
            start_time=now,
        )
        mock_monitoring_port.get_system_status.return_value = expected_status

        # Act
        result = await monitoring_service.get_system_status()

        # Assert
        assert result == expected_status
        mock_monitoring_port.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_status_failure(self, monitoring_service, mock_monitoring_port):
        """Test handling system status retrieval failures."""
        # Arrange
        mock_monitoring_port.get_system_status.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await monitoring_service.get_system_status()

        assert "Failed to get system status: Database error" in str(exc_info.value)
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_check_readiness_when_ready(self, monitoring_service, mock_monitoring_port):
        """Test readiness check when service is ready."""
        # Arrange
        mock_monitoring_port.is_ready.return_value = True

        # Act
        result = await monitoring_service.check_readiness()

        # Assert
        assert result == {"status": "ready"}
        mock_monitoring_port.is_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_readiness_when_not_ready(self, monitoring_service, mock_monitoring_port):
        """Test readiness check when service is not ready."""
        # Arrange
        mock_monitoring_port.is_ready.return_value = False

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await monitoring_service.check_readiness()

        assert "Service is not ready" in str(exc_info.value)
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_check_readiness_failure(self, monitoring_service, mock_monitoring_port):
        """Test handling readiness check failures."""
        # Arrange
        mock_monitoring_port.is_ready.side_effect = Exception("Connection timeout")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await monitoring_service.check_readiness()

        assert "Readiness check failed: Connection timeout" in str(exc_info.value)
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

    def test_get_welcome_message(self, monitoring_service: MonitoringService) -> None:
        """Test getting the welcome message."""
        # Act
        result = monitoring_service.get_welcome_message()

        # Assert
        assert result == {"message": "Welcome to AegisTrader Management Service"}
        # Note: This method doesn't use any ports, so no mocks to verify
