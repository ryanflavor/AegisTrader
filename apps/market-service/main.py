"""Main entry point for market-service.

This service uses the AegisSDK Service class which provides:
- Automatic service registration and discovery
- Built-in heartbeat management
- Lifecycle management (start/stop/health)
- RPC method registration
- Signal handling

No need to reimplement these features - the SDK handles everything!
"""

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime

# Import AegisSDK components - these provide all infrastructure
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Import your business logic (if using DDD)
# from application.use_cases import YourUseCase
# from domain.services import YourDomainService

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MarketServiceService:
    """Service implementation using SDK Service class."""

    def __init__(self):
        """Initialize the service."""
        self.service = None
        self.nats = None

        # Initialize your domain services here (if using DDD)
        # self.domain_service = YourDomainService()
        # self.use_case = YourUseCase(self.domain_service)

    async def setup_handlers(self, service: Service) -> None:
        """Register RPC handlers with the SDK service.

        The SDK Service class provides:
        - Automatic request/response handling
        - Error management
        - Serialization/deserialization
        """

        async def handle_ping(params: dict) -> dict:
            """Health check endpoint - always include this."""
            return {"pong": True, "timestamp": params.get("timestamp")}

        async def handle_health(params: dict) -> dict:
            """Health status endpoint - always include this."""
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance_id": self.instance_id,
                "version": self.version,
            }

        # TODO: Add your business logic handlers here
        # async def handle_your_method(params: dict) -> dict:
        #     result = await self.use_case.execute(params)
        #     return result

        # Register handlers with SDK service
        await service.register_rpc_method("ping", handle_ping)
        await service.register_rpc_method("health", handle_health)
        # await service.register_rpc_method("your_method", handle_your_method)

        logger.info(f"Registered RPC handlers for {self.service_name}")

    async def run(self) -> None:
        """Run the service using SDK Service class.

        The SDK handles:
        - Service lifecycle (starting, running, stopping)
        - Automatic heartbeats (no manual implementation needed!)
        - Service registration (no manual KV operations needed!)
        - Graceful shutdown
        """
        try:
            # Configuration
            self.service_name = os.getenv("SERVICE_NAME", "market-service")
            nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
            self.version = os.getenv("SERVICE_VERSION", "1.0.0")
            self.instance_id = os.getenv(
                "SERVICE_INSTANCE_ID",
                f"{self.service_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            )

            logger.info(
                f"Starting {self.service_name} (instance: {self.instance_id}, version: {self.version})"
            )

            # Step 1: Connect to NATS
            self.nats = NATSAdapter()
            await self.nats.connect(nats_url)
            logger.info("Connected to NATS")

            # Step 2: Setup KV store for service registry
            kv_store = NATSKVStore(self.nats)
            await kv_store.connect("service_registry")
            registry = KVServiceRegistry(kv_store=kv_store)

            # Step 3: Create SDK Service (handles ALL infrastructure!)
            config = ServiceConfig(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                heartbeat_interval=10.0,  # SDK handles heartbeat automatically!
                registry_ttl=30.0,
                enable_registration=True,  # SDK handles registration automatically!
            )

            self.service = Service(
                service_name=config.service_name,
                message_bus=self.nats,
                instance_id=config.instance_id,
                version=config.version,
                service_registry=registry,
                logger=SimpleLogger(self.service_name),
                heartbeat_interval=config.heartbeat_interval,
                registry_ttl=config.registry_ttl,
                enable_registration=config.enable_registration,
            )

            # Step 4: Setup your business logic handlers
            await self.setup_handlers(self.service)

            # Step 5: Start service - SDK handles EVERYTHING!
            # - Lifecycle management
            # - Signal handling (SIGTERM, SIGINT)
            # - Automatic heartbeats
            # - Service registration
            # - Error recovery
            await self.service.start()
            logger.info(f"{self.service_name} started successfully")

            # Keep running until shutdown
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Service failed: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Starting cleanup...")

        # Stop SDK service (handles all cleanup)
        if self.service:
            await self.service.stop()
            logger.info("SDK service stopped")

        # Disconnect NATS
        if self.nats:
            await self.nats.disconnect()
            logger.info("NATS disconnected")

        logger.info("Cleanup complete")


async def main():
    """Main entry point."""
    service = MarketServiceService()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await service.run()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted")
