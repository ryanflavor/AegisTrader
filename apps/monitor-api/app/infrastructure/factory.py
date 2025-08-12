"""Infrastructure factory for creating adapters and dependencies.

This module follows the Factory pattern to centralize the creation of
infrastructure components, promoting loose coupling and testability.
"""

from __future__ import annotations

from typing import Any

from ..domain.models import ServiceConfiguration
from ..ports.configuration import ConfigurationPort
from ..ports.monitoring import MonitoringPort
from ..ports.sdk_monitoring import SDKMonitoringPort
from ..ports.service_instance_repository import ServiceInstanceRepositoryPort
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort
from .aegis_sdk_kv_adapter import AegisSDKKVAdapter
from .configuration_adapter import EnvironmentConfigurationAdapter
from .monitoring_adapter import MonitoringAdapter
from .sdk_monitoring_adapter import SDKMonitoringAdapter
from .service_instance_repository_adapter import ServiceInstanceRepositoryAdapter


class InfrastructureFactory:
    """Factory for creating infrastructure adapters following hexagonal architecture.

    This factory encapsulates the creation logic for all infrastructure components,
    making it easy to swap implementations and configure dependencies.
    """

    @staticmethod
    def create_configuration_port() -> ConfigurationPort:
        """Create a configuration port adapter.

        Returns:
            ConfigurationPort implementation
        """
        return EnvironmentConfigurationAdapter()

    @staticmethod
    def create_monitoring_port(
        config: ServiceConfiguration,
        start_time: Any,
        instance_repository: ServiceInstanceRepositoryPort | None = None,
    ) -> MonitoringPort:
        """Create a monitoring port adapter.

        Args:
            config: Service configuration
            start_time: Service start time
            instance_repository: Optional service instance repository

        Returns:
            MonitoringPort implementation
        """
        # Note: MonitoringAdapter constructor expects (config, instance_repository),
        # not (config, start_time). start_time is managed internally by MonitoringAdapter
        return MonitoringAdapter(config, instance_repository)

    @staticmethod
    async def create_kv_store_port(nats_url: str) -> ServiceRegistryKVStorePort:
        """Create a KV store port adapter.

        Args:
            nats_url: NATS server URL

        Returns:
            ServiceRegistryKVStorePort implementation
        """
        adapter = AegisSDKKVAdapter()
        await adapter.connect(nats_url)
        return adapter

    @staticmethod
    def create_service_instance_repository(
        kv_store: Any, stale_threshold_seconds: int = 35
    ) -> ServiceInstanceRepositoryPort:
        """Create a service instance repository adapter.

        Args:
            kv_store: KV store instance (raw or wrapped)
            stale_threshold_seconds: Stale threshold in seconds

        Returns:
            ServiceInstanceRepositoryPort implementation
        """
        # Get raw KV if it's wrapped
        if hasattr(kv_store, "raw_kv"):
            kv_store = kv_store.raw_kv
        return ServiceInstanceRepositoryAdapter(kv_store, stale_threshold_seconds)

    @staticmethod
    def create_sdk_monitoring_port(kv_store: Any) -> SDKMonitoringPort:
        """Create an SDK monitoring port adapter.

        Args:
            kv_store: KV store instance

        Returns:
            SDKMonitoringPort implementation
        """
        # Get raw KV if it's wrapped
        if hasattr(kv_store, "raw_kv"):
            kv_store = kv_store.raw_kv
        return SDKMonitoringAdapter(kv_store)

    @classmethod
    def create_all_adapters(
        cls, config: ServiceConfiguration, start_time: Any, kv_store: Any
    ) -> dict[str, Any]:
        """Create all infrastructure adapters.

        Args:
            config: Service configuration
            start_time: Service start time
            kv_store: KV store instance

        Returns:
            Dictionary of all adapters keyed by port name
        """
        # Create instance repository first since monitoring depends on it
        instance_repository = cls.create_service_instance_repository(
            kv_store, config.stale_threshold_seconds
        )

        return {
            "configuration": cls.create_configuration_port(),
            "monitoring": cls.create_monitoring_port(config, start_time, instance_repository),
            "service_instance_repository": instance_repository,
            "sdk_monitoring": cls.create_sdk_monitoring_port(kv_store),
        }
