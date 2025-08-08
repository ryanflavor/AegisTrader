"""Adapter for SDK's KVServiceRegistry to match our port interface.

This thin adapter wraps the aegis-sdk KVServiceRegistry to implement
our ServiceRegistryPort interface, maintaining clean architecture boundaries.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure import KVServiceRegistry

from ..domain.models import ServiceRegistrationData
from ..ports.service_registry import RegistrationError, ServiceRegistryPort

logger = logging.getLogger(__name__)


class KVRegistryAdapter(ServiceRegistryPort):
    """Adapter wrapping SDK's KVServiceRegistry for our port interface."""

    def __init__(self, kv_registry: KVServiceRegistry, service_name: str, instance_id: str) -> None:
        """Initialize the KV registry adapter.

        Args:
            kv_registry: SDK's KVServiceRegistry instance
            service_name: Name of this service
            instance_id: Instance ID of this service
        """
        self._registry = kv_registry
        self._service_name = service_name
        self._instance_id = instance_id
        self._current_instance: ServiceInstance | None = None

    async def register_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Register service definition with the platform.

        Note: SDK's KVServiceRegistry focuses on instance registration.
        Service definitions are typically managed at a higher level.
        This method is kept for interface compatibility.

        Args:
            registration: Service registration data containing definition and metadata
        """
        # Log the definition for visibility
        logger.info(
            f"Service definition registered: {registration.definition.service_name} "
            f"v{registration.definition.version} by {registration.definition.owner}"
        )
        # In a real implementation, this might store in a separate KV bucket
        # For now, we just log it as the SDK focuses on instance registration

    async def update_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Update existing service definition.

        Args:
            registration: Updated service registration data
        """
        logger.info(
            f"Service definition updated: {registration.definition.service_name} "
            f"v{registration.definition.version}"
        )

    async def check_service_exists(self, service_name: str) -> bool:
        """Check if a service definition already exists.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service exists, False otherwise
        """
        try:
            # Check if any instances exist for this service
            instances = await self._registry.list_instances(ServiceName(service_name))
            return len(instances) > 0
        except Exception:
            return False

    async def register_instance(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Register a service instance with TTL.

        Args:
            service_name: Name of the service
            instance_id: Unique instance identifier
            instance_data: Instance metadata and status
            ttl_seconds: Time-to-live in seconds

        Raises:
            RegistrationError: If instance registration fails
        """
        try:
            # Create ServiceInstance from SDK models
            instance = ServiceInstance(
                service_name=ServiceName(service_name),
                instance_id=InstanceId(instance_id),
                version=instance_data.get("version", "1.0.0"),
                status=instance_data.get("status", "ACTIVE"),
                metadata=instance_data.get("metadata", {}),
                last_heartbeat=datetime.now(UTC),
            )

            # Register with TTL for auto-expiry
            await self._registry.register(instance=instance, ttl_seconds=ttl_seconds)
            self._current_instance = instance

            logger.info(
                f"Instance registered: {service_name}/{instance_id} with TTL={ttl_seconds}s"
            )

        except Exception as e:
            logger.error(f"Failed to register instance: {e}")
            raise RegistrationError(
                f"Failed to register instance {instance_id}", service_name=service_name
            ) from e

    async def update_instance_heartbeat(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Update instance heartbeat to maintain registration.

        The SDK's KVServiceRegistry automatically re-registers if needed.

        Args:
            service_name: Name of the service
            instance_id: Unique instance identifier
            instance_data: Updated instance metadata
            ttl_seconds: Time-to-live in seconds

        Raises:
            RegistrationError: If heartbeat update fails
        """
        try:
            # Update instance with fresh heartbeat timestamp
            instance = ServiceInstance(
                service_name=ServiceName(service_name),
                instance_id=InstanceId(instance_id),
                version=instance_data.get("version", "1.0.0"),
                status=instance_data.get("status", "ACTIVE"),
                metadata=instance_data.get("metadata", {}),
                last_heartbeat=datetime.now(UTC),
            )

            # SDK's update_heartbeat will re-register if instance expired
            await self._registry.update_heartbeat(instance=instance, ttl_seconds=ttl_seconds)
            self._current_instance = instance

            logger.debug(f"Heartbeat updated: {service_name}/{instance_id}")

        except Exception as e:
            logger.error(f"Failed to update heartbeat: {e}")
            raise RegistrationError(
                f"Failed to update heartbeat for {instance_id}", service_name=service_name
            ) from e

    async def deregister_instance(self, service_name: str, instance_id: str) -> None:
        """Remove a service instance from the registry.

        Args:
            service_name: Name of the service
            instance_id: Instance to deregister

        Raises:
            RegistrationError: If deregistration fails
        """
        try:
            await self._registry.deregister(ServiceName(service_name), InstanceId(instance_id))
            logger.info(f"Instance deregistered: {service_name}/{instance_id}")
        except Exception as e:
            logger.error(f"Failed to deregister instance: {e}")
            raise RegistrationError(
                f"Failed to deregister instance {instance_id}", service_name=service_name
            ) from e

    async def update_heartbeat(self) -> bool:
        """Simplified heartbeat update using stored instance.

        Returns:
            True if heartbeat was successful
        """
        if not self._current_instance:
            logger.warning("No instance registered to update heartbeat")
            return False

        try:
            # Update with current timestamp
            self._current_instance.last_heartbeat = datetime.now(UTC)
            await self._registry.update_heartbeat(instance=self._current_instance, ttl_seconds=30)
            return True
        except Exception as e:
            logger.error(f"Heartbeat update failed: {e}")
            return False

    async def deregister(self) -> None:
        """Deregister the current instance."""
        if self._current_instance:
            await self.deregister_instance(
                str(self._current_instance.service_name),
                str(self._current_instance.instance_id),
            )
            self._current_instance = None
