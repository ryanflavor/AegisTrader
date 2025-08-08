"""Comprehensive tests for SDK monitoring routes following TDD and hexagonal architecture.

These tests verify the API routes with proper mocking and request/response validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.application.sdk_monitoring_service import SDKMonitoringService
from app.infrastructure.api.sdk_monitoring_routes import (
    ConfigValidationResult,
    EventStreamMetrics,
    FailoverMetrics,
    LoadTestMetrics,
    TestScenarioRequest,
    TestScenarioResponse,
    get_event_stream_metrics,
    list_examples,
    list_test_scenarios,
    run_example,
    run_load_test,
    run_test_scenario,
    test_failover,
    validate_configuration,
)
from fastapi import HTTPException


class TestSDKMonitoringRoutes:
    """Test cases for SDK monitoring API routes."""

    @pytest.fixture
    def mock_service(self) -> Mock:
        """Create a mock SDK monitoring service."""
        service = Mock(spec=SDKMonitoringService)
        service.run_test_scenario = AsyncMock()
        service.list_test_scenarios = AsyncMock()
        service.get_event_stream_metrics = AsyncMock()
        service.run_load_test = AsyncMock()
        service.test_failover = AsyncMock()
        service.validate_configuration = AsyncMock()
        service.list_examples = AsyncMock()
        service.run_example = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_run_test_scenario_success(self, mock_service: Mock) -> None:
        """Test successful test scenario execution."""
        # Setup
        request = TestScenarioRequest(scenario="connectivity", timeout=30)
        mock_service.run_test_scenario.return_value = {
            "scenario": "connectivity",
            "success": True,
            "duration_ms": 150.5,
            "results": {"nats_connected": True, "services_found": 3},
            "errors": [],
        }

        # Act
        with patch(
            "app.infrastructure.api.sdk_monitoring_routes.get_sdk_monitoring_service",
            return_value=mock_service,
        ):
            result = await run_test_scenario(request, mock_service)

        # Assert
        assert isinstance(result, TestScenarioResponse)
        assert result.scenario == "connectivity"
        assert result.success is True
        assert result.duration_ms == 150.5
        assert result.results["nats_connected"] is True
        assert len(result.errors) == 0
        mock_service.run_test_scenario.assert_called_once_with(scenario="connectivity", timeout=30)

    @pytest.mark.asyncio
    async def test_run_test_scenario_failure(self, mock_service: Mock) -> None:
        """Test test scenario execution with failure."""
        # Setup
        request = TestScenarioRequest(scenario="failover", timeout=60)
        mock_service.run_test_scenario.return_value = {
            "scenario": "failover",
            "success": False,
            "duration_ms": 2500.0,
            "results": {},
            "errors": ["Service not responding", "Timeout exceeded"],
        }

        # Act
        result = await run_test_scenario(request, mock_service)

        # Assert
        assert result.scenario == "failover"
        assert result.success is False
        assert result.duration_ms == 2500.0
        assert len(result.errors) == 2
        assert "Service not responding" in result.errors

    @pytest.mark.asyncio
    async def test_run_test_scenario_exception(self, mock_service: Mock) -> None:
        """Test test scenario execution with exception."""
        # Setup
        request = TestScenarioRequest(scenario="error_test")
        mock_service.run_test_scenario.side_effect = Exception("Service error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await run_test_scenario(request, mock_service)

        assert exc_info.value.status_code == 500
        assert "Service error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_test_scenarios_success(self, mock_service: Mock) -> None:
        """Test listing test scenarios."""
        # Setup
        mock_service.list_test_scenarios.return_value = {
            "basic": ["connectivity", "service_discovery"],
            "advanced": ["failover", "load_test"],
            "patterns": ["single_active", "event_driven"],
        }

        # Act
        result = await list_test_scenarios(mock_service)

        # Assert
        assert "basic" in result
        assert "connectivity" in result["basic"]
        assert "advanced" in result
        assert "failover" in result["advanced"]
        mock_service.list_test_scenarios.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_test_scenarios_exception(self, mock_service: Mock) -> None:
        """Test listing test scenarios with exception."""
        # Setup
        mock_service.list_test_scenarios.side_effect = Exception("List failed")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await list_test_scenarios(mock_service)

        assert exc_info.value.status_code == 500
        assert "List failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_event_stream_metrics_success(self, mock_service: Mock) -> None:
        """Test getting event stream metrics."""
        # Setup
        mock_service.get_event_stream_metrics.return_value = {
            "total_events": 15000,
            "events_per_second": 312.5,
            "event_types": {
                "order.created": 5000,
                "order.processed": 4800,
                "payment.completed": 5200,
            },
            "subscription_modes": {"COMPETE": 3, "BROADCAST": 2},
            "errors": 5,
        }

        # Act
        result = await get_event_stream_metrics(mock_service)

        # Assert
        assert isinstance(result, EventStreamMetrics)
        assert result.total_events == 15000
        assert result.events_per_second == 312.5
        assert result.event_types["order.created"] == 5000
        assert result.subscription_modes["COMPETE"] == 3
        assert result.errors == 5
        mock_service.get_event_stream_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_stream_metrics_exception(self, mock_service: Mock) -> None:
        """Test getting event stream metrics with exception."""
        # Setup
        mock_service.get_event_stream_metrics.side_effect = Exception("Metrics unavailable")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_event_stream_metrics(mock_service)

        assert exc_info.value.status_code == 500
        assert "Metrics unavailable" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_run_load_test_success(self, mock_service: Mock) -> None:
        """Test running load test."""
        # Setup
        mock_service.run_load_test.return_value = {
            "requests_sent": 6000,
            "requests_per_second": 200,
            "latency_p50_ms": 15.2,
            "latency_p95_ms": 52.8,
            "latency_p99_ms": 142.3,
            "error_rate": 0.002,
            "duration_seconds": 30,
        }

        # Act
        result = await run_load_test(
            target_service="test-service",
            duration_seconds=30,
            requests_per_second=200,
            service=mock_service,
        )

        # Assert
        assert isinstance(result, LoadTestMetrics)
        assert result.requests_sent == 6000
        assert result.requests_per_second == 200
        assert result.latency_p50_ms == 15.2
        assert result.latency_p95_ms == 52.8
        assert result.latency_p99_ms == 142.3
        assert result.error_rate == 0.002
        assert result.duration_seconds == 30
        mock_service.run_load_test.assert_called_once_with(
            target_service="test-service", duration_seconds=30, requests_per_second=200
        )

    @pytest.mark.asyncio
    async def test_run_load_test_with_defaults(self, mock_service: Mock) -> None:
        """Test running load test with default parameters."""
        # Setup
        mock_service.run_load_test.return_value = {
            "requests_sent": 3000,
            "requests_per_second": 100,
            "latency_p50_ms": 12.5,
            "latency_p95_ms": 45.2,
            "latency_p99_ms": 125.8,
            "error_rate": 0.001,
            "duration_seconds": 30,
        }

        # Act
        result = await run_load_test(target_service="test-service", service=mock_service)

        # Assert
        assert result.requests_sent == 3000
        assert result.requests_per_second == 100
        mock_service.run_load_test.assert_called_once_with(
            target_service="test-service", duration_seconds=30, requests_per_second=100
        )

    @pytest.mark.asyncio
    async def test_run_load_test_exception(self, mock_service: Mock) -> None:
        """Test running load test with exception."""
        # Setup
        mock_service.run_load_test.side_effect = Exception("Load test failed")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await run_load_test(target_service="test-service", service=mock_service)

        assert exc_info.value.status_code == 500
        assert "Load test failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_test_failover_success(self, mock_service: Mock) -> None:
        """Test failover testing."""
        # Setup
        mock_service.test_failover.return_value = {
            "failover_time_ms": 1350.2,
            "leader_changes": 3,
            "failed_requests": 5,
            "successful_requests": 995,
            "availability_percentage": 99.5,
        }

        # Act
        result = await test_failover(target_service="critical-service", service=mock_service)

        # Assert
        assert isinstance(result, FailoverMetrics)
        assert result.failover_time_ms == 1350.2
        assert result.leader_changes == 3
        assert result.failed_requests == 5
        assert result.successful_requests == 995
        assert result.availability_percentage == 99.5
        mock_service.test_failover.assert_called_once_with("critical-service")

    @pytest.mark.asyncio
    async def test_test_failover_exception(self, mock_service: Mock) -> None:
        """Test failover testing with exception."""
        # Setup
        mock_service.test_failover.side_effect = Exception("Failover test error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await test_failover(target_service="test-service", service=mock_service)

        assert exc_info.value.status_code == 500
        assert "Failover test error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_configuration_success(self, mock_service: Mock) -> None:
        """Test configuration validation."""
        # Setup
        mock_service.validate_configuration.return_value = {
            "valid": True,
            "nats_connected": True,
            "k8s_accessible": True,
            "services_discovered": 5,
            "issues": [],
            "recommendations": [],
        }

        # Act
        result = await validate_configuration(mock_service)

        # Assert
        assert isinstance(result, ConfigValidationResult)
        assert result.valid is True
        assert result.nats_connected is True
        assert result.k8s_accessible is True
        assert result.services_discovered == 5
        assert len(result.issues) == 0
        assert len(result.recommendations) == 0
        mock_service.validate_configuration.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_configuration_with_issues(self, mock_service: Mock) -> None:
        """Test configuration validation with issues."""
        # Setup
        mock_service.validate_configuration.return_value = {
            "valid": False,
            "nats_connected": False,
            "k8s_accessible": True,
            "services_discovered": 0,
            "issues": ["NATS connection failed", "No services found"],
            "recommendations": ["Check NATS port forwarding", "Verify services are deployed"],
        }

        # Act
        result = await validate_configuration(mock_service)

        # Assert
        assert result.valid is False
        assert result.nats_connected is False
        assert result.services_discovered == 0
        assert len(result.issues) == 2
        assert "NATS connection failed" in result.issues
        assert len(result.recommendations) == 2
        assert "Check NATS port forwarding" in result.recommendations

    @pytest.mark.asyncio
    async def test_validate_configuration_exception(self, mock_service: Mock) -> None:
        """Test configuration validation with exception."""
        # Setup
        mock_service.validate_configuration.side_effect = Exception("Validation error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await validate_configuration(mock_service)

        assert exc_info.value.status_code == 500
        assert "Validation error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_examples_success(self, mock_service: Mock) -> None:
        """Test listing SDK examples."""
        # Setup
        mock_service.list_examples.return_value = {
            "quickstart": ["echo_service", "echo_client"],
            "patterns": ["single_active", "event_driven"],
            "tools": ["service_explorer", "event_monitor"],
        }

        # Act
        result = await list_examples(mock_service)

        # Assert
        assert "quickstart" in result
        assert "echo_service" in result["quickstart"]
        assert "patterns" in result
        assert "single_active" in result["patterns"]
        mock_service.list_examples.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_examples_exception(self, mock_service: Mock) -> None:
        """Test listing examples with exception."""
        # Setup
        mock_service.list_examples.side_effect = Exception("List examples failed")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await list_examples(mock_service)

        assert exc_info.value.status_code == 500
        assert "List examples failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_run_example_success(self, mock_service: Mock) -> None:
        """Test running an SDK example."""
        # Setup
        mock_service.run_example.return_value = {
            "example": "echo_service",
            "status": "completed",
            "output": "Example executed successfully",
            "duration_ms": 750.5,
            "logs": ["Starting echo_service...", "Service registered", "Example completed"],
        }

        # Act
        result = await run_example(example_name="echo_service", service=mock_service)

        # Assert
        assert result["example"] == "echo_service"
        assert result["status"] == "completed"
        assert "output" in result
        assert result["duration_ms"] == 750.5
        assert len(result["logs"]) == 3
        mock_service.run_example.assert_called_once_with("echo_service")

    @pytest.mark.asyncio
    async def test_run_example_exception(self, mock_service: Mock) -> None:
        """Test running example with exception."""
        # Setup
        mock_service.run_example.side_effect = Exception("Example execution failed")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await run_example(example_name="bad_example", service=mock_service)

        assert exc_info.value.status_code == 500
        assert "Example execution failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_route_parameter_validation(self, mock_service: Mock) -> None:
        """Test route parameter validation."""
        # Test with invalid timeout
        request = TestScenarioRequest(scenario="test", timeout=-1)
        mock_service.run_test_scenario.return_value = {
            "scenario": "test",
            "success": True,
            "duration_ms": 100,
            "results": {},
            "errors": [],
        }

        # Should still work but service should handle validation
        result = await run_test_scenario(request, mock_service)
        assert result.scenario == "test"
        mock_service.run_test_scenario.assert_called_with(scenario="test", timeout=-1)

    @pytest.mark.asyncio
    async def test_response_model_validation(self, mock_service: Mock) -> None:
        """Test response model validation."""
        # Setup - Missing required field
        mock_service.run_test_scenario.return_value = {
            "scenario": "test",
            "success": True,
            "duration_ms": 100,
            # Missing 'results' field
            "errors": [],
        }

        # Act
        result = await run_test_scenario(TestScenarioRequest(scenario="test"), mock_service)

        # Assert - Should handle missing field with default
        assert result.scenario == "test"
        assert result.results == {}  # Default value
