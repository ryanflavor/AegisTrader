"""Unit tests for the MonitoringService.

These tests verify the monitoring service orchestration logic,
including health checks, system status, and error handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.monitoring_service import MonitoringService
from app.domain.exceptions import HealthCheckFailedException, ServiceUnavailableException
from app.domain.models import DetailedHealthStatus, HealthStatus, SystemStatus

if TYPE_CHECKING:
    pass


class TestMonitoringService:
    """Test cases for MonitoringService."""

    @pytest.fixture
    def mock_monitoring_port(self) -> Mock:
        """Create a mock monitoring port."""
        port = Mock()
        port.check_health = AsyncMock()
        port.get_system_status = AsyncMock()
        port.get_start_time = AsyncMock()
        port.is_ready = AsyncMock()
        port.get_detailed_health = AsyncMock()
        return port

    @pytest.fixture
    def mock_configuration_port(self) -> Mock:
        """Create a mock configuration port."""
        port = Mock()
        port.load_configuration = Mock()
        port.validate_configuration = Mock()
        return port

    @pytest.fixture
    def monitoring_service(
        self, mock_monitoring_port: Mock, mock_configuration_port: Mock
    ) -> MonitoringService:
        """Create a monitoring service instance."""
        return MonitoringService(mock_monitoring_port, mock_configuration_port)

    @pytest.mark.asyncio
    async def test_get_health_status_success(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test successful health status retrieval."""
        # Arrange
        expected_health = HealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            nats_url="nats://test:4222",
            timestamp=datetime.now(),
        )
        mock_monitoring_port.check_health.return_value = expected_health

        # Act
        result = await monitoring_service.get_health_status()

        # Assert
        assert result == expected_health
        mock_monitoring_port.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_health_status_failure(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test health status retrieval when check fails."""
        # Arrange
        mock_monitoring_port.check_health.side_effect = Exception("Health check failed")

        # Act & Assert
        with pytest.raises(HealthCheckFailedException) as exc_info:
            await monitoring_service.get_health_status()

        assert "Health check failed" in str(exc_info.value)
        mock_monitoring_port.check_health.assert_called_once()

    def test_get_welcome_message(self, monitoring_service: MonitoringService) -> None:
        """Test welcome message generation."""
        # Act
        result = monitoring_service.get_welcome_message()

        # Assert
        assert result == {"message": "Welcome to AegisTrader Management Service"}

    @pytest.mark.asyncio
    async def test_check_readiness_ready(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test readiness check when service is ready."""
        # Arrange
        mock_monitoring_port.is_ready.return_value = True

        # Act
        result = await monitoring_service.check_readiness()

        # Assert
        assert result == {"status": "ready"}
        mock_monitoring_port.is_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_readiness_not_ready(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test readiness check when service is not ready."""
        # Arrange
        mock_monitoring_port.is_ready.return_value = False

        # Act
        result = await monitoring_service.check_readiness()

        # Assert
        assert result == {"status": "not ready", "reason": "Service is initializing"}
        mock_monitoring_port.is_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_readiness_error(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test readiness check error handling."""
        # Arrange
        mock_monitoring_port.is_ready.side_effect = Exception("Connection error")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await monitoring_service.check_readiness()

        assert "Readiness check failed" in str(exc_info.value)
        mock_monitoring_port.is_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_status_success(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test successful system status retrieval."""
        # Arrange
        expected_status = SystemStatus(
            timestamp=datetime.now(),
            uptime_seconds=3600.0,
            environment="production",
            connected_services=5,
            deployment_version="v1.2.3",
            start_time=datetime.now(),
        )
        mock_monitoring_port.get_system_status.return_value = expected_status

        # Act
        result = await monitoring_service.get_system_status()

        # Assert
        assert result == expected_status
        mock_monitoring_port.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_status_failure(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test system status retrieval error handling."""
        # Arrange
        mock_monitoring_port.get_system_status.side_effect = Exception("Status error")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await monitoring_service.get_system_status()

        assert "Failed to get system status" in str(exc_info.value)
        mock_monitoring_port.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_detailed_health_status_success(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test successful detailed health status retrieval."""
        # Arrange
        expected_health = DetailedHealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            cpu_percent=45.0,
            memory_percent=60.0,
            disk_usage_percent=70.0,
            nats_status="healthy",
            nats_latency_ms=10.0,
            timestamp=datetime.now(),
        )
        mock_monitoring_port.get_detailed_health.return_value = expected_health

        # Act
        result = await monitoring_service.get_detailed_health_status()

        # Assert
        assert result == expected_health
        mock_monitoring_port.get_detailed_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_detailed_health_status_failure(
        self,
        monitoring_service: MonitoringService,
        mock_monitoring_port: Mock,
    ) -> None:
        """Test detailed health status error handling."""
        # Arrange
        mock_monitoring_port.get_detailed_health.side_effect = Exception("Detailed health error")

        # Act & Assert
        with pytest.raises(HealthCheckFailedException) as exc_info:
            await monitoring_service.get_detailed_health_status()

        assert "Detailed health check failed" in str(exc_info.value)
        mock_monitoring_port.get_detailed_health.assert_called_once()

    def test_monitoring_service_initialization(
        self,
        mock_monitoring_port: Mock,
        mock_configuration_port: Mock,
    ) -> None:
        """Test monitoring service initialization."""
        # Act
        service = MonitoringService(mock_monitoring_port, mock_configuration_port)

        # Assert
        assert service._monitoring_port == mock_monitoring_port
        assert service._configuration_port == mock_configuration_port
