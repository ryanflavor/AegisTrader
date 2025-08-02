"""Main entry point for the AegisTrader Monitor API.

This module sets up the FastAPI application using hexagonal architecture,
with clear separation between framework concerns and business logic.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .domain.exceptions import DomainException
from .domain.models import ServiceError
from .infrastructure.api.dependencies import (
    get_configuration_port,
)
from .infrastructure.api.routes import router

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks for the application.
    """
    logger.info("Starting AegisTrader Management Service")

    try:
        # Load and validate configuration during startup
        config_port = get_configuration_port()
        config = config_port.load_configuration()

        # Log configuration (without sensitive data)
        logger.info(f"Service configured for environment: {config.environment}")
        logger.info(f"API Port: {config.api_port}")
        logger.info(f"Log Level: {config.log_level}")

        logger.info("All routes registered successfully")
        logger.info("Service startup complete")
        logger.info("Service is ready to handle requests")

        yield

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    finally:
        logger.info("Shutting down AegisTrader Management Service")


app = FastAPI(
    title="AegisTrader Management Service",
    description="Management and monitoring API for the AegisTrader system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(DomainException)
async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    """Handle domain-specific exceptions."""
    logger.warning(f"Domain exception: {exc.message} (code: {exc.error_code})")

    # Map error codes to HTTP status codes
    status_code_map = {
        "SERVICE_UNAVAILABLE": 503,
        "HEALTH_CHECK_FAILED": 503,
        "CONFIGURATION_ERROR": 500,
    }

    status_code = status_code_map.get(exc.error_code, 500)

    error = ServiceError(
        detail=exc.message,
        error_code=exc.error_code,
    )

    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(exclude={"timestamp"}),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    error = ServiceError(
        detail="An internal server error occurred",
        error_code="INTERNAL_ERROR",
    )

    return JSONResponse(
        status_code=500,
        content=error.model_dump(exclude={"timestamp"}),
    )


# Include routes from the infrastructure layer
app.include_router(router)
