"""Application service for service registry management.

This module implements the business logic for managing service definitions,
coordinating between the domain layer and infrastructure adapters.
"""

from __future__ import annotations

import logging

from ..domain.exceptions import (
    ConcurrentUpdateException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
)
from ..domain.models import ServiceDefinition
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort
from ..utils.timezone import utc8_timestamp_factory

logger = logging.getLogger(__name__)


class ServiceRegistryService:
    """Service for managing service definitions in the registry."""

    def __init__(self, kv_store: ServiceRegistryKVStorePort):
        """Initialize the service registry.

        Args:
            kv_store: The KV Store port implementation
        """
        self._kv_store = kv_store

    async def create_service(self, service_data: dict) -> ServiceDefinition:
        """Create a new service definition.

        Args:
            service_data: Dictionary containing service details

        Returns:
            The created ServiceDefinition

        Raises:
            ServiceAlreadyExistsException: If service already exists
            KVStoreException: If storage fails
        """
        # Generate timestamps
        now = utc8_timestamp_factory()

        # Create the service definition
        service = ServiceDefinition(
            service_name=service_data["service_name"],
            owner=service_data["owner"],
            description=service_data["description"],
            version=service_data["version"],
            created_at=now,
            updated_at=now,
        )

        # Store in KV Store
        try:
            await self._kv_store.put(service.service_name, service)
        except ValueError as e:
            if "already exists" in str(e):
                raise ServiceAlreadyExistsException(service.service_name) from e
            raise

        logger.info(f"Created service: {service.service_name}")
        return service

    async def get_service(self, service_name: str) -> ServiceDefinition | None:
        """Get a service definition by name.

        Args:
            service_name: The service name

        Returns:
            ServiceDefinition if found, None otherwise

        Raises:
            KVStoreException: If retrieval fails
        """
        service = await self._kv_store.get(service_name)
        if service:
            logger.info(f"Retrieved service: {service_name}")
        else:
            logger.warning(f"Service not found: {service_name}")
        return service

    async def update_service(
        self, service_name: str, updates: dict, revision: int | None = None
    ) -> ServiceDefinition:
        """Update an existing service definition.

        Args:
            service_name: The service name
            updates: Dictionary of fields to update
            revision: Optional revision for optimistic locking

        Returns:
            The updated ServiceDefinition

        Raises:
            ServiceNotFoundException: If service doesn't exist
            ConcurrentUpdateException: If revision mismatch
            KVStoreException: If update fails
        """
        # Get existing service
        existing = await self._kv_store.get(service_name)
        if not existing:
            raise ServiceNotFoundException(service_name)

        # Update fields
        service_data = existing.model_dump()
        service_data.update(updates)
        service_data["updated_at"] = utc8_timestamp_factory()

        # Create updated service
        updated_service = ServiceDefinition(**service_data)

        # Update in KV Store
        try:
            await self._kv_store.update(service_name, updated_service, revision)
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise ServiceNotFoundException(service_name) from e
            if "Revision mismatch" in error_msg:
                raise ConcurrentUpdateException(service_name) from e
            raise

        logger.info(f"Updated service: {service_name}")
        return updated_service

    async def delete_service(self, service_name: str) -> None:
        """Delete a service definition.

        Args:
            service_name: The service name

        Raises:
            ServiceNotFoundException: If service doesn't exist
            KVStoreException: If deletion fails
        """
        try:
            await self._kv_store.delete(service_name)
        except ValueError as e:
            if "not found" in str(e):
                raise ServiceNotFoundException(service_name) from e
            raise
        logger.info(f"Deleted service: {service_name}")

    async def list_services(self) -> list[ServiceDefinition]:
        """List all service definitions.

        Returns:
            List of all ServiceDefinitions

        Raises:
            KVStoreException: If listing fails
        """
        services = await self._kv_store.list_all()
        logger.info(f"Listed {len(services)} services")
        return services

    async def get_service_with_revision(
        self, service_name: str
    ) -> tuple[ServiceDefinition | None, int | None]:
        """Get a service definition with its revision.

        Args:
            service_name: The service name

        Returns:
            Tuple of (ServiceDefinition, revision) or (None, None)

        Raises:
            KVStoreException: If retrieval fails
        """
        return await self._kv_store.get_with_revision(service_name)
