"""
Aggregate Roots for Market Data bounded context.

Aggregates ensure consistency boundaries and protect business invariants.
They are the only entry points for modifying entities within the aggregate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from .entities import MarketDataSession, MarketDataSubscription
from .events import (
    DomainEvent,
    GatewayConnected,
    GatewayDisconnected,
    MarketSessionEnded,
    MarketSessionStarted,
    SubscriptionLimitReached,
)
from .value_objects import InstrumentType, Symbol, Tick


class MarketDataGateway(BaseModel):
    """
    Aggregate root for managing market data gateway connections.

    This aggregate ensures consistency for:
    - Gateway lifecycle management
    - Session management
    - Subscription limits
    - Connection health monitoring

    Business Invariants:
    - Only one active session per gateway at a time
    - Cannot exceed max subscriptions per gateway
    - Must maintain minimum heartbeat frequency
    - Cannot process ticks without active session
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # Identity
    id: UUID = Field(default_factory=uuid4)
    gateway_id: str
    gateway_type: str  # CTP, SOPT, etc.

    # Configuration
    max_subscriptions: Annotated[int, Field(gt=0)] = 100
    heartbeat_timeout_seconds: Annotated[int, Field(gt=0)] = 30

    # State
    is_connected: bool = False
    connected_at: datetime | None = None
    last_heartbeat_at: datetime | None = None

    # Session management
    current_session: MarketDataSession | None = None
    session_history: list[UUID] = Field(default_factory=list)

    # Statistics
    total_sessions: Annotated[int, Field(ge=0)] = 0
    total_ticks_processed: Annotated[int, Field(ge=0)] = 0
    total_errors: Annotated[int, Field(ge=0)] = 0

    # Use PrivateAttr for private fields in Pydantic v2
    _events: list[DomainEvent] = PrivateAttr(default_factory=list)

    @field_validator("gateway_id")
    @classmethod
    def validate_gateway_id(cls, v: str) -> str:
        """Ensure gateway_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Gateway ID cannot be empty")
        return v.strip()

    def connect(self, connection_params: dict[str, str] | None = None) -> None:
        """
        Connect the gateway and start a new session.

        Business Rules:
        - Cannot connect if already connected
        - Creates new session on connection
        - Raises GatewayConnected event
        """
        if self.is_connected:
            raise ValueError(f"Gateway {self.gateway_id} is already connected")

        # Create new session
        new_session = MarketDataSession(
            gateway_id=self.gateway_id,
            is_connected=False,
        )
        new_session.connect(connection_params)

        # Update gateway state
        self.is_connected = True
        self.connected_at = datetime.now(UTC)
        self.last_heartbeat_at = datetime.now(UTC)
        self.current_session = new_session
        self.session_history.append(new_session.id)
        self.total_sessions += 1

        # Raise events
        self._events.append(
            GatewayConnected(
                aggregate_id=str(self.id),
                gateway_id=self.gateway_id,
                gateway_type=self.gateway_type,
                connection_time=self.connected_at,
            )
        )

        self._events.append(
            MarketSessionStarted(
                aggregate_id=str(self.id),
                gateway_id=self.gateway_id,
                session_id=new_session.id,
                connection_params=connection_params or {},
            )
        )

    def disconnect(self, reason: str = "Manual disconnect") -> None:
        """
        Disconnect the gateway and end current session.

        Business Rules:
        - Cannot disconnect if not connected
        - Ends current session
        - Raises GatewayDisconnected and MarketSessionEnded events
        """
        if not self.is_connected:
            raise ValueError(f"Gateway {self.gateway_id} is not connected")

        if not self.current_session:
            raise ValueError(f"Gateway {self.gateway_id} has no active session")

        # End current session
        session = self.current_session
        session.disconnect()

        # Calculate session statistics
        session_duration = session.session_duration or 0

        # Update gateway state
        self.is_connected = False
        self.current_session = None

        # Raise events
        self._events.append(
            MarketSessionEnded(
                aggregate_id=str(self.id),
                gateway_id=self.gateway_id,
                session_id=session.id,
                total_ticks=session.total_ticks_received,
                total_errors=session.total_errors,
                duration_seconds=session_duration,
            )
        )

        self._events.append(
            GatewayDisconnected(
                aggregate_id=str(self.id),
                gateway_id=self.gateway_id,
                reason=reason,
                disconnection_time=datetime.now(UTC),
            )
        )

    def subscribe(
        self,
        symbol: Symbol,
        subscriber_id: str,
        instrument_type: InstrumentType,
    ) -> MarketDataSubscription:
        """
        Create a new market data subscription.

        Business Rules:
        - Gateway must be connected
        - Cannot exceed max subscriptions
        - Cannot duplicate symbol subscription in same session
        - Returns created subscription
        """
        if not self.is_connected:
            raise ValueError(f"Cannot subscribe: Gateway {self.gateway_id} is not connected")

        if not self.current_session:
            raise ValueError(f"Gateway {self.gateway_id} has no active session")

        # Check subscription limit
        if self.current_session.active_subscription_count >= self.max_subscriptions:
            self._events.append(
                SubscriptionLimitReached(
                    aggregate_id=str(self.id),
                    gateway_id=self.gateway_id,
                    current_count=self.current_session.active_subscription_count,
                    max_allowed=self.max_subscriptions,
                    requested_symbol=symbol,
                )
            )
            raise ValueError(
                f"Subscription limit reached: {self.max_subscriptions} "
                f"for gateway {self.gateway_id}"
            )

        # Create subscription (starts inactive)
        subscription = MarketDataSubscription(
            symbol=symbol,
            subscriber_id=subscriber_id,
            instrument_type=instrument_type,
            is_active=False,  # Start inactive so subscribe() can be called
        )

        # Activate subscription (will raise event)
        subscription.subscribe()

        # Add to session (will validate no duplicates)
        self.current_session.add_subscription(subscription)

        # Collect events from subscription
        for event in subscription.collect_events():
            self._events.append(event)

        return subscription

    def unsubscribe(self, symbol: Symbol) -> bool:
        """
        Cancel a market data subscription.

        Business Rules:
        - Gateway must be connected
        - Returns True if unsubscribed, False if not found
        """
        if not self.is_connected:
            raise ValueError(f"Cannot unsubscribe: Gateway {self.gateway_id} is not connected")

        if not self.current_session:
            raise ValueError(f"Gateway {self.gateway_id} has no active session")

        subscription = self.current_session.remove_subscription(symbol)

        if subscription:
            # Collect events from subscription
            for event in subscription.collect_events():
                self._events.append(event)
            return True

        return False

    def process_tick(self, tick: Tick) -> None:
        """
        Process incoming market tick.

        Business Rules:
        - Gateway must be connected
        - Session must have active subscription for symbol
        - Updates statistics
        - Propagates tick to subscription
        """
        if not self.is_connected:
            raise ValueError(f"Cannot process tick: Gateway {self.gateway_id} is not connected")

        if not self.current_session:
            raise ValueError(f"Gateway {self.gateway_id} has no active session")

        try:
            self.current_session.process_tick(tick)
            self.total_ticks_processed += 1

            # Collect events from subscriptions
            symbol_key = str(tick.symbol)
            subscription = self.current_session.subscriptions.get(symbol_key)
            if subscription:
                for event in subscription.collect_events():
                    self._events.append(event)

        except Exception as e:
            self.total_errors += 1
            raise e

    def update_heartbeat(self) -> None:
        """
        Update gateway heartbeat timestamp.

        Business Rules:
        - Gateway must be connected
        - Updates session heartbeat
        """
        if not self.is_connected:
            raise ValueError(f"Cannot update heartbeat: Gateway {self.gateway_id} is not connected")

        if not self.current_session:
            raise ValueError(f"Gateway {self.gateway_id} has no active session")

        self.last_heartbeat_at = datetime.now(UTC)
        self.current_session.update_heartbeat()

    def is_healthy(self) -> bool:
        """
        Check if gateway connection is healthy.

        Health criteria:
        - Must be connected
        - Session must be healthy
        - Heartbeat within timeout period
        """
        if not self.is_connected or not self.current_session:
            return False

        if not self.last_heartbeat_at:
            return False

        time_since_heartbeat = (datetime.now(UTC) - self.last_heartbeat_at).total_seconds()
        if time_since_heartbeat > self.heartbeat_timeout_seconds:
            return False

        return self.current_session.is_healthy

    def collect_events(self) -> list[DomainEvent]:
        """Collect and clear all domain events."""
        events = self._events.copy()
        self._events.clear()

        # Also collect events from current session if exists
        if self.current_session:
            for subscription in self.current_session.subscriptions.values():
                events.extend(subscription.collect_events())

        return events

    @property
    def active_subscription_count(self) -> int:
        """Get count of active subscriptions."""
        if not self.current_session:
            return 0
        return self.current_session.active_subscription_count

    @property
    def subscription_symbols(self) -> list[str]:
        """Get list of subscribed symbols."""
        if not self.current_session:
            return []
        return [
            str(sub.symbol) for sub in self.current_session.subscriptions.values() if sub.is_active
        ]
