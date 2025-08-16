"""Main entry point for market-service.

This minimal entry point follows DDD and hexagonal architecture principles:
- All infrastructure setup is delegated to ApplicationFactory
- Main only handles signal management and bootstrapping
- Clean separation of concerns
"""

import asyncio
import logging
import signal

from infra.factories.application_factory import ApplicationFactory

# Import and use centralized logging configuration
from logging_config import setup_logging

# Setup logging with clean output
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Main entry point - uses ApplicationFactory for dependency injection."""
    launcher = None
    factory = ApplicationFactory()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Create application with all dependencies injected
        launcher = await factory.create_application()

        # Run the application
        await launcher.run()

    except asyncio.CancelledError:
        logger.info("Service cancelled")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
    finally:
        if launcher:
            await launcher.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted")
