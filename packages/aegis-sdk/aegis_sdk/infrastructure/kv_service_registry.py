"""KV Store-based implementation of the Service Registry port."""

from __future__ import annotations

from ..domain.exceptions import KVStoreError
from ..domain.models import KVOptions, ServiceInstance
from ..ports.kv_store import KVStorePort
from ..ports.logger import LoggerPort
from ..ports.service_registry import ServiceRegistryPort


class KVServiceRegistry(ServiceRegistryPort):
    """Service registry implementation using KV Store.

    This adapter implements service registration using a key-value store
    with TTL support for automatic expiration of stale registrations.
    """

    def __init__(self, kv_store: KVStorePort, logger: LoggerPort | None = None):
        """Initialize KV-based service registry.

        Args:
            kv_store: The KV store port implementation
            logger: Optional logger for debugging
        """
        self._kv_store = kv_store
        self._logger = logger
        self._key_prefix = "service-instances"

    def _make_key(self, service_name: str, instance_id: str) -> str:
        """Generate registry key for a service instance.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier

        Returns:
            Registry key following pattern: service-instances.{service}.{instance}
        """
        return f"{self._key_prefix}.{service_name}.{instance_id}"

    async def register(self, instance: ServiceInstance, ttl_seconds: int) -> None:
        """Register a service instance with TTL.

        The instance's heartbeat timestamp should already be updated by the caller.
        This method focuses on the infrastructure concern of storing in KV.
        """
        key = self._make_key(instance.service_name, instance.instance_id)

        # Validate TTL
        if ttl_seconds <= 0:
            raise ValueError(f"TTL must be positive, got {ttl_seconds}")

        # Store instance data with TTL
        try:
            await self._kv_store.put(
                key,
                instance.model_dump(by_alias=True),  # Use camelCase for compatibility
                options=KVOptions(ttl=int(ttl_seconds)),  # Convert to int for KVOptions
            )

            if self._logger:
                self._logger.info(
                    "Service instance registered",
                    service=instance.service_name,
                    instance=instance.instance_id,
                    ttl=ttl_seconds,
                    status=instance.status,
                )
        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to register service instance",
                    service=instance.service_name,
                    instance=instance.instance_id,
                    error=str(e),
                )
            raise KVStoreError(
                f"Failed to register instance {instance.instance_id}",
                operation="register",
                key=key,
            ) from e

    async def update_heartbeat(self, instance: ServiceInstance, ttl_seconds: int) -> None:
        """Update heartbeat for a service instance.

        If the instance is not found in the registry, it will be re-registered.
        This provides resilience against temporary KV store failures.
        """
        key = self._make_key(instance.service_name, instance.instance_id)

        try:
            # Check if entry exists
            entry = await self._kv_store.get(key)
            if not entry:
                # Entry was lost, re-register
                if self._logger:
                    self._logger.info(
                        "Re-registering lost service instance",
                        service=instance.service_name,
                        instance=instance.instance_id,
                    )
                await self.register(instance, ttl_seconds)
                return

            # Update with TTL (heartbeat timestamp already updated by caller)
            await self._kv_store.put(
                key,
                instance.model_dump(by_alias=True),
                options=KVOptions(ttl=ttl_seconds),
            )

            if self._logger:
                self._logger.debug(
                    "Heartbeat updated",
                    service=instance.service_name,
                    instance=instance.instance_id,
                    ttl=ttl_seconds,
                )

        except KVStoreError:
            # Re-raise KV store errors with context
            raise
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    "Failed to update heartbeat",
                    service=instance.service_name,
                    instance=instance.instance_id,
                    error=str(e),
                )
            raise KVStoreError(
                f"Failed to update heartbeat for {instance.instance_id}",
                operation="update_heartbeat",
                key=key,
            ) from e

    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Remove a service instance from the registry."""
        key = self._make_key(service_name, instance_id)

        try:
            success = await self._kv_store.delete(key)

            if self._logger:
                if success:
                    self._logger.info(
                        "Service instance deregistered",
                        service=service_name,
                        instance=instance_id,
                    )
                else:
                    self._logger.warning(
                        "Service instance not found for deregistration",
                        service=service_name,
                        instance=instance_id,
                    )

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to deregister service instance",
                    service=service_name,
                    instance=instance_id,
                    error=str(e),
                )
            raise KVStoreError(
                f"Failed to deregister instance {instance_id}",
                operation="deregister",
                key=key,
            ) from e

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance."""
        key = self._make_key(service_name, instance_id)

        try:
            entry = await self._kv_store.get(key)
            if not entry:
                return None

            # Convert from stored format to ServiceInstance
            # Handle both snake_case and camelCase for compatibility
            data = entry.value
            if isinstance(data, dict):
                # Normalize field names to snake_case
                if "serviceName" in data and "service_name" not in data:
                    data["service_name"] = data.pop("serviceName")
                if "instanceId" in data and "instance_id" not in data:
                    data["instance_id"] = data.pop("instanceId")
                if "lastHeartbeat" in data and "last_heartbeat" not in data:
                    data["last_heartbeat"] = data.pop("lastHeartbeat")
                if "stickyActiveGroup" in data and "sticky_active_group" not in data:
                    data["sticky_active_group"] = data.pop("stickyActiveGroup")

                return ServiceInstance(**data)

            return None

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to get service instance",
                    service=service_name,
                    instance=instance_id,
                    error=str(e),
                )
            return None

    async def list_instances(self, service_name: str) -> list[ServiceInstance]:
        """List all instances of a service."""
        prefix = f"{self._key_prefix}.{service_name}."
        instances = []

        try:
            # Get all keys with the service prefix
            keys = await self._kv_store.keys(prefix)

            # Fetch all instances
            for key in keys:
                # Extract instance_id from key
                parts = key.split(".")
                if len(parts) >= 3:
                    instance_id = parts[-1]
                    instance = await self.get_instance(service_name, instance_id)
                    if instance:
                        instances.append(instance)

            return instances

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to list service instances",
                    service=service_name,
                    error=str(e),
                )
            return []

    async def list_all_services(self) -> dict[str, list[ServiceInstance]]:
        """List all services and their instances."""
        services: dict[str, list[ServiceInstance]] = {}

        try:
            # Get all registry keys
            all_keys = await self._kv_store.keys(f"{self._key_prefix}.")

            # Group by service name
            for key in all_keys:
                parts = key.split(".")
                if len(parts) >= 3:
                    service_name = parts[1]
                    instance_id = parts[2]

                    instance = await self.get_instance(service_name, instance_id)
                    if instance:
                        if service_name not in services:
                            services[service_name] = []
                        services[service_name].append(instance)

            return services

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to list all services",
                    error=str(e),
                )
            return {}
