"""Comprehensive tests for SDKMonitoringAdapter following TDD and hexagonal architecture.

These tests verify the infrastructure adapter implementation with proper
mocking at architectural boundaries and complete code coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from app.domain.models import ServiceDefinition
from app.infrastructure.sdk_monitoring_adapter import SDKMonitoringAdapter


class TestSDKMonitoringAdapter:
    """Test cases for SDKMonitoringAdapter following hexagonal architecture."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        mock = Mock()
        # Create mock service definitions
        now = datetime.now(UTC)
        service1 = ServiceDefinition(
            service_name="service-one",
            owner="test-team",
            description="Test service 1",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        service2 = ServiceDefinition(
            service_name="service-two",
            owner="test-team",
            description="Test service 2",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock.list_all = AsyncMock(return_value=[service1, service2])
        return mock

    @pytest.fixture
    def adapter(self, mock_kv_store: Mock) -> SDKMonitoringAdapter:
        """Create an adapter instance with mocked KV store."""
        return SDKMonitoringAdapter(mock_kv_store)

    @pytest.mark.asyncio
    async def test_run_tests_connectivity(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running connectivity test scenario."""
        result = await adapter.run_tests("connectivity")

        assert result["scenario"] == "connectivity"
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert len(result["tests"]) == 2

    @pytest.mark.asyncio
    async def test_run_tests_service_discovery(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running service discovery test scenario."""
        result = await adapter.run_tests("service_discovery")

        assert result["scenario"] == "service_discovery"
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["tests"][1]["value"] == 2  # Two services found

    @pytest.mark.asyncio
    async def test_get_test_scenarios(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting available test scenarios."""
        scenarios = await adapter.get_test_scenarios()

        assert len(scenarios) == 5
        assert any(s["name"] == "connectivity" for s in scenarios)
        assert any(s["name"] == "failover" for s in scenarios)

    @pytest.mark.asyncio
    async def test_get_event_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event metrics."""
        metrics = await adapter.get_event_metrics(["orders", "payments"])

        assert metrics["topics"] == ["orders", "payments"]
        assert "orders" in metrics["metrics_by_topic"]
        assert "payments" in metrics["metrics_by_topic"]

    @pytest.mark.asyncio
    async def test_get_load_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting load metrics for a service."""
        metrics = await adapter.get_load_metrics("test-service")

        assert metrics["service"] == "test-service"
        assert "requests_per_second" in metrics
        assert "latency_p50_ms" in metrics

    @pytest.mark.asyncio
    async def test_get_failover_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting failover metrics."""
        metrics = await adapter.get_failover_metrics("test-service")

        assert metrics["service"] == "test-service"
        assert "failover_time_ms" in metrics
        assert "leader_changes" in metrics

    @pytest.mark.asyncio
    async def test_validate_config(self, adapter: SDKMonitoringAdapter) -> None:
        """Test config validation."""
        config = {
            "nats_url": "nats://localhost:4222",
            "service_name": "test-service",
        }

        result = await adapter.validate_config(config)

        assert result["valid"] is True
        assert result["nats_connected"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_config_missing_fields(self, adapter: SDKMonitoringAdapter) -> None:
        """Test config validation with missing fields."""
        config = {}

        result = await adapter.validate_config(config)

        assert result["valid"] is False
        assert "Missing NATS URL" in result["issues"]
        assert "Missing service name" in result["issues"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting service dependencies."""
        deps = await adapter.get_service_dependencies("order-service")

        assert deps["service"] == "order-service"
        assert "inventory-service" in deps["direct_dependencies"]
        assert "payment-service" in deps["direct_dependencies"]

    @pytest.mark.asyncio
    async def test_run_test_scenario(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running a test scenario."""
        result = await adapter.run_test_scenario("connectivity")

        assert result["scenario"] == "connectivity"
        assert result["success"] is True
        assert result["results"]["nats_connected"] is True

    @pytest.mark.asyncio
    async def test_list_test_scenarios(self, adapter: SDKMonitoringAdapter) -> None:
        """Test listing test scenarios."""
        scenarios = await adapter.list_test_scenarios()

        assert "basic" in scenarios
        assert "advanced" in scenarios
        assert "patterns" in scenarios

    @pytest.mark.asyncio
    async def test_get_event_stream_metrics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event stream metrics."""
        metrics = await adapter.get_event_stream_metrics()

        assert metrics["total_events"] == 10000
        assert metrics["events_per_second"] == 250.5
        assert "order.created" in metrics["event_types"]

    @pytest.mark.asyncio
    async def test_run_load_test(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running a load test."""
        result = await adapter.run_load_test("test-service", 30, 100)

        assert result["requests_sent"] == 3000
        assert result["requests_per_second"] == 100
        assert "latency_p50_ms" in result

    @pytest.mark.asyncio
    async def test_test_failover(self, adapter: SDKMonitoringAdapter) -> None:
        """Test failover testing."""
        result = await adapter.test_failover("test-service")

        assert "failover_time_ms" in result
        assert result["leader_changes"] == 2
        assert result["availability_percentage"] == 99.7

    @pytest.mark.asyncio
    async def test_validate_configuration(self, adapter: SDKMonitoringAdapter) -> None:
        """Test configuration validation."""
        result = await adapter.validate_configuration()

        assert result["valid"] is True
        assert result["nats_connected"] is True
        assert result["services_discovered"] == 2

    @pytest.mark.asyncio
    async def test_list_examples(self, adapter: SDKMonitoringAdapter) -> None:
        """Test listing SDK examples."""
        examples = await adapter.list_examples()

        assert "quickstart" in examples
        assert "patterns" in examples
        assert "tools" in examples

    @pytest.mark.asyncio
    async def test_run_example(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running an SDK example."""
        result = await adapter.run_example("echo_service")

        assert result["example"] == "echo_service"
        assert result["status"] == "completed"
        assert "output" in result
        assert len(result["logs"]) == 4

    @pytest.mark.asyncio
    async def test_run_tests_with_tags(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running tests with tags filter."""
        result = await adapter.run_tests("connectivity", tags=["basic", "infrastructure"])

        assert result["scenario"] == "connectivity"
        assert result["tags"] == ["basic", "infrastructure"]
        assert result["passed"] == 2

    @pytest.mark.asyncio
    async def test_run_tests_unknown_scenario(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running unknown test scenario."""
        result = await adapter.run_tests("unknown_scenario")

        assert result["scenario"] == "unknown_scenario"
        assert result["failed"] == 1
        assert result["passed"] == 0
        assert result["tests"][0]["status"] == "failed"
        assert "Unknown scenario" in result["tests"][0]["error"]

    @pytest.mark.asyncio
    async def test_get_event_metrics_no_topics(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting event metrics without specific topics."""
        metrics = await adapter.get_event_metrics()

        assert metrics["total_events"] == 10000
        assert metrics["events_per_second"] == 250.5
        assert len(metrics["topics"]) == 3
        assert "orders" in metrics["metrics_by_topic"]

    @pytest.mark.asyncio
    async def test_get_load_metrics_system_wide(self, adapter: SDKMonitoringAdapter) -> None:
        """Test getting system-wide load metrics."""
        metrics = await adapter.get_load_metrics()

        assert metrics["total_requests_per_second"] == 5000
        assert metrics["services"] == 10
        assert metrics["average_latency_ms"] == 25.5
        assert metrics["system_error_rate"] == 0.002

    @pytest.mark.asyncio
    async def test_validate_config_invalid_nats_url(self, adapter: SDKMonitoringAdapter) -> None:
        """Test config validation with invalid NATS URL."""
        config = {
            "nats_url": "invalid://localhost:4222",
            "service_name": "test-service",
        }

        result = await adapter.validate_config(config)

        assert result["valid"] is True  # Valid despite warning
        assert "NATS URL should start with 'nats://'" in result["warnings"]

    @pytest.mark.asyncio
    async def test_validate_config_short_service_name(self, adapter: SDKMonitoringAdapter) -> None:
        """Test config validation with short service name."""
        config = {
            "nats_url": "nats://localhost:4222",
            "service_name": "ab",
        }

        result = await adapter.validate_config(config)

        assert result["valid"] is True  # Valid despite warning
        assert "Service name should be at least 3 characters" in result["warnings"]

    @pytest.mark.asyncio
    async def test_validate_config_connection_error(
        self, adapter: SDKMonitoringAdapter, mock_kv_store: Mock
    ) -> None:
        """Test config validation with connection error."""
        config = {
            "nats_url": "nats://localhost:4222",
            "service_name": "test-service",
        }
        mock_kv_store.list_all.side_effect = Exception("Connection failed")

        result = await adapter.validate_config(config)

        assert result["valid"] is False
        assert result["nats_connected"] is False
        assert "Cannot connect to NATS" in result["issues"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_payment_service(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test getting dependencies for payment service."""
        deps = await adapter.get_service_dependencies("payment-service")

        assert deps["service"] == "payment-service"
        assert "user-service" in deps["direct_dependencies"]
        assert "fraud-service" in deps["direct_dependencies"]
        assert "notification-service" in deps["indirect_dependencies"]

    @pytest.mark.asyncio
    async def test_get_service_dependencies_generic_service(
        self, adapter: SDKMonitoringAdapter
    ) -> None:
        """Test getting dependencies for generic service."""
        deps = await adapter.get_service_dependencies("generic-service")

        assert deps["service"] == "generic-service"
        assert "nats" in deps["direct_dependencies"]
        assert "kv-store" in deps["direct_dependencies"]

    @pytest.mark.asyncio
    async def test_run_test_scenario_rpc_call(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running RPC call test scenario."""
        result = await adapter.run_test_scenario("rpc_call")

        assert result["scenario"] == "rpc_call"
        assert result["success"] is True
        assert result["results"]["rpc_available"] is True
        assert result["results"]["latency_ms"] == 15.3

    @pytest.mark.asyncio
    async def test_run_test_scenario_event_stream(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running event stream test scenario."""
        result = await adapter.run_test_scenario("event_stream")

        assert result["scenario"] == "event_stream"
        assert result["success"] is True
        assert result["results"]["events_received"] == 100
        assert result["results"]["events_per_second"] == 50.0

    @pytest.mark.asyncio
    async def test_run_test_scenario_with_error(
        self, adapter: SDKMonitoringAdapter, mock_kv_store: Mock
    ) -> None:
        """Test running test scenario with error."""
        mock_kv_store.list_all.side_effect = Exception("KV store error")

        result = await adapter.run_test_scenario("connectivity")

        assert result["scenario"] == "connectivity"
        assert result["success"] is False
        assert "KV store error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_run_test_scenario_unknown(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running unknown test scenario."""
        result = await adapter.run_test_scenario("unknown_test")

        assert result["scenario"] == "unknown_test"
        assert result["success"] is False
        assert "Unknown scenario: unknown_test" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_validate_configuration_with_error(
        self, adapter: SDKMonitoringAdapter, mock_kv_store: Mock
    ) -> None:
        """Test configuration validation with connection error."""
        mock_kv_store.list_all.side_effect = Exception("Connection failed")

        result = await adapter.validate_configuration()

        assert result["valid"] is False
        assert result["nats_connected"] is False
        assert "NATS connection failed" in result["issues"][0]
        assert "Check NATS port-forwarding" in result["recommendations"][0]

    @pytest.mark.asyncio
    async def test_validate_configuration_success(self, adapter: SDKMonitoringAdapter) -> None:
        """Test successful configuration validation."""
        result = await adapter.validate_configuration()

        assert result["valid"] is True
        assert result["nats_connected"] is True
        assert result["k8s_accessible"] is True
        assert result["services_discovered"] == 2
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_run_test_scenario_service_discovery(self, adapter: SDKMonitoringAdapter) -> None:
        """Test service discovery scenario."""
        result = await adapter.run_test_scenario("service_discovery")

        assert result["scenario"] == "service_discovery"
        assert result["success"] is True
        assert result["results"]["total_services"] == 2
        assert len(result["results"]["service_names"]) == 2

    @pytest.mark.asyncio
    async def test_run_test_scenario_with_timeout(self, adapter: SDKMonitoringAdapter) -> None:
        """Test running test scenario with timeout parameter."""
        result = await adapter.run_test_scenario("connectivity", timeout=60)

        assert result["scenario"] == "connectivity"
        assert result["success"] is True
        assert "duration_ms" in result
