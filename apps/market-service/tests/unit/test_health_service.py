"""
Unit tests for the extended health service that leverages SDK health management.

This test suite validates that our health service properly extends the SDK's
health management capabilities rather than duplicating them.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from application.health_service import (
    HealthCheckRequest,
    HealthCheckResponse,
)


@pytest.mark.asyncio
class TestDomainHealthService:
    """Unit tests for DomainHealthService that extends SDK health management."""

    @pytest.fixture
    def mock_sdk_service(self):
        """Create a mock SDK Service with health manager."""
        service = MagicMock()
        service.service_name = "market-service"
        service.version = "2.0.0"
        service.instance_id = "market-service-test-123"

        # Mock the SDK's health manager
        health_manager = MagicMock()
        health_manager.is_healthy = MagicMock(return_value=True)
        health_manager._heartbeat_task = MagicMock()  # Simulates active heartbeat
        health_manager._consecutive_failures = 0
        service._health_manager = health_manager

        # Mock registry
        service._registry = MagicMock()

        return service

    @pytest.fixture
    def mock_gateway_repo(self):
        """Create a mock gateway repository."""
        repo = AsyncMock()
        repo.list_active = AsyncMock(return_value=[MagicMock(), MagicMock()])  # 2 active gateways
        return repo

    @pytest.fixture
    def mock_tick_repo(self):
        """Create a mock tick repository."""
        repo = AsyncMock()
        repo.count_ticks = AsyncMock(return_value=0)  # Returns 0 for health check
        return repo

    @pytest.fixture
    def mock_market_source(self):
        """Create a mock market data source."""
        source = MagicMock()
        source.is_connected = True
        return source

    @pytest.fixture
    def mock_nats(self):
        """Create a mock NATS adapter."""
        nats = MagicMock()
        nats.is_connected = MagicMock(return_value=True)
        return nats

    @pytest.fixture
    def health_service(
        self, mock_sdk_service, mock_gateway_repo, mock_tick_repo, mock_market_source, mock_nats
    ):
        """Create an extended health service instance with mocks."""
        from application.health_service import DomainHealthService

        return DomainHealthService(
            service=mock_sdk_service,
            gateway_repo=mock_gateway_repo,
            tick_repo=mock_tick_repo,
            market_source=mock_market_source,
            nats_adapter=mock_nats,
        )

    async def test_health_check_leverages_sdk_health_manager(
        self, health_service, mock_sdk_service
    ):
        """Test that health check leverages SDK's health manager for infrastructure health."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        # Verify SDK health manager was consulted
        mock_sdk_service._health_manager.is_healthy.assert_called_once()

        assert isinstance(response, HealthCheckResponse)
        assert response.status == "healthy"
        assert response.infrastructure_health.sdk_health_status is True
        assert response.infrastructure_health.heartbeat_active is True
        assert response.infrastructure_health.consecutive_failures == 0

    async def test_domain_health_checks_independent_of_sdk(self, health_service):
        """Test that domain-specific health checks work independently of SDK."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        # Domain-specific checks should still work
        assert response.domain_health.active_gateways == 2
        assert response.domain_health.gateway_status == "multiple_gateways"
        assert response.domain_health.market_source_connected is True
        assert response.domain_health.tick_repository_available is True

    async def test_health_aggregation_considers_both_layers(self, health_service, mock_sdk_service):
        """Test that overall health considers both SDK and domain health."""
        # Test with healthy SDK but degraded domain
        health_service._gateway_repo.list_active = AsyncMock(return_value=[])  # No gateways

        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert response.status == "degraded"  # Domain issues cause degradation
        assert response.infrastructure_health.sdk_health_status is True
        assert response.domain_health.active_gateways == 0

    async def test_health_check_when_sdk_unhealthy(self, health_service, mock_sdk_service):
        """Test health check when SDK health manager reports unhealthy."""
        # Make SDK health manager report unhealthy
        mock_sdk_service._health_manager.is_healthy.return_value = False
        mock_sdk_service._health_manager._consecutive_failures = 5

        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert response.status == "unhealthy"  # SDK unhealthy means overall unhealthy
        assert response.infrastructure_health.sdk_health_status is False
        assert response.infrastructure_health.consecutive_failures == 5

    async def test_get_domain_metrics(self, health_service):
        """Test that domain-specific metrics are collected."""
        metrics = await health_service.get_domain_metrics()

        assert metrics["gateways"]["active_count"] == 2
        assert metrics["gateways"]["status"] == "multiple_gateways"
        assert metrics["market_source"]["connected"] is True
        assert metrics["tick_repository"]["available"] is True

    async def test_get_infrastructure_metrics_from_sdk(self, health_service, mock_sdk_service):
        """Test that infrastructure metrics are retrieved from SDK."""
        # Mock SDK's metrics if available
        mock_sdk_service.get_metrics = MagicMock(
            return_value={
                "counters": {"rpc.calls": 100},
                "gauges": {"connections": 5},
            }
        )

        metrics = await health_service.get_infrastructure_metrics()

        assert metrics["sdk_metrics"]["counters"]["rpc.calls"] == 100
        assert metrics["sdk_metrics"]["gauges"]["connections"] == 5
        assert metrics["heartbeat"]["active"] is True
        assert metrics["heartbeat"]["consecutive_failures"] == 0

    async def test_health_check_graceful_fallback_without_sdk(self):
        """Test health check works gracefully when SDK service is not available."""
        # Create health service without SDK service
        from application.health_service import DomainHealthService

        health_service = DomainHealthService(
            service=None,
            gateway_repo=AsyncMock(list_active=AsyncMock(return_value=[])),
            tick_repo=AsyncMock(count_ticks=AsyncMock(return_value=0)),
            market_source=MagicMock(is_connected=False),
            nats_adapter=MagicMock(is_connected=MagicMock(return_value=False)),
        )

        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert response.status == "unhealthy"  # No SDK means unhealthy
        assert response.infrastructure_health.sdk_health_status is False
        assert response.infrastructure_health.sdk_available is False

    async def test_extended_health_info_includes_sdk_details(
        self, health_service, mock_sdk_service
    ):
        """Test that extended health info includes SDK service details."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert response.service_name == "market-service"
        assert response.version == "2.0.0"
        assert response.instance_id == "market-service-test-123"
        assert response.infrastructure_health.service_registry_connected is True

    async def test_health_check_with_custom_checks(self, health_service):
        """Test adding custom health checks to the extended service."""
        # Add a custom check
        custom_check_called = False

        async def custom_check():
            nonlocal custom_check_called
            custom_check_called = True
            return {"custom": "ok"}

        health_service.add_custom_check("custom_check", custom_check)

        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        assert custom_check_called
        assert response.custom_checks["custom_check"] == {"custom": "ok"}

    async def test_health_status_calculation_priority(self, health_service, mock_sdk_service):
        """Test that health status calculation follows correct priority."""
        # SDK unhealthy should override everything
        mock_sdk_service._health_manager.is_healthy.return_value = False
        response = await health_service.health_check(HealthCheckRequest())
        assert response.status == "unhealthy"

        # SDK healthy but message bus down
        mock_sdk_service._health_manager.is_healthy.return_value = True
        health_service._nats.is_connected.return_value = False
        response = await health_service.health_check(HealthCheckRequest())
        assert response.status == "unhealthy"

        # All infrastructure healthy but domain degraded
        health_service._nats.is_connected.return_value = True
        health_service._gateway_repo.list_active = AsyncMock(return_value=[])
        response = await health_service.health_check(HealthCheckRequest())
        assert response.status == "degraded"
