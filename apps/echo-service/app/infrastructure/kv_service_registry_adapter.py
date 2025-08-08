"""Infrastructure adapter for service registry using NATS KV store.

This adapter implements the ServiceRegistryPort using NATS KV store,
providing service definition and instance registration capabilities.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import KVOptions
from aegis_sdk.ports.kv_store import KVStorePort

from ..domain.models import ServiceRegistrationData
from ..ports.service_registry import RegistrationError, ServiceRegistryPort

logger = logging.getLogger(__name__)


class KVServiceRegistryAdapter(ServiceRegistryPort):
    """NATS KV implementation of the service registry port."""

    def __init__(self, kv_store: KVStorePort) -> None:
        """Initialize the KV service registry adapter.

        Args:
            kv_store: NATS KV store port for data persistence
        """
        self._kv_store = kv_store
        self._instance_key_prefix = "service-instances"

    async def register_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Register service definition with the platform.

        Service definitions are stored with simple keys like "echo-service"
        without any prefix, as expected by monitor-api.
        """
        try:
            # Check if service already exists
            service_name = registration.definition.service_name
            existing = await self._kv_store.get(service_name)

            if existing:
                logger.info(f"Service definition already exists for {service_name}, updating...")
                await self.update_service_definition(registration)
            else:
                # Store service definition with no prefix - just the service name
                service_def = registration.to_service_definition_dict()
                await self._kv_store.put(
                    key=service_name,  # No prefix, just service name
                    value=service_def,
                    options=None,  # No TTL for service definitions
                )
                logger.info(
                    f"Registered service definition: {service_name} "
                    f"(owner: {registration.definition.owner}, "
                    f"version: {registration.definition.version})"
                )

        except Exception as e:
            logger.error(f"Failed to register service definition: {e}")
            raise RegistrationError(
                f"Failed to register service definition: {e}",
                service_name=registration.definition.service_name,
            ) from e

    async def update_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Update existing service definition."""
        try:
            service_name = registration.definition.service_name

            # Update the updated_at timestamp
            service_def = registration.to_service_definition_dict()
            service_def["updated_at"] = datetime.now(UTC).isoformat()

            await self._kv_store.put(
                key=service_name,
                value=service_def,
                options=None,  # No TTL for service definitions
            )

            logger.info(
                f"Updated service definition: {service_name} "
                f"(version: {registration.definition.version})"
            )

        except Exception as e:
            logger.error(f"Failed to update service definition: {e}")
            raise RegistrationError(
                f"Failed to update service definition: {e}",
                service_name=registration.definition.service_name,
            ) from e

    async def check_service_exists(self, service_name: str) -> bool:
        """Check if a service definition already exists."""
        try:
            entry = await self._kv_store.get(service_name)
            return entry is not None
        except Exception as e:
            logger.warning(f"Error checking service existence: {e}")
            return False

    async def register_instance(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Register a service instance with TTL.

        Instances are stored with keys like "service-instances__echo-service__<instance-id>"
        as expected by monitor-api.
        """
        try:
            # Create instance key with double underscore separator
            key = f"{self._instance_key_prefix}__{service_name}__{instance_id}"

            # Ensure required fields are present
            if "lastHeartbeat" not in instance_data:
                instance_data["lastHeartbeat"] = datetime.now(UTC).isoformat()

            if "status" not in instance_data:
                instance_data["status"] = ServiceStatus.ACTIVE.value

            # Store instance with TTL
            await self._kv_store.put(
                key=key,
                value=instance_data,
                options=KVOptions(ttl=ttl_seconds),
            )

            logger.debug(
                f"Registered instance: {service_name}/{instance_id} with TTL {ttl_seconds}s"
            )

        except Exception as e:
            logger.error(f"Failed to register instance: {e}")
            raise RegistrationError(
                f"Failed to register instance {instance_id}: {e}",
                service_name=service_name,
            ) from e

    async def update_instance_heartbeat(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Update instance heartbeat to maintain registration."""
        try:
            key = f"{self._instance_key_prefix}__{service_name}__{instance_id}"

            # Check if instance exists
            existing = await self._kv_store.get(key)
            if not existing:
                # Re-register if lost
                logger.info(f"Re-registering lost instance: {service_name}/{instance_id}")
                await self.register_instance(service_name, instance_id, instance_data, ttl_seconds)
                return

            # Update heartbeat timestamp
            instance_data["lastHeartbeat"] = datetime.now(UTC).isoformat()

            # Update with TTL
            await self._kv_store.put(
                key=key,
                value=instance_data,
                options=KVOptions(ttl=ttl_seconds),
            )

            logger.debug(f"Updated heartbeat: {service_name}/{instance_id}")

        except Exception as e:
            logger.warning(f"Failed to update heartbeat: {e}")
            # Don't raise - heartbeat failures should be recoverable
            # The instance will be re-registered on next attempt

    async def deregister_instance(self, service_name: str, instance_id: str) -> None:
        """Remove a service instance from the registry."""
        try:
            key = f"{self._instance_key_prefix}__{service_name}__{instance_id}"
            success = await self._kv_store.delete(key)

            if success:
                logger.info(f"Deregistered instance: {service_name}/{instance_id}")
            else:
                logger.warning(
                    f"Instance not found for deregistration: {service_name}/{instance_id}"
                )

        except Exception as e:
            logger.error(f"Failed to deregister instance: {e}")
            raise RegistrationError(
                f"Failed to deregister instance {instance_id}: {e}",
                service_name=service_name,
            ) from e
