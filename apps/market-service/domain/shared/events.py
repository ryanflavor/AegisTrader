"""
Domain event base classes.

Domain events represent facts that have occurred within the domain.
They are immutable and carry information about state changes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: str = ""
    event_type: str = ""

    def __post_init__(self):
        """Set event type if not provided."""
        if not self.event_type:
            object.__setattr__(self, "event_type", self.__class__.__name__)


@dataclass(frozen=True)
class GatewayConnectedEvent(DomainEvent):
    """Event raised when a gateway connects."""

    gateway_id: str = ""
    gateway_type: str = ""
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class GatewayDisconnectedEvent(DomainEvent):
    """Event raised when a gateway disconnects."""

    gateway_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class MarketDataReceivedEvent(DomainEvent):
    """Event raised when market data is received."""

    symbol: str = ""
    exchange: str = ""
    price: float = 0.0
    volume: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class SubscriptionCreatedEvent(DomainEvent):
    """Event raised when a new subscription is created."""

    subscription_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    exchange: str = ""
    subscriber_id: str = ""
