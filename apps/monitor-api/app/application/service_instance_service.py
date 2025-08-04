"""Application service for service instance monitoring.

This module implements the business logic for monitoring service instances,
coordinating between the domain layer and infrastructure adapters.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..domain.exceptions import ServiceNotFoundException
from ..domain.models import ServiceInstance

if TYPE_CHECKING:
    from ..ports.service_instance_repository import ServiceInstanceRepositoryPort

logger = logging.getLogger(__name__)


class ServiceInstanceService:
    """Service for monitoring and managing service instances."""

    def __init__(self, repository: ServiceInstanceRepositoryPort):
        """Initialize the service instance service.

        Args:
            repository: The service instance repository
        """
        self._repository = repository

    async def list_all_instances(self) -> list[ServiceInstance]:
        """List all service instances.

        Returns:
            List of all service instances

        Raises:
            KVStoreException: If retrieval fails
        """
        instances = await self._repository.get_all_instances()
        logger.info(f"Listed {len(instances)} service instances")
        return instances

    async def list_instances_by_service(self, service_name: str) -> list[ServiceInstance]:
        """List all instances of a specific service.

        Args:
            service_name: Name of the service

        Returns:
            List of service instances for the given service

        Raises:
            KVStoreException: If retrieval fails
        """
        instances = await self._repository.get_instances_by_service(service_name)
        logger.info(f"Listed {len(instances)} instances for service {service_name}")
        return instances

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance:
        """Get details of a specific service instance.

        Args:
            service_name: Name of the service
            instance_id: ID of the instance

        Returns:
            The service instance

        Raises:
            ServiceNotFoundException: If instance not found
            KVStoreException: If retrieval fails
        """
        instance = await self._repository.get_instance(service_name, instance_id)
        if not instance:
            raise ServiceNotFoundException(
                f"Instance {instance_id} of service {service_name} not found"
            )

        logger.info(f"Retrieved instance {service_name}/{instance_id}")
        return instance

    async def get_health_summary(self) -> dict[str, int]:
        """Get a summary of instance health across all services.

        Returns:
            Dictionary with counts by status

        Raises:
            KVStoreException: If retrieval fails
        """
        instances = await self._repository.get_all_instances()

        summary = {
            "total": len(instances),
            "active": sum(1 for inst in instances if inst.status == "ACTIVE"),
            "unhealthy": sum(1 for inst in instances if inst.status == "UNHEALTHY"),
            "standby": sum(1 for inst in instances if inst.status == "STANDBY"),
        }

        logger.info(f"Health summary: {summary}")
        return summary

    async def get_stale_instances(self, threshold_minutes: int = 5) -> list[ServiceInstance]:
        """Get instances that haven't sent a heartbeat recently.

        Args:
            threshold_minutes: Minutes since last heartbeat to consider stale

        Returns:
            List of stale service instances

        Raises:
            KVStoreException: If retrieval fails
        """
        instances = await self._repository.get_all_instances()
        now = datetime.now(UTC)
        threshold = timedelta(minutes=threshold_minutes)

        stale = []
        for instance in instances:
            # Ensure heartbeat is timezone-aware
            heartbeat = instance.last_heartbeat
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=UTC)

            if now - heartbeat > threshold:
                stale.append(instance)

        logger.info(f"Found {len(stale)} stale instances (threshold: {threshold_minutes} minutes)")
        return stale

    async def get_active_instances_count(self) -> int:
        """Get the count of active service instances.

        Returns:
            Number of active instances

        Raises:
            KVStoreException: If counting fails
        """
        count = await self._repository.count_active_instances()
        logger.info(f"Active instance count: {count}")
        return count

    async def get_instances_by_status(self, status: str) -> list[ServiceInstance]:
        """Get all instances with a specific status.

        Args:
            status: Status to filter by (ACTIVE, UNHEALTHY, STANDBY)

        Returns:
            List of service instances with the given status

        Raises:
            ValueError: If invalid status provided
            KVStoreException: If retrieval fails
        """
        # Validate status
        valid_statuses = {"ACTIVE", "UNHEALTHY", "STANDBY"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        instances = await self._repository.get_instances_by_status(status)
        logger.info(f"Listed {len(instances)} instances with status {status}")
        return instances

    async def get_service_distribution(self) -> dict[str, int]:
        """Get the distribution of instances across services.

        Returns:
            Dictionary mapping service names to instance counts

        Raises:
            KVStoreException: If retrieval fails
        """
        instances = await self._repository.get_all_instances()

        distribution: dict[str, int] = {}
        for instance in instances:
            distribution[instance.service_name] = distribution.get(instance.service_name, 0) + 1

        logger.info(f"Service distribution: {distribution}")
        return distribution
