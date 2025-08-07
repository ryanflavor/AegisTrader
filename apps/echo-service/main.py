#!/usr/bin/env python3
"""Echo Service - World-class DDD showcase with hexagonal architecture.

This service demonstrates:
- Domain-Driven Design with hexagonal architecture
- Dependency injection and inversion of control
- Port and adapter pattern for infrastructure
- Multiple RPC endpoints with different modes
- Comprehensive metrics and health checks
- Auto-detection of K8s vs local environment
- Clean separation of concerns across layers
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.infrastructure.factory import EchoServiceFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ServiceRunner:
    """Runner for the echo service application."""

    def __init__(self):
        """Initialize the service runner."""
        self.application_service = None
        self.shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Run the service until shutdown signal."""
        try:
            # Create service using factory pattern
            logger.info("Creating Echo Service using factory pattern...")
            self.application_service = await EchoServiceFactory.create_production_service()

            # Start the application service
            await self.application_service.start()

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error(f"Failed to run service: {e}", exc_info=True)
            raise
        finally:
            # Ensure cleanup happens
            if self.application_service:
                await self.application_service.stop()

    def signal_handler(self, sig, _frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        self.shutdown_event.set()


async def main():
    """Main entry point with clean architecture."""
    runner = ServiceRunner()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, runner.signal_handler)
    signal.signal(signal.SIGTERM, runner.signal_handler)

    try:
        await runner.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
