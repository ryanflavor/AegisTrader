"""Service launcher that handles service initialization and lifecycle.

This module follows hexagonal architecture:
- Pure application orchestration
- Accepts dependencies via constructor injection
- Manages service lifecycle
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from application.use_cases import (
    ConnectGatewayRequest,
    GetMarketDataRequest,
    ProcessTickRequest,
    SubscribeMarketDataRequest,
)

if TYPE_CHECKING:
    from aegis_sdk.application.service import Service
    from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

    from application.health_service import DomainHealthService
    from application.use_cases import (
        ConnectGatewayUseCase,
        GetMarketDataUseCase,
        ProcessTickUseCase,
        SubscribeMarketDataUseCase,
    )
    from infra.factories.application_factory import ApplicationConfig
    from infra.repositories.in_memory import (
        InMemoryEventStore,
        InMemoryMarketDataGatewayRepository,
        InMemoryTickDataRepository,
    )

logger = logging.getLogger(__name__)


class ServiceLauncher:
    """
    Launches and manages the market service.

    This class follows pure application orchestration pattern:
    - All dependencies are injected via constructor
    - No infrastructure creation
    - Clean separation of concerns
    """

    def __init__(
        self,
        config: "ApplicationConfig",
        sdk_service: "Service",
        nats: "NATSAdapter",
        repositories: dict,
        services: dict,
        use_cases: dict,
        ctp_gateway_service: object | None = None,
    ):
        """
        Initialize service launcher with injected dependencies.

        Args:
            config: Application configuration
            sdk_service: Configured SDK service instance
            nats: Connected NATS adapter
            repositories: Dictionary of repository instances
            services: Dictionary of domain/application services
            use_cases: Dictionary of use case instances
            ctp_gateway_service: Optional CTP gateway service
        """
        # Configuration
        self.config = config
        self.service_name = config.service_name
        self.version = config.version
        self.instance_id = config.instance_id

        # Infrastructure
        self.service = sdk_service
        self.nats = nats
        self.ctp_gateway_service = ctp_gateway_service

        # Repositories
        self.gateway_repo: InMemoryMarketDataGatewayRepository = repositories["gateway_repo"]
        self.tick_repo: InMemoryTickDataRepository = repositories["tick_repo"]
        self.event_store: InMemoryEventStore = repositories["event_store"]

        # Services
        self.market_source = services["market_source"]
        self.event_publisher = services["event_publisher"]
        self.health_service: DomainHealthService = services["health_service"]

        # Use cases
        self.connect_gateway_use_case: ConnectGatewayUseCase = use_cases["connect_gateway"]
        self.subscribe_use_case: SubscribeMarketDataUseCase = use_cases["subscribe"]
        self.process_tick_use_case: ProcessTickUseCase = use_cases["process_tick"]
        self.get_market_data_use_case: GetMarketDataUseCase = use_cases["get_market_data"]

    async def setup_handlers(self) -> None:
        """Register RPC handlers with the SDK service."""

        async def handle_ping(params: dict) -> dict:
            """Health check endpoint."""
            return {"pong": True, "timestamp": params.get("timestamp")}

        async def handle_health(params: dict) -> dict:
            """Health status endpoint."""
            gateways = await self.gateway_repo.list_active()
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance_id": self.instance_id,
                "version": self.version,
                "active_gateways": len(gateways),
            }

        async def handle_health_check(params: dict) -> dict:
            """Domain health check endpoint."""
            from application.health_service import HealthCheckRequest

            request = HealthCheckRequest(timestamp=params.get("timestamp"))
            if self.health_service:
                response = await self.health_service.health_check(request)
                return response.model_dump()
            return {
                "status": "unknown",
                "message": "Health service not initialized",
                "timestamp": datetime.now(UTC).isoformat(),
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

        # Register handlers
        await self.service.register_rpc_method("ping", handle_ping)
        await self.service.register_rpc_method("health", handle_health)
        await self.service.register_rpc_method("health_check", handle_health_check)
        await self.service.register_rpc_method("connect_gateway", handle_connect_gateway)
        await self.service.register_rpc_method("subscribe", handle_subscribe)
        await self.service.register_rpc_method("process_tick", handle_process_tick)
        await self.service.register_rpc_method("get_market_data", handle_get_market_data)

        logger.info(f"Registered RPC handlers for {self.service_name}")

    async def run(self) -> None:
        """
        Run the service.

        All dependencies are already injected, so we just need to:
        1. Setup handlers
        2. Start the SDK service
        3. Start optional CTP gateway if configured
        4. Keep running until shutdown
        """
        logger.info(
            f"Starting {self.service_name} (instance: {self.instance_id}, version: {self.version})"
        )

        # Setup RPC handlers
        await self.setup_handlers()

        # Start SDK service
        await self.service.start()
        logger.info(f"{self.service_name} started successfully")

        # Wait for service to stabilize
        await asyncio.sleep(2)

        # Start CTP gateway if configured
        if self.ctp_gateway_service:
            logger.info("Starting CTP Gateway Service...")
            await self.ctp_gateway_service.start()
            logger.info("CTP Gateway Service started successfully")

        # Keep running until shutdown
        while True:
            await asyncio.sleep(1)

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Starting cleanup...")

        # Stop CTP gateway if initialized
        if self.ctp_gateway_service:
            try:
                await self.ctp_gateway_service.stop()
                logger.info("CTP Gateway Service stopped")
            except Exception as e:
                logger.error(f"Error stopping CTP Gateway: {e}")

        # Disconnect market source
        if self.market_source:
            await self.market_source.disconnect()

        # Stop SDK service
        if self.service:
            await self.service.stop()
            logger.info("SDK service stopped")

        # Disconnect NATS
        if self.nats:
            await self.nats.disconnect()
            logger.info("NATS disconnected")

        logger.info("Cleanup complete")
