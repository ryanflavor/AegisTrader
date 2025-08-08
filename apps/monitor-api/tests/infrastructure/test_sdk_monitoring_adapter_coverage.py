"""Additional tests for SDKMonitoringAdapter to improve coverage.

These tests cover the remaining methods and edge cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from app.infrastructure.sdk_monitoring_adapter import SDKMonitoringAdapter


class TestSDKMonitoringAdapterCoverage:
    """Additional test cases for SDKMonitoringAdapter to improve coverage."""

    @pytest.fixture
    def adapter(self) -> SDKMonitoringAdapter:
        """Create an adapter instance with mocked KV store."""
        mock_kv_store = Mock()
        mock_kv_store.list_all = AsyncMock(return_value=["service-1", "service-2"])
        return SDKMonitoringAdapter(mock_kv_store)

    @pytest.mark.asyncio
    async def test_run_tests_connectivity_scenario(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running connectivity test scenario."""
        # Act
        result = await adapter.run_tests("connectivity")

        # Assert
        assert result["scenario"] == "connectivity"
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert len(result["tests"]) == 2
        assert result["tests"][0]["name"] == "nats_connection"
        assert result["tests"][0]["status"] == "passed"

    @pytest.mark.asyncio
    async def test_run_tests_service_discovery_scenario(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test running service discovery test scenario."""
        # Act
        result = await adapter.run_tests("service_discovery")

        # Assert
        assert result["scenario"] == "service_discovery"
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["tests"][1]["value"] == 2  # Two services from mock

    @pytest.mark.asyncio
    async def test_run_tests_unknown_scenario(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running unknown test scenario."""
        # Act
        result = await adapter.run_tests("unknown_scenario")

        # Assert
        assert result["scenario"] == "unknown_scenario"
        assert result["passed"] == 0
        assert result["failed"] == 1
        assert result["tests"][0]["error"] == "Unknown scenario"

    @pytest.mark.asyncio
    async def test_run_tests_with_tags(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running tests with tags."""
        # Act
        result = await adapter.run_tests("connectivity", tags=["basic", "infrastructure"])

        # Assert
        assert result["tags"] == ["basic", "infrastructure"]
        assert result["passed"] == 2

    @pytest.mark.asyncio
    async def test_get_test_scenarios(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting available test scenarios."""
        # Act
        scenarios = await adapter.get_test_scenarios()

        # Assert
        assert len(scenarios) == 5
        assert any(s["name"] == "connectivity" for s in scenarios)
        assert any(s["name"] == "failover" for s in scenarios)
        assert all("tags" in s for s in scenarios)
        assert all("duration_estimate_ms" in s for s in scenarios)

    @pytest.mark.asyncio
    async def test_get_event_metrics_with_topics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event metrics with specific topics."""
        # Act
        metrics = await adapter.get_event_metrics(topics=["orders", "payments"])

        # Assert
        assert metrics["topics"] == ["orders", "payments"]
        assert "orders" in metrics["metrics_by_topic"]
        assert "payments" in metrics["metrics_by_topic"]
        assert metrics["metrics_by_topic"]["orders"]["errors"] == 0

    @pytest.mark.asyncio
    async def test_get_event_metrics_without_topics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event metrics without specific topics."""
        # Act
        metrics = await adapter.get_event_metrics()

        # Assert
        assert metrics["topics"] == ["orders", "payments", "inventory"]
        assert len(metrics["metrics_by_topic"]) == 3

    @pytest.mark.asyncio
    async def test_get_load_metrics_for_service(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting load metrics for specific service."""
        # Act
        metrics = await adapter.get_load_metrics("test-service")

        # Assert
        assert metrics["service"] == "test-service"
        assert "requests_per_second" in metrics
        assert "latency_p50_ms" in metrics
        assert "error_rate" in metrics

    @pytest.mark.asyncio
    async def test_get_load_metrics_system_wide(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting system-wide load metrics."""
        # Act
        metrics = await adapter.get_load_metrics()

        # Assert
        assert "total_requests_per_second" in metrics
        assert "services" in metrics
        assert "average_latency_ms" in metrics

    @pytest.mark.asyncio
    async def test_get_failover_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting failover metrics for a service."""
        # Act
        metrics = await adapter.get_failover_metrics("test-service")

        # Assert
        assert metrics["service"] == "test-service"
        assert "failover_time_ms" in metrics
        assert "leader_changes" in metrics
        assert metrics["current_leader"] == "test-service-instance-1"

    @pytest.mark.asyncio
    async def test_validate_config_valid(self, adapter: SDKMonitoringAdapter) -> None:
        """Test validating a valid configuration."""
        # Arrange
        config = {
            "nats_url": "nats://localhost:4222",
            "service_name": "test-service",
        }

        # Act
        result = await adapter.validate_config(config)

        # Assert
        assert result["valid"] is True
        assert result["nats_connected"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_config_missing_nats_url(self, adapter: SDKMonitoringAdapter) -> None:
        """Test validating configuration with missing NATS URL."""
        # Arrange
        config = {"service_name": "test-service"}

        # Act
        result = await adapter.validate_config(config)

        # Assert
        assert result["valid"] is False
        assert "Missing NATS URL" in result["issues"]

    @pytest.mark.asyncio
    async def test_validate_config_connection_failure(self, adapter: SDKMonitoringAdapter) -> None:
        """Test validating configuration when connection fails."""
        # Arrange
        config = {
            "nats_url": "nats://localhost:4222",
            "service_name": "test-service",
        }
        adapter.kv_store.list_all = AsyncMock(side_effect=Exception("Connection failed"))

        # Act
        result = await adapter.validate_config(config)

        # Assert
        assert result["valid"] is False
        assert "Cannot connect to NATS" in result["issues"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_order_service(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test getting dependencies for order service."""
        # Act
        deps = await adapter.get_service_dependencies("order-service")

        # Assert
        assert deps["service"] == "order-service"
        assert "inventory-service" in deps["direct_dependencies"]
        assert "payment-service" in deps["direct_dependencies"]
        assert len(deps["dependency_graph"]) > 0

    @pytest.mark.asyncio
    async def test_get_service_dependencies_payment_service(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test getting dependencies for payment service."""
        # Act
        deps = await adapter.get_service_dependencies("payment-service")

        # Assert
        assert deps["service"] == "payment-service"
        assert "user-service" in deps["direct_dependencies"]
        assert "fraud-service" in deps["direct_dependencies"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_generic_service(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test getting dependencies for generic service."""
        # Act
        deps = await adapter.get_service_dependencies("generic-service")

        # Assert
        assert deps["service"] == "generic-service"
        assert "nats" in deps["direct_dependencies"]
        assert "kv-store" in deps["direct_dependencies"]

    @pytest.mark.asyncio
    async def test_run_test_scenario_connectivity(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running connectivity test scenario."""
        # Act
        result = await adapter.run_test_scenario("connectivity")

        # Assert
        assert result["scenario"] == "connectivity"
        assert result["success"] is True
        assert result["results"]["nats_connected"] is True
        assert result["results"]["services_found"] == 2

    @pytest.mark.asyncio
    async def test_run_test_scenario_rpc_call(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running RPC call test scenario."""
        # Act
        result = await adapter.run_test_scenario("rpc_call")

        # Assert
        assert result["scenario"] == "rpc_call"
        assert result["success"] is True
        assert result["results"]["rpc_available"] is True
        assert "latency_ms" in result["results"]

    @pytest.mark.asyncio
    async def test_run_test_scenario_event_stream(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running event stream test scenario."""
        # Act
        result = await adapter.run_test_scenario("event_stream")

        # Assert
        assert result["scenario"] == "event_stream"
        assert result["success"] is True
        assert result["results"]["events_received"] == 100
        assert result["results"]["subscription_active"] is True

    @pytest.mark.asyncio
    async def test_run_test_scenario_unknown(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running unknown test scenario."""
        # Act
        result = await adapter.run_test_scenario("unknown")

        # Assert
        assert result["scenario"] == "unknown"
        assert result["success"] is False
        assert "Unknown scenario: unknown" in result["errors"]

    @pytest.mark.asyncio
    async def test_run_test_scenario_with_exception(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running test scenario that raises exception."""
        # Arrange
        adapter.kv_store.list_all = AsyncMock(side_effect=Exception("Test error"))

        # Act
        result = await adapter.run_test_scenario("connectivity")

        # Assert
        assert result["success"] is False
        assert "Test error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_list_test_scenarios(self, adapter: SDKMonitoringAdapter) -> None:
        """Test listing available test scenarios."""
        # Act
        scenarios = await adapter.list_test_scenarios()

        # Assert
        assert "basic" in scenarios
        assert "advanced" in scenarios
        assert "patterns" in scenarios
        assert "connectivity" in scenarios["basic"]
        assert "failover" in scenarios["advanced"]

    @pytest.mark.asyncio
    async def test_get_event_stream_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event stream metrics."""
        # Act
        metrics = await adapter.get_event_stream_metrics()

        # Assert
        assert metrics["total_events"] == 10000
        assert metrics["events_per_second"] == 250.5
        assert "order.created" in metrics["event_types"]
        assert metrics["errors"] == 0

    @pytest.mark.asyncio
    async def test_run_load_test(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running a load test."""
        # Act
        result = await adapter.run_load_test(
            "test-service", duration_seconds=60, requests_per_second=200
        )

        # Assert
        assert result["requests_sent"] == 12000  # 60 * 200
        assert result["requests_per_second"] == 200
        assert "latency_p50_ms" in result
        assert result["error_rate"] == 0.001

    @pytest.mark.asyncio
    async def test_test_failover(self, adapter: SDKMonitoringAdapter) -> None:
        """Test failover testing."""
        # Act
        result = await adapter.test_failover("test-service")

        # Assert
        assert "failover_time_ms" in result
        assert result["leader_changes"] == 2
        assert result["availability_percentage"] == 99.7

    @pytest.mark.asyncio
    async def test_validate_configuration(self, adapter: SDKMonitoringAdapter) -> None:
        """Test configuration validation."""
        # Act
        result = await adapter.validate_configuration()

        # Assert
        assert result["valid"] is True
        assert result["nats_connected"] is True
        assert result["services_discovered"] == 2

    @pytest.mark.asyncio
    async def test_validate_configuration_with_failure(self, adapter: SDKMonitoringAdapter) -> None:
        """Test configuration validation with connection failure."""
        # Arrange
        adapter.kv_store.list_all = AsyncMock(side_effect=Exception("Connection error"))

        # Act
        result = await adapter.validate_configuration()

        # Assert
        assert result["valid"] is False
        assert result["nats_connected"] is False
        assert "Connection error" in result["issues"][0]
        assert "kubectl port-forward" in result["recommendations"][0]

    @pytest.mark.asyncio
    async def test_list_examples(self, adapter: SDKMonitoringAdapter) -> None:
        """Test listing SDK examples."""
        # Act
        examples = await adapter.list_examples()

        # Assert
        assert "quickstart" in examples
        assert "patterns" in examples
        assert "tools" in examples
        assert "echo_service" in examples["quickstart"]

    @pytest.mark.asyncio
    async def test_run_example(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running an SDK example."""
        # Act
        result = await adapter.run_example("echo_service")

        # Assert
        assert result["example"] == "echo_service"
        assert result["status"] == "completed"
        assert "output" in result
        assert len(result["logs"]) > 0
