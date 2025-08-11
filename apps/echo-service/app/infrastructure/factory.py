"""Factory for creating the echo service using aegis-sdk-dev bootstrap utilities.

This factory uses aegis-sdk-dev's bootstrap_sdk function to initialize
all infrastructure components properly, avoiding any wheel reinvention.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from aegis_sdk_dev.quickstart.bootstrap import (
    SDKBootstrapConfig,
    bootstrap_sdk,
    cleanup_service_context,
)

from ..application.echo_service import EchoApplicationService

logger = logging.getLogger(__name__)


class EchoServiceFactory:
    """Factory for creating echo service instances using SDK-dev bootstrap."""

    @staticmethod
    async def create_production_service() -> EchoApplicationService:
        """Create a production echo service using SDK-dev bootstrap.

        Returns:
            Configured echo application service

        Raises:
            RuntimeError: If unable to create service
        """
        try:
            # Get configuration from environment
            nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
            service_name = os.getenv("SERVICE_NAME", "echo-service")
            instance_id = os.getenv("SERVICE_INSTANCE_ID")
            version = os.getenv("SERVICE_VERSION", "1.0.0")

            # Log configuration
            logger.info(
                f"Bootstrapping Echo Service:\n"
                f"  Service Name: {service_name}\n"
                f"  Instance ID: {instance_id or 'auto-generated'}\n"
                f"  Version: {version}\n"
                f"  NATS URL: {nats_url}"
            )

            # Bootstrap SDK using aegis-sdk-dev
            bootstrap_config = SDKBootstrapConfig(
                nats_url=nats_url,
                service_name=service_name,
                kv_bucket="service_registry",
                enable_watchable=True,
            )

            context = await bootstrap_sdk(bootstrap_config)

            # Create echo service with bootstrapped components
            service = EchoApplicationService(
                service_name=service_name,
                message_bus=context.message_bus,
                instance_id=instance_id,
                version=version,
                service_registry=context.service_registry,
                service_discovery=context.service_discovery,
                registry_ttl=30.0,
                heartbeat_interval=15.0,
                enable_registration=True,
            )

            # Store context for cleanup
            service._bootstrap_context = context

            return service

        except Exception as e:
            logger.error(f"Failed to create production service: {e}")
            raise RuntimeError(f"Unable to create echo service: {e}") from e

    @staticmethod
    async def cleanup_service(service: EchoApplicationService) -> None:
        """Clean up service and its bootstrap context.

        Args:
            service: Service to clean up
        """
        try:
            # Stop the service
            await service.stop()

            # Clean up bootstrap context if present
            if hasattr(service, "_bootstrap_context"):
                await cleanup_service_context(service._bootstrap_context)

        except Exception as e:
            logger.error(f"Error during service cleanup: {e}")

    @staticmethod
    def create_test_service(**kwargs: Any) -> EchoApplicationService:
        """Create a test echo service with mock dependencies.

        Args:
            **kwargs: Configuration overrides for testing

        Returns:
            Configured echo application service for testing
        """
        from unittest.mock import AsyncMock

        from aegis_sdk.ports.message_bus import MessageBusPort
        from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort
        from aegis_sdk.ports.service_registry import ServiceRegistryPort

        # Create mock dependencies
        mock_message_bus = AsyncMock(spec=MessageBusPort)
        mock_registry = AsyncMock(spec=ServiceRegistryPort) if kwargs.get("with_registry") else None
        mock_discovery = (
            AsyncMock(spec=ServiceDiscoveryPort) if kwargs.get("with_discovery") else None
        )

        # Create service with mocks
        service = EchoApplicationService(
            service_name=kwargs.get("service_name", "echo-service-test"),
            message_bus=mock_message_bus,
            instance_id=kwargs.get("instance_id", "test-instance"),
            version=kwargs.get("version", "1.0.0"),
            service_registry=mock_registry,
            service_discovery=mock_discovery,
            heartbeat_interval=kwargs.get("heartbeat_interval", 15.0),
            registry_ttl=kwargs.get("registry_ttl", 30.0),
            enable_registration=False,  # Disable for tests
        )

        return service
