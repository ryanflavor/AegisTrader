"""Unit tests for Echo Service application layer.

Tests for use cases, command handlers, and query handlers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from application.commands import (
    ProcessEchoCommand,
    RegisterServiceCommand,
    ResetMetricsCommand,
)
from application.handlers import CommandHandler, QueryHandler
from application.queries import (
    GetHealthQuery,
    GetMetricsQuery,
    PingQuery,
)
from application.use_cases import (
    EchoUseCase,
    GetMetricsUseCase,
    HealthCheckUseCase,
    PingUseCase,
    ServiceRegistrationUseCase,
)
from domain.entities import EchoResponse, ServiceMetrics
from domain.services import EchoProcessor, HealthChecker, MetricsCollector
from domain.value_objects import EchoMode, MessagePriority


@pytest.fixture
def echo_processor():
    """Create a mock echo processor."""
    processor = AsyncMock(spec=EchoProcessor)
    processor.instance_id = "test-instance-123"
    return processor


@pytest.fixture
def metrics_collector():
    """Create a mock metrics collector."""
    collector = MagicMock(spec=MetricsCollector)
    metrics = ServiceMetrics(
        instance_id="test-instance-123",
        total_requests=100,
        successful_requests=95,
        failed_requests=5,
    )
    collector.metrics = metrics
    collector.get_current_metrics.return_value = metrics
    return collector


@pytest.fixture
def health_checker():
    """Create a mock health checker."""
    checker = MagicMock(spec=HealthChecker)
    checker.instance_id = "test-instance-123"
    checker.version = "1.0.0"
    return checker


@pytest.fixture
def registration_repository():
    """Create a mock registration repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def echo_use_case(echo_processor, metrics_collector):
    """Create an echo use case with mocked dependencies."""
    return EchoUseCase(echo_processor, metrics_collector)


@pytest.fixture
def metrics_use_case(metrics_collector):
    """Create a metrics use case with mocked dependencies."""
    return GetMetricsUseCase(metrics_collector)


@pytest.fixture
def health_use_case(health_checker, metrics_collector, registration_repository):
    """Create a health check use case with mocked dependencies."""
    return HealthCheckUseCase(health_checker, metrics_collector, registration_repository)


@pytest.fixture
def ping_use_case():
    """Create a ping use case."""
    return PingUseCase("test-instance-123")


@pytest.fixture
def registration_use_case(registration_repository):
    """Create a registration use case with mocked dependencies."""
    return ServiceRegistrationUseCase(registration_repository)


class TestEchoUseCase:
    """Test cases for EchoUseCase."""

    @pytest.mark.asyncio
    async def test_execute_simple_echo(self, echo_use_case, echo_processor, metrics_collector):
        """Test executing a simple echo request."""
        # Arrange
        request_data = {
            "message": "Hello, World!",
            "mode": "simple",
            "priority": "normal",
        }

        response = EchoResponse(
            original="Hello, World!",
            echoed="Hello, World!",
            mode=EchoMode.SIMPLE,
            instance_id="test-instance-123",
            processing_time_ms=10.5,
            sequence_number=1,
        )
        echo_processor.process_echo.return_value = response

        # Act
        result = await echo_use_case.execute(request_data)

        # Assert
        assert result["original"] == "Hello, World!"
        assert result["echoed"] == "Hello, World!"
        assert result["mode"] == "simple"
        assert result["instance_id"] == "test-instance-123"
        echo_processor.process_echo.assert_called_once()
        metrics_collector.record_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_batch_echo(self, echo_use_case, echo_processor):
        """Test executing a batch echo request."""
        # Arrange
        batch_data = {
            "requests": [
                {"message": "Hello", "mode": "simple"},
                {"message": "World", "mode": "reverse"},
            ],
            "batch_id": "batch-123",
            "priority": "normal",
        }

        responses = [
            EchoResponse(
                original="Hello",
                echoed="Hello",
                mode=EchoMode.SIMPLE,
                instance_id="test-instance-123",
                processing_time_ms=5.0,
                sequence_number=1,
            ),
            EchoResponse(
                original="World",
                echoed="dlroW",
                mode=EchoMode.REVERSE,
                instance_id="test-instance-123",
                processing_time_ms=7.0,
                sequence_number=2,
            ),
        ]
        echo_processor.process_batch.return_value = responses

        # Act
        result = await echo_use_case.execute_batch(batch_data)

        # Assert
        assert len(result) == 2
        assert result[0]["echoed"] == "Hello"
        assert result[1]["echoed"] == "dlroW"
        echo_processor.process_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_error(self, echo_use_case, echo_processor, metrics_collector):
        """Test handling errors during echo processing."""
        # Arrange
        request_data = {"message": "Test", "mode": "simple"}
        echo_processor.process_echo.side_effect = Exception("Processing failed")

        # Act & Assert
        with pytest.raises(Exception, match="Processing failed"):
            await echo_use_case.execute(request_data)

        # Verify failure was recorded
        metrics_collector.record_request.assert_called_with(
            mode=EchoMode.SIMPLE,
            priority=MessagePriority.NORMAL,
            latency_ms=0.0,
            success=False,
        )


class TestGetMetricsUseCase:
    """Test cases for GetMetricsUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_metrics_summary(self, metrics_use_case, metrics_collector):
        """Test retrieving metrics summary."""
        # Arrange
        metrics_collector.get_metrics_summary.return_value = {
            "instance_id": "test-instance-123",
            "total_requests": 100,
            "success_rate": 95.0,
            "average_latency_ms": 15.5,
        }
        metrics_collector.get_current_metrics.return_value = ServiceMetrics(
            instance_id="test-instance-123",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
        )

        # Act
        result = await metrics_use_case.execute()

        # Assert
        assert result["instance_id"] == "test-instance-123"
        assert result["total_requests"] == 100
        assert result["success_rate"] == 95.0
        assert result["failed_requests"] == 5

    @pytest.mark.asyncio
    async def test_get_detailed_metrics(self, metrics_use_case, metrics_collector):
        """Test retrieving detailed metrics."""
        # Arrange
        metrics = ServiceMetrics(
            instance_id="test-instance-123",
            total_requests=50,
            successful_requests=48,
            failed_requests=2,
        )
        metrics_collector.get_current_metrics.return_value = metrics

        # Act
        result = await metrics_use_case.get_detailed_metrics()

        # Assert
        assert result == metrics
        assert result.total_requests == 50


class TestHealthCheckUseCase:
    """Test cases for HealthCheckUseCase."""

    @pytest.mark.asyncio
    async def test_execute_healthy_status(self, health_use_case, health_checker):
        """Test health check returning healthy status."""
        # Arrange
        health_checker.check_dependencies = AsyncMock(
            return_value={"nats": True, "monitor_api": True}
        )
        health_checker.is_healthy.return_value = True
        health_checker.get_health_status.return_value = {
            "status": "healthy",
            "instance_id": "test-instance-123",
            "version": "1.0.0",
            "checks": {"nats": True, "monitor_api": True},
        }

        # Act
        result = await health_use_case.execute()

        # Assert
        assert result["status"] == "healthy"
        assert result["instance_id"] == "test-instance-123"
        assert "checks" in result
        health_checker.check_dependencies.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_error_returns_unhealthy(self, health_use_case, health_checker):
        """Test health check handling errors."""
        # Arrange
        health_checker.check_dependencies = AsyncMock(side_effect=Exception("Connection failed"))

        # Act
        result = await health_use_case.execute()

        # Assert
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert "Connection failed" in result["error"]


class TestServiceRegistrationUseCase:
    """Test cases for ServiceRegistrationUseCase."""

    @pytest.mark.asyncio
    async def test_register_service(self, registration_use_case, registration_repository):
        """Test service registration."""
        # Arrange
        registration_data = {
            "definition": {
                "service_name": "echo-service",
                "owner": "team-echo",
                "description": "Echo service",
                "version": "1.0.0",
            },
            "instance_id": "test-instance-123",
            "nats_url": "nats://localhost:4222",
        }

        # Act
        result = await registration_use_case.register_service(registration_data)

        # Assert
        assert result["status"] == "registered"
        assert result["instance_id"] == "test-instance-123"
        assert result["service_name"] == "echo-service"
        registration_repository.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_registration(self, registration_use_case, registration_repository):
        """Test refreshing service registration."""
        # Arrange
        registration_repository.update_heartbeat.return_value = True

        # Act
        result = await registration_use_case.refresh_registration("test-instance-123")

        # Assert
        assert result["status"] == "refreshed"
        assert result["instance_id"] == "test-instance-123"
        registration_repository.update_heartbeat.assert_called_once_with("test-instance-123")


class TestPingUseCase:
    """Test cases for PingUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_pong(self, ping_use_case):
        """Test ping returns pong with instance ID."""
        # Act
        result = await ping_use_case.execute()

        # Assert
        assert result["status"] == "pong"
        assert result["instance_id"] == "test-instance-123"


class TestCommandHandler:
    """Test cases for CommandHandler."""

    @pytest.fixture
    def command_handler(
        self, echo_use_case, registration_use_case, metrics_use_case, health_use_case
    ):
        """Create a command handler with mocked dependencies."""
        return CommandHandler(
            echo_use_case=echo_use_case,
            registration_use_case=registration_use_case,
            metrics_use_case=metrics_use_case,
            health_use_case=health_use_case,
        )

    @pytest.mark.asyncio
    async def test_handle_process_echo(self, command_handler, echo_use_case):
        """Test handling ProcessEchoCommand."""
        # Arrange
        command = ProcessEchoCommand(
            message="Test message",
            mode="simple",
            correlation_id="corr-123",
        )
        echo_use_case.execute = AsyncMock(return_value={"echoed": "Test message"})

        # Act
        result = await command_handler.handle_process_echo(command)

        # Assert
        assert result["echoed"] == "Test message"
        assert result["correlation_id"] == "corr-123"
        echo_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_register_service(self, command_handler, registration_use_case):
        """Test handling RegisterServiceCommand."""
        # Arrange
        command = RegisterServiceCommand(
            service_name="echo-service",
            owner="team-echo",
            description="Echo service",
            version="1.0.0",
            instance_id="test-instance-123",
            nats_url="nats://localhost:4222",
        )
        registration_use_case.register_service = AsyncMock(return_value={"status": "registered"})

        # Act
        result = await command_handler.handle_register_service(command)

        # Assert
        assert result["status"] == "registered"
        registration_use_case.register_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_reset_metrics(self, command_handler, metrics_use_case):
        """Test handling ResetMetricsCommand."""
        # Arrange
        command = ResetMetricsCommand(confirm=True)

        # Act
        result = await command_handler.handle_reset_metrics(command)

        # Assert
        assert result["status"] == "metrics_reset"
        metrics_use_case.metrics_collector.reset_metrics.assert_called_once()


class TestQueryHandler:
    """Test cases for QueryHandler."""

    @pytest.fixture
    def query_handler(self, metrics_use_case, health_use_case, ping_use_case):
        """Create a query handler with mocked dependencies."""
        return QueryHandler(
            metrics_use_case=metrics_use_case,
            health_use_case=health_use_case,
            ping_use_case=ping_use_case,
            service_info={"service_name": "echo-service", "version": "1.0.0"},
        )

    @pytest.mark.asyncio
    async def test_handle_get_metrics(self, query_handler, metrics_use_case):
        """Test handling GetMetricsQuery."""
        # Arrange
        query = GetMetricsQuery(detailed=False)
        metrics_use_case.execute = AsyncMock(
            return_value={"total_requests": 100, "success_rate": 95.0}
        )

        # Act
        result = await query_handler.handle_get_metrics(query)

        # Assert
        assert result["total_requests"] == 100
        assert result["success_rate"] == 95.0
        metrics_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_get_health(self, query_handler, health_use_case):
        """Test handling GetHealthQuery."""
        # Arrange
        query = GetHealthQuery(include_dependencies=True, include_metrics=True)
        health_use_case.execute = AsyncMock(
            return_value={"status": "healthy", "instance_id": "test-instance-123"}
        )

        # Act
        result = await query_handler.handle_get_health(query)

        # Assert
        assert result["status"] == "healthy"
        assert result["instance_id"] == "test-instance-123"
        health_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_ping(self, query_handler, ping_use_case):
        """Test handling PingQuery."""
        # Arrange
        query = PingQuery(echo_message="Hello")
        ping_use_case.execute = AsyncMock(
            return_value={"status": "pong", "instance_id": "test-instance-123"}
        )

        # Act
        result = await query_handler.handle_ping(query)

        # Assert
        assert result["status"] == "pong"
        assert result["instance_id"] == "test-instance-123"
        assert result["echo"] == "Hello"
        ping_use_case.execute.assert_called_once()
