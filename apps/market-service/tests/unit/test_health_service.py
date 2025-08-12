"""
Unit tests for the health check service.
"""

from datetime import UTC, datetime

import pytest

from application.health_service import HealthCheckRequest, HealthCheckResponse, HealthCheckService


@pytest.mark.asyncio
class TestHealthCheckService:
    """Unit tests for HealthCheckService."""

    @pytest.fixture
    def health_service(self):
        """Create a health service instance."""
        return HealthCheckService()

    async def test_health_check_returns_healthy_status(self, health_service):
        """Test that health check returns healthy status when all indicators are good."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert isinstance(response, HealthCheckResponse)
        assert response.status == "healthy"
        assert response.service_name == "market-service"
        assert response.version == "0.1.0"
        assert isinstance(response.timestamp, datetime)

    async def test_health_check_with_timestamp_in_request(self, health_service):
        """Test health check with timestamp provided in request."""
        request_time = datetime.now(UTC)
        request = HealthCheckRequest(timestamp=request_time)
        response = await health_service.health_check(request)

        assert response.status == "healthy"
        assert response.timestamp >= request_time

    async def test_gateway_health_check(self, health_service):
        """Test gateway health check method."""
        result = await health_service._check_gateway_health()
        assert isinstance(result, bool)
        assert result is True  # Currently returns True as placeholder

    async def test_message_bus_health_check(self, health_service):
        """Test message bus health check method."""
        result = await health_service._check_message_bus_health()
        assert isinstance(result, bool)
        assert result is True  # Currently returns True as placeholder

    async def test_database_health_check(self, health_service):
        """Test database health check method."""
        result = await health_service._check_database_health()
        assert isinstance(result, bool)
        assert result is True  # Currently returns True as placeholder

    async def test_aggregate_health_status_all_healthy(self, health_service):
        """Test health aggregation when all components are healthy."""
        status = health_service._aggregate_health_status(
            gateway_ready=True, message_bus_connected=True, database_connected=True
        )
        assert status == "healthy"

    async def test_aggregate_health_status_message_bus_down(self, health_service):
        """Test health aggregation when message bus is down."""
        status = health_service._aggregate_health_status(
            gateway_ready=True, message_bus_connected=False, database_connected=True
        )
        assert status == "unhealthy"

    async def test_aggregate_health_status_gateway_down(self, health_service):
        """Test health aggregation when gateway is down."""
        status = health_service._aggregate_health_status(
            gateway_ready=False, message_bus_connected=True, database_connected=True
        )
        assert status == "degraded"

    async def test_aggregate_health_status_database_down(self, health_service):
        """Test health aggregation when database is down."""
        status = health_service._aggregate_health_status(
            gateway_ready=True, message_bus_connected=True, database_connected=False
        )
        assert status == "degraded"

    async def test_aggregate_health_status_multiple_down(self, health_service):
        """Test health aggregation when multiple components are down."""
        status = health_service._aggregate_health_status(
            gateway_ready=False, message_bus_connected=False, database_connected=False
        )
        assert status == "unhealthy"
