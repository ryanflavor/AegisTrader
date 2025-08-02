"""API routes for service registry management.

This module defines all service registry CRUD endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ...domain.models import ServiceDefinition
from .dependencies import get_service_registry

if TYPE_CHECKING:
    from ...application.service_registry_service import ServiceRegistryService


# Request/Response models
class ServiceCreateRequest(BaseModel):
    """Request model for creating a service."""

    model_config = ConfigDict(strict=True)

    service_name: str = Field(
        ...,
        description="Unique service identifier",
        pattern=r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$",
        min_length=3,
        max_length=64,
    )
    owner: str = Field(
        ...,
        description="Service owner or team",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        ...,
        description="Service description",
        min_length=1,
        max_length=500,
    )
    version: str = Field(
        ...,
        description="Service version",
        pattern=r"^\d+\.\d+\.\d+$",
    )


class ServiceUpdateRequest(BaseModel):
    """Request model for updating a service."""

    model_config = ConfigDict(strict=True)

    owner: str | None = Field(
        None,
        description="Service owner or team",
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        None,
        description="Service description",
        min_length=1,
        max_length=500,
    )
    version: str | None = Field(
        None,
        description="Service version",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    revision: int | None = Field(
        None,
        description="Current revision for optimistic locking",
    )


# Create router
router = APIRouter(prefix="/api/services", tags=["Service Registry"])


@router.get("", response_model=list[ServiceDefinition])
async def list_services(
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> list[ServiceDefinition]:
    """List all service definitions."""
    return await service_registry.list_services()


@router.post(
    "",
    response_model=ServiceDefinition,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    request: ServiceCreateRequest,
    response: Response,
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> ServiceDefinition:
    """Create a new service definition."""
    service = await service_registry.create_service(request.model_dump())
    # Add Location header
    response.headers["Location"] = f"/api/services/{service.service_name}"
    return service


@router.get("/{service_name}", response_model=ServiceDefinition)
async def get_service(
    service_name: str,
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> ServiceDefinition:
    """Get a specific service definition by name."""
    from ...domain.exceptions import ServiceNotFoundException

    service = await service_registry.get_service(service_name)
    if not service:
        raise ServiceNotFoundException(service_name)
    return service


@router.put("/{service_name}", response_model=ServiceDefinition)
async def update_service(
    service_name: str,
    request: ServiceUpdateRequest,
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> ServiceDefinition:
    """Update an existing service definition."""
    from fastapi import HTTPException

    # Extract revision from request
    revision = request.revision
    updates = request.model_dump(exclude={"revision"}, exclude_none=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    return await service_registry.update_service(service_name, updates, revision)


@router.delete("/{service_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_name: str,
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> Response:
    """Delete a service definition."""
    await service_registry.delete_service(service_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Add support for getting service with revision (for optimistic locking)
@router.get("/{service_name}/revision", response_model=dict)
async def get_service_with_revision(
    service_name: str,
    service_registry: ServiceRegistryService = Depends(get_service_registry),  # noqa: B008
) -> dict:
    """Get a service definition with its revision number for optimistic locking."""
    from ...domain.exceptions import ServiceNotFoundException

    service, revision = await service_registry.get_service_with_revision(service_name)
    if not service:
        raise ServiceNotFoundException(service_name)
    return {
        "service": service.model_dump(),
        "revision": revision,
    }
