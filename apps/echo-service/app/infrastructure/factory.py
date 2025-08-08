"""Factory for creating the echo service application with proper dependency injection.

This factory follows the Factory Pattern to decouple the application core from
concrete infrastructure implementations, enabling easy swapping for testing.
Uses aegis-sdk components for clean hexagonal architecture.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure import (
    KVServiceRegistry,
    NATSAdapter,
    NATSConnectionConfig,
    NATSKVStore,
)

from ..application.echo_service import EchoApplicationService
from ..ports.configuration import ConfigurationPort
from ..ports.service_bus import ServiceBusPort
from ..ports.service_registry import ServiceRegistryPort
from .aegis_service_bus_adapter import AegisServiceBusAdapter
from .environment_configuration_adapter import EnvironmentConfigurationAdapter
from .kv_registry_adapter import KVRegistryAdapter

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
            instance_id = configuration.get_instance_id()
            service_name = configuration.get_service_name()
            version = configuration.get_service_version()

            logger.info(
                f"Environment Detection:\n"
                f"  Running in Kubernetes: {in_k8s}\n"
                f"  Instance ID: {instance_id}\n"
                f"  Service Name: {service_name}\n"
                f"  Version: {version}\n"
                f"  NATS URL: {configuration.get_nats_url() or 'auto-detect'}"
            )

            # Create NATS connection configuration using SDK
            nats_config = NATSConnectionConfig(
                servers=[configuration.get_nats_url()] if configuration.get_nats_url() else None,
                name=f"{service_name}-{instance_id}",
                service_name=ServiceName(service_name),
                instance_id=InstanceId(instance_id),
                connect_timeout=5.0,
                reconnect_time_wait=2.0,
                max_reconnect_attempts=60,
                enable_jetstream=True,
            )

            # Create SDK's NATS adapter and connect
            nats_adapter = NATSAdapter(config=nats_config)
            await nats_adapter.connect()
            logger.info("NATS connection established using SDK")

            # Create KV store for service registry
            kv_store = NATSKVStore(
                nats_adapter=nats_adapter,
                bucket_name="service_registry",
                ttl_seconds=30,  # 30 second TTL for heartbeats
            )
            await kv_store.initialize()

            # Create SDK's KV-based service registry with auto re-registration
            kv_service_registry = KVServiceRegistry(kv_store=kv_store)

            # Create our adapter that wraps the SDK registry
            service_registry = KVRegistryAdapter(
                kv_registry=kv_service_registry,
                service_name=service_name,
                instance_id=instance_id,
            )

            # Register service instance with metadata
            await service_registry.register_instance(
                service_name=service_name,
                instance_id=instance_id,
                instance_data={
                    "version": version,
                    "status": "ACTIVE",
                    "metadata": {
                        "environment": "kubernetes" if in_k8s else "local",
                        "nats_url": configuration.get_nats_url() or "auto",
                    },
                },
                ttl_seconds=30,  # 30 second TTL for auto-expiry
            )
            logger.info("Service registered with auto re-registration support")

            # Create service bus adapter wrapping SDK's NATS adapter
            service_bus = AegisServiceBusAdapter(
                nats_adapter=nats_adapter,
                service_name=service_name,
                instance_id=instance_id,
            )

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
            service_registry: Optional mock service registry
            config_defaults: Optional default configuration values

        Returns:
            Configured echo application service for testing
        """
        # Use provided configuration or create test configuration
        if configuration is None:
            test_defaults = {
                "service_name": "echo-service-test",
                "version": "1.0.0",
                "service_type": "service",
                "debug": True,
                "instance_id": f"test-{uuid.uuid4().hex[:8]}",
                "nats_url": "nats://localhost:4222",
            }
            if config_defaults:
                test_defaults.update(config_defaults)

            # Set environment variables for test configuration
            for key, value in test_defaults.items():
                os.environ[key.upper()] = str(value)

            configuration = EnvironmentConfigurationAdapter()

        # Create and return application service with test dependencies
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
            service_registry: Optional custom service registry

        Returns:
            Configured echo application service
        """
        return EchoApplicationService(
            service_bus=service_bus,
            configuration=configuration,
            service_registry=service_registry,
        )
