"""Monitoring port interface.

Defines the abstract interface for monitoring and health check operations.
This port is part of the hexagonal architecture and should be implemented
by infrastructure adapters.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from ..domain.models import HealthStatus, SystemStatus


class MonitoringPort(ABC):
    """Abstract interface for monitoring operations."""

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Check the health status of the service.

        Returns:
            HealthStatus: Current health status of the service

        Raises:
            HealthCheckFailedException: If health check fails
        """
        pass

    @abstractmethod
    async def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status information.

        Returns:
            SystemStatus: Current system status including uptime and environment

        Raises:
            ServiceUnavailableException: If unable to retrieve system status
        """
        pass

    @abstractmethod
    async def get_start_time(self) -> datetime:
        """Get the service start time.

        Returns:
            datetime: When the service was started
        """
        pass

    @abstractmethod
    async def is_ready(self) -> bool:
        """Check if the service is ready to handle requests.

        Returns:
            bool: True if service is ready, False otherwise
        """
        pass
