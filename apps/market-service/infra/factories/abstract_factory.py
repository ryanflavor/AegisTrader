"""
Abstract factory pattern for infrastructure components.

Follows DDD and hexagonal architecture principles to provide
clean dependency injection and component creation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from domain.ports import (
    EventPublisher,
    EventStore,
    MarketDataGatewayRepository,
    MarketDataSource,
    TickDataRepository,
)

# Type variables for generic factory
T = TypeVar("T")
ConfigT = TypeVar("ConfigT", bound=BaseModel)


class AbstractRepositoryFactory(ABC):
    """Abstract factory for creating repository instances."""

    @abstractmethod
    async def create_gateway_repository(
        self, config: BaseModel | None = None
    ) -> MarketDataGatewayRepository:
        """Create market data gateway repository.

        Args:
            config: Optional configuration for the repository

        Returns:
            MarketDataGatewayRepository implementation
        """
        pass

    @abstractmethod
    async def create_tick_repository(self, config: BaseModel | None = None) -> TickDataRepository:
        """Create tick data repository.

        Args:
            config: Optional configuration for the repository

        Returns:
            TickDataRepository implementation
        """
        pass

    @abstractmethod
    async def create_event_store(self, config: BaseModel | None = None) -> EventStore:
        """Create event store.

        Args:
            config: Optional configuration for the event store

        Returns:
            EventStore implementation
        """
        pass


class AbstractServiceFactory(ABC):
    """Abstract factory for creating service components."""

    @abstractmethod
    async def create_market_source(self, config: BaseModel | None = None) -> MarketDataSource:
        """Create market data source.

        Args:
            config: Optional configuration for the market source

        Returns:
            MarketDataSource implementation
        """
        pass

    @abstractmethod
    async def create_event_publisher(self, config: BaseModel | None = None) -> EventPublisher:
        """Create event publisher.

        Args:
            config: Optional configuration for the publisher

        Returns:
            EventPublisher implementation
        """
        pass


class AbstractInfrastructureFactory(ABC):
    """Main abstract factory for all infrastructure components."""

    @abstractmethod
    def get_repository_factory(self) -> AbstractRepositoryFactory:
        """Get repository factory instance.

        Returns:
            Repository factory for creating repositories
        """
        pass

    @abstractmethod
    def get_service_factory(self) -> AbstractServiceFactory:
        """Get service factory instance.

        Returns:
            Service factory for creating services
        """
        pass

    @abstractmethod
    async def initialize(self, config: BaseModel) -> None:
        """Initialize the infrastructure factory.

        Args:
            config: Configuration for initialization
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up all resources."""
        pass


class BaseComponentFactory(ABC, Generic[T, ConfigT]):
    """Base factory for creating configured components."""

    def __init__(self, default_config: ConfigT | None = None):
        """Initialize with optional default configuration.

        Args:
            default_config: Default configuration to use if none provided
        """
        self.default_config = default_config

    @abstractmethod
    async def create(self, config: ConfigT | None = None) -> T:
        """Create component instance.

        Args:
            config: Optional configuration override

        Returns:
            Created component instance
        """
        pass

    def get_config(self, config: ConfigT | None = None) -> ConfigT:
        """Get configuration with fallback to default.

        Args:
            config: Optional configuration override

        Returns:
            Configuration to use
        """
        if config is not None:
            return config
        if self.default_config is not None:
            return self.default_config
        raise ValueError("No configuration provided and no default available")


class FactoryRegistry:
    """Registry for managing factory instances."""

    def __init__(self):
        """Initialize empty registry."""
        self._factories: dict[str, Any] = {}

    def register(self, name: str, factory: Any) -> None:
        """Register a factory.

        Args:
            name: Name to register under
            factory: Factory instance
        """
        if name in self._factories:
            raise ValueError(f"Factory '{name}' already registered")
        self._factories[name] = factory

    def get(self, name: str) -> Any:
        """Get a registered factory.

        Args:
            name: Name of the factory

        Returns:
            Factory instance

        Raises:
            KeyError: If factory not found
        """
        if name not in self._factories:
            raise KeyError(f"Factory '{name}' not found")
        return self._factories[name]

    def unregister(self, name: str) -> None:
        """Unregister a factory.

        Args:
            name: Name of the factory to remove
        """
        self._factories.pop(name, None)

    def clear(self) -> None:
        """Clear all registered factories."""
        self._factories.clear()

    def list_factories(self) -> list[str]:
        """List all registered factory names.

        Returns:
            List of factory names
        """
        return list(self._factories.keys())
