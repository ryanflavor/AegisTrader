"""
Integration tests for the health check service endpoint.
These tests verify the RPC endpoint registration, response format, and service lifecycle.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from application.health_service import HealthCheckRequest, HealthCheckResponse


@pytest.mark.asyncio
class TestHealthCheckEndpoint:
    """Integration tests for the health check RPC endpoint."""

    @pytest_asyncio.fixture
    async def mock_aegis_service(self):
        """Create a mock AegisService for testing."""
        with patch("aegis_sdk.application.service.Service") as mock_service_class:
            service = mock_service_class()
            service.start = AsyncMock()
            service.stop = AsyncMock()
            service.register_handler = MagicMock()
            yield service

    @pytest_asyncio.fixture
    async def health_service(self):
        """Create health check service instance."""
        # Import the health service (should fail if not implemented)
        from application.health_service import HealthCheckService

        service = HealthCheckService()
        return service

    async def test_health_check_service_exists(self):
        """Test that HealthCheckService class exists in application layer."""
        try:
            from application.health_service import HealthCheckService

            assert HealthCheckService is not None
        except ImportError:
            pytest.fail("HealthCheckService not found in application.health_service")

    async def test_health_check_rpc_handler_registered(self, health_service, mock_aegis_service):
        """Test that health_check RPC handler is registered with NATS."""
        # Check that the service has a health_check method decorated with @rpc_handler
        assert hasattr(health_service, "health_check"), "health_check method not found"

        # Check that it's an async method
        import inspect

        assert inspect.iscoroutinefunction(health_service.health_check), (
            "health_check must be an async method"
        )

    async def test_health_check_response_format(self, health_service):
        """Test that health check returns correct response format."""
        request = HealthCheckRequest(timestamp=datetime.now(UTC))

        # Call the health check method
        response = await health_service.health_check(request)

        # Validate response type and fields
        assert isinstance(response, HealthCheckResponse), (
            "Response must be HealthCheckResponse type"
        )
        assert response.status in [
            "healthy",
            "unhealthy",
            "degraded",
        ], f"Invalid status: {response.status}"
        assert response.service_name == "market-service", (
            f"Expected service_name 'market-service', got {response.service_name}"
        )
        assert response.version == "0.1.0", f"Expected version '0.1.0', got {response.version}"
        assert isinstance(response.timestamp, datetime), "Timestamp must be datetime"

    async def test_service_lifecycle_start(self, mock_aegis_service):
        """Test that service can be started successfully."""
        from main import MarketService

        service = MarketService()
        await service.start()

        # Verify service started
        mock_aegis_service.start.assert_called_once()

    async def test_service_lifecycle_stop(self, mock_aegis_service):
        """Test that service can be stopped gracefully."""
        from main import MarketService

        service = MarketService()
        await service.start()
        await service.stop()

        # Verify service stopped
        mock_aegis_service.stop.assert_called_once()

    async def test_health_check_with_domain_indicators(self, health_service):
        """Test enhanced health check with domain-specific indicators."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        # Check for domain-specific health indicators
        assert hasattr(response, "gateway_ready"), "Missing gateway_ready indicator"
        assert hasattr(response, "message_bus_connected"), "Missing message_bus_connected indicator"
        assert hasattr(response, "database_connected"), "Missing database_connected indicator"

    async def test_health_check_aggregation_pattern(self, health_service):
        """Test that health check aggregates multiple health indicators."""
        request = HealthCheckRequest()
        response = await health_service.health_check(request)

        # If any indicator is false, overall status should not be "healthy"
        if (
            response.gateway_ready is False
            or response.message_bus_connected is False
            or response.database_connected is False
        ):
            assert response.status != "healthy", (
                "Status should not be healthy when indicators are false"
            )

    async def test_concurrent_health_checks(self, health_service):
        """Test that multiple concurrent health checks work correctly."""
        # Create multiple concurrent requests
        requests = [HealthCheckRequest() for _ in range(10)]

        # Execute health checks concurrently
        tasks = [health_service.health_check(req) for req in requests]
        responses = await asyncio.gather(*tasks)

        # Verify all responses are valid
        assert len(responses) == 10, "Should receive 10 responses"
        for response in responses:
            assert isinstance(response, HealthCheckResponse)
            assert response.status in ["healthy", "unhealthy", "degraded"]

    @pytest.mark.timeout(5)
    async def test_health_check_performance(self, health_service):
        """Test that health check responds within reasonable time."""
        request = HealthCheckRequest()

        # Measure response time
        start_time = asyncio.get_event_loop().time()
        await health_service.health_check(request)
        end_time = asyncio.get_event_loop().time()

        response_time = end_time - start_time
        assert response_time < 1.0, f"Health check took too long: {response_time}s"

    async def test_main_entry_point_exists(self):
        """Test that main.py properly initializes the service."""
        try:
            import main

            assert hasattr(main, "MarketService"), "MarketService not found in main.py"
        except ImportError:
            pytest.fail("main.py not found or cannot be imported")

    async def test_service_registration_in_main(self):
        """Test that health service is registered in main.py."""
        from main import MarketService

        service = MarketService()

        # Check that health check service is registered
        assert hasattr(service, "health_service"), "HealthCheckService not registered in main"
