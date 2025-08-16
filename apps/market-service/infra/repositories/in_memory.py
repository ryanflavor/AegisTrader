"""
Infrastructure Repository Implementations.

Concrete implementations of domain repository interfaces.
These are adapters in hexagonal architecture.
"""

from __future__ import annotations

from uuid import UUID

from domain.market_data import (
    DomainEvent,
    MarketDataGateway,
    Symbol,
    Tick,
    TimeRange,
)
from domain.ports import (
    EventStore,
    MarketDataGatewayRepository,
    TickDataRepository,
)

from .base import BaseEventStore, BaseRepository, RepositoryConfig


class InMemoryMarketDataGatewayRepository(
    BaseRepository[MarketDataGateway], MarketDataGatewayRepository
):
    """
    In-memory implementation of MarketDataGatewayRepository.

    Useful for testing and development.
    """

    def __init__(self, config: RepositoryConfig | None = None):
        """Initialize in-memory storage."""
        super().__init__(config)
        self._gateways: dict[str, MarketDataGateway] = {}
        self._gateways_by_uuid: dict[UUID, MarketDataGateway] = {}

    async def save(self, gateway: MarketDataGateway) -> None:
        """Persist a gateway aggregate."""
        self._gateways[gateway.gateway_id] = gateway
        self._gateways_by_uuid[gateway.id] = gateway
        self._add_to_cache(gateway.gateway_id, gateway)

    async def get(self, gateway_id: str) -> MarketDataGateway | None:
        """Retrieve a gateway by ID."""
        # Check cache first
        cached = self._get_from_cache(gateway_id)
        if cached:
            return cached

        gateway = self._gateways.get(gateway_id)
        if gateway:
            self._add_to_cache(gateway_id, gateway)
        return gateway

    async def get_by_uuid(self, id: UUID) -> MarketDataGateway | None:
        """Retrieve a gateway by UUID."""
        return self._gateways_by_uuid.get(id)

    async def list_active(self) -> list[MarketDataGateway]:
        """List all active gateways."""
        return [g for g in self._gateways.values() if g.is_connected]

    async def exists(self, gateway_id: str) -> bool:
        """Check if a gateway exists."""
        return gateway_id in self._gateways


class InMemoryTickDataRepository(TickDataRepository):
    """
    In-memory implementation of TickDataRepository.

    Stores ticks in memory with indexing by symbol.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._ticks: dict[str, list[Tick]] = {}

    async def save_tick(self, tick: Tick) -> None:
        """Save a single tick."""
        symbol_key = str(tick.symbol)
        if symbol_key not in self._ticks:
            self._ticks[symbol_key] = []
        self._ticks[symbol_key].append(tick)
        # Keep sorted by timestamp
        self._ticks[symbol_key].sort(key=lambda t: t.timestamp)

    async def save_ticks(self, ticks: list[Tick]) -> None:
        """Save multiple ticks in batch."""
        for tick in ticks:
            await self.save_tick(tick)

    async def get_ticks(
        self,
        symbol: Symbol,
        time_range: TimeRange,
        limit: int | None = None,
    ) -> list[Tick]:
        """Retrieve ticks for a symbol within time range."""
        symbol_key = str(symbol)
        if symbol_key not in self._ticks:
            return []

        # Filter by time range
        filtered = [
            tick
            for tick in self._ticks[symbol_key]
            if time_range.start <= tick.timestamp <= time_range.end
        ]

        # Apply limit if specified
        if limit:
            filtered = filtered[:limit]

        return filtered

    async def get_latest_tick(self, symbol: Symbol) -> Tick | None:
        """Get the most recent tick for a symbol."""
        symbol_key = str(symbol)
        if symbol_key not in self._ticks or not self._ticks[symbol_key]:
            return None
        return self._ticks[symbol_key][-1]

    async def count_ticks(self, symbol: Symbol, time_range: TimeRange) -> int:
        """Count ticks for a symbol within time range."""
        ticks = await self.get_ticks(symbol, time_range)
        return len(ticks)


class InMemoryEventStore(BaseEventStore, EventStore):
    """
    In-memory implementation of EventStore.

    Stores domain events in memory for testing.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._events: dict[str, list[DomainEvent]] = {}
        self._events_by_type: dict[str, list[DomainEvent]] = {}

    async def append_events(self, aggregate_id: str, events: list[DomainEvent]) -> None:
        """Append events to the event stream."""
        if aggregate_id not in self._events:
            self._events[aggregate_id] = []

        for event in events:
            self._events[aggregate_id].append(event)

            # Index by type
            event_type = event.event_type
            if event_type not in self._events_by_type:
                self._events_by_type[event_type] = []
            self._events_by_type[event_type].append(event)

    async def get_events(
        self,
        aggregate_id: str,
        from_version: int | None = None,
    ) -> list[DomainEvent]:
        """Retrieve events for an aggregate."""
        if aggregate_id not in self._events:
            return []

        events = self._events[aggregate_id]

        if from_version is not None:
            events = [e for e in events if e.version >= from_version]

        return events

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int | None = None,
    ) -> list[DomainEvent]:
        """Retrieve events by type."""
        events = self._events_by_type.get(event_type, [])

        if limit:
            events = events[:limit]

        return events
