"""
Domain Ports (Interfaces) for Market Service.

These are abstract interfaces that define how the domain
interacts with external systems. Concrete implementations
(adapters) are in the infrastructure layer.

This follows hexagonal architecture where the domain defines
the interfaces it needs, and infrastructure provides implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from domain.market_data import (
    DomainEvent,
    MarketDataGateway,
    Symbol,
    Tick,
    TimeRange,
)

# Repository Interfaces (Secondary Ports)


class MarketDataGatewayRepository(Protocol):
    """
    Repository interface for MarketDataGateway aggregate.

    This is a secondary port - the domain calls it,
    infrastructure implements it.
    """

    async def save(self, gateway: MarketDataGateway) -> None:
        """Persist a gateway aggregate."""
        ...

    async def get(self, gateway_id: str) -> MarketDataGateway | None:
        """Retrieve a gateway by ID."""
        ...

    async def get_by_uuid(self, id: UUID) -> MarketDataGateway | None:
        """Retrieve a gateway by UUID."""
        ...

    async def list_active(self) -> list[MarketDataGateway]:
        """List all active gateways."""
        ...

    async def exists(self, gateway_id: str) -> bool:
        """Check if a gateway exists."""
        ...


class TickDataRepository(Protocol):
    """
    Repository interface for tick data persistence.

    Handles storage and retrieval of market ticks.
    """

    async def save_tick(self, tick: Tick) -> None:
        """Save a single tick."""
        ...

    async def save_ticks(self, ticks: list[Tick]) -> None:
        """Save multiple ticks in batch."""
        ...

    async def get_ticks(
        self,
        symbol: Symbol,
        time_range: TimeRange,
        limit: int | None = None,
    ) -> list[Tick]:
        """Retrieve ticks for a symbol within time range."""
        ...

    async def get_latest_tick(self, symbol: Symbol) -> Tick | None:
        """Get the most recent tick for a symbol."""
        ...

    async def count_ticks(self, symbol: Symbol, time_range: TimeRange) -> int:
        """Count ticks for a symbol within time range."""
        ...


class EventStore(Protocol):
    """
    Event store interface for domain events.

    Persists and retrieves domain events for event sourcing.
    """

    async def append_events(self, aggregate_id: str, events: list[DomainEvent]) -> None:
        """Append events to the event stream."""
        ...

    async def get_events(
        self,
        aggregate_id: str,
        from_version: int | None = None,
    ) -> list[DomainEvent]:
        """Retrieve events for an aggregate."""
        ...

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int | None = None,
    ) -> list[DomainEvent]:
        """Retrieve events by type."""
        ...


# External Service Interfaces (Secondary Ports)


class MarketDataSource(Protocol):
    """
    Interface for external market data sources.

    This port defines how the domain receives market data
    from external systems (gateways, feeds, etc).
    """

    async def connect(self, params: dict[str, str]) -> None:
        """Connect to market data source."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from market data source."""
        ...

    async def subscribe(self, symbol: Symbol) -> None:
        """Subscribe to market data for a symbol."""
        ...

    async def unsubscribe(self, symbol: Symbol) -> None:
        """Unsubscribe from market data for a symbol."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if connected to source."""
        ...


class EventPublisher(Protocol):
    """
    Interface for publishing domain events.

    Used to publish events to external systems
    (message bus, event streaming, etc).
    """

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single event."""
        ...

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Publish multiple events."""
        ...


# Unit of Work Pattern


class UnitOfWork(ABC):
    """
    Unit of Work pattern for managing transactions.

    Ensures consistency across multiple repository operations.
    """

    gateways: MarketDataGatewayRepository
    ticks: TickDataRepository
    events: EventStore

    @abstractmethod
    async def __aenter__(self):
        """Begin transaction."""
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End transaction."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
        ...
