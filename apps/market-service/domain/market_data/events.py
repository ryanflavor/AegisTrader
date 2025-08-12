"""
Domain Events for Market Data bounded context.

These events represent important things that have happened
in the domain. They are immutable and use Pydantic v2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .value_objects import InstrumentType, Symbol, Tick


class DomainEvent(BaseModel):
    """
    Base class for all domain events.

    Provides common fields and behavior for domain events.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: str
    version: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Get the event type name."""
        return self.__class__.__name__


class MarketDataSubscribed(DomainEvent):
    """Event raised when market data subscription is created."""

    symbol: Symbol
    subscriber_id: str
    instrument_type: InstrumentType


class MarketDataUnsubscribed(DomainEvent):
    """Event raised when market data subscription is cancelled."""

    symbol: Symbol
    subscriber_id: str
    total_ticks: int


class TickReceived(DomainEvent):
    """Event raised when a tick is received from market source."""

    tick: Tick
    source: str
    gateway_id: str


class TickProcessed(DomainEvent):
    """Event raised when a tick has been processed."""

    symbol: Symbol
    tick: Tick
    subscriber_id: str


class TickValidationFailed(DomainEvent):
    """Event raised when tick validation fails."""

    symbol: Symbol
    reason: str
    tick_data: dict[str, Any]


class MarketSessionStarted(DomainEvent):
    """Event raised when a market session starts."""

    gateway_id: str
    session_id: UUID
    connection_params: dict[str, str]


class MarketSessionEnded(DomainEvent):
    """Event raised when a market session ends."""

    gateway_id: str
    session_id: UUID
    total_ticks: int
    total_errors: int
    duration_seconds: float


class GatewayConnected(DomainEvent):
    """Event raised when gateway connection is established."""

    gateway_id: str
    gateway_type: str
    connection_time: datetime


class GatewayDisconnected(DomainEvent):
    """Event raised when gateway connection is lost."""

    gateway_id: str
    reason: str
    disconnection_time: datetime


class SubscriptionLimitReached(DomainEvent):
    """Event raised when subscription limit is reached."""

    gateway_id: str
    current_count: int
    max_allowed: int
    requested_symbol: Symbol


class AnomalyDetected(DomainEvent):
    """Event raised when market data anomaly is detected."""

    symbol: Symbol
    anomaly_type: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    tick_data: dict[str, Any]


class HeartbeatReceived(DomainEvent):
    """Event raised when gateway heartbeat is received."""

    gateway_id: str
    session_id: UUID
    latency_ms: float | None = None


class DataQualityIssue(DomainEvent):
    """Event raised when data quality issue is detected."""

    symbol: Symbol
    issue_type: str  # MISSING_DATA, STALE_DATA, INVALID_PRICE, etc.
    description: str
    affected_ticks: int
