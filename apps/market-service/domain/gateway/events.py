"""
Gateway domain events
Following DDD patterns with Event Sourcing support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.shared.events import DomainEvent


@dataclass(frozen=True)
class GatewayEvent(DomainEvent):
    """Base class for gateway domain events"""

    gateway_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class GatewayConnected(GatewayEvent):
    """Event raised when gateway successfully connects"""

    gateway_type: str = ""
    connection_details: dict | None = None


@dataclass(frozen=True)
class GatewayDisconnected(GatewayEvent):
    """Event raised when gateway disconnects"""

    gateway_type: str = ""
    reason: str = ""
    error_code: int | None = None


@dataclass(frozen=True)
class ConnectionAttempted(GatewayEvent):
    """Event raised when connection attempt is made"""

    attempt_number: int = 0
    gateway_type: str = ""


@dataclass(frozen=True)
class ReconnectionScheduled(GatewayEvent):
    """Event raised when reconnection is scheduled"""

    next_attempt_in: int = 0  # seconds
    attempt_number: int = 0


@dataclass(frozen=True)
class HeartbeatReceived(GatewayEvent):
    """Event raised when heartbeat is received"""

    latency_ms: int | None = None
    sequence_number: int | None = None


@dataclass(frozen=True)
class HeartbeatTimeout(GatewayEvent):
    """Event raised when heartbeat times out"""

    last_heartbeat: datetime | None = None
    timeout_seconds: int = 0


@dataclass(frozen=True)
class LeadershipAcquired(GatewayEvent):
    """Event raised when gateway instance acquires leadership"""

    instance_id: str | None = None
    previous_leader: str | None = None


@dataclass(frozen=True)
class LeadershipLost(GatewayEvent):
    """Event raised when gateway instance loses leadership"""

    instance_id: str | None = None
    new_leader: str | None = None
    voluntary: bool = True  # Whether leadership was voluntarily released


@dataclass(frozen=True)
class AuthenticationSucceeded(GatewayEvent):
    """Event raised when authentication succeeds"""

    gateway_type: str = ""
    user_id: str = ""
    broker_id: str | None = None


@dataclass(frozen=True)
class AuthenticationFailed(GatewayEvent):
    """Event raised when authentication fails"""

    gateway_type: str = ""
    error_message: str = ""
    error_code: int | None = None
    retry_allowed: bool = True


@dataclass(frozen=True)
class MarketDataSubscribed(GatewayEvent):
    """Event raised when market data subscription succeeds"""

    symbols: list[str] = field(default_factory=list)
    subscription_type: str = "realtime"  # realtime, snapshot, etc.


@dataclass(frozen=True)
class MarketDataUnsubscribed(GatewayEvent):
    """Event raised when market data is unsubscribed"""

    symbols: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True)
class GatewayError(GatewayEvent):
    """Event raised when gateway encounters an error"""

    error_type: str = ""
    error_message: str = ""
    error_code: int | None = None
    recoverable: bool = True
    stack_trace: str | None = None


@dataclass(frozen=True)
class ConnectionStateChanged(GatewayEvent):
    """Event raised when connection state changes"""

    previous_state: str = ""
    new_state: str = ""
    trigger: str = ""  # What triggered the state change
