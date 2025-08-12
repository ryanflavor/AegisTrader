"""
Value Objects for Market Data bounded context.

These immutable objects represent fundamental market concepts.
All use Pydantic v2 with strict validation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InstrumentType(str, Enum):
    """Types of financial instruments."""

    STOCK = "STOCK"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"


class OrderType(str, Enum):
    """Types of orders."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(str, Enum):
    """Side of the order."""

    BUY = "BUY"
    SELL = "SELL"


class Symbol(BaseModel):
    """
    Represents a trading symbol/ticker.

    Immutable value object that encapsulates symbol validation rules.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: Annotated[str, Field(min_length=1, max_length=20)]
    exchange: Annotated[str, Field(min_length=1, max_length=10)]

    @field_validator("value")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol."""
        v = v.strip().upper()
        if not v:
            raise ValueError("Symbol cannot be empty")
        if not v.replace(".", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid symbol format: {v}")
        return v

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        """Validate and normalize exchange."""
        v = v.strip().upper()
        if not v:
            raise ValueError("Exchange cannot be empty")
        return v

    def __str__(self) -> str:
        """String representation."""
        return f"{self.value}.{self.exchange}"


class Price(BaseModel):
    """
    Represents a price value with precision handling.

    Uses Decimal for accurate financial calculations.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: Annotated[Decimal, Field(ge=0, decimal_places=4)]
    currency: Annotated[str, Field(default="USD", min_length=3, max_length=3)]

    @field_validator("value")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Ensure price has proper precision."""
        if v < 0:
            raise ValueError("Price cannot be negative")
        # Quantize to 4 decimal places
        return v.quantize(Decimal("0.0001"))

    def add(self, other: Price) -> Price:
        """Add two prices (must be same currency)."""
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add prices with different currencies: {self.currency} != {other.currency}"
            )
        return Price(value=self.value + other.value, currency=self.currency)

    def multiply(self, factor: Decimal) -> Price:
        """Multiply price by a factor."""
        return Price(value=self.value * factor, currency=self.currency)

    def __str__(self) -> str:
        """String representation."""
        return f"{self.currency} {self.value:.4f}"


class Volume(BaseModel):
    """Represents trading volume."""

    model_config = ConfigDict(frozen=True, strict=True)

    value: Annotated[int, Field(ge=0)]

    def add(self, other: Volume) -> Volume:
        """Add two volumes."""
        return Volume(value=self.value + other.value)

    def __str__(self) -> str:
        """String representation."""
        return f"{self.value:,}"


class MarketDepth(BaseModel):
    """
    Represents market depth at a specific price level.

    Immutable snapshot of bid/ask at a price point.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    bid_price: Price
    bid_volume: Volume
    ask_price: Price
    ask_volume: Volume
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v

    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread."""
        if self.bid_price.currency != self.ask_price.currency:
            raise ValueError("Cannot calculate spread with different currencies")
        return self.ask_price.value - self.bid_price.value

    @property
    def mid_price(self) -> Price:
        """Calculate mid price."""
        if self.bid_price.currency != self.ask_price.currency:
            raise ValueError("Cannot calculate mid price with different currencies")
        mid_value = (self.bid_price.value + self.ask_price.value) / 2
        return Price(value=mid_value, currency=self.bid_price.currency)


class Tick(BaseModel):
    """
    Represents a single market tick/trade.

    Immutable record of a single market event.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    symbol: Symbol
    price: Price
    volume: Volume
    timestamp: datetime
    sequence_number: Annotated[int, Field(ge=0)]

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v

    def __str__(self) -> str:
        """String representation."""
        return f"Tick({self.symbol} @ {self.price} x {self.volume} at {self.timestamp.isoformat()})"


class TimeRange(BaseModel):
    """
    Represents a time range for queries.

    Ensures start is before end and both are timezone-aware.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        """Ensure timestamps are timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")
        return v

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        """Ensure end is after start."""
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("End time must be after start time")
        return v

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return (self.end - self.start).total_seconds()
