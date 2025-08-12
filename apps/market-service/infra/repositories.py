"""
Infrastructure Repository Implementations.

Concrete implementations of domain repository interfaces.
These are adapters in hexagonal architecture.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
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


class InMemoryMarketDataGatewayRepository(MarketDataGatewayRepository):
    """
    In-memory implementation of MarketDataGatewayRepository.

    Useful for testing and development.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._gateways: dict[str, MarketDataGateway] = {}
        self._gateways_by_uuid: dict[UUID, MarketDataGateway] = {}

    async def save(self, gateway: MarketDataGateway) -> None:
        """Persist a gateway aggregate."""
        self._gateways[gateway.gateway_id] = gateway
        self._gateways_by_uuid[gateway.id] = gateway

    async def get(self, gateway_id: str) -> MarketDataGateway | None:
        """Retrieve a gateway by ID."""
        return self._gateways.get(gateway_id)

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


class InMemoryEventStore(EventStore):
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


class ClickHouseTickDataRepository(TickDataRepository):
    """
    ClickHouse implementation of TickDataRepository.

    Stores ticks in ClickHouse for high-performance queries.
    """

    def __init__(self, connection_params: dict[str, Any]):
        """Initialize with ClickHouse connection."""
        # Import only when needed to avoid hard dependency
        try:
            from clickhouse_driver import Client
        except ImportError:
            raise ImportError("clickhouse-driver required for ClickHouseTickDataRepository")

        self.client = Client(**connection_params)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure the ticks table exists."""
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS market_ticks (
                symbol String,
                exchange String,
                price Decimal64(4),
                volume UInt64,
                timestamp DateTime64(3, 'UTC'),
                sequence_number UInt64,
                inserted_at DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, exchange, timestamp, sequence_number)
            SETTINGS index_granularity = 8192
        """
        )

    async def save_tick(self, tick: Tick) -> None:
        """Save a single tick."""
        self.client.execute(
            """
            INSERT INTO market_ticks (symbol, exchange, price, volume, timestamp, sequence_number)
            VALUES
            """,
            [
                (
                    tick.symbol.value,
                    tick.symbol.exchange,
                    float(tick.price.value),
                    tick.volume.value,
                    tick.timestamp,
                    tick.sequence_number,
                )
            ],
        )

    async def save_ticks(self, ticks: list[Tick]) -> None:
        """Save multiple ticks in batch."""
        if not ticks:
            return

        data = [
            (
                tick.symbol.value,
                tick.symbol.exchange,
                float(tick.price.value),
                tick.volume.value,
                tick.timestamp,
                tick.sequence_number,
            )
            for tick in ticks
        ]

        self.client.execute(
            """
            INSERT INTO market_ticks (symbol, exchange, price, volume, timestamp, sequence_number)
            VALUES
            """,
            data,
        )

    async def get_ticks(
        self,
        symbol: Symbol,
        time_range: TimeRange,
        limit: int | None = None,
    ) -> list[Tick]:
        """Retrieve ticks for a symbol within time range."""
        query = """
            SELECT symbol, exchange, price, volume, timestamp, sequence_number
            FROM market_ticks
            WHERE symbol = %(symbol)s
                AND exchange = %(exchange)s
                AND timestamp >= %(start)s
                AND timestamp <= %(end)s
            ORDER BY timestamp, sequence_number
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = self.client.execute(
            query,
            {
                "symbol": symbol.value,
                "exchange": symbol.exchange,
                "start": time_range.start,
                "end": time_range.end,
            },
        )

        from domain.market_data import Price, Volume

        return [
            Tick(
                symbol=Symbol(value=row[0], exchange=row[1]),
                price=Price(value=Decimal(str(row[2]))),
                volume=Volume(value=row[3]),
                timestamp=row[4],
                sequence_number=row[5],
            )
            for row in rows
        ]

    async def get_latest_tick(self, symbol: Symbol) -> Tick | None:
        """Get the most recent tick for a symbol."""
        query = """
            SELECT symbol, exchange, price, volume, timestamp, sequence_number
            FROM market_ticks
            WHERE symbol = %(symbol)s
                AND exchange = %(exchange)s
            ORDER BY timestamp DESC, sequence_number DESC
            LIMIT 1
        """

        rows = self.client.execute(
            query,
            {
                "symbol": symbol.value,
                "exchange": symbol.exchange,
            },
        )

        if not rows:
            return None

        row = rows[0]

        from domain.market_data import Price, Volume

        return Tick(
            symbol=Symbol(value=row[0], exchange=row[1]),
            price=Price(value=Decimal(str(row[2]))),
            volume=Volume(value=row[3]),
            timestamp=row[4],
            sequence_number=row[5],
        )

    async def count_ticks(self, symbol: Symbol, time_range: TimeRange) -> int:
        """Count ticks for a symbol within time range."""
        query = """
            SELECT count() as cnt
            FROM market_ticks
            WHERE symbol = %(symbol)s
                AND exchange = %(exchange)s
                AND timestamp >= %(start)s
                AND timestamp <= %(end)s
        """

        rows = self.client.execute(
            query,
            {
                "symbol": symbol.value,
                "exchange": symbol.exchange,
                "start": time_range.start,
                "end": time_range.end,
            },
        )

        return rows[0][0] if rows else 0
