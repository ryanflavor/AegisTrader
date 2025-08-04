"""API routes for service instance monitoring.

This module defines endpoints for viewing active service instances,
following hexagonal architecture by delegating to the application service.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from ...application.service_instance_service import ServiceInstanceService
from ...domain.exceptions import ServiceNotFoundException
from ...domain.models import ServiceInstance
from ..connection_manager import get_connection_manager

if TYPE_CHECKING:
    from ..connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/instances", tags=["Service Instances"])


async def get_service_instance_service(
    connection_manager: ConnectionManager = Depends(get_connection_manager),  # noqa: B008
) -> ServiceInstanceService:
    """Dependency to get the service instance service."""
    return ServiceInstanceService(connection_manager.instance_repository)


@router.get("", response_model=list[ServiceInstance])
async def list_service_instances(
    service: ServiceInstanceService = Depends(get_service_instance_service),  # noqa: B008
) -> list[ServiceInstance]:
    """List all active service instances."""
    try:
        return await service.list_all_instances()
    except Exception as e:
        logger.error(f"Failed to list service instances: {e}")
        raise HTTPException(status_code=500, detail="Failed to list service instances") from e


@router.get("/{service_name}", response_model=list[ServiceInstance])
async def list_service_instances_by_name(
    service_name: str,
    service: ServiceInstanceService = Depends(get_service_instance_service),  # noqa: B008
) -> list[ServiceInstance]:
    """List all instances of a specific service."""
    try:
        return await service.list_instances_by_service(service_name)
    except Exception as e:
        logger.error(f"Failed to list instances for service {service_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list instances for service {service_name}"
        ) from e


@router.get("/health/summary", response_model=dict[str, int])
async def get_health_summary(
    service: ServiceInstanceService = Depends(get_service_instance_service),  # noqa: B008
) -> dict[str, int]:
    """Get a summary of instance health across all services."""
    try:
        return await service.get_health_summary()
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health summary") from e


@router.get("/status/{status}", response_model=list[ServiceInstance])
async def get_instances_by_status(
    status: str,
    service: ServiceInstanceService = Depends(get_service_instance_service),  # noqa: B008
) -> list[ServiceInstance]:
    """Get all instances with a specific status."""
    try:
        return await service.get_instances_by_status(status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get instances by status {status}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get instances by status") from e


@router.get("/{service_name}/{instance_id}", response_model=ServiceInstance)
async def get_service_instance(
    service_name: str,
    instance_id: str,
    service: ServiceInstanceService = Depends(get_service_instance_service),  # noqa: B008
) -> ServiceInstance:
    """Get details of a specific service instance."""
    try:
        return await service.get_instance(service_name, instance_id)
    except ServiceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get instance {instance_id} of service {service_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get instance details") from e
