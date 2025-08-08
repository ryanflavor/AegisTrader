"""Unit tests for the echo application service."""

from __future__ import annotations

from unittest.mock import call

import pytest
from app.application.echo_service import EchoApplicationService


class TestEchoApplicationService:
    """Test cases for the EchoApplicationService."""

    def test_initialization(self, mock_service_bus, mock_configuration):
        """Test that the service initializes correctly."""
        # Act
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Assert
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_configuration
        # Verify RPC handlers were registered
        assert mock_service_bus.register_rpc_handler.call_count == 5
        expected_calls = [
            call("echo", service._handle_echo),
            call("batch_echo", service._handle_batch_echo),
            call("metrics", service._handle_metrics),
            call("health", service._handle_health),
            call("ping", service._handle_ping),
        ]
        mock_service_bus.register_rpc_handler.assert_has_calls(expected_calls)

    @pytest.mark.asyncio
    async def test_start(self, mock_service_bus, mock_configuration):
        """Test starting the application service."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Act
        await service.start()

        # Assert
        mock_service_bus.start.assert_called_once()
        assert service._health_use_case.nats_connected is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_service_bus, mock_configuration):
        """Test stopping the application service."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        await service.start()

        # Act
        await service.stop()

        # Assert
        mock_service_bus.stop.assert_called_once()
        assert service._health_use_case.nats_connected is False

    @pytest.mark.asyncio
    async def test_handle_echo_success(self, mock_service_bus, mock_configuration):
        """Test successful echo request handling."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        params = {"message": "Hello Test", "mode": "simple"}

        # Act
        result = await service._handle_echo(params)

        # Assert
        assert "echoed" in result
        assert "original" in result
        assert result["original"] == "Hello Test"
        assert result["instance_id"] == "test-instance-1"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_handle_echo_invalid_request(self, mock_service_bus, mock_configuration):
        """Test echo request with invalid parameters."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        params = {}  # Missing required 'message' field

        # Act
        result = await service._handle_echo(params)

        # Assert
        assert "error" in result
        assert "Invalid request" in result["error"]
        assert result["instance_id"] == "test-instance-1"

    @pytest.mark.asyncio
    async def test_handle_batch_echo(self, mock_service_bus, mock_configuration):
        """Test batch echo request handling."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        params = {"messages": ["First", "Second", "Third"]}

        # Act
        result = await service._handle_batch_echo(params)

        # Assert
        assert "results" in result
        assert "count" in result
        assert result["count"] == 3
        assert len(result["results"]) == 3
        assert result["instance_id"] == "test-instance-1"

    @pytest.mark.asyncio
    async def test_handle_metrics(self, mock_service_bus, mock_configuration):
        """Test metrics endpoint handling."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Act
        result = await service._handle_metrics({})

        # Assert
        assert "instance_id" in result
        assert "total_requests" in result
        assert "successful_requests" in result
        assert "average_latency_ms" in result
        assert result["instance_id"] == "test-instance-1"

    @pytest.mark.asyncio
    async def test_handle_health(self, mock_service_bus, mock_configuration):
        """Test health check endpoint handling."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        await service.start()  # Sets NATS as connected

        # Act
        result = await service._handle_health({})

        # Assert
        assert "status" in result
        assert "instance_id" in result
        assert "version" in result
        assert "checks" in result
        assert result["instance_id"] == "test-instance-1"
        assert result["version"] == "test-1.0.0"

    @pytest.mark.asyncio
    async def test_handle_ping(self, mock_service_bus, mock_configuration):
        """Test ping endpoint handling."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )
        params = {"timestamp": "2024-01-01T00:00:00"}

        # Act
        result = await service._handle_ping(params)

        # Assert
        assert result["pong"] is True
        assert result["instance_id"] == "test-instance-1"
        assert result["timestamp"] == "2024-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_handle_echo_generic_exception(self, mock_service_bus, mock_configuration):
        """Test echo request handling with generic exception."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Mock the use case to raise a generic exception
        from unittest.mock import AsyncMock

        service._echo_use_case.execute = AsyncMock(side_effect=RuntimeError("Processing error"))

        params = {"message": "test", "mode": "simple"}

        # Act
        result = await service._handle_echo(params)

        # Assert
        assert "error" in result
        assert "Processing error" in result["error"]
        assert result["instance_id"] == "test-instance-1"

    @pytest.mark.asyncio
    async def test_handle_batch_echo_with_error(self, mock_service_bus, mock_configuration):
        """Test batch echo with some messages failing."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Mock to fail on second message
        from unittest.mock import AsyncMock

        async def execute_with_error(request):
            if request.message == "fail_this":
                raise RuntimeError("Batch item failed")
            # Call real implementation for others
            from app.domain.models import EchoMode, EchoResponse

            return EchoResponse(
                original=request.message,
                echoed=request.message,
                mode=EchoMode.BATCH,
                processing_time_ms=1.0,
                sequence_number=1,
                instance_id="test-instance-1",
            )

        service._echo_use_case.execute = AsyncMock(side_effect=execute_with_error)

        params = {"messages": ["first", "fail_this", "third"]}

        # Act
        result = await service._handle_batch_echo(params)

        # Assert
        assert result["count"] == 3
        assert len(result["results"]) == 3
        # First should succeed
        assert "error" not in result["results"][0]
        # Second should have error
        assert "error" in result["results"][1]
        assert "Batch item failed" in result["results"][1]["error"]
        # Third should succeed
        assert "error" not in result["results"][2]

    @pytest.mark.asyncio
    async def test_handle_metrics_exception(self, mock_service_bus, mock_configuration):
        """Test metrics endpoint with exception."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Mock the use case to raise exception
        from unittest.mock import AsyncMock

        service._metrics_use_case.execute = AsyncMock(side_effect=RuntimeError("Metrics error"))

        # Act
        result = await service._handle_metrics({})

        # Assert
        assert "error" in result
        assert "Metrics error" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_health_exception(self, mock_service_bus, mock_configuration):
        """Test health endpoint with exception."""
        # Arrange
        service = EchoApplicationService(
            mock_service_bus, mock_configuration, service_registry=None
        )

        # Mock the use case to raise exception
        from unittest.mock import AsyncMock

        service._health_use_case.execute = AsyncMock(side_effect=RuntimeError("Health check error"))

        # Act
        result = await service._handle_health({})

        # Assert
        assert result["status"] == "error"
        assert "error" in result
        assert "Health check error" in result["error"]
        assert result["instance_id"] == "test-instance-1"
