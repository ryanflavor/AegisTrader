"""Adapter implementation for service instance repository.

This module implements the ServiceInstanceRepositoryPort using NATS KV Store
through the AegisSDK, maintaining separation between domain and infrastructure.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ..domain.exceptions import KVStoreException
from ..domain.models import ServiceInstance
from ..ports.service_instance_repository import ServiceInstanceRepositoryPort

if TYPE_CHECKING:
    from nats.js.kv import KeyValue

logger = logging.getLogger(__name__)


class ServiceInstanceRepositoryAdapter(ServiceInstanceRepositoryPort):
    """NATS KV Store implementation of service instance repository."""

    def __init__(self, kv_store: KeyValue):
        """Initialize the repository adapter.

        Args:
            kv_store: NATS KV Store instance
        """
        self._kv = kv_store
        self._prefix = "service-instances"

    async def get_all_instances(self) -> list[ServiceInstance]:
        """Retrieve all service instances from the KV Store."""
        try:
            # List all keys with service-instances prefix
            keys = await self._kv.keys(f"{self._prefix}.*")

            instances = []
            for key in keys:
                try:
                    # Get the value
                    entry = await self._kv.get(key)
                    if entry and entry.value:
                        # Parse the JSON data
                        data = json.loads(entry.value.decode())
                        instance = ServiceInstance(**data)
                        instances.append(instance)
                except Exception as e:
                    logger.error(f"Failed to parse instance data for key {key}: {e}")
                    continue

            # Sort by service name and instance ID for consistency
            instances.sort(key=lambda x: (x.service_name, x.instance_id))

            logger.debug(f"Retrieved {len(instances)} service instances")
            return instances

        except Exception as e:
            logger.error(f"Failed to retrieve all instances: {e}")
            raise KVStoreException(f"Failed to retrieve all instances: {e}") from e

    async def get_instances_by_service(self, service_name: str) -> list[ServiceInstance]:
        """Retrieve all instances of a specific service."""
        try:
            # List keys for this service
            keys = await self._kv.keys(f"{self._prefix}.{service_name}.*")

            instances = []
            for key in keys:
                try:
                    # Get the value
                    entry = await self._kv.get(key)
                    if entry and entry.value:
                        # Parse the JSON data
                        data = json.loads(entry.value.decode())
                        instance = ServiceInstance(**data)
                        instances.append(instance)
                except Exception as e:
                    logger.error(f"Failed to parse instance data for key {key}: {e}")
                    continue

            # Sort by instance ID for consistency
            instances.sort(key=lambda x: x.instance_id)

            logger.debug(f"Retrieved {len(instances)} instances for service {service_name}")
            return instances

        except Exception as e:
            logger.error(f"Failed to retrieve instances for service {service_name}: {e}")
            raise KVStoreException(
                f"Failed to retrieve instances for service {service_name}: {e}"
            ) from e

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Retrieve a specific service instance."""
        try:
            # Get the specific instance
            key = f"{self._prefix}.{service_name}.{instance_id}"
            entry = await self._kv.get(key)

            if not entry or not entry.value:
                logger.debug(f"Instance not found: {service_name}/{instance_id}")
                return None

            # Parse the JSON data
            data = json.loads(entry.value.decode())
            instance = ServiceInstance(**data)

            logger.debug(f"Retrieved instance: {service_name}/{instance_id}")
            return instance

        except Exception as e:
            logger.error(f"Failed to retrieve instance {service_name}/{instance_id}: {e}")
            raise KVStoreException(
                f"Failed to retrieve instance {service_name}/{instance_id}: {e}"
            ) from e

    async def count_active_instances(self) -> int:
        """Count the number of active service instances."""
        try:
            # Get all instances and filter by status
            instances = await self.get_all_instances()
            active_count = sum(1 for inst in instances if inst.status == "ACTIVE")

            logger.debug(f"Counted {active_count} active instances")
            return active_count

        except Exception as e:
            logger.error(f"Failed to count active instances: {e}")
            raise KVStoreException(f"Failed to count active instances: {e}") from e

    async def get_instances_by_status(self, status: str) -> list[ServiceInstance]:
        """Retrieve all instances with a specific status."""
        try:
            # Validate status
            valid_statuses = {"ACTIVE", "UNHEALTHY", "STANDBY"}
            if status not in valid_statuses:
                raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

            # Get all instances and filter by status
            instances = await self.get_all_instances()
            filtered = [inst for inst in instances if inst.status == status]

            logger.debug(f"Retrieved {len(filtered)} instances with status {status}")
            return filtered

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve instances by status {status}: {e}")
            raise KVStoreException(f"Failed to retrieve instances by status {status}: {e}") from e
