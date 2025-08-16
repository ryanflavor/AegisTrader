"""
Application Factory for Market Service.

This factory follows hexagonal architecture principles by:
1. Centralizing dependency injection
2. Separating infrastructure creation from application logic
3. Providing clear boundaries between layers
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from aegis_sdk.application.dependency_provider import DependencyProvider
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure import DefaultUseCaseFactory, InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from pydantic import BaseModel, ConfigDict, Field

from application.health_service import DomainHealthService
from application.service_launcher import ServiceLauncher
from application.use_cases import (
    ConnectGatewayUseCase,
    GetMarketDataUseCase,
    ProcessTickUseCase,
    SubscribeMarketDataUseCase,
)
from infra.adapters.nats.nats_market_source import NATSMarketDataSource
from infra.election_factory import ElectionFactory
from infra.event_publisher_adapter import SDKEventPublisherAdapter
from infra.repositories.in_memory import (
    InMemoryEventStore,
    InMemoryMarketDataGatewayRepository,
    InMemoryTickDataRepository,
)

if TYPE_CHECKING:
    pass


class ApplicationConfig(BaseModel):
    """Configuration for the application."""

    model_config = ConfigDict(strict=True)

    service_name: str = Field(default="market-service")
    version: str = Field(default="2.0.0")
    instance_id: str | None = None
    nats_url: str = Field(default="nats://localhost:4222")
    enable_ctp_gateway: bool = Field(default=False)
    heartbeat_interval: float = Field(default=10.0)
    registry_ttl: float = Field(default=30.0)
    enable_registration: bool = Field(default=True)

    def generate_instance_id(self) -> str:
        """Generate instance ID if not provided."""
        if self.instance_id:
            return self.instance_id
        return f"{self.service_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


class ApplicationFactory:
    """
    Factory for creating the Market Service application.

    This factory follows the Dependency Injection pattern to:
    - Separate infrastructure concerns from business logic
    - Enable testing with mock dependencies
    - Provide clear layer boundaries
    """

    def __init__(self, config: ApplicationConfig | None = None):
        """Initialize factory with configuration."""
        self.config = config or self._load_config_from_env()
        self.config.instance_id = self.config.generate_instance_id()

    @staticmethod
    def _load_config_from_env() -> ApplicationConfig:
        """Load configuration from environment variables."""
        return ApplicationConfig(
            service_name=os.getenv("SERVICE_NAME", "market-service"),
            version=os.getenv("SERVICE_VERSION", "2.0.0"),
            instance_id=os.getenv("SERVICE_INSTANCE_ID"),
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            enable_ctp_gateway=os.getenv("ENABLE_CTP_GATEWAY", "false").lower() == "true",
            heartbeat_interval=float(os.getenv("HEARTBEAT_INTERVAL", "10.0")),
            registry_ttl=float(os.getenv("REGISTRY_TTL", "30.0")),
            enable_registration=os.getenv("ENABLE_REGISTRATION", "true").lower() == "true",
        )

    async def create_infrastructure(self) -> dict:
        """
        Create all infrastructure components.

        Returns a dictionary of infrastructure dependencies.
        """
        # Connect to NATS
        nats = NATSAdapter()
        await nats.connect(self.config.nats_url)

        # Create KV stores
        service_kv = NATSKVStore(nats)
        await service_kv.connect("service_registry")

        gateway_kv = None
        if self.config.enable_ctp_gateway:
            gateway_kv = NATSKVStore(nats)
            await gateway_kv.connect("gateway_registry")

        # Create registries
        service_registry = KVServiceRegistry(kv_store=service_kv)
        gateway_registry = KVServiceRegistry(kv_store=gateway_kv) if gateway_kv else None

        # Create logger
        logger = SimpleLogger(self.config.service_name)

        # Create SDK service
        sdk_config = ServiceConfig(
            service_name=self.config.service_name,
            instance_id=self.config.instance_id,
            version=self.config.version,
            heartbeat_interval=self.config.heartbeat_interval,
            registry_ttl=self.config.registry_ttl,
            enable_registration=self.config.enable_registration,
        )

        sdk_service = Service(
            service_name=sdk_config.service_name,
            message_bus=nats,
            instance_id=sdk_config.instance_id,
            version=sdk_config.version,
            service_registry=service_registry,
            logger=logger,
            heartbeat_interval=sdk_config.heartbeat_interval,
            registry_ttl=sdk_config.registry_ttl,
            enable_registration=sdk_config.enable_registration,
        )

        return {
            "nats": nats,
            "sdk_service": sdk_service,
            "service_registry": service_registry,
            "gateway_registry": gateway_registry,
            "logger": logger,
        }

    def create_repositories(self) -> dict:
        """Create repository instances."""
        return {
            "gateway_repo": InMemoryMarketDataGatewayRepository(),
            "tick_repo": InMemoryTickDataRepository(),
            "event_store": InMemoryEventStore(),
        }

    def create_domain_services(self, infrastructure: dict, repositories: dict) -> dict:
        """Create domain and application services."""
        # Create market data source
        market_source = NATSMarketDataSource(infrastructure["nats"])

        # Create event publisher
        event_publisher = SDKEventPublisherAdapter(infrastructure["sdk_service"])

        # Create health service
        health_service = DomainHealthService(
            service=infrastructure["sdk_service"],
            gateway_repo=repositories["gateway_repo"],
            tick_repo=repositories["tick_repo"],
            market_source=market_source,
            nats_adapter=infrastructure["nats"],
        )

        return {
            "market_source": market_source,
            "event_publisher": event_publisher,
            "health_service": health_service,
        }

    def create_use_cases(self, repositories: dict, services: dict) -> dict:
        """Create application use cases."""
        return {
            "connect_gateway": ConnectGatewayUseCase(
                repositories["gateway_repo"],
                services["market_source"],
                services["event_publisher"],
            ),
            "subscribe": SubscribeMarketDataUseCase(
                repositories["gateway_repo"],
                services["market_source"],
                services["event_publisher"],
            ),
            "process_tick": ProcessTickUseCase(
                repositories["gateway_repo"],
                repositories["tick_repo"],
                services["event_publisher"],
            ),
            "get_market_data": GetMarketDataUseCase(
                repositories["tick_repo"],
            ),
        }

    async def create_ctp_gateway_service(self, infrastructure: dict) -> object | None:
        """
        Create CTP gateway service if enabled.

        This is kept separate as it's an optional component.
        """
        if not self.config.enable_ctp_gateway:
            return None

        # Register SDK dependencies for CTP
        DependencyProvider.register_defaults(
            election_factory=ElectionFactory(),
            use_case_factory=DefaultUseCaseFactory(),
            metrics_class=InMemoryMetrics,
        )

        # Import here to avoid circular dependency
        from infra.factories.ctp_service_factory import CTPServiceFactory

        return await CTPServiceFactory.create_gateway_service(
            nats_adapter=infrastructure["nats"],
            service_registry=infrastructure["gateway_registry"],
            service_discovery=None,
            instance_id=self.config.instance_id,
        )

    async def create_application(self) -> ServiceLauncher:
        """
        Create the complete application with all dependencies.

        This is the main factory method that assembles the entire application.
        """
        # Create layers in order
        infrastructure = await self.create_infrastructure()
        repositories = self.create_repositories()
        services = self.create_domain_services(infrastructure, repositories)
        use_cases = self.create_use_cases(repositories, services)

        # Create optional CTP gateway
        ctp_gateway = await self.create_ctp_gateway_service(infrastructure)

        # Create service launcher with injected dependencies
        launcher = ServiceLauncher(
            config=self.config,
            sdk_service=infrastructure["sdk_service"],
            nats=infrastructure["nats"],
            repositories=repositories,
            services=services,
            use_cases=use_cases,
            ctp_gateway_service=ctp_gateway,
        )

        return launcher

    async def cleanup(self, launcher: ServiceLauncher) -> None:
        """Clean up all resources."""
        if launcher:
            await launcher.cleanup()
