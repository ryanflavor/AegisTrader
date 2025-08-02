"""Application service for monitoring operations.

This service orchestrates monitoring operations using domain models and ports.
It contains the business logic for health checks and system status.
"""

from ..domain.exceptions import HealthCheckFailedException, ServiceUnavailableException
from ..domain.models import HealthStatus, SystemStatus
from ..ports.configuration import ConfigurationPort
from ..ports.monitoring import MonitoringPort


class MonitoringService:
    """Application service that orchestrates monitoring operations."""

    def __init__(
        self,
        monitoring_port: MonitoringPort,
        configuration_port: ConfigurationPort,
    ):
        """Initialize the monitoring service.

        Args:
            monitoring_port: Port for monitoring operations
            configuration_port: Port for configuration management
        """
        self._monitoring_port = monitoring_port
        self._configuration_port = configuration_port

    async def get_health_status(self) -> HealthStatus:
        """Get the current health status of the service.

        Returns:
            HealthStatus: Current health status

        Raises:
            HealthCheckFailedException: If unable to determine health status
        """
        try:
            return await self._monitoring_port.check_health()
        except Exception as e:
            raise HealthCheckFailedException(f"Failed to check health: {str(e)}") from e

    async def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status.

        Returns:
            SystemStatus: Current system status

        Raises:
            ServiceUnavailableException: If unable to retrieve system status
        """
        try:
            return await self._monitoring_port.get_system_status()
        except Exception as e:
            raise ServiceUnavailableException(
                f"Failed to get system status: {str(e)}"
            ) from e

    async def check_readiness(self) -> dict[str, str]:
        """Check if the service is ready to handle requests.

        Returns:
            dict: Readiness status

        Raises:
            ServiceUnavailableException: If service is not ready
        """
        try:
            is_ready = await self._monitoring_port.is_ready()
            if not is_ready:
                raise ServiceUnavailableException("Service is not ready")
            return {"status": "ready"}
        except Exception as e:
            raise ServiceUnavailableException(
                f"Readiness check failed: {str(e)}"
            ) from e

    def get_welcome_message(self) -> dict[str, str]:
        """Get the welcome message for the root endpoint.

        Returns:
            dict: Welcome message
        """
        return {"message": "Welcome to AegisTrader Management Service"}
