"""Main entry point for the AegisTrader Monitor API.

This module sets up the FastAPI application using hexagonal architecture,
with clear separation between framework concerns and business logic.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .infrastructure.api.dependencies import get_configuration_port
from .infrastructure.api.error_handlers import register_error_handlers
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
    cleanup_task = None

    try:
        # Load and validate configuration during startup
        config_port = get_configuration_port()
        config = config_port.load_configuration()

        # Log configuration (without sensitive data)
        logger.info(f"Service configured for environment: {config.environment}")
        logger.info(f"API Port: {config.api_port}")
        logger.info(f"Log Level: {config.log_level}")

        # Initialize connection manager
        from .infrastructure.connection_manager import ConnectionManager, set_connection_manager

        connection_manager = ConnectionManager(config)
        await connection_manager.startup()
        set_connection_manager(connection_manager)

        # Start periodic cleanup task for stale entries
        from .infrastructure.api.dependencies import get_kv_store
        from .infrastructure.cleanup_task import StaleEntryCleanupTask

        try:
            kv_store = get_kv_store()
            cleanup_task = StaleEntryCleanupTask(
                kv_store=kv_store,
                cleanup_interval=300,  # 5 minutes
                stale_threshold=35,  # 30s TTL + 5s buffer
            )
            cleanup_task.start()
            logger.info("Started periodic cleanup task for stale service entries")
        except Exception as e:
            logger.warning(f"Failed to start cleanup task: {e}")
            # Don't fail startup if cleanup task fails

        logger.info("All connections initialized successfully")
        logger.info("All routes registered successfully")
        logger.info("Service startup complete")
        logger.info("Service is ready to handle requests")

        yield

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    finally:
        logger.info("Shutting down AegisTrader Management Service")

        # Stop cleanup task
        if cleanup_task:
            try:
                await cleanup_task.stop()
            except Exception as e:
                logger.warning(f"Error stopping cleanup task: {e}")

        # Clean up connections
        try:
            from .infrastructure.connection_manager import get_connection_manager

            manager = get_connection_manager()
            await manager.shutdown()
        except Exception:
            pass  # Ignore errors during shutdown  # nosec B110


app = FastAPI(
    title="AegisTrader Management Service",
    description="Management and monitoring API for the AegisTrader system",
    version="0.1.0",
    lifespan=lifespan,
)

# Register error handlers
register_error_handlers(app)

# Include routes from the infrastructure layer
app.include_router(router)
