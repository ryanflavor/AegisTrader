"""
ClickHouse repository implementation.

Production-ready persistence layer for high-volume tick data.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.market_data import Price, Symbol, Tick, TimeRange, Volume
from domain.ports import TickDataRepository


class ClickHouseConfig(BaseModel):
    """Configuration for ClickHouse connection."""

    model_config = ConfigDict(strict=True, frozen=True)

    host: str = Field(default="localhost", description="ClickHouse host")
    port: int = Field(default=9000, description="ClickHouse port", gt=0, le=65535)
    database: str = Field(default="default", description="Database name")
    user: str = Field(default="default", description="Username")
    password: str = Field(default="", description="Password")

    # Performance settings
    batch_size: int = Field(default=1000, description="Batch insert size", gt=0)
    compression: bool = Field(default=True, description="Enable compression")

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is not empty."""
        if not v or not v.strip():
            raise ValueError("Host cannot be empty")
        return v.strip()


class ClickHouseTickDataRepository(TickDataRepository):
    """
    ClickHouse implementation of TickDataRepository.

    Stores ticks in ClickHouse for high-performance queries.
    Follows hexagonal architecture by implementing the domain port.
    """

    def __init__(self, config: ClickHouseConfig):
        """Initialize with ClickHouse configuration.

        Args:
            config: ClickHouse connection configuration
        """
        # Import only when needed to avoid hard dependency
        try:
            from clickhouse_driver import Client
        except ImportError as e:
            raise ImportError(
                "clickhouse-driver required for ClickHouseTickDataRepository. "
                "Install with: pip install clickhouse-driver"
            ) from e

        self.config = config
        self.client = Client(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password,
            compression=config.compression,
        )
        self._ensure_table()
        self._batch_buffer: list[tuple] = []

    def _ensure_table(self) -> None:
        """Ensure the ticks table exists with proper schema."""
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
        """Save a single tick, using batch buffer for efficiency.

        Args:
            tick: The tick to save
        """
        self._batch_buffer.append(self._tick_to_tuple(tick))

        if len(self._batch_buffer) >= self.config.batch_size:
            await self._flush_batch()

    async def save_ticks(self, ticks: list[Tick]) -> None:
        """Save multiple ticks in batch.

        Args:
            ticks: List of ticks to save
        """
        if not ticks:
            return

        data = [self._tick_to_tuple(tick) for tick in ticks]

        # Add to buffer and flush if needed
        self._batch_buffer.extend(data)

        if len(self._batch_buffer) >= self.config.batch_size:
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Flush the batch buffer to ClickHouse."""
        if not self._batch_buffer:
            return

        self.client.execute(
            """
            INSERT INTO market_ticks (symbol, exchange, price, volume, timestamp, sequence_number)
            VALUES
            """,
            self._batch_buffer,
        )
        self._batch_buffer.clear()

    def _tick_to_tuple(self, tick: Tick) -> tuple:
        """Convert tick to tuple for ClickHouse insertion.

        Args:
            tick: The tick to convert

        Returns:
            Tuple representation of the tick
        """
        return (
            tick.symbol.value,
            tick.symbol.exchange,
            float(tick.price.value),
            tick.volume.value,
            tick.timestamp,
            tick.sequence_number,
        )

    async def get_ticks(
        self,
        symbol: Symbol,
        time_range: TimeRange,
        limit: int | None = None,
    ) -> list[Tick]:
        """Retrieve ticks for a symbol within time range.

        Args:
            symbol: The symbol to query
            time_range: Time range for the query
            limit: Optional limit on number of results

        Returns:
            List of ticks matching the criteria
        """
        # Flush any pending writes first
        await self._flush_batch()

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

        return [self._row_to_tick(row) for row in rows]

    async def get_latest_tick(self, symbol: Symbol) -> Tick | None:
        """Get the most recent tick for a symbol.

        Args:
            symbol: The symbol to query

        Returns:
            The latest tick if found, None otherwise
        """
        # Flush any pending writes first
        await self._flush_batch()

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

        return self._row_to_tick(rows[0])

    async def count_ticks(self, symbol: Symbol, time_range: TimeRange) -> int:
        """Count ticks for a symbol within time range.

        Args:
            symbol: The symbol to query
            time_range: Time range for the query

        Returns:
            Count of ticks matching the criteria
        """
        # Flush any pending writes first
        await self._flush_batch()

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

    def _row_to_tick(self, row: tuple) -> Tick:
        """Convert a database row to a Tick object.

        Args:
            row: Database row tuple

        Returns:
            Tick domain object
        """
        return Tick(
            symbol=Symbol(value=row[0], exchange=row[1]),
            price=Price(value=Decimal(str(row[2]))),
            volume=Volume(value=row[3]),
            timestamp=row[4],
            sequence_number=row[5],
        )

    async def close(self) -> None:
        """Close the ClickHouse connection and flush pending data."""
        await self._flush_batch()
        # ClickHouse client doesn't have an explicit close method
