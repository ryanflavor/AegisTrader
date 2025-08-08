"""Monitoring port interface.

Defines the protocol interface for monitoring and health check operations.
This port is part of the hexagonal architecture and should be implemented
by infrastructure adapters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..domain.models import DetailedHealthStatus, HealthStatus, SystemStatus


class MonitoringPort(Protocol):
    """Protocol interface for monitoring operations."""

    async def check_health(self) -> HealthStatus:
        """Check the health status of the service.

        Returns:
            HealthStatus: Current health status of the service

        Raises:
            HealthCheckFailedException: If health check fails
        """
        ...

    async def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status information.

        Returns:
            SystemStatus: Current system status including uptime and environment

        Raises:
            ServiceUnavailableException: If unable to retrieve system status
        """
        ...

    async def get_start_time(self) -> datetime:
        """Get the service start time.

        Returns:
            datetime: When the service was started
        """
        ...

    async def is_ready(self) -> bool:
        """Check if the service is ready to handle requests.

        Returns:
            bool: True if service is ready, False otherwise
        """
        ...

    async def get_detailed_health(self) -> DetailedHealthStatus:
        """Get detailed health status with system metrics.

        Returns:
            DetailedHealthStatus: Detailed health information including metrics

        Raises:
            HealthCheckFailedException: If unable to get detailed health
        """
        ...
