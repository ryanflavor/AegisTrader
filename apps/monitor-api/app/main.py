from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Track service start time
service_start_time = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status of the service")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    nats_url: str = Field(..., description="NATS connection URL")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")


class SystemStatus(BaseModel):
    timestamp: str = Field(..., description="Current server timestamp")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    environment: str = Field(..., description="Current environment")
    connected_services: int = Field(0, description="Number of connected services")
    deployment_version: str = Field(..., description="Deployment version")


# Environment variable validation
def validate_environment() -> dict[str, str]:
    """Validate required environment variables."""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    api_port = int(os.getenv("API_PORT", "8100"))

    # Log configuration
    logger.info(f"NATS URL: {nats_url}")
    logger.info(f"API Port: {api_port}")
    logger.info(f"Log Level: {log_level}")

    return {
        "nats_url": nats_url,
        "api_port": api_port,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager."""
    global service_start_time
    logger.info("Starting AegisTrader Management Service")

    # Validate environment on startup
    env_config = validate_environment()
    app.state.config = env_config

    # Set service start time
    service_start_time = datetime.now()
    app.state.start_time = service_start_time

    logger.info("Service startup complete")
    yield
    logger.info("Shutting down AegisTrader Management Service")


app = FastAPI(
    title="AegisTrader Management Service",
    description="Management and monitoring API for the AegisTrader system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=ErrorResponse(
            detail="Internal server error occurred", error_code="INTERNAL_ERROR"
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with service status."""
    try:
        config = app.state.config
        return HealthResponse(
            status="healthy",
            service="management-service",
            version="0.1.0",
            nats_url=config["nats_url"],
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                detail="Service unhealthy", error_code="HEALTH_CHECK_FAILED"
            ).model_dump(),
        )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with welcome message."""
    return {"message": "Welcome to AegisTrader Management Service"}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint for Kubernetes."""
    return {"status": "ready"}


@app.get("/status", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    """Get current system status with deployment information."""
    try:
        current_time = datetime.now()
        start_time = app.state.start_time
        uptime_seconds = (current_time - start_time).total_seconds()

        return SystemStatus(
            timestamp=current_time.isoformat(),
            uptime_seconds=uptime_seconds,
            environment=os.getenv("ENVIRONMENT", "development"),
            connected_services=0,  # Will be implemented when NATS integration is added
            deployment_version="v1.0.0-demo",
        )
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                detail="Failed to retrieve system status",
                error_code="STATUS_CHECK_FAILED",
            ).model_dump(),
        )
# Updated at 2025年 08月 01日 星期五 21:01:36 CST
