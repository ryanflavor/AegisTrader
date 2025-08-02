"""Monitoring adapter implementation.

Concrete implementation of the MonitoringPort interface.
"""

import asyncio
import os
import time
from datetime import datetime

import psutil

from ..domain.models import (
    DetailedHealthStatus,
    HealthStatus,
    ServiceConfiguration,
    SystemStatus,
)
from ..ports.monitoring import MonitoringPort


class MonitoringAdapter(MonitoringPort):
    """Concrete implementation of monitoring operations."""

    def __init__(self, config: ServiceConfiguration):
        """Initialize the monitoring adapter.

        Args:
            config: Service configuration
        """
        self._config = config
        self._start_time = datetime.now()

    async def check_health(self) -> HealthStatus:
        """Check the health status of the service.

        Returns:
            HealthStatus: Current health status
        """
        # In a real implementation, this would check actual service dependencies
        # For now, we'll return a healthy status
        return HealthStatus(
            status="healthy",
            service_name="management-service",
            version="0.1.0",
            nats_url=self._config.nats_url,
            timestamp=datetime.now(),
        )

    async def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status information.

        Returns:
            SystemStatus: Current system status
        """
        current_time = datetime.now()
        uptime_seconds = (current_time - self._start_time).total_seconds()

        return SystemStatus(
            timestamp=current_time,
            uptime_seconds=uptime_seconds,
            environment=self._config.environment,
            connected_services=0,  # Will be implemented when NATS integration is added
            deployment_version=os.getenv("DEPLOYMENT_VERSION", "v1.0.0-demo"),
            start_time=self._start_time,
        )

    async def get_start_time(self) -> datetime:
        """Get the service start time.

        Returns:
            datetime: When the service was started
        """
        return self._start_time

    async def is_ready(self) -> bool:
        """Check if the service is ready to handle requests.

        Returns:
            bool: True if service is ready
        """
        # In a real implementation, this would check if all dependencies are ready
        # For now, we'll return True after a basic check
        return self._start_time is not None

    async def get_detailed_health(self) -> DetailedHealthStatus:
        """Get detailed health status with system metrics.

        Returns:
            DetailedHealthStatus: Detailed health information
        """
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage("/")

        # Check NATS connection (simulated)
        nats_start = time.time()
        # In real implementation, this would ping NATS
        await self._simulate_nats_check()
        nats_latency = (time.time() - nats_start) * 1000  # Convert to ms

        return DetailedHealthStatus(
            status="healthy",
            service_name="management-service",
            version="0.1.0",
            cpu_percent=cpu_percent,
            memory_percent=memory_info.percent,
            disk_usage_percent=disk_info.percent,
            nats_status="healthy",
            nats_latency_ms=nats_latency,
            timestamp=datetime.now(),
        )

    async def _simulate_nats_check(self) -> None:
        """Simulate NATS connection check."""
        # Simulate network latency
        await asyncio.sleep(0.01)  # 10ms simulated latency
