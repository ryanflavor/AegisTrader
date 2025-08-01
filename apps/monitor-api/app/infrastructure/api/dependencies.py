"""FastAPI dependency injection setup.

This module configures dependency injection for the FastAPI application,
providing a clean separation between the framework and the application logic.
"""

from functools import lru_cache

from ...application.monitoring_service import MonitoringService
from ...domain.models import ServiceConfiguration
from ...ports.configuration import ConfigurationPort
from ...ports.monitoring import MonitoringPort
from ..configuration_adapter import EnvironmentConfigurationAdapter
from ..monitoring_adapter import MonitoringAdapter


@lru_cache
def get_configuration_port() -> ConfigurationPort:
    """Get the configuration port instance.

    Returns:
        ConfigurationPort: Configuration port implementation
    """
    return EnvironmentConfigurationAdapter()


@lru_cache
def get_service_configuration() -> ServiceConfiguration:
    """Get the service configuration.

    Returns:
        ServiceConfiguration: Loaded service configuration
    """
    config_port = get_configuration_port()
    return config_port.load_configuration()


@lru_cache
def get_monitoring_port() -> MonitoringPort:
    """Get the monitoring port instance.

    Returns:
        MonitoringPort: Monitoring port implementation
    """
    config = get_service_configuration()
    return MonitoringAdapter(config)


@lru_cache
def get_monitoring_service() -> MonitoringService:
    """Get the monitoring service instance.

    Returns:
        MonitoringService: Application service for monitoring
    """
    monitoring_port = get_monitoring_port()
    config_port = get_configuration_port()
    return MonitoringService(monitoring_port, config_port)
