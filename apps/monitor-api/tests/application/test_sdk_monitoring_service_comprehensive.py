"""Comprehensive tests for SDKMonitoringService to achieve 90%+ coverage.

These tests cover all edge cases, error scenarios, and untested code paths
following TDD and hexagonal architecture principles.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.sdk_monitoring_service import (
    EventStreamMetrics,
    FailoverMetrics,
    LoadTestMetrics,
    SDKMonitoringService,
    TestResult,
    TestScenario,
    TestSuiteReport,
)
from app.domain.exceptions import ServiceUnavailableException

if TYPE_CHECKING:
    pass


class TestSDKMonitoringServiceComprehensive:
    """Comprehensive test cases for SDKMonitoringService achieving full coverage."""

    @pytest.fixture
    def mock_adapter(self) -> Mock:
        """Create a mock SDK monitoring adapter with all methods."""
        mock = Mock()
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

    # Test initialization and internal state
    def test_service_initialization(self, service: SDKMonitoringService) -> None:
        """Test service initialization with proper defaults."""
        assert service._test_results_cache == {}
        assert isinstance(service._event_metrics, EventStreamMetrics)
        assert service._event_metrics.total_events == 0
        assert isinstance(service._load_metrics, LoadTestMetrics)
        assert service._load_metrics.requests_per_second == 0
        assert isinstance(service._failover_metrics, FailoverMetrics)
        assert service._failover_metrics.current_leader is None

    # Test run_test_scenario with various edge cases
    @pytest.mark.asyncio
    async def test_run_test_scenario_empty_results(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test running test scenario with empty results."""
        # Arrange
        mock_adapter.run_tests.return_value = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
            "success_rate": 0.0,
            "tests": [],
        }

        # Act
        result = await service.run_test_scenario("empty-test")

        # Assert
        assert result.scenario == "empty-test"
        assert result.total_tests == 0
        assert len(result.results) == 0
        assert "empty-test" in service._test_results_cache

    @pytest.mark.asyncio
    async def test_run_test_scenario_missing_fields(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test run_test_scenario with missing fields in response."""
        # Arrange - Missing some fields that should use defaults
        mock_adapter.run_tests.return_value = {
            "total_tests": 5,
            # Missing passed, failed, skipped, errors
            "tests": [
                {"name": "test_1", "status": "passed", "duration": 0.5},
                # Missing message and error fields
            ],
        }

        # Act
        result = await service.run_test_scenario("partial", tags=None)

        # Assert
        assert result.total_tests == 5
        assert result.passed == 0  # Should use default
        assert result.failed == 0
        assert len(result.results) == 1
        assert result.results[0].message is None
        assert result.results[0].error is None

    @pytest.mark.asyncio
    async def test_run_test_scenario_network_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test run_test_scenario with network error."""
        # Arrange
        mock_adapter.run_tests.side_effect = ConnectionError("Network unreachable")

        # Act & Assert
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await service.run_test_scenario("network-test", tags=["integration"])

        assert "Failed to run test scenario" in str(exc_info.value)
        assert "Network unreachable" in str(exc_info.value)

    # Test get_test_scenarios edge cases
    @pytest.mark.asyncio
    async def test_get_test_scenarios_empty(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting test scenarios when none exist."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = []

        # Act
        result = await service.get_test_scenarios()

        # Assert
        assert result == []
        mock_adapter.get_test_scenarios.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_test_scenarios_partial_data(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting test scenarios with missing optional fields."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = [
            {
                "name": "minimal",
                "description": "Minimal test",
                # Missing tests and tags - should use defaults
            },
            {
                "name": "partial",
                "description": "Partial test",
                "tests": ["test_a"],
                # Missing tags
            },
        ]

        # Act
        result = await service.get_test_scenarios()

        # Assert
        assert len(result) == 2
        assert result[0].tests == []
        assert result[0].tags == []
        assert result[1].tests == ["test_a"]
        assert result[1].tags == []

    # Test get_last_test_report cache behavior
    @pytest.mark.asyncio
    async def test_get_last_test_report_multiple_scenarios(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test cache isolation between different scenarios."""
        # Arrange - Run multiple scenarios to populate cache
        mock_adapter.run_tests.return_value = {
            "total_tests": 1,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 1.0,
            "success_rate": 100.0,
            "tests": [],
        }
        await service.run_test_scenario("scenario1")

        mock_adapter.run_tests.return_value["total_tests"] = 2
        await service.run_test_scenario("scenario2")

        # Act
        result1 = await service.get_last_test_report("scenario1")
        result2 = await service.get_last_test_report("scenario2")
        result3 = await service.get_last_test_report("scenario3")

        # Assert
        assert result1 is not None and result1.total_tests == 1
        assert result2 is not None and result2.total_tests == 2
        assert result3 is None

    # Test monitor_event_stream edge cases
    @pytest.mark.asyncio
    async def test_monitor_event_stream_no_last_event_time(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test event stream monitoring without last_event_time."""
        # Arrange
        mock_adapter.get_event_metrics.return_value = {
            "total_events": 500,
            "events_per_second": 25.0,
            "events_by_type": {"created": 250, "updated": 250},
            "events_by_service": {"service-x": 500},
            # No last_event_time field
        }

        # Act
        result = await service.monitor_event_stream(topics=None)

        # Assert
        assert result.total_events == 500
        assert result.last_event_time is None

    @pytest.mark.asyncio
    async def test_monitor_event_stream_malformed_timestamp(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test event stream with malformed timestamp returns cached."""
        # Arrange
        mock_adapter.get_event_metrics.return_value = {
            "total_events": 100,
            "events_per_second": 10.0,
            "last_event_time": "not-a-valid-timestamp",
        }

        # Act - Should handle error and return cached metrics
        result = await service.monitor_event_stream(["topic1"])

        # Assert - Should return default cached metrics due to error
        assert result.total_events == 0  # Default cached value
        assert result.events_per_second == 0.0

    @pytest.mark.asyncio
    async def test_monitor_event_stream_timeout_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test event stream monitoring with timeout returns cached."""
        # Arrange
        mock_adapter.get_event_metrics.side_effect = TimeoutError("Request timed out")

        # Act
        result = await service.monitor_event_stream(["slow-topic"])

        # Assert - Should return cached (default) metrics
        assert result.total_events == 0
        assert result.events_per_second == 0.0
        assert result.events_by_type == {}

    # Test get_load_test_metrics edge cases
    @pytest.mark.asyncio
    async def test_get_load_test_metrics_no_service(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test load test metrics without specifying service."""
        # Arrange
        mock_adapter.get_load_metrics.return_value = {
            "rps": 500.0,
            "mean_latency": 15.0,
            "p95_latency": 50.0,
            "p99_latency": 100.0,
            "error_rate": 0.05,
            "connections": 250,
        }

        # Act
        result = await service.get_load_test_metrics(service_name=None)

        # Assert
        assert result.requests_per_second == 500.0
        assert result.error_rate == 0.05
        mock_adapter.get_load_metrics.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_get_load_test_metrics_partial_data(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test load test metrics with missing fields."""
        # Arrange - Missing some metrics
        mock_adapter.get_load_metrics.return_value = {
            "rps": 100.0,
            # Missing other fields
        }

        # Act
        result = await service.get_load_test_metrics("test-service")

        # Assert - Should use defaults for missing fields
        assert result.requests_per_second == 100.0
        assert result.mean_latency_ms == 0.0
        assert result.p95_latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_get_load_test_metrics_exception_returns_cached(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test load test metrics returns cached on exception."""
        # Arrange - First populate cache
        mock_adapter.get_load_metrics.return_value = {
            "rps": 1000.0,
            "mean_latency": 20.0,
            "p95_latency": 80.0,
            "p99_latency": 150.0,
            "error_rate": 0.01,
            "connections": 500,
        }
        await service.get_load_test_metrics("cached-service")

        # Now cause an error
        mock_adapter.get_load_metrics.side_effect = RuntimeError("Metrics unavailable")

        # Act
        result = await service.get_load_test_metrics("error-service")

        # Assert - Should return cached metrics
        assert result.requests_per_second == 1000.0
        assert result.mean_latency_ms == 20.0

    # Test get_failover_metrics edge cases
    @pytest.mark.asyncio
    async def test_get_failover_metrics_no_failover(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test failover metrics when no failovers occurred."""
        # Arrange
        mock_adapter.get_failover_metrics.return_value = {
            "current_leader": "instance-primary",
            "failover_count": 0,
            "mean_failover_time": 0.0,
            # No last_failover since none occurred
            "availability": 100.0,
        }

        # Act
        result = await service.get_failover_metrics("stable-service")

        # Assert
        assert result.current_leader == "instance-primary"
        assert result.failover_count == 0
        assert result.last_failover is None
        assert result.availability_percentage == 100.0

    @pytest.mark.asyncio
    async def test_get_failover_metrics_invalid_timestamp(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test failover metrics with invalid timestamp returns cached."""
        # Arrange
        mock_adapter.get_failover_metrics.return_value = {
            "current_leader": "leader-1",
            "failover_count": 5,
            "last_failover": "invalid-timestamp",
        }

        # Act - Should handle error and return cached
        result = await service.get_failover_metrics("error-service")

        # Assert - Should return default cached metrics
        assert result.current_leader is None
        assert result.failover_count == 0

    @pytest.mark.asyncio
    async def test_get_failover_metrics_missing_fields(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test failover metrics with missing fields uses defaults."""
        # Arrange
        mock_adapter.get_failover_metrics.return_value = {
            "current_leader": "leader-2",
            # Missing other fields
        }

        # Act
        result = await service.get_failover_metrics("partial-service")

        # Assert
        assert result.current_leader == "leader-2"
        assert result.failover_count == 0  # Default
        assert result.mean_failover_time_ms == 0.0  # Default
        assert result.availability_percentage == 100.0  # Default

    @pytest.mark.asyncio
    async def test_get_failover_metrics_exception_returns_cached(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test failover metrics returns cached on exception."""
        # Arrange - First set some cached values
        mock_adapter.get_failover_metrics.return_value = {
            "current_leader": "cached-leader",
            "failover_count": 3,
            "mean_failover_time": 2000.0,
            "availability": 99.5,
        }
        await service.get_failover_metrics("cached-service")

        # Now cause an exception
        mock_adapter.get_failover_metrics.side_effect = Exception("Connection lost")

        # Act
        result = await service.get_failover_metrics("error-service")

        # Assert - Should return cached metrics
        assert result.current_leader == "cached-leader"
        assert result.failover_count == 3

    # Test validate_configuration
    @pytest.mark.asyncio
    async def test_validate_configuration_empty_config(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test validating empty configuration."""
        # Arrange
        mock_adapter.validate_config.return_value = {
            "valid": False,
            "errors": ["Configuration is empty"],
            "warnings": [],
        }

        # Act
        result = await service.validate_configuration({})

        # Assert
        assert result["valid"] is False
        assert "Configuration is empty" in result["errors"]

    @pytest.mark.asyncio
    async def test_validate_configuration_complex_config(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test validating complex nested configuration."""
        # Arrange
        complex_config = {
            "service": {
                "name": "complex-service",
                "port": 8080,
                "features": ["auth", "logging", "metrics"],
            },
            "database": {
                "host": "localhost",
                "port": 5432,
            },
        }
        mock_adapter.validate_config.return_value = {
            "valid": True,
            "errors": [],
            "warnings": ["Consider using connection pooling"],
        }

        # Act
        result = await service.validate_configuration(complex_config)

        # Assert
        assert result["valid"] is True
        assert len(result["warnings"]) == 1
        mock_adapter.validate_config.assert_called_once_with(complex_config)

    @pytest.mark.asyncio
    async def test_validate_configuration_network_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test configuration validation with network error."""
        # Arrange
        mock_adapter.validate_config.side_effect = ConnectionError("Service unavailable")

        # Act
        result = await service.validate_configuration({"test": "config"})

        # Assert
        assert result["valid"] is False
        assert "Service unavailable" in result["errors"][0]
        assert result["warnings"] == []

    # Test get_service_dependencies
    @pytest.mark.asyncio
    async def test_get_service_dependencies_circular(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting service dependencies with circular dependencies."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = {
            "service_name": "service-a",
            "dependencies": ["service-b", "service-c"],
            "dependents": ["service-c"],  # Circular: c depends on a, a depends on c
            "status": "warning",
            "message": "Circular dependency detected",
        }

        # Act
        result = await service.get_service_dependencies("service-a")

        # Assert
        assert result["service_name"] == "service-a"
        assert "service-c" in result["dependencies"]
        assert "service-c" in result["dependents"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_no_deps(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting dependencies for standalone service."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = {
            "service_name": "standalone",
            "dependencies": [],
            "dependents": [],
        }

        # Act
        result = await service.get_service_dependencies("standalone")

        # Assert
        assert result["dependencies"] == []
        assert result["dependents"] == []

    # Test get_service_health edge cases
    @pytest.mark.asyncio
    async def test_get_service_health_unhealthy(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health for unhealthy service."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = {
            "status": "unhealthy",
            "instance_count": 0,
            "error": "All instances failed health check",
        }

        # Act
        result = await service.get_service_health("unhealthy-service")

        # Assert
        assert result is not None
        assert result["status"] == "unhealthy"
        assert result["instance_count"] == 0

    @pytest.mark.asyncio
    async def test_get_service_health_empty_response(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health with empty response from dependencies."""
        # Arrange
        mock_adapter.get_service_dependencies.return_value = {}

        # Act
        result = await service.get_service_health("empty-service")

        # Assert
        assert result is not None
        assert result["service_name"] == "empty-service"
        assert result["status"] == "unknown"  # Default when not provided
        assert result["instance_count"] == 0  # Default when not provided

    @pytest.mark.asyncio
    async def test_get_service_health_timeout(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health with timeout returns None."""
        # Arrange
        mock_adapter.get_service_dependencies.side_effect = TimeoutError("Request timed out")

        # Act
        result = await service.get_service_health("timeout-service")

        # Assert
        assert result is None

    # Test get_all_services_health edge cases
    @pytest.mark.asyncio
    async def test_get_all_services_health_mixed_statuses(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting health for services with mixed statuses."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = [
            {"name": "healthy-service"},
            {"name": "degraded-service"},
            {"name": "unhealthy-service"},
        ]

        # Act
        result = await service.get_all_services_health()

        # Assert
        assert len(result) == 3
        # All return "healthy" as default in current implementation
        for health in result:
            assert health["status"] == "healthy"
            assert health["instance_count"] == 1

    @pytest.mark.asyncio
    async def test_get_all_services_health_partial_data(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting all services health with incomplete scenario data."""
        # Arrange
        mock_adapter.get_test_scenarios.return_value = [
            {"name": "service-1", "description": "Service 1"},
            {"description": "Service without name"},  # Missing name
            {},  # Empty scenario
        ]

        # Act
        result = await service.get_all_services_health()

        # Assert
        assert len(result) == 3
        assert result[0]["service_name"] == "service-1"
        assert result[1]["service_name"] == "unknown"  # Default for missing name
        assert result[2]["service_name"] == "unknown"

    @pytest.mark.asyncio
    async def test_get_all_services_health_network_error(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test getting all services health with network error."""
        # Arrange
        mock_adapter.get_test_scenarios.side_effect = ConnectionError("Network down")

        # Act
        result = await service.get_all_services_health()

        # Assert
        assert result == []

    # Test model classes and their validators
    def test_test_scenario_model_validation(self) -> None:
        """Test TestScenario model validation."""
        # Valid scenario
        scenario = TestScenario(
            name="test",
            description="Test scenario",
            tests=["test1", "test2"],
            tags=["unit", "fast"],
        )
        assert scenario.name == "test"

        # Empty lists should work
        minimal = TestScenario(name="minimal", description="Minimal")
        assert minimal.tests == []
        assert minimal.tags == []

    def test_test_result_model_validation(self) -> None:
        """Test TestResult model validation."""
        # Full result
        result = TestResult(
            name="test_example",
            status="passed",
            duration=1.5,
            message="Test passed successfully",
            error=None,
        )
        assert result.status == "passed"

        # Minimal result
        minimal = TestResult(name="test", status="skipped", duration=0.0)
        assert minimal.message is None
        assert minimal.error is None

    def test_test_suite_report_model(self) -> None:
        """Test TestSuiteReport model."""
        # Create report with results
        report = TestSuiteReport(
            scenario="integration",
            total_tests=10,
            passed=7,
            failed=2,
            skipped=1,
            errors=0,
            duration=15.5,
            success_rate=70.0,
            results=[
                TestResult(name="test1", status="passed", duration=1.0),
                TestResult(name="test2", status="failed", duration=0.5, error="AssertionError"),
            ],
        )
        assert report.total_tests == 10
        assert len(report.results) == 2
        assert report.timestamp is not None

    def test_event_stream_metrics_model(self) -> None:
        """Test EventStreamMetrics model."""
        metrics = EventStreamMetrics(
            total_events=1000,
            events_per_second=50.0,
            events_by_type={"create": 400, "update": 600},
            events_by_service={"service-a": 700, "service-b": 300},
            last_event_time=datetime.now(UTC),
        )
        assert metrics.total_events == 1000
        assert metrics.events_by_type["create"] == 400

    def test_load_test_metrics_model(self) -> None:
        """Test LoadTestMetrics model."""
        metrics = LoadTestMetrics(
            requests_per_second=1000.0,
            mean_latency_ms=25.0,
            p95_latency_ms=100.0,
            p99_latency_ms=200.0,
            error_rate=0.01,
            active_connections=500,
        )
        assert metrics.requests_per_second == 1000.0
        assert metrics.error_rate == 0.01

    def test_failover_metrics_model(self) -> None:
        """Test FailoverMetrics model."""
        metrics = FailoverMetrics(
            current_leader="instance-1",
            failover_count=2,
            mean_failover_time_ms=1500.0,
            last_failover=datetime.now(UTC),
            availability_percentage=99.95,
        )
        assert metrics.current_leader == "instance-1"
        assert metrics.failover_count == 2

    # Test concurrent operations
    @pytest.mark.asyncio
    async def test_concurrent_test_scenarios(
        self, service: SDKMonitoringService, mock_adapter: Mock
    ) -> None:
        """Test running multiple test scenarios concurrently."""
        import asyncio

        # Arrange
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

        # Act - Run multiple scenarios concurrently
        tasks = [service.run_test_scenario(f"scenario-{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        assert all(r.total_tests == 5 for r in results)
        assert len(service._test_results_cache) == 5

    @pytest.mark.asyncio
    async def test_service_follows_hexagonal_principles(
        self, service: SDKMonitoringService
    ) -> None:
        """Verify the service adheres to hexagonal architecture."""
        # The service should only depend on the port interface
        assert hasattr(service, "_monitoring_port")

        # Check that service doesn't have infrastructure concerns
        import inspect

        source = inspect.getsource(SDKMonitoringService)

        # Should not contain infrastructure-specific imports or code
        assert "import nats" not in source
        assert "import redis" not in source
        assert "import psycopg" not in source
        assert "import mysql" not in source

        # Should use port abstraction
        assert "monitoring_port" in source

        # Should handle business logic
        assert "TestSuiteReport" in source
        assert "EventStreamMetrics" in source
