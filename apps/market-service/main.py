"""Main entry point for market-service.

This service implements Domain-Driven Design with hexagonal architecture:
- Domain layer: Pure business logic (market data, gateways, subscriptions)
- Application layer: Use cases orchestrating domain logic
- Infrastructure layer: External adapters (NATS, databases, etc.)

The service uses the AegisSDK Service class which provides:
- Automatic service registration and discovery
- Built-in heartbeat management
- Lifecycle management (start/stop/health)
- RPC method registration
- Signal handling
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

# Import application layer use cases
from application.use_cases import (
    ConnectGatewayRequest,
    ConnectGatewayUseCase,
    GetMarketDataRequest,
    GetMarketDataUseCase,
    ProcessTickRequest,
    ProcessTickUseCase,
    SubscribeMarketDataRequest,
    SubscribeMarketDataUseCase,
)

# Import infrastructure implementations
from infra.repositories import (
    InMemoryEventStore,
    InMemoryMarketDataGatewayRepository,
    InMemoryTickDataRepository,
)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


# Infrastructure Adapters (implementing domain ports)


class NATSMarketDataSource:
    """NATS implementation of MarketDataSource port."""

    def __init__(self, nats_adapter: NATSAdapter):
        """Initialize with NATS adapter."""
        self.nats = nats_adapter
        self._is_connected = False

    async def connect(self, params: dict[str, str]) -> None:
        """Connect to market data source."""
        # NATS connection is handled by NATSAdapter
        self._is_connected = True
        logger.info(f"Market data source connected with params: {params}")

    async def disconnect(self) -> None:
        """Disconnect from market data source."""
        self._is_connected = False
        logger.info("Market data source disconnected")

    async def subscribe(self, symbol) -> None:
        """Subscribe to market data for a symbol."""
        # In real implementation, would subscribe to NATS subject
        subject = f"market.{symbol.exchange}.{symbol.value}"
        logger.info(f"Subscribed to {subject}")

    async def unsubscribe(self, symbol) -> None:
        """Unsubscribe from market data for a symbol."""
        subject = f"market.{symbol.exchange}.{symbol.value}"
        logger.info(f"Unsubscribed from {subject}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to source."""
        return self._is_connected


class NATSEventPublisher:
    """NATS implementation of EventPublisher port."""

    def __init__(self, nats_adapter: NATSAdapter):
        """Initialize with NATS adapter."""
        self.nats = nats_adapter

    async def publish(self, event) -> None:
        """Publish a single event."""
        subject = f"events.{event.event_type.lower()}"
        await self.nats.publish(subject, event.model_dump_json())

    async def publish_batch(self, events: list) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)


class MarketService:
    """Service implementation using SDK Service class with DDD/Hexagonal architecture."""

    def __init__(self):
        """Initialize the service."""
        self.service = None
        self.nats = None

        # Initialize repositories (infrastructure layer)
        self.gateway_repo = InMemoryMarketDataGatewayRepository()
        self.tick_repo = InMemoryTickDataRepository()
        self.event_store = InMemoryEventStore()

        # Will be initialized after NATS connection
        self.market_source = None
        self.event_publisher = None

        # Use cases (application layer)
        self.connect_gateway_use_case = None
        self.subscribe_use_case = None
        self.process_tick_use_case = None
        self.get_market_data_use_case = None

        # Service metadata
        self.service_name = ""
        self.instance_id = ""
        self.version = ""

    async def setup_handlers(self, service: Service) -> None:
        """Register RPC handlers with the SDK service.

        These handlers implement the primary ports of our hexagonal architecture,
        exposing application use cases through RPC.
        """

        async def handle_ping(params: dict) -> dict:
            """Health check endpoint - always include this."""
            return {"pong": True, "timestamp": params.get("timestamp")}

        async def handle_health(params: dict) -> dict:
            """Health status endpoint with DDD context."""
            gateways = await self.gateway_repo.list_active()
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance_id": self.instance_id,
                "version": self.version,
                "active_gateways": len(gateways),
                "domain_status": {
                    "gateway_repository": "active",
                    "tick_repository": "active",
                    "event_store": "active",
                },
            }

        async def handle_connect_gateway(params: dict) -> dict:
            """Connect a market data gateway."""
            request = ConnectGatewayRequest(**params)
            response = await self.connect_gateway_use_case.execute(request)
            return response.model_dump()

        async def handle_subscribe(params: dict) -> dict:
            """Subscribe to market data."""
            request = SubscribeMarketDataRequest(**params)
            response = await self.subscribe_use_case.execute(request)
            return response.model_dump()

        async def handle_process_tick(params: dict) -> dict:
            """Process incoming market tick."""
            request = ProcessTickRequest(**params)
            success = await self.process_tick_use_case.execute(request)
            return {"success": success}

        async def handle_get_market_data(params: dict) -> dict:
            """Retrieve historical market data."""
            request = GetMarketDataRequest(**params)
            response = await self.get_market_data_use_case.execute(request)
            return response.model_dump()

        # Register handlers with SDK service
        await service.register_rpc_method("ping", handle_ping)
        await service.register_rpc_method("health", handle_health)
        await service.register_rpc_method("connect_gateway", handle_connect_gateway)
        await service.register_rpc_method("subscribe", handle_subscribe)
        await service.register_rpc_method("process_tick", handle_process_tick)
        await service.register_rpc_method("get_market_data", handle_get_market_data)

        logger.info(f"Registered RPC handlers for {self.service_name}")

    async def run(self) -> None:
        """Run the service using SDK Service class with DDD architecture.

        The SDK handles infrastructure concerns while we focus on domain logic.
        """
        try:
            # Configuration
            self.service_name = os.getenv("SERVICE_NAME", "market-service")
            nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
            self.version = os.getenv("SERVICE_VERSION", "2.0.0")  # Updated for DDD refactor
            self.instance_id = os.getenv(
                "SERVICE_INSTANCE_ID",
                f"{self.service_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            )

            logger.info(
                f"Starting {self.service_name} "
                f"(instance: {self.instance_id}, version: {self.version})"
            )

            # Step 1: Connect to NATS (infrastructure)
            self.nats = NATSAdapter()
            await self.nats.connect(nats_url)
            logger.info("Connected to NATS")

            # Step 2: Initialize infrastructure adapters
            self.market_source = NATSMarketDataSource(self.nats)
            self.event_publisher = NATSEventPublisher(self.nats)

            # Step 3: Initialize use cases with dependencies
            self.connect_gateway_use_case = ConnectGatewayUseCase(
                self.gateway_repo, self.market_source, self.event_publisher
            )
            self.subscribe_use_case = SubscribeMarketDataUseCase(
                self.gateway_repo, self.market_source, self.event_publisher
            )
            self.process_tick_use_case = ProcessTickUseCase(
                self.gateway_repo, self.tick_repo, self.event_publisher
            )
            self.get_market_data_use_case = GetMarketDataUseCase(self.tick_repo)

            # Step 4: Setup KV store for service registry
            kv_store = NATSKVStore(self.nats)
            await kv_store.connect("service_registry")
            registry = KVServiceRegistry(kv_store=kv_store)

            # Step 5: Create SDK Service (handles infrastructure)
            config = ServiceConfig(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                heartbeat_interval=10.0,
                registry_ttl=30.0,
                enable_registration=True,
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

            # Step 6: Setup business logic handlers
            await self.setup_handlers(self.service)

            # Step 7: Start service
            await self.service.start()
            logger.info(f"{self.service_name} started successfully with DDD architecture")

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

        # Disconnect market source
        if self.market_source:
            await self.market_source.disconnect()

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
    service = MarketService()

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
