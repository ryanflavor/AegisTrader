"""
Concrete infrastructure factory implementation.

Provides production-ready implementations of all infrastructure components
following hexagonal architecture and DDD principles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from pydantic import BaseModel

from domain.ports import (
    EventPublisher,
    EventStore,
    MarketDataGatewayRepository,
    MarketDataSource,
    TickDataRepository,
)
from infra.adapters.nats.nats_market_source import (
    MarketDataSourceConfig,
    NATSMarketDataSource,
)
from infra.event_publisher_adapter import SDKEventPublisherAdapter
from infra.repositories.base import RepositoryConfig
from infra.repositories.clickhouse import ClickHouseConfig, ClickHouseTickDataRepository
from infra.repositories.in_memory import (
    InMemoryEventStore,
    InMemoryMarketDataGatewayRepository,
    InMemoryTickDataRepository,
)

from .abstract_factory import (
    AbstractInfrastructureFactory,
    AbstractRepositoryFactory,
    AbstractServiceFactory,
    FactoryRegistry,
)

if TYPE_CHECKING:
    from aegis_sdk.application.service import Service


class InMemoryRepositoryFactory(AbstractRepositoryFactory):
    """Factory for creating in-memory repository instances."""

    async def create_gateway_repository(
        self, config: BaseModel | None = None
    ) -> MarketDataGatewayRepository:
        """Create in-memory gateway repository."""
        repo_config = config if isinstance(config, RepositoryConfig) else RepositoryConfig()
        return InMemoryMarketDataGatewayRepository(repo_config)

    async def create_tick_repository(self, config: BaseModel | None = None) -> TickDataRepository:
        """Create in-memory tick repository."""
        return InMemoryTickDataRepository()

    async def create_event_store(self, config: BaseModel | None = None) -> EventStore:
        """Create in-memory event store."""
        return InMemoryEventStore()


class ProductionRepositoryFactory(AbstractRepositoryFactory):
    """Factory for creating production repository instances."""

    def __init__(self, clickhouse_config: ClickHouseConfig | None = None):
        """Initialize with optional ClickHouse configuration.

        Args:
            clickhouse_config: Configuration for ClickHouse connection
        """
        self.clickhouse_config = clickhouse_config

    async def create_gateway_repository(
        self, config: BaseModel | None = None
    ) -> MarketDataGatewayRepository:
        """Create production gateway repository with caching."""
        repo_config = (
            config
            if isinstance(config, RepositoryConfig)
            else RepositoryConfig(enable_caching=True, cache_ttl_seconds=60, max_cache_size=100)
        )
        return InMemoryMarketDataGatewayRepository(repo_config)

    async def create_tick_repository(self, config: BaseModel | None = None) -> TickDataRepository:
        """Create ClickHouse tick repository if configured, otherwise in-memory."""
        if self.clickhouse_config:
            return ClickHouseTickDataRepository(self.clickhouse_config)
        return InMemoryTickDataRepository()

    async def create_event_store(self, config: BaseModel | None = None) -> EventStore:
        """Create production event store."""
        # In production, this could be Kafka, EventStore DB, etc.
        # For now, using in-memory with potential for persistence
        return InMemoryEventStore()


class ServiceComponentFactory(AbstractServiceFactory):
    """Factory for creating service components."""

    def __init__(self, nats_adapter: NATSAdapter | None = None, sdk_service: Service | None = None):
        """Initialize with required dependencies.

        Args:
            nats_adapter: NATS adapter for messaging
            sdk_service: SDK service instance
        """
        self.nats_adapter = nats_adapter
        self.sdk_service = sdk_service

    async def create_market_source(self, config: BaseModel | None = None) -> MarketDataSource:
        """Create NATS market data source."""
        if not self.nats_adapter:
            raise ValueError("NATS adapter required for market source")

        source_config = (
            config if isinstance(config, MarketDataSourceConfig) else MarketDataSourceConfig()
        )
        return NATSMarketDataSource(self.nats_adapter, source_config)

    async def create_event_publisher(self, config: BaseModel | None = None) -> EventPublisher:
        """Create SDK event publisher."""
        if not self.sdk_service:
            raise ValueError("SDK service required for event publisher")

        return SDKEventPublisherAdapter(self.sdk_service)


class InfrastructureFactory(AbstractInfrastructureFactory):
    """Main infrastructure factory implementation."""

    def __init__(self, environment: str = "development"):
        """Initialize infrastructure factory.

        Args:
            environment: Environment name (development, staging, production)
        """
        self.environment = environment
        self._repository_factory: AbstractRepositoryFactory | None = None
        self._service_factory: AbstractServiceFactory | None = None
        self._registry = FactoryRegistry()
        self._nats_adapter: NATSAdapter | None = None
        self._sdk_service: Service | None = None

    def get_repository_factory(self) -> AbstractRepositoryFactory:
        """Get repository factory based on environment."""
        if not self._repository_factory:
            if self.environment == "production":
                # Try to load ClickHouse config from environment
                try:
                    clickhouse_config = ClickHouseConfig.from_env("CLICKHOUSE_")
                    self._repository_factory = ProductionRepositoryFactory(clickhouse_config)
                except Exception:
                    # Fall back to in-memory if ClickHouse not configured
                    self._repository_factory = ProductionRepositoryFactory()
            else:
                self._repository_factory = InMemoryRepositoryFactory()

        return self._repository_factory

    def get_service_factory(self) -> AbstractServiceFactory:
        """Get service factory."""
        if not self._service_factory:
            self._service_factory = ServiceComponentFactory(self._nats_adapter, self._sdk_service)
        return self._service_factory

    async def initialize(self, config: BaseModel) -> None:
        """Initialize infrastructure components.

        Args:
            config: Configuration containing NATS and service details
        """
        # Extract NATS configuration
        if hasattr(config, "nats_url"):
            self._nats_adapter = NATSAdapter()
            await self._nats_adapter.connect(config.nats_url)

        # SDK service would be initialized here
        # self._sdk_service = await create_sdk_service(config)

        # Register factories
        self._registry.register("repository", self.get_repository_factory())
        self._registry.register("service", self.get_service_factory())

    async def cleanup(self) -> None:
        """Clean up all resources."""
        # Close NATS connection
        if self._nats_adapter:
            await self._nats_adapter.close()

        # Clear registry
        self._registry.clear()

        # Reset factories
        self._repository_factory = None
        self._service_factory = None

    def set_sdk_service(self, service: Service) -> None:
        """Set SDK service for factories that need it.

        Args:
            service: SDK service instance
        """
        self._sdk_service = service
        if self._service_factory:
            self._service_factory.sdk_service = service

    def set_nats_adapter(self, adapter: NATSAdapter) -> None:
        """Set NATS adapter for factories that need it.

        Args:
            adapter: NATS adapter instance
        """
        self._nats_adapter = adapter
        if self._service_factory:
            self._service_factory.nats_adapter = adapter


def create_infrastructure_factory(environment: str = "development") -> InfrastructureFactory:
    """Create infrastructure factory for the specified environment.

    Args:
        environment: Target environment (development, staging, production)

    Returns:
        Configured infrastructure factory
    """
    return InfrastructureFactory(environment)
