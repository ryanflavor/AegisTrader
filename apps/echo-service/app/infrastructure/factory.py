"""Factory for creating the echo service application with proper dependency injection.

This factory follows the Factory Pattern to decouple the application core from
concrete infrastructure implementations, enabling easy swapping for testing.
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_sdk.developer import quick_setup
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

from ..application.echo_service import EchoApplicationService
from ..ports.configuration import ConfigurationPort
from ..ports.service_bus import ServiceBusPort
from ..ports.service_registry import ServiceRegistryPort
from .aegis_service_bus_adapter import AegisServiceBusAdapter
from .environment_configuration_adapter import EnvironmentConfigurationAdapter
from .kv_service_registry_adapter import KVServiceRegistryAdapter

logger = logging.getLogger(__name__)


class EchoServiceFactory:
    """Factory for creating echo service instances with dependencies."""

    @staticmethod
    async def create_production_service() -> EchoApplicationService:
        """Create a production echo service with real infrastructure.

        Returns:
            Configured echo application service

        Raises:
            RuntimeError: If unable to create service
        """
        try:
            # Create configuration adapter
            configuration = EnvironmentConfigurationAdapter()

            # Log environment detection
            in_k8s = configuration.is_kubernetes_environment()
            logger.info(
                f"Environment Detection:\n"
                f"  Running in Kubernetes: {in_k8s}\n"
                f"  Instance ID: {configuration.get_instance_id()}\n"
                f"  NATS URL: {configuration.get_nats_url() or 'auto-detect'}"
            )

            # Create Aegis SDK service
            aegis_service = await quick_setup(
                service_name=configuration.get_service_name(),
                service_type=configuration.get_service_type(),
                version=configuration.get_service_version(),
                debug=configuration.is_debug_enabled(),
            )

            # Create service bus adapter
            service_bus = AegisServiceBusAdapter(aegis_service)

            # Create KV store and service registry
            service_registry = None
            try:
                # Access the NATS connection from the aegis service
                if hasattr(aegis_service, "_bus") and hasattr(aegis_service._bus, "_conn"):
                    nats_conn = aegis_service._bus._conn
                    kv_store = NATSKVStore(
                        conn=nats_conn,
                        bucket="AEGIS_REGISTRY",  # Same bucket as monitor-api
                    )
                    await kv_store.initialize()
                    service_registry = KVServiceRegistryAdapter(kv_store)
                    logger.info("Service registry initialized successfully")
                else:
                    logger.warning("Could not access NATS connection for service registry")
            except Exception as e:
                logger.warning(f"Failed to initialize service registry: {e}")
                # Continue without registry - non-critical for echo service

            # Create and return application service
            return EchoApplicationService(
                service_bus=service_bus,
                configuration=configuration,
                service_registry=service_registry,
            )

        except Exception as e:
            logger.error(f"Failed to create production service: {e}")
            raise RuntimeError(f"Unable to create echo service: {e}") from e

    @staticmethod
    def create_test_service(
        service_bus: ServiceBusPort,
        configuration: ConfigurationPort | None = None,
        service_registry: ServiceRegistryPort | None = None,
        config_defaults: dict[str, Any] | None = None,
    ) -> EchoApplicationService:
        """Create a test echo service with injected dependencies.

        Args:
            service_bus: Mock or test service bus implementation
            configuration: Optional mock configuration
            config_defaults: Optional default configuration values

        Returns:
            Configured echo application service for testing
        """
        # Use provided configuration or create test configuration
        if configuration is None:
            test_defaults = {
                "service_name": "echo-service-test",
                "version": "test",
                "service_type": "service",
                "debug": True,
            }
            if config_defaults:
                test_defaults.update(config_defaults)
            configuration = EnvironmentConfigurationAdapter(defaults=test_defaults)

        # Create and return application service with test registry
        return EchoApplicationService(
            service_bus=service_bus,
            configuration=configuration,
            service_registry=service_registry,
        )

    @staticmethod
    async def create_with_custom_adapters(
        service_bus: ServiceBusPort,
        configuration: ConfigurationPort,
        service_registry: ServiceRegistryPort | None = None,
    ) -> EchoApplicationService:
        """Create echo service with custom adapter implementations.

        This method allows for complete flexibility in providing
        infrastructure implementations, useful for testing or
        alternative deployment scenarios.

        Args:
            service_bus: Custom service bus implementation
            configuration: Custom configuration implementation

        Returns:
            Configured echo application service
        """
        return EchoApplicationService(
            service_bus=service_bus,
            configuration=configuration,
            service_registry=service_registry,
        )
