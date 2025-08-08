"""Comprehensive unit tests for the Echo Application Service.

Testing all application service methods including edge cases,
error handling, and complete code coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.echo_service import EchoApplicationService
from app.domain.models import EchoMode


@pytest.fixture
def mock_service_bus():
    """Create mock service bus."""
    bus = AsyncMock()
    bus.register_rpc_handler = MagicMock()
    bus.start = AsyncMock()
    bus.stop = AsyncMock()
    return bus


@pytest.fixture
def mock_configuration():
    """Create mock configuration."""
    config = MagicMock()
    config.get_instance_id.return_value = "test-instance-123"
    config.get_service_name.return_value = "echo-service-test"
    config.get_service_version.return_value = "1.0.0"
    return config


@pytest.fixture
def mock_service_registry():
    """Create mock service registry."""
    registry = AsyncMock()
    registry.update_heartbeat = AsyncMock(return_value=True)
    registry.deregister_instance = AsyncMock()
    return registry


@pytest.fixture
def echo_service(mock_service_bus, mock_configuration, mock_service_registry):
    """Create echo application service with mocks."""
    return EchoApplicationService(
        service_bus=mock_service_bus,
        configuration=mock_configuration,
        service_registry=mock_service_registry,
    )


class TestEchoApplicationServiceComprehensive:
    """Comprehensive tests for Echo Application Service."""

    @pytest.mark.asyncio
    async def test_update_heartbeat_with_registry(self, echo_service, mock_service_registry):
        """Test heartbeat update when registry is available."""
        mock_service_registry.update_heartbeat.return_value = True

        await echo_service.update_heartbeat()

        mock_service_registry.update_heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_heartbeat_without_registry(self, mock_service_bus, mock_configuration):
        """Test heartbeat update when no registry is available."""
        # Create service without registry
        service = EchoApplicationService(
            service_bus=mock_service_bus,
            configuration=mock_configuration,
            service_registry=None,
        )

        # Should not raise error
        await service.update_heartbeat()

    @pytest.mark.asyncio
    async def test_update_heartbeat_failure(self, echo_service, mock_service_registry):
        """Test heartbeat update when update fails."""
        mock_service_registry.update_heartbeat.return_value = False

        with patch("app.application.echo_service.logger") as mock_logger:
            await echo_service.update_heartbeat()

            mock_service_registry.update_heartbeat.assert_called_once()
            mock_logger.warning.assert_called_once_with("Heartbeat update failed")

    @pytest.mark.asyncio
    async def test_update_heartbeat_exception(self, echo_service, mock_service_registry):
        """Test heartbeat update when exception occurs."""
        mock_service_registry.update_heartbeat.side_effect = Exception("Network error")

        with patch("app.application.echo_service.logger") as mock_logger:
            await echo_service.update_heartbeat()

            mock_service_registry.update_heartbeat.assert_called_once()
            mock_logger.debug.assert_called_once()
            assert "Failed to update heartbeat: Network error" in mock_logger.debug.call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_logs_comprehensive_info(self, echo_service, mock_service_bus):
        """Test that start method logs comprehensive service information."""
        with patch("app.application.echo_service.logger") as mock_logger:
            await echo_service.start()

            # Verify service bus was started
            mock_service_bus.start.assert_called_once()

            # Verify comprehensive logging
            info_calls = mock_logger.info.call_args_list
            assert len(info_calls) >= 2

            # Check starting message
            first_log = info_calls[0][0][0]
            assert "Starting Echo Application Service" in first_log
            assert "test-instance-123" in first_log

            # Check success message with details
            second_log = info_calls[1][0][0]
            assert "Echo Application Service started successfully" in second_log
            assert "Instance: test-instance-123" in second_log
            assert "Version: 1.0.0" in second_log
            assert "Service Name: echo-service-test" in second_log
            assert "Load-Balanced" in second_log

    @pytest.mark.asyncio
    async def test_stop_with_registry_deregistration_failure(
        self, echo_service, mock_service_registry
    ):
        """Test stop method when deregistration fails."""
        mock_service_registry.deregister_instance.side_effect = Exception("Registry error")

        with patch("app.application.echo_service.logger") as mock_logger:
            await echo_service.stop()

            # Should handle error gracefully
            mock_service_registry.deregister_instance.assert_called_once()
            warning_calls = list(mock_logger.warning.call_args_list)
            assert any("Failed to deregister instance" in str(call) for call in warning_calls)

    @pytest.mark.asyncio
    async def test_handle_echo_with_transform_mode(self, echo_service):
        """Test echo handler with transform mode."""
        params = {
            "message": "hello world",
            "mode": "transform",
            "transform_type": "uppercase",
        }

        with patch.object(echo_service._echo_use_case, "execute") as mock_execute:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "original": "hello world",
                "transformed": "HELLO WORLD",
                "mode": "transform",
                "instance_id": "test-instance-123",
            }
            mock_execute.return_value = mock_response

            result = await echo_service._handle_echo(params)

            assert result["transformed"] == "HELLO WORLD"
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_echo_with_reverse_mode(self, echo_service):
        """Test echo handler with reverse mode."""
        params = {
            "message": "hello",
            "mode": "reverse",
        }

        with patch.object(echo_service._echo_use_case, "execute") as mock_execute:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "original": "hello",
                "reversed": "olleh",
                "mode": "reverse",
                "instance_id": "test-instance-123",
            }
            mock_execute.return_value = mock_response

            result = await echo_service._handle_echo(params)

            assert result["reversed"] == "olleh"

    @pytest.mark.asyncio
    async def test_handle_batch_echo_with_mixed_results(self, echo_service):
        """Test batch echo with some successes and some failures."""
        params = {
            "messages": ["message1", "message2", "message3"],
        }

        with patch.object(echo_service._echo_use_case, "execute") as mock_execute:
            # First succeeds, second fails, third succeeds
            responses = [
                MagicMock(model_dump=lambda: {"echo": "message1", "original": "message1"}),
                Exception("Processing error"),
                MagicMock(model_dump=lambda: {"echo": "message3", "original": "message3"}),
            ]
            mock_execute.side_effect = responses

            result = await echo_service._handle_batch_echo(params)

            assert result["count"] == 3
            assert len(result["results"]) == 3
            assert result["results"][0]["echo"] == "message1"
            assert "error" in result["results"][1]
            assert result["results"][2]["echo"] == "message3"

    @pytest.mark.asyncio
    async def test_handle_metrics_error(self, echo_service):
        """Test metrics handler when error occurs."""
        with patch.object(echo_service._metrics_use_case, "execute") as mock_execute:
            mock_execute.side_effect = Exception("Metrics error")

            result = await echo_service._handle_metrics({})

            assert "error" in result
            assert result["error"] == "Metrics error"

    @pytest.mark.asyncio
    async def test_handle_health_error(self, echo_service, mock_configuration):
        """Test health handler when error occurs."""
        with patch.object(echo_service._health_use_case, "execute") as mock_execute:
            mock_execute.side_effect = Exception("Health check failed")

            result = await echo_service._handle_health({})

            assert result["status"] == "error"
            assert result["error"] == "Health check failed"
            assert result["instance_id"] == "test-instance-123"

    @pytest.mark.asyncio
    async def test_handle_ping_with_timestamp(self, echo_service, mock_configuration):
        """Test ping handler with timestamp parameter."""
        params = {"timestamp": "2024-01-15T10:30:00Z"}

        result = await echo_service._handle_ping(params)

        assert result["pong"] is True
        assert result["instance_id"] == "test-instance-123"
        assert result["timestamp"] == "2024-01-15T10:30:00Z"

    @pytest.mark.asyncio
    async def test_handle_ping_without_timestamp(self, echo_service, mock_configuration):
        """Test ping handler without timestamp parameter."""
        params = {}

        result = await echo_service._handle_ping(params)

        assert result["pong"] is True
        assert result["instance_id"] == "test-instance-123"
        assert result["timestamp"] is None

    def test_initialization_registers_all_handlers(self, mock_service_bus, mock_configuration):
        """Test that initialization registers all RPC handlers."""
        _ = EchoApplicationService(
            service_bus=mock_service_bus,
            configuration=mock_configuration,
        )

        # Verify all handlers were registered
        expected_handlers = ["echo", "batch_echo", "metrics", "health", "ping"]
        assert mock_service_bus.register_rpc_handler.call_count == len(expected_handlers)

        registered_methods = [
            call[0][0] for call in mock_service_bus.register_rpc_handler.call_args_list
        ]
        for handler in expected_handlers:
            assert handler in registered_methods

    @pytest.mark.asyncio
    async def test_stop_calculates_final_metrics(self, echo_service, mock_service_bus):
        """Test that stop method calculates and logs final metrics."""
        # Setup metrics
        with patch.object(echo_service._metrics_use_case, "execute") as mock_execute:
            mock_metrics = MagicMock()
            mock_metrics.total_requests = 100
            mock_metrics.successful_requests = 95
            mock_metrics.average_latency_ms = 25.5
            mock_metrics.uptime_seconds = 3600.0
            mock_execute.return_value = mock_metrics

            with patch("app.application.echo_service.logger") as mock_logger:
                await echo_service.stop()

                # Verify final metrics were logged
                info_calls = mock_logger.info.call_args_list
                final_metrics_log = info_calls[-1][0][0]

                assert "Final Metrics" in final_metrics_log
                assert "Total Requests: 100" in final_metrics_log
                assert "Success Rate: 95.0%" in final_metrics_log
                assert "Average Latency: 25.50ms" in final_metrics_log
                assert "Uptime: 3600.0s" in final_metrics_log

    @pytest.mark.asyncio
    async def test_handle_echo_records_failed_metrics(self, echo_service):
        """Test that failed echo requests are recorded in metrics."""
        params = {"invalid": "data"}  # Will cause validation error

        with patch.object(echo_service._metrics, "record_request") as mock_record:
            result = await echo_service._handle_echo(params)

            assert "error" in result
            # Verify failed request was recorded
            mock_record.assert_called_once_with(
                mode=EchoMode.SIMPLE,
                latency_ms=0.0,
                success=False,
            )

    @pytest.mark.asyncio
    async def test_handle_echo_unexpected_exception(self, echo_service):
        """Test echo handler with unexpected exception."""
        params = {"message": "test"}

        with patch.object(echo_service._echo_use_case, "execute") as mock_execute:
            mock_execute.side_effect = RuntimeError("Unexpected error")

            with patch.object(echo_service._metrics, "record_request") as mock_record:
                result = await echo_service._handle_echo(params)

                assert "error" in result
                assert "Unexpected error" in result["error"]
                # Verify failed request was recorded
                mock_record.assert_called_once_with(
                    mode=EchoMode.SIMPLE,
                    latency_ms=0.0,
                    success=False,
                )
