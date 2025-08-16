"""
Gateway domain model - Aggregate Root
Following DDD patterns with Pydantic v2
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from domain.gateway.events import (
    GatewayConnected,
    GatewayDisconnected,
    HeartbeatReceived,
    LeadershipAcquired,
    LeadershipLost,
)
from domain.gateway.value_objects import (
    ConnectionState,
    GatewayConfig,
    GatewayId,
    GatewayType,
)
from domain.shared.events import DomainEvent


class Gateway(BaseModel):
    """
    Gateway Aggregate Root
    Manages connection lifecycle and state for exchange gateways
    """

    gateway_id: GatewayId
    gateway_type: GatewayType
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    config: GatewayConfig
    last_heartbeat: datetime | None = None
    is_leader: bool = False
    connection_attempts: int = 0
    last_connection_attempt: datetime | None = None
    events: list[DomainEvent] = Field(default_factory=list, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def connect(self) -> list[DomainEvent]:
        """
        Initiate connection to the exchange
        Returns domain events generated
        """
        if self.connection_state == ConnectionState.CONNECTED:
            return []

        if self.connection_state == ConnectionState.CONNECTING:
            return []  # Already connecting

        # Update state
        self.connection_state = ConnectionState.CONNECTING
        self.connection_attempts += 1
        self.last_connection_attempt = datetime.now()

        # Generate event
        event = GatewayConnected(
            gateway_id=str(self.gateway_id),
            gateway_type=(
                self.gateway_type.value
                if isinstance(self.gateway_type, GatewayType)
                else str(self.gateway_type)
            ),
        )
        self.events.append(event)

        return [event]

    def disconnect(self) -> list[DomainEvent]:
        """
        Gracefully disconnect from the exchange
        Returns domain events generated
        """
        if self.connection_state == ConnectionState.DISCONNECTED:
            return []

        # Update state
        _ = self.connection_state  # Store for potential future use
        self.connection_state = ConnectionState.DISCONNECTED
        self.last_heartbeat = None

        # Generate event
        event = GatewayDisconnected(
            gateway_id=str(self.gateway_id),
            gateway_type=(
                self.gateway_type.value
                if isinstance(self.gateway_type, GatewayType)
                else str(self.gateway_type)
            ),
            reason="Graceful disconnection",
        )
        self.events.append(event)

        return [event]

    def handle_heartbeat(self) -> list[DomainEvent]:
        """
        Update heartbeat timestamp
        Returns domain events generated
        """
        if self.connection_state != ConnectionState.CONNECTED:
            return []  # Ignore heartbeat if not connected

        # Update state
        self.last_heartbeat = datetime.now()

        # Generate event
        event = HeartbeatReceived(
            gateway_id=str(self.gateway_id),
        )
        self.events.append(event)

        return [event]

    def acquire_leadership(self) -> list[DomainEvent]:
        """
        Acquire leadership for this gateway instance
        Returns domain events generated
        """
        if self.is_leader:
            return []  # Already leader

        # Update state
        self.is_leader = True

        # Generate event
        event = LeadershipAcquired(
            gateway_id=str(self.gateway_id),
        )
        self.events.append(event)

        return [event]

    def lose_leadership(self) -> list[DomainEvent]:
        """
        Lose leadership for this gateway instance
        Returns domain events generated
        """
        if not self.is_leader:
            return []  # Not leader

        # Update state
        self.is_leader = False

        # Generate event
        event = LeadershipLost(
            gateway_id=str(self.gateway_id),
        )
        self.events.append(event)

        # If connected, should disconnect
        if self.connection_state == ConnectionState.CONNECTED:
            disconnect_events = self.disconnect()
            return [event] + disconnect_events

        return [event]

    def mark_connected(self) -> None:
        """Mark gateway as successfully connected"""
        self.connection_state = ConnectionState.CONNECTED

    def mark_reconnecting(self) -> None:
        """Mark gateway as attempting to reconnect"""
        self.connection_state = ConnectionState.RECONNECTING

    def is_connected(self) -> bool:
        """Check if gateway is connected"""
        return self.connection_state == ConnectionState.CONNECTED

    def is_healthy(self) -> bool:
        """
        Check if gateway is healthy
        Considers connection state and heartbeat freshness
        """
        if not self.is_connected():
            return False

        if self.last_heartbeat is None:
            return False

        # Check heartbeat freshness (default 60 seconds)
        heartbeat_timeout = (
            self.config.heartbeat_config.timeout if hasattr(self.config, "heartbeat_config") else 60
        )
        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()

        return time_since_heartbeat < heartbeat_timeout

    def get_events(self) -> list[DomainEvent]:
        """Get and clear pending domain events"""
        events = self.events.copy()
        self.events.clear()
        return events
