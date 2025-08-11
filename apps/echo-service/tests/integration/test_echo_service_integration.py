"""Integration tests for echo service following TDD and hexagonal architecture."""

from __future__ import annotations

import pytest
from app.application.echo_service import EchoApplicationService
from app.infrastructure.environment_configuration_adapter import (
    EnvironmentConfigurationAdapter,
)
from app.infrastructure.factory import EchoServiceFactory
from app.ports.service_bus import ServiceBusPort


class MockServiceBus(ServiceBusPort):
    """Mock service bus for integration testing."""

    def __init__(self):
        """Initialize mock service bus."""
        self._handlers = {}
        self._connected = False
        self._instance_id = "integration-test-123"

    async def start(self) -> None:
        """Start the service bus."""
        self._connected = True

    async def stop(self) -> None:
        """Stop the service bus."""
        self._connected = False

    def register_rpc_handler(self, method: str, handler) -> None:
        """Register an RPC handler."""
        self._handlers[method] = handler

    async def call_rpc(self, target: str, method: str, params: dict, timeout: float = 5.0) -> dict:
        """Call an RPC method (not used in these tests)."""
        return {}

    def get_instance_id(self) -> str:
        """Get instance ID."""
        return self._instance_id

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def call_handler(self, method: str, params: dict) -> dict:
        """Helper method to call registered handlers directly."""
        if method in self._handlers:
            return await self._handlers[method](params)
        raise ValueError(f"No handler for method: {method}")


class TestEchoServiceIntegration:
    """Integration tests for echo service."""

    @pytest.fixture
    def service_bus(self):
        """Create mock service bus."""
        return MockServiceBus()

    @pytest.fixture
    def configuration(self):
        """Create test configuration."""
        return EnvironmentConfigurationAdapter(
            defaults={
                "service_name": "echo-service-integration",
                "version": "1.0.0",
                "service_type": "service",
                "debug": True,
            }
        )

    @pytest.fixture
    def service(self, service_bus, configuration):
        """Create echo service with test dependencies."""
        return EchoServiceFactory.create_test_service(
            service_bus=service_bus,
            configuration=configuration,
        )

    @pytest.mark.asyncio
    async def test_full_echo_workflow(self, service, service_bus):
        """Test complete echo workflow from request to response."""
        # Start the service
        await service.start()
        assert service_bus.is_connected()

        # Test simple echo
        result = await service_bus.call_handler(
            "echo", {"message": "Hello Integration", "mode": "simple"}
        )
        assert result["original"] == "Hello Integration"
        assert result["echo"] == "Hello Integration"
        assert result["mode"] == "simple"

        # Test delayed echo
        result = await service_bus.call_handler(
            "echo",
            {"message": "Delayed", "mode": "delayed", "delay_seconds": 0.01},  # 10ms
        )
        assert result["original"] == "Delayed"
        assert result["processing_time_ms"] >= 10  # Should be at least 10ms

        # Test transform echo
        result = await service_bus.call_handler(
            "echo",
            {
                "message": "transform me",
                "mode": "transform",
                "transform_type": "uppercase",
            },
        )
        assert result["echo"] == "TRANSFORM ME"

        # Stop the service
        await service.stop()
        assert not service_bus.is_connected()

    @pytest.mark.asyncio
    async def test_batch_processing(self, service, service_bus):
        """Test batch echo processing."""
        await service.start()

        result = await service_bus.call_handler(
            "batch_echo",
            {"messages": ["First", "Second", "Third", "Fourth", "Fifth"]},
        )

        assert result["count"] == 5
        assert len(result["results"]) == 5
        for i, msg in enumerate(["First", "Second", "Third", "Fourth", "Fifth"]):
            assert result["results"][i]["original"] == msg
            # In batch mode, messages are repeated 3 times with " | " separator
            assert result["results"][i]["echo"] == f"{msg} | {msg} | {msg}"

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, service, service_bus):
        """Test that metrics are properly tracked."""
        await service.start()

        # Get initial metrics
        metrics = await service_bus.call_handler("metrics", {})
        assert metrics["total_requests"] == 0

        # Make some requests
        for i in range(5):
            await service_bus.call_handler("echo", {"message": f"Test {i}", "mode": "simple"})

        # Check updated metrics
        metrics = await service_bus.call_handler("metrics", {})
        assert metrics["total_requests"] == 5
        assert metrics["successful_requests"] == 5
        assert metrics["failed_requests"] == 0
        assert metrics["average_latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_health_check_states(self, service, service_bus):
        """Test health check in different states."""
        # Check health before starting (NATS not connected)
        health = await service_bus.call_handler("health", {})
        assert health["status"] == "unhealthy"
        assert health["checks"]["nats"] is False

        # Start service and check health
        await service.start()
        health = await service_bus.call_handler("health", {})
        assert health["status"] == "healthy"
        assert health["checks"]["nats"] is True
        assert health["checks"]["processor"] is True

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, service, service_bus):
        """Test error handling across the stack."""
        await service.start()

        # Test invalid request
        result = await service_bus.call_handler("echo", {})  # Missing message
        assert "error" in result
        assert "Invalid request" in result["error"]

        # Test invalid mode
        result = await service_bus.call_handler("echo", {"message": "test", "mode": "invalid_mode"})
        assert "error" in result

        # Metrics should still work after errors
        metrics = await service_bus.call_handler("metrics", {})
        assert metrics["failed_requests"] >= 1

    @pytest.mark.asyncio
    async def test_ping_pong(self, service, service_bus):
        """Test ping endpoint."""
        await service.start()

        result = await service_bus.call_handler("ping", {"timestamp": "2024-01-01T12:00:00"})
        assert result["pong"] is True
        assert result["timestamp"] == "2024-01-01T12:00:00"
        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_all_transform_types(self, service, service_bus):
        """Test all available transform types."""
        await service.start()

        # Test uppercase
        result = await service_bus.call_handler(
            "echo",
            {
                "message": "hello world",
                "mode": "transform",
                "transform_type": "uppercase",
            },
        )
        assert result["echo"] == "HELLO WORLD"

        # Test lowercase
        result = await service_bus.call_handler(
            "echo",
            {
                "message": "HELLO WORLD",
                "mode": "transform",
                "transform_type": "lowercase",
            },
        )
        assert result["echo"] == "hello world"

        # Test reverse
        result = await service_bus.call_handler(
            "echo",
            {"message": "hello", "mode": "transform", "transform_type": "reverse"},
        )
        assert result["echo"] == "olleh"

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, service, service_bus):
        """Test complete service lifecycle."""
        # Service should not be connected initially
        assert not service_bus.is_connected()

        # Start service
        await service.start()
        assert service_bus.is_connected()

        # Make a request to verify it's working
        result = await service_bus.call_handler(
            "echo", {"message": "lifecycle test", "mode": "simple"}
        )
        assert result["echo"] == "lifecycle test"

        # Stop service
        await service.stop()
        assert not service_bus.is_connected()

        # Start again to verify restart works
        await service.start()
        assert service_bus.is_connected()

        result = await service_bus.call_handler(
            "echo", {"message": "restart test", "mode": "simple"}
        )
        assert result["echo"] == "restart test"

        await service.stop()


class TestFactoryIntegration:
    """Integration tests for the factory pattern."""

    def test_create_test_service_with_defaults(self):
        """Test creating service with default test configuration."""
        mock_bus = MockServiceBus()
        service = EchoServiceFactory.create_test_service(service_bus=mock_bus)

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_bus
        assert service._configuration.get_service_name() == "echo-service-test"

    def test_create_test_service_with_custom_config(self):
        """Test creating service with custom configuration."""
        mock_bus = MockServiceBus()
        custom_config = EnvironmentConfigurationAdapter(
            defaults={
                "service_name": "custom-echo",
                "version": "2.0.0",
            }
        )

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_bus,
            configuration=custom_config,
        )

        assert service._configuration == custom_config
        assert service._configuration.get_service_name() == "custom-echo"

    @pytest.mark.asyncio
    async def test_create_with_custom_adapters(self):
        """Test creating service with custom adapters."""
        mock_bus = MockServiceBus()
        custom_config = EnvironmentConfigurationAdapter(defaults={"service_name": "custom-service"})

        service = await EchoServiceFactory.create_with_custom_adapters(
            service_bus=mock_bus,
            configuration=custom_config,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_bus
        assert service._configuration == custom_config
