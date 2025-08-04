"""Unit tests for API routes.

These tests verify the behavior of API endpoints,
including proper response formatting and error handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.domain.models import (
    DetailedHealthStatus,
    HealthStatus,
    SystemStatus,
)
from app.infrastructure.api.routes import (
    detailed_health_check,
    health_check,
    readiness_check,
    root,
    system_status,
)

if TYPE_CHECKING:
    pass


class TestRoutes:
    """Test cases for API routes."""

    @pytest.fixture
    def mock_monitoring_service(self) -> Mock:
        """Create a mock monitoring service."""
        service = Mock()
        service.get_health_status = AsyncMock()
        service.get_welcome_message = Mock()
        service.check_readiness = AsyncMock()
        service.get_system_status = AsyncMock()
        service.get_detailed_health_status = AsyncMock()
        return service

    @pytest.fixture
    def mock_health_status(self) -> HealthStatus:
        """Create a mock health status."""
        return HealthStatus(
            status="healthy",
            service_name="management-service",
            version="0.1.0",
            nats_url="nats://test:4222",
            timestamp=datetime.now(),
        )

    @pytest.fixture
    def mock_system_status(self) -> SystemStatus:
        """Create a mock system status."""
        start_time = datetime.now() - timedelta(hours=2)
        return SystemStatus(
            timestamp=datetime.now(),
            uptime_seconds=7200.0,
            environment="development",
            connected_services=5,
            deployment_version="v1.2.3",
            start_time=start_time,
        )

    @pytest.fixture
    def mock_detailed_health_status(self) -> DetailedHealthStatus:
        """Create a mock detailed health status."""
        return DetailedHealthStatus(
            status="healthy",
            service_name="management-service",
            version="0.1.0",
            cpu_percent=45.5,
            memory_percent=62.3,
            disk_usage_percent=75.8,
            nats_status="healthy",
            nats_latency_ms=12.5,
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_health_check_success(
        self, mock_monitoring_service: Mock, mock_health_status: HealthStatus
    ) -> None:
        """Test successful health check endpoint."""
        # Arrange
        mock_monitoring_service.get_health_status.return_value = mock_health_status

        # Act
        response = await health_check(monitoring_service=mock_monitoring_service)

        # Assert
        assert response.status == "healthy"
        assert response.service == "management-service"
        assert response.version == "0.1.0"
        assert response.nats_url == "nats://test:4222"
        mock_monitoring_service.get_health_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_root_endpoint(self, mock_monitoring_service: Mock) -> None:
        """Test root endpoint returns welcome message."""
        # Arrange
        expected_message = {"message": "Welcome to AegisTrader Management Service"}
        mock_monitoring_service.get_welcome_message.return_value = expected_message

        # Act
        response = await root(monitoring_service=mock_monitoring_service)

        # Assert
        assert response == expected_message
        mock_monitoring_service.get_welcome_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_readiness_check_ready(self, mock_monitoring_service: Mock) -> None:
        """Test readiness check when service is ready."""
        # Arrange
        mock_monitoring_service.check_readiness.return_value = {"status": "ready"}

        # Act
        response = await readiness_check(monitoring_service=mock_monitoring_service)

        # Assert
        assert response == {"status": "ready"}
        mock_monitoring_service.check_readiness.assert_called_once()

    @pytest.mark.asyncio
    async def test_readiness_check_not_ready(self, mock_monitoring_service: Mock) -> None:
        """Test readiness check when service is not ready."""
        # Arrange
        mock_monitoring_service.check_readiness.return_value = {
            "status": "not ready",
            "reason": "initializing",
        }

        # Act
        response = await readiness_check(monitoring_service=mock_monitoring_service)

        # Assert
        assert response == {"status": "not ready", "reason": "initializing"}
        mock_monitoring_service.check_readiness.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_status_success(
        self, mock_monitoring_service: Mock, mock_system_status: SystemStatus
    ) -> None:
        """Test system status endpoint."""
        # Arrange
        mock_monitoring_service.get_system_status.return_value = mock_system_status

        # Act
        response = await system_status(monitoring_service=mock_monitoring_service)

        # Assert
        assert response.uptime_seconds == 7200.0
        assert response.environment == "development"
        assert response.connected_services == 5
        assert response.deployment_version == "v1.2.3"
        assert isinstance(response.timestamp, str)  # Should be ISO format string
        mock_monitoring_service.get_system_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_detailed_health_check_success(
        self, mock_monitoring_service: Mock, mock_detailed_health_status: DetailedHealthStatus
    ) -> None:
        """Test detailed health check endpoint."""
        # Arrange
        mock_monitoring_service.get_detailed_health_status.return_value = (
            mock_detailed_health_status
        )

        # Act
        response = await detailed_health_check(monitoring_service=mock_monitoring_service)

        # Assert
        assert response.status == "healthy"
        assert response.service == "management-service"
        assert response.version == "0.1.0"
        assert response.system_metrics.cpu_percent == 45.5
        assert response.system_metrics.memory_percent == 62.3
        assert response.system_metrics.disk_usage_percent == 75.8
        assert response.dependencies["nats"].status == "healthy"
        assert response.dependencies["nats"].latency_ms == 12.5
        mock_monitoring_service.get_detailed_health_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_error_handling(self, mock_monitoring_service: Mock) -> None:
        """Test health check handles service errors gracefully."""
        # Arrange
        mock_monitoring_service.get_health_status.side_effect = Exception("Service error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await health_check(monitoring_service=mock_monitoring_service)

        assert "Service error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_system_status_with_long_uptime(self, mock_monitoring_service: Mock) -> None:
        """Test system status with extended uptime."""
        # Arrange
        start_time = datetime.now() - timedelta(days=7, hours=3, minutes=45)
        mock_status = SystemStatus(
            timestamp=datetime.now(),
            uptime_seconds=613500.0,  # 7 days, 3 hours, 45 minutes
            environment="production",
            connected_services=12,
            deployment_version="v2.0.0-stable",
            start_time=start_time,
        )
        mock_monitoring_service.get_system_status.return_value = mock_status

        # Act
        response = await system_status(monitoring_service=mock_monitoring_service)

        # Assert
        assert response.uptime_seconds == 613500.0
        assert response.environment == "production"
        assert response.connected_services == 12

    @pytest.mark.asyncio
    async def test_detailed_health_check_unhealthy_dependencies(
        self, mock_monitoring_service: Mock
    ) -> None:
        """Test detailed health check with unhealthy dependencies."""
        # Arrange
        mock_detailed_health = DetailedHealthStatus(
            status="degraded",
            service_name="management-service",
            version="0.1.0",
            cpu_percent=85.0,
            memory_percent=92.0,
            disk_usage_percent=95.0,
            nats_status="unhealthy",
            nats_latency_ms=5000.0,  # Very high latency
            timestamp=datetime.now(),
        )
        mock_monitoring_service.get_detailed_health_status.return_value = mock_detailed_health

        # Act
        response = await detailed_health_check(monitoring_service=mock_monitoring_service)

        # Assert
        assert response.status == "degraded"
        assert response.system_metrics.cpu_percent == 85.0
        assert response.system_metrics.memory_percent == 92.0
        assert response.system_metrics.disk_usage_percent == 95.0
        assert response.dependencies["nats"].status == "unhealthy"
        assert response.dependencies["nats"].latency_ms == 5000.0
