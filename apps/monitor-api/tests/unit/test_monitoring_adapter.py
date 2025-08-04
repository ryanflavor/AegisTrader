"""Unit tests for the MonitoringAdapter.

These tests verify the monitoring adapter implementation including
health checks, system status reporting, and detailed health metrics.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from app.domain.models import ServiceConfiguration
from app.infrastructure.monitoring_adapter import MonitoringAdapter

if TYPE_CHECKING:
    pass


class TestMonitoringAdapter:
    """Test cases for MonitoringAdapter."""

    @pytest.fixture
    def mock_config(self) -> ServiceConfiguration:
        """Create a mock service configuration."""
        return ServiceConfiguration(
            nats_url="nats://test:4222",
            api_port=8100,
            log_level="INFO",
            environment="development",
        )

    @pytest.fixture
    def monitoring_adapter(self, mock_config: ServiceConfiguration) -> MonitoringAdapter:
        """Create a monitoring adapter instance."""
        return MonitoringAdapter(mock_config)

    def test_init(
        self, monitoring_adapter: MonitoringAdapter, mock_config: ServiceConfiguration
    ) -> None:
        """Test MonitoringAdapter initialization."""
        # Assert
        assert monitoring_adapter._config == mock_config
        assert monitoring_adapter._start_time is not None
        assert isinstance(monitoring_adapter._start_time, datetime)

    @pytest.mark.asyncio
    async def test_check_health(
        self, monitoring_adapter: MonitoringAdapter, mock_config: ServiceConfiguration
    ) -> None:
        """Test health check returns correct status."""
        # Act
        health_status = await monitoring_adapter.check_health()

        # Assert
        assert health_status.status == "healthy"
        assert health_status.service_name == "management-service"
        assert health_status.version == "0.1.0"
        assert health_status.nats_url == mock_config.nats_url
        assert health_status.timestamp is not None
        assert isinstance(health_status.timestamp, datetime)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"DEPLOYMENT_VERSION": "v2.0.0-test"})
    async def test_get_system_status_with_deployment_version(
        self, monitoring_adapter: MonitoringAdapter, mock_config: ServiceConfiguration
    ) -> None:
        """Test system status with custom deployment version."""
        # Act
        system_status = await monitoring_adapter.get_system_status()

        # Assert
        assert system_status.deployment_version == "v2.0.0-test"
        assert system_status.environment == mock_config.environment
        assert system_status.connected_services == 0
        assert system_status.uptime_seconds >= 0
        assert system_status.timestamp is not None
        assert system_status.start_time == monitoring_adapter._start_time

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    async def test_get_system_status_default_deployment_version(
        self, monitoring_adapter: MonitoringAdapter
    ) -> None:
        """Test system status with default deployment version."""
        # Act
        system_status = await monitoring_adapter.get_system_status()

        # Assert
        assert system_status.deployment_version == "v1.0.0-demo"

    @pytest.mark.asyncio
    async def test_get_system_status_uptime_calculation(
        self, mock_config: ServiceConfiguration
    ) -> None:
        """Test that uptime is calculated correctly."""
        # Arrange
        with patch("app.infrastructure.monitoring_adapter.now_utc8") as mock_now:
            # Set start time
            start_time = datetime(2024, 1, 1, 10, 0, 0)
            mock_now.return_value = start_time
            adapter = MonitoringAdapter(mock_config)

            # Set current time to 1 hour later
            current_time = start_time + timedelta(hours=1)
            mock_now.return_value = current_time

            # Act
            system_status = await adapter.get_system_status()

            # Assert
            assert system_status.uptime_seconds == 3600.0  # 1 hour in seconds
            assert system_status.timestamp == current_time

    @pytest.mark.asyncio
    async def test_get_start_time(self, monitoring_adapter: MonitoringAdapter) -> None:
        """Test getting service start time."""
        # Act
        start_time = await monitoring_adapter.get_start_time()

        # Assert
        assert start_time == monitoring_adapter._start_time
        assert isinstance(start_time, datetime)

    @pytest.mark.asyncio
    async def test_is_ready_true(self, monitoring_adapter: MonitoringAdapter) -> None:
        """Test is_ready returns True when start_time is set."""
        # Act
        is_ready = await monitoring_adapter.is_ready()

        # Assert
        assert is_ready is True

    @pytest.mark.asyncio
    async def test_is_ready_false(self, mock_config: ServiceConfiguration) -> None:
        """Test is_ready returns False when start_time is None."""
        # Arrange
        adapter = MonitoringAdapter(mock_config)
        adapter._start_time = None

        # Act
        is_ready = await adapter.is_ready()

        # Assert
        assert is_ready is False

    @pytest.mark.asyncio
    @patch("app.infrastructure.monitoring_adapter.psutil.cpu_percent")
    @patch("app.infrastructure.monitoring_adapter.psutil.virtual_memory")
    @patch("app.infrastructure.monitoring_adapter.psutil.disk_usage")
    @patch("app.infrastructure.monitoring_adapter.time.time")
    async def test_get_detailed_health(
        self,
        mock_time: Mock,
        mock_disk_usage: Mock,
        mock_virtual_memory: Mock,
        mock_cpu_percent: Mock,
        monitoring_adapter: MonitoringAdapter,
    ) -> None:
        """Test getting detailed health status with system metrics."""
        # Arrange
        mock_cpu_percent.return_value = 45.5

        mock_memory_info = Mock()
        mock_memory_info.percent = 62.3
        mock_virtual_memory.return_value = mock_memory_info

        mock_disk_info = Mock()
        mock_disk_info.percent = 75.8
        mock_disk_usage.return_value = mock_disk_info

        # Simulate timing for NATS check
        mock_time.side_effect = [1000.0, 1000.015]  # 15ms latency

        # Act
        detailed_health = await monitoring_adapter.get_detailed_health()

        # Assert
        assert detailed_health.status == "healthy"
        assert detailed_health.service_name == "management-service"
        assert detailed_health.version == "0.1.0"
        assert detailed_health.cpu_percent == 45.5
        assert detailed_health.memory_percent == 62.3
        assert detailed_health.disk_usage_percent == 75.8
        assert detailed_health.nats_status == "healthy"
        assert (
            abs(detailed_health.nats_latency_ms - 15.0) < 0.01
        )  # Allow small floating point difference
        assert detailed_health.timestamp is not None

        # Verify system metric calls
        mock_cpu_percent.assert_called_once_with(interval=0.1)
        mock_virtual_memory.assert_called_once()
        mock_disk_usage.assert_called_once_with("/")

    @pytest.mark.asyncio
    async def test_simulate_nats_check(self, monitoring_adapter: MonitoringAdapter) -> None:
        """Test that _simulate_nats_check introduces appropriate delay."""
        # Arrange
        start_time = asyncio.get_event_loop().time()

        # Act
        await monitoring_adapter._simulate_nats_check()

        # Assert
        elapsed_time = asyncio.get_event_loop().time() - start_time
        # Should take at least 10ms (0.01 seconds)
        assert elapsed_time >= 0.01
        # But not too much longer (allow some tolerance)
        assert elapsed_time < 0.02

    @pytest.mark.asyncio
    @patch("app.infrastructure.monitoring_adapter.psutil.cpu_percent")
    async def test_get_detailed_health_cpu_interval(
        self,
        mock_cpu_percent: Mock,
        monitoring_adapter: MonitoringAdapter,
    ) -> None:
        """Test that CPU measurement uses correct interval."""
        # Arrange
        mock_cpu_percent.return_value = 50.0

        with (
            patch("app.infrastructure.monitoring_adapter.psutil.virtual_memory") as mock_vm,
            patch("app.infrastructure.monitoring_adapter.psutil.disk_usage") as mock_disk,
        ):
            mock_memory_info = Mock()
            mock_memory_info.percent = 60.0
            mock_vm.return_value = mock_memory_info

            mock_disk_info = Mock()
            mock_disk_info.percent = 70.0
            mock_disk.return_value = mock_disk_info

            # Act
            await monitoring_adapter.get_detailed_health()

            # Assert
            mock_cpu_percent.assert_called_once_with(interval=0.1)

    @pytest.mark.asyncio
    async def test_multiple_health_checks_consistent(
        self, monitoring_adapter: MonitoringAdapter
    ) -> None:
        """Test that multiple health checks return consistent service info."""
        # Act
        health1 = await monitoring_adapter.check_health()
        health2 = await monitoring_adapter.check_health()
        health3 = await monitoring_adapter.check_health()

        # Assert - Service info should be consistent
        assert health1.service_name == health2.service_name == health3.service_name
        assert health1.version == health2.version == health3.version
        assert health1.status == health2.status == health3.status
        assert health1.nats_url == health2.nats_url == health3.nats_url

        # Timestamps should be different (or at least non-decreasing)
        assert health1.timestamp <= health2.timestamp <= health3.timestamp

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, monitoring_adapter: MonitoringAdapter) -> None:
        """Test that adapter handles concurrent health checks correctly."""
        # Act - Run multiple health checks concurrently
        results = await asyncio.gather(
            monitoring_adapter.check_health(),
            monitoring_adapter.check_health(),
            monitoring_adapter.check_health(),
            monitoring_adapter.check_health(),
            monitoring_adapter.check_health(),
        )

        # Assert - All should complete successfully
        assert len(results) == 5
        for health in results:
            assert health.status == "healthy"
            assert health.service_name == "management-service"

    @pytest.mark.asyncio
    @patch(
        "app.infrastructure.monitoring_adapter.psutil.cpu_percent",
        side_effect=Exception("CPU error"),
    )
    async def test_get_detailed_health_handles_cpu_error(
        self,
        mock_cpu_percent: Mock,
        monitoring_adapter: MonitoringAdapter,
    ) -> None:
        """Test that detailed health handles CPU measurement errors."""
        # Act & Assert - Should raise the exception
        with pytest.raises(Exception) as exc_info:
            await monitoring_adapter.get_detailed_health()

        assert "CPU error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_time_immutable(self, monitoring_adapter: MonitoringAdapter) -> None:
        """Test that start time doesn't change after initialization."""
        # Arrange
        original_start_time = monitoring_adapter._start_time

        # Act - Wait a bit and check various operations
        await asyncio.sleep(0.1)
        await monitoring_adapter.check_health()
        await monitoring_adapter.get_system_status()
        current_start_time = await monitoring_adapter.get_start_time()

        # Assert - Start time should remain the same
        assert current_start_time == original_start_time
