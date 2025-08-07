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
        service = EchoApplicationService(mock_service_bus, mock_configuration)

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
        service = EchoApplicationService(mock_service_bus, mock_configuration)

        # Act
        await service.start()

        # Assert
        mock_service_bus.start.assert_called_once()
        assert service._health_use_case.nats_connected is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_service_bus, mock_configuration):
        """Test stopping the application service."""
        # Arrange
        service = EchoApplicationService(mock_service_bus, mock_configuration)
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
        service = EchoApplicationService(mock_service_bus, mock_configuration)
        params = {"message": "Hello Test", "mode": "simple"}

        # Act
        result = await service._handle_echo(params)

        # Assert
        assert "echo" in result
        assert "original" in result
        assert result["original"] == "Hello Test"
        assert result["instance_id"] == "test-instance-1"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_handle_echo_invalid_request(self, mock_service_bus, mock_configuration):
        """Test echo request with invalid parameters."""
        # Arrange
        service = EchoApplicationService(mock_service_bus, mock_configuration)
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
        service = EchoApplicationService(mock_service_bus, mock_configuration)
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
        service = EchoApplicationService(mock_service_bus, mock_configuration)

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
        service = EchoApplicationService(mock_service_bus, mock_configuration)
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
        service = EchoApplicationService(mock_service_bus, mock_configuration)
        params = {"timestamp": "2024-01-01T00:00:00"}

        # Act
        result = await service._handle_ping(params)

        # Assert
        assert result["pong"] is True
        assert result["instance_id"] == "test-instance-1"
        assert result["timestamp"] == "2024-01-01T00:00:00"
