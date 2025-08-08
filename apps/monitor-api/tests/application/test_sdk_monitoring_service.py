"""Tests for SDKMonitoringService following TDD and hexagonal architecture.

These tests verify the actual application service implementation with proper
mocking at architectural boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.sdk_monitoring_service import (
    SDKMonitoringService,
    TestScenario,
    TestSuiteReport,
)
from app.domain.exceptions import ServiceUnavailableException

if TYPE_CHECKING:
    pass


class TestSDKMonitoringService:
    """Test cases for SDKMonitoringService following hexagonal architecture."""

    @pytest.fixture
    def mock_adapter(self) -> Mock:
        """Create a mock SDK monitoring adapter."""
        mock = Mock()
        # Only mock methods that actually exist in SDKMonitoringPort
        mock.run_tests = AsyncMock()
        mock.get_test_scenarios = AsyncMock()
        mock.get_event_metrics = AsyncMock()
        mock.get_load_metrics = AsyncMock()
        mock.get_failover_metrics = AsyncMock()
        mock.validate_config = AsyncMock()
        mock.get_service_dependencies = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_adapter: Mock) -> SDKMonitoringService:
        """Create an SDK monitoring service instance."""
        return SDKMonitoringService(mock_adapter)

    @pytest.mark.asyncio
    async def test_run_test_scenario_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test running a test scenario successfully."""
        # Arrange
        mock_adapter.run_tests.return_value = {
            "total_tests": 10,
            "passed": 8,
            "failed": 1,
            "skipped": 1,
            "errors": 0,
            "duration": 5.5,
            "success_rate": 80.0,
            "tests": [
                {"name": "test_1", "status": "passed", "duration": 0.5},
                {"name": "test_2", "status": "failed", "duration": 0.3, "error": "AssertionError"},
            ],
        }

        # Act
        result = await service.run_test_scenario("integration", ["smoke"])

        # Assert
        assert isinstance(result, TestSuiteReport)
        assert result.scenario == "integration"
        assert result.total_tests == 10
        assert result.passed == 8
        assert result.failed == 1
        assert result.success_rate == 80.0
        assert len(result.results) == 2
        mock_adapter.run_tests.assert_called_once_with("integration", ["smoke"])

    @pytest.mark.asyncio
    async def test_run_test_scenario_failure(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test handling failure when running test scenario."""
        # Arrange
        mock_adapter.run_tests.side_effect = Exception("Test runner failed")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await service.run_test_scenario("integration")

        assert "Failed to run test scenario" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_test_scenarios_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting available test scenarios."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = [
            {
                "name": "unit",
                "description": "Unit tests",
                "tests": ["test_a", "test_b"],
                "tags": ["fast", "isolated"],
            },
            {
                "name": "integration",
                "description": "Integration tests",
                "tests": ["test_c"],
                "tags": ["slow"],
            },
        ]

        # Act
        result = await service.get_test_scenarios()

        # Assert
        assert len(result) == 2
        assert all(isinstance(s, TestScenario) for s in result)
        assert result[0].name == "unit"
        assert result[0].description == "Unit tests"
        assert result[0].tests == ["test_a", "test_b"]
        assert result[0].tags == ["fast", "isolated"]

    @pytest.mark.asyncio
    async def test_get_last_test_report(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting the last test report from cache."""
        # Arrange - first run a test to populate cache
        mock_adapter.run_tests.return_value = {
            "total_tests": 5,
            "passed": 5,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 2.0,
            "success_rate": 100.0,
            "tests": [],
        }
        await service.run_test_scenario("unit")

        # Act
        result = await service.get_last_test_report("unit")

        # Assert
        assert result is not None
        assert result.scenario == "unit"
        assert result.total_tests == 5
        assert result.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_get_last_test_report_not_found(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting last test report when not in cache."""
        # Act
        result = await service.get_last_test_report("non-existent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_monitor_event_stream_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test monitoring event stream metrics."""
        # Arrange
        mock_adapter.get_event_metrics.return_value = {
            "total_events": 1000,
            "events_per_second": 50.5,
            "events_by_type": {"created": 500, "updated": 300, "deleted": 200},
            "events_by_service": {"service-a": 600, "service-b": 400},
            "last_event_time": datetime.now(UTC).isoformat(),
        }

        # Act
        result = await service.monitor_event_stream(["topic1", "topic2"])

        # Assert
        assert result.total_events == 1000
        assert result.events_per_second == 50.5
        assert result.events_by_type["created"] == 500
        assert result.events_by_service["service-a"] == 600
        mock_adapter.get_event_metrics.assert_called_once_with(["topic1", "topic2"])

    @pytest.mark.asyncio
    async def test_monitor_event_stream_error_returns_cached(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test event stream monitoring returns cached metrics on error."""
        # Arrange
        mock_adapter.get_event_metrics.side_effect = Exception("Connection failed")

        # Act
        result = await service.monitor_event_stream()

        # Assert - should return default/cached metrics
        assert result.total_events == 0
        assert result.events_per_second == 0.0

    @pytest.mark.asyncio
    async def test_get_load_test_metrics_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting load test metrics."""
        # Arrange
        mock_adapter.get_load_metrics.return_value = {
            "rps": 1000.0,
            "mean_latency": 25.5,
            "p95_latency": 100.0,
            "p99_latency": 250.0,
            "error_rate": 0.1,
            "connections": 500,
        }

        # Act
        result = await service.get_load_test_metrics("test-service")

        # Assert
        assert result.requests_per_second == 1000.0
        assert result.mean_latency_ms == 25.5
        assert result.p95_latency_ms == 100.0
        assert result.p99_latency_ms == 250.0
        assert result.error_rate == 0.1
        assert result.active_connections == 500
        mock_adapter.get_load_metrics.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_failover_metrics_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting failover metrics."""
        # Arrange
        mock_adapter.get_failover_metrics.return_value = {
            "current_leader": "instance-1",
            "failover_count": 3,
            "mean_failover_time": 1500.0,
            "last_failover": datetime.now(UTC).isoformat(),
            "availability": 99.9,
        }

        # Act
        result = await service.get_failover_metrics("test-service")

        # Assert
        assert result.current_leader == "instance-1"
        assert result.failover_count == 3
        assert result.mean_failover_time_ms == 1500.0
        assert result.availability_percentage == 99.9
        mock_adapter.get_failover_metrics.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_validate_configuration_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test validating configuration successfully."""
        # Arrange
        config = {"service_name": "test", "port": 8080}
        mock_adapter.validate_config.return_value = {
            "valid": True,
            "errors": [],
            "warnings": ["Consider using environment variables"],
        }

        # Act
        result = await service.validate_configuration(config)

        # Assert
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 1
        mock_adapter.validate_config.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_validate_configuration_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test configuration validation on error."""
        # Arrange
        config = {"service_name": "test"}
        mock_adapter.validate_config.side_effect = Exception("Validation failed")

        # Act
        result = await service.validate_configuration(config)

        # Assert
        assert result["valid"] is False
        assert "Validation failed" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting service dependencies successfully."""
        # Arrange
        expected_deps = {
            "service_name": "test-service",
            "dependencies": ["database", "cache", "message-queue"],
            "dependents": ["api-gateway", "worker-service"],
        }
        mock_adapter.get_service_dependencies.return_value = expected_deps

        # Act
        result = await service.get_service_dependencies("test-service")

        # Assert
        assert result == expected_deps
        mock_adapter.get_service_dependencies.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_service_health_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting service health successfully."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = {
            "status": "healthy",
            "instance_count": 3,
        }

        # Act
        result = await service.get_service_health("test-service")

        # Assert
        assert result is not None
        assert result["service_name"] == "test-service"
        assert result["status"] == "healthy"
        assert result["instance_count"] == 3
        mock_adapter.get_service_dependencies.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_service_health_not_found(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting service health when service not found."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = None

        # Act
        result = await service.get_service_health("non-existent-service")

        # Assert
        assert result is None
        mock_adapter.get_service_dependencies.assert_called_once_with("non-existent-service")

    @pytest.mark.asyncio
    async def test_get_service_health_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting service health when error occurs."""
        # Arrange
        mock_adapter.get_service_dependencies.side_effect = Exception("Adapter error")

        # Act
        result = await service.get_service_health("test-service")

        # Assert - should return None on error
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_services_health_success(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health for all services successfully."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = [
            {"name": "service-a", "description": "Service A"},
            {"name": "service-b", "description": "Service B"},
        ]

        # Act
        result = await service.get_all_services_health()

        # Assert
        assert len(result) == 2
        assert result[0]["service_name"] == "service-a"
        assert result[0]["status"] == "healthy"
        assert result[1]["service_name"] == "service-b"
        assert result[1]["status"] == "healthy"
        mock_adapter.get_test_scenarios.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_services_health_empty(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health when no services exist."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = []

        # Act
        result = await service.get_all_services_health()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_services_health_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health for all services on error."""
        # Arrange
        mock_adapter.get_test_scenarios.side_effect = Exception("Connection error")

        # Act
        result = await service.get_all_services_health()

        # Assert - should return empty list on error
        assert result == []

    @pytest.mark.asyncio
    async def test_service_follows_hexagonal_architecture(
        self, service: SDKMonitoringService
    ) -> None:
        """Test that the service follows hexagonal architecture principles."""
        # The service should only depend on the port interface, not concrete implementations
        assert hasattr(service, "_monitoring_port")
        # The service should not have any infrastructure dependencies
        import inspect

        source = inspect.getsource(SDKMonitoringService)
        assert "nats" not in source.lower()
        assert "redis" not in source.lower()
        assert "database" not in source.lower()
