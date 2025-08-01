from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status of the service")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    nats_url: str = Field(..., description="NATS connection URL")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")


# Environment variable validation
def validate_environment() -> Dict[str, str]:
    """Validate required environment variables."""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

    # Log configuration
    logger.info(f"NATS URL: {nats_url}")

    return {
        "nats_url": nats_url,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting AegisTrader Management Service")

    # Validate environment on startup
    env_config = validate_environment()
    app.state.config = env_config

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
async def root() -> Dict[str, str]:
    """Root endpoint with welcome message."""
    return {"message": "Welcome to AegisTrader Management Service"}


@app.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """Readiness check endpoint for Kubernetes."""
    return {"status": "ready"}
