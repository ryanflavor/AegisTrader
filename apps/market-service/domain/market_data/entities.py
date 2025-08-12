"""
Domain Entities for Market Data bounded context.

These entities have identity and mutable state, representing
core business concepts with behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from .events import MarketDataSubscribed, MarketDataUnsubscribed, TickProcessed
from .value_objects import InstrumentType, Symbol, Tick


class MarketDataSubscription(BaseModel):
    """
    Entity representing a subscription to market data.

    This entity manages the lifecycle of market data subscriptions,
    tracking what symbols are being monitored and their status.
    """

    model_config = ConfigDict(strict=True)

    id: UUID = Field(default_factory=uuid4)
    symbol: Symbol
    subscriber_id: str
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_tick_at: datetime | None = None
    tick_count: Annotated[int, Field(ge=0)] = 0
    is_active: bool = True
    instrument_type: InstrumentType

    # Domain events raised by this entity (use PrivateAttr in Pydantic v2)
    _events: list[MarketDataSubscribed | MarketDataUnsubscribed | TickProcessed] = PrivateAttr(
        default_factory=list
    )

    def subscribe(self) -> None:
        """
        Activate subscription and raise domain event.

        Business rule: Cannot subscribe if already active.
        """
        if self.is_active:
            raise ValueError(f"Subscription {self.id} is already active")

        self.is_active = True
        self.subscribed_at = datetime.now(UTC)
        self.tick_count = 0
        self.last_tick_at = None

        # Raise domain event
        self._events.append(
            MarketDataSubscribed(
                aggregate_id=str(self.id),
                symbol=self.symbol,
                subscriber_id=self.subscriber_id,
                instrument_type=self.instrument_type,
            )
        )

    def unsubscribe(self) -> None:
        """
        Deactivate subscription and raise domain event.

        Business rule: Cannot unsubscribe if already inactive.
        """
        if not self.is_active:
            raise ValueError(f"Subscription {self.id} is already inactive")

        self.is_active = False

        # Raise domain event
        self._events.append(
            MarketDataUnsubscribed(
                aggregate_id=str(self.id),
                symbol=self.symbol,
                subscriber_id=self.subscriber_id,
                total_ticks=self.tick_count,
            )
        )

    def process_tick(self, tick: Tick) -> None:
        """
        Process incoming tick for this subscription.

        Business rules:
        - Must be active to process ticks
        - Tick symbol must match subscription symbol
        - Updates statistics
        """
        if not self.is_active:
            raise ValueError(f"Cannot process tick for inactive subscription {self.id}")

        if tick.symbol != self.symbol:
            raise ValueError(
                f"Tick symbol {tick.symbol} does not match subscription symbol {self.symbol}"
            )

        self.tick_count += 1
        self.last_tick_at = tick.timestamp

        # Raise domain event
        self._events.append(
            TickProcessed(
                aggregate_id=str(self.id),
                symbol=self.symbol,
                tick=tick,
                subscriber_id=self.subscriber_id,
            )
        )

    def collect_events(self) -> list[MarketDataSubscribed | MarketDataUnsubscribed | TickProcessed]:
        """Collect and clear domain events."""
        events = self._events.copy()
        self._events.clear()
        return events

    @property
    def duration(self) -> float | None:
        """Calculate subscription duration in seconds."""
        if not self.last_tick_at:
            return None
        return (self.last_tick_at - self.subscribed_at).total_seconds()


class MarketDataSession(BaseModel):
    """
    Entity representing a market data session.

    Manages the lifecycle of a market data connection session,
    including multiple subscriptions and session statistics.
    """

    model_config = ConfigDict(strict=True)

    id: UUID = Field(default_factory=uuid4)
    gateway_id: str
    session_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_ended_at: datetime | None = None
    is_connected: bool = False
    total_ticks_received: Annotated[int, Field(ge=0)] = 0
    total_errors: Annotated[int, Field(ge=0)] = 0
    subscriptions: dict[str, MarketDataSubscription] = Field(default_factory=dict)

    # Connection metadata
    connection_params: dict[str, str] = Field(default_factory=dict)
    last_heartbeat_at: datetime | None = None

    def connect(self, params: dict[str, str] | None = None) -> None:
        """
        Establish market data session connection.

        Business rule: Cannot connect if already connected.
        """
        if self.is_connected:
            raise ValueError(f"Session {self.id} is already connected")

        self.is_connected = True
        self.session_started_at = datetime.now(UTC)
        self.last_heartbeat_at = datetime.now(UTC)

        if params:
            self.connection_params = params

    def disconnect(self) -> None:
        """
        Disconnect market data session.

        Business rules:
        - Cannot disconnect if not connected
        - All subscriptions are deactivated
        """
        if not self.is_connected:
            raise ValueError(f"Session {self.id} is not connected")

        # Deactivate all subscriptions
        for subscription in self.subscriptions.values():
            if subscription.is_active:
                subscription.unsubscribe()

        self.is_connected = False
        self.session_ended_at = datetime.now(UTC)

    def add_subscription(self, subscription: MarketDataSubscription) -> None:
        """
        Add a subscription to this session.

        Business rules:
        - Session must be connected
        - Cannot add duplicate symbols
        """
        if not self.is_connected:
            raise ValueError(f"Cannot add subscription to disconnected session {self.id}")

        symbol_key = str(subscription.symbol)
        if symbol_key in self.subscriptions:
            raise ValueError(f"Symbol {symbol_key} already subscribed in session {self.id}")

        self.subscriptions[symbol_key] = subscription

    def remove_subscription(self, symbol: Symbol) -> MarketDataSubscription | None:
        """
        Remove a subscription from this session.

        Returns the removed subscription or None if not found.
        """
        symbol_key = str(symbol)
        subscription = self.subscriptions.get(symbol_key)

        if subscription and subscription.is_active:
            subscription.unsubscribe()

        return self.subscriptions.pop(symbol_key, None)

    def process_tick(self, tick: Tick) -> None:
        """
        Process incoming tick through appropriate subscription.

        Business rules:
        - Session must be connected
        - Symbol must have active subscription
        - Updates session statistics
        """
        if not self.is_connected:
            raise ValueError(f"Cannot process tick in disconnected session {self.id}")

        symbol_key = str(tick.symbol)
        subscription = self.subscriptions.get(symbol_key)

        if not subscription:
            raise ValueError(f"No subscription found for symbol {symbol_key}")

        if not subscription.is_active:
            raise ValueError(f"Subscription for symbol {symbol_key} is not active")

        try:
            subscription.process_tick(tick)
            self.total_ticks_received += 1
        except Exception as e:
            self.total_errors += 1
            raise e

    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        if not self.is_connected:
            raise ValueError(f"Cannot update heartbeat for disconnected session {self.id}")

        self.last_heartbeat_at = datetime.now(UTC)

    @property
    def session_duration(self) -> float | None:
        """Calculate session duration in seconds."""
        if not self.session_ended_at:
            if self.is_connected:
                return (datetime.now(UTC) - self.session_started_at).total_seconds()
            return None
        return (self.session_ended_at - self.session_started_at).total_seconds()

    @property
    def active_subscription_count(self) -> int:
        """Count active subscriptions."""
        return sum(1 for sub in self.subscriptions.values() if sub.is_active)

    @property
    def is_healthy(self) -> bool:
        """
        Check if session is healthy based on heartbeat.

        Considers unhealthy if no heartbeat in last 30 seconds.
        """
        if not self.is_connected or not self.last_heartbeat_at:
            return False

        time_since_heartbeat = (datetime.now(UTC) - self.last_heartbeat_at).total_seconds()
        return time_since_heartbeat < 30
