"""API routes for the monitoring service.

This module defines all FastAPI routes, keeping the web framework
concerns separate from the business logic.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...application.monitoring_service import MonitoringService
from .dependencies import get_monitoring_service
from .service_instance_routes import router as instance_router
from .service_routes import router as service_router

logger = logging.getLogger(__name__)


# Response models for API (DTOs)
class HealthResponse(BaseModel):
    """API response model for health endpoint."""

    status: str
    service: str
    version: str
    nats_url: str


class SystemStatusResponse(BaseModel):
    """API response model for system status."""

    timestamp: str
    uptime_seconds: float
    environment: str
    connected_services: int
    deployment_version: str


class SystemMetrics(BaseModel):
    """System resource metrics."""

    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float


class DependencyStatus(BaseModel):
    """Status of a dependency."""

    status: str
    latency_ms: float


class DetailedHealthResponse(BaseModel):
    """API response model for detailed health endpoint."""

    status: str
    service: str
    version: str
    system_metrics: SystemMetrics
    dependencies: dict[str, DependencyStatus]


# Create router
router = APIRouter()

# Include service registry routes
router.include_router(service_router)
logger.info(f"Included service_router with prefix: {service_router.prefix}")

router.include_router(instance_router)
logger.info(f"Included instance_router with prefix: {instance_router.prefix}")


@router.get("/health", response_model=HealthResponse)
async def health_check(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),  # noqa: B008
) -> HealthResponse:
    """Health check endpoint with service status."""
    health_status = await monitoring_service.get_health_status()
    return HealthResponse(
        status=health_status.status,
        service=health_status.service_name,
        version=health_status.version,
        nats_url=health_status.nats_url,
    )


@router.get("/")
async def root(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),  # noqa: B008
) -> dict[str, str]:
    """Root endpoint with welcome message."""
    return monitoring_service.get_welcome_message()


@router.get("/ready")
async def readiness_check(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),  # noqa: B008
) -> dict[str, str]:
    """Readiness check endpoint for Kubernetes."""
    return await monitoring_service.check_readiness()


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),  # noqa: B008
) -> SystemStatusResponse:
    """Get current system status with deployment information."""
    status = await monitoring_service.get_system_status()
    return SystemStatusResponse(
        timestamp=status.timestamp.isoformat(),
        uptime_seconds=status.uptime_seconds,
        environment=status.environment,
        connected_services=status.connected_services,
        deployment_version=status.deployment_version,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    monitoring_service: MonitoringService = Depends(get_monitoring_service),  # noqa: B008
) -> DetailedHealthResponse:
    """Detailed health check endpoint with system metrics and dependencies."""
    detailed_health = await monitoring_service.get_detailed_health_status()
    return DetailedHealthResponse(
        status=detailed_health.status,
        service=detailed_health.service_name,
        version=detailed_health.version,
        system_metrics=SystemMetrics(
            cpu_percent=detailed_health.cpu_percent,
            memory_percent=detailed_health.memory_percent,
            disk_usage_percent=detailed_health.disk_usage_percent,
        ),
        dependencies={
            "nats": DependencyStatus(
                status=detailed_health.nats_status,
                latency_ms=detailed_health.nats_latency_ms,
            )
        },
    )
