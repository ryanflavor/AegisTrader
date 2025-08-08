"""Service registry adapter for Echo Service.

This adapter handles service registration with the monitor-api,
registering both ServiceDefinition and ServiceInstance in NATS KV store.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import ServiceRegistrationData
from ..ports.service_registry import ServiceRegistryPort
from .nats_connection_adapter import NATSConnectionAdapter

# Python 3.10 compatibility
UTC = UTC

logger = logging.getLogger(__name__)


class ServiceDefinition(BaseModel):
    """Service definition model matching monitor-api expectations."""

    model_config = ConfigDict(frozen=True, strict=True)

    service_name: str = Field(..., pattern=r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
    owner: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    created_at: str = Field(...)  # ISO format timestamp
    updated_at: str = Field(...)  # ISO format timestamp


class ServiceInstance(BaseModel):
    """Service instance model matching monitor-api expectations."""

    model_config = ConfigDict(frozen=True, strict=True, alias_generator=None, populate_by_name=True)

    service_name: str = Field(..., alias="serviceName", pattern=r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
    instance_id: str = Field(..., alias="instanceId", min_length=1, max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    status: str = Field(..., pattern=r"^(ACTIVE|UNHEALTHY|STANDBY)$")
    last_heartbeat: str = Field(..., alias="lastHeartbeat")  # ISO format timestamp
    sticky_active_group: str | None = Field(None, alias="stickyActiveGroup")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceRegistryAdapter(ServiceRegistryPort):
    """Adapter for service registry operations using NATS KV store.

    This adapter handles:
    1. Registering ServiceDefinition with key "echo-service" (no prefix)
    2. Registering ServiceInstance with key "service-instances__echo-service__<id>"
    3. Maintaining heartbeat for instance registration
    """

    def __init__(self, nats_adapter: NATSConnectionAdapter) -> None:
        """Initialize service registry adapter.

        Args:
            nats_adapter: NATS connection adapter
        """
        self._nats = nats_adapter
        self._kv_bucket = None
        self._heartbeat_task = None
        self._instance_id = None
        self._service_name = None

    async def connect(self) -> None:
        """Connect to the service registry KV store."""
        try:
            # Try to get existing bucket first, create if it doesn't exist
            try:
                self._kv_bucket = await self._nats.get_kv_bucket("service_registry")
                logger.info("Connected to existing service registry KV store")
            except Exception:
                # Bucket doesn't exist, create it
                self._kv_bucket = await self._nats.create_kv_bucket("service_registry")
                logger.info("Created new service registry KV store")
        except Exception as e:
            logger.error(f"Failed to connect to service registry: {e}")
            raise

    async def register_service_definition(
        self,
        service_name: str,
        owner: str,
        description: str,
        version: str,
    ) -> bool:
        """Register service definition in KV store.

        Args:
            service_name: Service name (e.g., "echo-service")
            owner: Service owner or team
            description: Service description
            version: Service version (semantic versioning)

        Returns:
            True if registration successful
        """
        if not self._kv_bucket:
            await self.connect()

        try:
            now = datetime.now(UTC).isoformat()

            # Create service definition
            definition = ServiceDefinition(
                service_name=service_name,
                owner=owner,
                description=description,
                version=version,
                created_at=now,
                updated_at=now,
            )

            # Store with service name as key (no prefix)
            key = service_name
            value = definition.model_dump_json()

            await self._kv_bucket.put(key, value.encode())
            logger.info(f"Registered service definition: {key}")

            # Store for later use
            self._service_name = service_name

            return True

        except Exception as e:
            logger.error(f"Failed to register service definition: {e}")
            return False

    async def register_service_instance(
        self,
        service_name: str,
        instance_id: str,
        version: str,
        status: str = "ACTIVE",
        sticky_active_group: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Register service instance in KV store.

        Args:
            service_name: Service name
            instance_id: Unique instance ID
            version: Service version
            status: Instance status (ACTIVE, UNHEALTHY, STANDBY)
            sticky_active_group: Optional sticky session group
            metadata: Optional metadata

        Returns:
            True if registration successful
        """
        if not self._kv_bucket:
            await self.connect()

        try:
            now = datetime.now(UTC).isoformat()

            # Create service instance
            instance = ServiceInstance(
                serviceName=service_name,
                instanceId=instance_id,
                version=version,
                status=status,
                lastHeartbeat=now,
                stickyActiveGroup=sticky_active_group,
                metadata=metadata or {},
            )

            # Store with pattern: service-instances__<service_name>__<instance_id>
            key = f"service-instances__{service_name}__{instance_id}"
            value = instance.model_dump_json(by_alias=True)

            await self._kv_bucket.put(key, value.encode())
            logger.info(f"Registered service instance: {key}")

            # Store for heartbeat
            self._instance_id = instance_id
            self._service_name = service_name

            # Start heartbeat task
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            logger.error(f"Failed to register service instance: {e}")
            return False

    async def update_heartbeat(self) -> bool:
        """Update instance heartbeat timestamp.

        Returns:
            True if update successful
        """
        if not self._kv_bucket or not self._instance_id or not self._service_name:
            return False

        try:
            key = f"service-instances__{self._service_name}__{self._instance_id}"

            # Get current instance data
            entry = await self._kv_bucket.get(key)
            if not entry or not entry.value:
                logger.warning(f"Instance not found: {key}")
                return False

            # Update heartbeat
            data = json.loads(entry.value.decode())
            data["lastHeartbeat"] = datetime.now(UTC).isoformat()

            # Store updated data
            await self._kv_bucket.put(key, json.dumps(data).encode())
            logger.debug(f"Updated heartbeat for {key}")

            return True

        except Exception as e:
            logger.error(f"Failed to update heartbeat: {e}")
            return False

    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic heartbeats."""
        interval = 30  # Send heartbeat every 30 seconds

        while True:
            try:
                await asyncio.sleep(interval)
                success = await self.update_heartbeat()
                if not success:
                    logger.warning("Heartbeat update failed")
            except asyncio.CancelledError:
                logger.info("Heartbeat task cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def deregister_instance(self) -> bool:
        """Deregister the current service instance.

        Returns:
            True if deregistration successful
        """
        if not self._kv_bucket or not self._instance_id or not self._service_name:
            return False

        try:
            # Cancel heartbeat task
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                self._heartbeat_task = None

            # Delete instance from KV store
            key = f"service-instances__{self._service_name}__{self._instance_id}"
            await self._kv_bucket.delete(key)
            logger.info(f"Deregistered service instance: {key}")

            return True

        except Exception as e:
            logger.error(f"Failed to deregister instance: {e}")
            return False

    async def get_service_definition(self, service_name: str) -> dict[str, Any] | None:
        """Get service definition from registry.

        Args:
            service_name: Service name to lookup

        Returns:
            Service definition data or None if not found
        """
        if not self._kv_bucket:
            await self.connect()

        try:
            entry = await self._kv_bucket.get(service_name)
            if entry and entry.value:
                return json.loads(entry.value.decode())
            return None
        except Exception as e:
            logger.error(f"Failed to get service definition: {e}")
            return None

    async def get_service_instances(self, service_name: str) -> list[dict[str, Any]]:
        """Get all instances for a service.

        Args:
            service_name: Service name

        Returns:
            List of service instances
        """
        if not self._kv_bucket:
            await self.connect()

        instances = []
        try:
            # List all keys with the service instance prefix
            prefix = f"service-instances__{service_name}__"
            keys = await self._kv_bucket.keys()

            for key in keys:
                if key.startswith(prefix):
                    entry = await self._kv_bucket.get(key)
                    if entry and entry.value:
                        instances.append(json.loads(entry.value.decode()))

            return instances

        except Exception as e:
            logger.error(f"Failed to get service instances: {e}")
            return []

    async def update_service_definition(self, registration: ServiceRegistrationData) -> None:
        """Update existing service definition.

        Args:
            registration: Updated service registration data

        Raises:
            RegistrationError: If update fails
        """
        from ..ports.service_registry import RegistrationError

        success = await self.register_service_definition(
            service_name=registration.definition.service_name,
            owner=registration.definition.owner,
            description=registration.definition.description,
            version=registration.definition.version,
        )
        if not success:
            raise RegistrationError(
                f"Failed to update service definition for {registration.definition.service_name}",
                registration.definition.service_name,
            )

    async def check_service_exists(self, service_name: str) -> bool:
        """Check if a service definition already exists.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service exists, False otherwise
        """
        definition = await self.get_service_definition(service_name)
        return definition is not None

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
        from ..ports.service_registry import RegistrationError

        success = await self.register_service_instance(
            service_name=service_name,
            instance_id=instance_id,
            version=instance_data.get("version", "1.0.0"),
            status=instance_data.get("status", "ACTIVE"),
            metadata=instance_data.get("metadata", {}),
        )
        if not success:
            raise RegistrationError(f"Failed to register instance {instance_id}", service_name)

    async def update_instance_heartbeat(
        self,
        service_name: str,
        instance_id: str,
        instance_data: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Update instance heartbeat to maintain registration.

        Args:
            service_name: Name of the service
            instance_id: Unique instance identifier
            instance_data: Updated instance metadata
            ttl_seconds: Time-to-live in seconds

        Raises:
            RegistrationError: If heartbeat update fails
        """
        from ..ports.service_registry import RegistrationError

        success = await self.update_heartbeat()
        if not success:
            raise RegistrationError(f"Failed to update heartbeat for {instance_id}", service_name)

    async def deregister_instance(
        self, service_name: str | None = None, instance_id: str | None = None
    ) -> None:
        """Remove a service instance from the registry.

        Args:
            service_name: Name of the service (optional if already set)
            instance_id: Instance to deregister (optional if already set)

        Raises:
            RegistrationError: If deregistration fails
        """
        from ..ports.service_registry import RegistrationError

        # Use provided values or instance variables
        svc_name = service_name or self._service_name
        inst_id = instance_id or self._instance_id

        if not svc_name or not inst_id:
            return  # Nothing to deregister

        success = await self.deregister()
        if not success:
            raise RegistrationError(f"Failed to deregister instance {inst_id}", svc_name)

    async def disconnect(self) -> None:
        """Disconnect from registry and clean up resources."""
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        # Deregister instance
        if self._instance_id:
            await self.deregister_instance()

        self._kv_bucket = None
        logger.info("Disconnected from service registry")
