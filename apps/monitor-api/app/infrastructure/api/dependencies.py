"""FastAPI dependency injection setup.

This module configures dependency injection for the FastAPI application,
providing a clean separation between the framework and the application logic.
"""

from __future__ import annotations

from functools import lru_cache

from ...application.monitoring_service import MonitoringService
from ...application.service_registry_service import ServiceRegistryService
from ...domain.models import ServiceConfiguration
from ...ports.configuration import ConfigurationPort
from ...ports.monitoring import MonitoringPort
from ...ports.service_registry_kv_store import ServiceRegistryKVStorePort
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
    # Try to get instance repository if available
    try:
        from ..connection_manager import get_connection_manager

        manager = get_connection_manager()
        instance_repository = manager.instance_repository
    except Exception:
        instance_repository = None

    return MonitoringAdapter(config, instance_repository)


@lru_cache
def get_monitoring_service() -> MonitoringService:
    """Get the monitoring service instance.

    Returns:
        MonitoringService: Application service for monitoring
    """
    monitoring_port = get_monitoring_port()
    config_port = get_configuration_port()
    return MonitoringService(monitoring_port, config_port)


def get_kv_store() -> ServiceRegistryKVStorePort:
    """Get the KV Store port instance from the connection manager.

    Returns:
        ServiceRegistryKVStorePort: KV Store port implementation
    """
    from ..connection_manager import get_connection_manager

    manager = get_connection_manager()
    return manager.kv_store


def get_service_registry() -> ServiceRegistryService:
    """Get the service registry instance.

    Returns:
        ServiceRegistryService: Application service for service registry
    """
    from ...application.service_registry_service import ServiceRegistryService

    kv_store = get_kv_store()
    return ServiceRegistryService(kv_store)
