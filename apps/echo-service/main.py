#!/usr/bin/env python3
"""Echo Service - Demonstrates clean SDK integration without reinventing wheels.

This service showcases:
- Full integration with aegis-sdk and aegis-sdk-dev
- No legacy code or custom adapters
- SDK's built-in service lifecycle management
- Automatic heartbeat and registration
- Domain-Driven Design with hexagonal architecture
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from app.infrastructure.factory import EchoServiceFactory

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the echo service."""
    service = None
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create service using factory with SDK-dev bootstrap
        logger.info("Creating Echo Service with SDK-dev bootstrap...")
        service = await EchoServiceFactory.create_production_service()

        # Start the service (SDK handles everything)
        logger.info("Starting Echo Service...")
        await service.start()

        logger.info("Echo Service is running. Press Ctrl+C to stop.")

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if service:
            logger.info("Shutting down Echo Service...")
            await EchoServiceFactory.cleanup_service(service)
        logger.info("Echo Service shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
