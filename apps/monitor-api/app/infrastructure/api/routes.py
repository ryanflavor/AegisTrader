"""API routes for the monitoring service.

This module defines all FastAPI routes, keeping the web framework
concerns separate from the business logic.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...application.monitoring_service import MonitoringService
from ...domain.exceptions import DomainException
from .dependencies import get_monitoring_service


# Response models for API (DTOs)
class HealthResponse(BaseModel):
    """API response model for health endpoint."""

    status: str
    service: str
    version: str
    nats_url: str


class ErrorResponse(BaseModel):
    """API response model for errors."""

    detail: str
    error_code: str


class SystemStatusResponse(BaseModel):
    """API response model for system status."""

    timestamp: str
    uptime_seconds: float
    environment: str
    connected_services: int
    deployment_version: str


# Create router
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> HealthResponse:
    """Health check endpoint with service status."""
    try:
        health_status = await monitoring_service.get_health_status()
        return HealthResponse(
            status=health_status.status,
            service=health_status.service_name,
            version=health_status.version,
            nats_url=health_status.nats_url,
        )
    except DomainException as e:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                detail=e.message,
                error_code=e.error_code,
            ).model_dump(),
        )


@router.get("/")
async def root(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, str]:
    """Root endpoint with welcome message."""
    return monitoring_service.get_welcome_message()


@router.get("/ready")
async def readiness_check(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, str]:
    """Readiness check endpoint for Kubernetes."""
    try:
        return await monitoring_service.check_readiness()
    except DomainException as e:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                detail=e.message,
                error_code=e.error_code,
            ).model_dump(),
        )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> SystemStatusResponse:
    """Get current system status with deployment information."""
    try:
        status = await monitoring_service.get_system_status()
        return SystemStatusResponse(
            timestamp=status.timestamp.isoformat(),
            uptime_seconds=status.uptime_seconds,
            environment=status.environment,
            connected_services=status.connected_services,
            deployment_version=status.deployment_version,
        )
    except DomainException as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                detail=e.message,
                error_code=e.error_code,
            ).model_dump(),
        )
