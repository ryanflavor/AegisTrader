"""Adapter implementation for service instance repository following DDD.

This module implements the ServiceInstanceRepositoryPort using NATS KV Store
through the AegisSDK, acting as an Anti-Corruption Layer between the monitor-api
bounded context and the SDK's service registry bounded context.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..domain.exceptions import KVStoreException
from ..domain.models import ServiceInstance
from ..ports.service_instance_repository import ServiceInstanceRepositoryPort

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ServiceInstanceRepositoryAdapter(ServiceInstanceRepositoryPort):
    """Repository adapter for service instances following hexagonal architecture.

    This adapter reads service instance data from the KV Store, which is written
    by services using the SDK. It acts as a read-only view into the runtime state
    of services, translating between the SDK's data model and monitor-api's domain model.
    """

    def __init__(self, kv_store: Any, stale_threshold_seconds: int = 35):
        """Initialize the repository adapter.

        Args:
            kv_store: NATS KV Store instance (raw KV or wrapper)
            stale_threshold_seconds: Seconds after which an entry is considered stale (default: 35)
        """
        self._kv = kv_store
        self._prefix = "service-instances__"  # SDK uses double underscore separator
        self._stale_threshold_seconds = stale_threshold_seconds

    async def get_all_instances(self) -> list[ServiceInstance]:
        """Retrieve all service instances from the KV Store.

        This reads the service instance data written by SDK services,
        translating it into our domain model.
        """
        try:
            # List all keys with service-instances prefix (SDK pattern)
            all_keys = await self._kv.keys()
            keys = [key for key in all_keys if key.startswith(self._prefix)]

            instances = []
            for key in keys:
                try:
                    # Get the value from KV Store
                    entry = await self._kv.get(key)
                    if entry and entry.value:
                        # Parse the data - handle both bytes and dict formats
                        if isinstance(entry.value, bytes):
                            data = json.loads(entry.value.decode())
                        elif isinstance(entry.value, str):
                            data = json.loads(entry.value)
                        else:
                            data = entry.value

                        # Translate SDK model to our domain model
                        instance = self._translate_to_domain_model(data)
                        # Filter out stale instances
                        if not self._is_stale(instance):
                            instances.append(instance)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse instance data for key {key}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to create instance from key {key}: {e}")
                    continue

            logger.info(f"Retrieved {len(instances)} service instances")
            return instances

        except Exception as e:
            logger.error(f"Failed to get all instances: {e}")
            raise KVStoreException(f"Failed to get all instances: {e}") from e

    async def get_instances_by_service(self, service_name: str) -> list[ServiceInstance]:
        """Retrieve instances for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            List of service instances for the specified service
        """
        try:
            # Build pattern for this service (SDK uses dot notation)
            pattern = f"{self._prefix}{service_name}."

            # List all keys matching the pattern
            all_keys = await self._kv.keys()
            keys = [key for key in all_keys if key.startswith(pattern)]

            instances = []
            for key in keys:
                try:
                    entry = await self._kv.get(key)
                    if entry and entry.value:
                        # Parse the data - handle both bytes and dict formats
                        if isinstance(entry.value, bytes):
                            data = json.loads(entry.value.decode())
                        elif isinstance(entry.value, str):
                            data = json.loads(entry.value)
                        else:
                            data = entry.value

                        instance = self._translate_to_domain_model(data)
                        # Filter out stale instances
                        if not self._is_stale(instance):
                            instances.append(instance)
                except Exception as e:
                    logger.warning(f"Failed to parse instance for key {key}: {e}")
                    continue

            logger.info(f"Retrieved {len(instances)} instances for service {service_name}")
            return instances

        except Exception as e:
            logger.error(f"Failed to get instances by service: {e}")
            raise KVStoreException(f"Failed to get instances by service: {e}") from e

    def _translate_to_domain_model(self, data: dict[str, Any]) -> ServiceInstance:
        """Translate SDK service instance data to our domain model.

        This is the Anti-Corruption Layer that translates between the SDK's
        data model and our bounded context's domain model.

        Args:
            data: Raw service instance data from SDK

        Returns:
            ServiceInstance domain model
        """
        # Handle different field naming conventions between SDK and monitor-api
        # SDK might use snake_case while our model uses camelCase aliases

        # Map fields with proper handling of missing data
        mapped_data = {
            "service_name": data.get("service_name", data.get("serviceName", "")),
            "instance_id": data.get("instance_id", data.get("instanceId", "")),
            "version": data.get("version", "0.0.0"),
            "status": data.get("status", "UNHEALTHY"),
            "last_heartbeat": self._parse_timestamp(
                data.get("last_heartbeat", data.get("lastHeartbeat"))
            ),
            "sticky_active_group": data.get("sticky_active_group", data.get("stickyActiveGroup")),
            "metadata": data.get("metadata", {}),
        }

        # Additional SDK fields that might be in metadata
        if "sticky_active_status" in data:
            mapped_data["metadata"]["sticky_active_status"] = data["sticky_active_status"]
        if "lifecycle_state" in data:
            mapped_data["metadata"]["lifecycle_state"] = data["lifecycle_state"]

        return ServiceInstance(**mapped_data)

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse timestamp from various formats.

        Args:
            value: Timestamp value in various formats

        Returns:
            datetime object or None if no valid timestamp
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Handle ISO format with Z or timezone
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                # Return None if parsing fails
                return None
        if isinstance(value, (int, float)):
            # Handle Unix timestamp
            return datetime.fromtimestamp(value)
        # Return None for unknown formats
        return None

    def _is_stale(self, instance: ServiceInstance) -> bool:
        """Check if a service instance is stale based on heartbeat age.

        Args:
            instance: Service instance to check

        Returns:
            True if the instance is stale, False otherwise
        """
        # Get current time (timezone-aware)
        now = datetime.now(UTC)

        # Make sure heartbeat is timezone-aware
        last_heartbeat = instance.last_heartbeat
        if last_heartbeat.tzinfo is None:
            # Assume UTC if no timezone
            last_heartbeat = last_heartbeat.replace(tzinfo=UTC)

        # Calculate heartbeat age
        heartbeat_age = now - last_heartbeat
        heartbeat_age_seconds = heartbeat_age.total_seconds()

        # Check if stale (older than threshold)
        is_stale = heartbeat_age_seconds > self._stale_threshold_seconds

        if is_stale:
            logger.debug(
                f"Instance {instance.service_name}/{instance.instance_id} is stale: "
                f"heartbeat age {heartbeat_age_seconds:.1f}s > {self._stale_threshold_seconds}s"
            )

        return is_stale

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Retrieve a specific service instance.

        Args:
            service_name: Name of the service
            instance_id: ID of the instance

        Returns:
            ServiceInstance if found, None otherwise

        Raises:
            KVStoreException: If retrieval fails
        """
        try:
            # Build the key for this specific instance
            key = f"{self._prefix}{service_name}.{instance_id}"

            # Get the value from KV Store
            entry = await self._kv.get(key)
            if entry and entry.value:
                # Parse the data - handle both bytes and dict formats
                if isinstance(entry.value, bytes):
                    data = json.loads(entry.value.decode())
                elif isinstance(entry.value, str):
                    data = json.loads(entry.value)
                else:
                    data = entry.value

                # Translate SDK model to our domain model
                instance = self._translate_to_domain_model(data)

                # Check if stale
                if self._is_stale(instance):
                    logger.debug(f"Instance is stale: {service_name}/{instance_id}")
                    return None

                logger.info(f"Retrieved instance: {service_name}/{instance_id}")
                return instance

            logger.debug(f"Instance not found: {service_name}/{instance_id}")
            return None

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse instance data for {service_name}/{instance_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get instance {service_name}/{instance_id}: {e}")
            raise KVStoreException(f"Failed to get instance: {e}") from e

    async def count_active_instances(self) -> int:
        """Count the number of active service instances.

        Returns:
            Number of instances with ACTIVE status

        Raises:
            KVStoreException: If counting fails
        """
        try:
            # Get all instances
            instances = await self.get_all_instances()

            # Count active ones
            active_count = sum(1 for instance in instances if instance.status == "ACTIVE")

            logger.info(f"Counted {active_count} active instances")
            return active_count

        except Exception as e:
            logger.error(f"Failed to count active instances: {e}")
            raise KVStoreException(f"Failed to count active instances: {e}") from e

    async def get_instances_by_status(self, status: str) -> list[ServiceInstance]:
        """Retrieve all instances with a specific status.

        Args:
            status: Status to filter by (ACTIVE, UNHEALTHY, STANDBY)

        Returns:
            List of service instances with the given status

        Raises:
            KVStoreException: If retrieval fails
        """
        try:
            # Get all instances
            instances = await self.get_all_instances()

            # Filter by status
            filtered_instances = [instance for instance in instances if instance.status == status]

            logger.info(f"Retrieved {len(filtered_instances)} instances with status {status}")
            return filtered_instances

        except Exception as e:
            logger.error(f"Failed to get instances by status: {e}")
            raise KVStoreException(f"Failed to get instances by status: {e}") from e
