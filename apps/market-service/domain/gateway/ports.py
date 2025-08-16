"""
Gateway port interface
Following Hexagonal Architecture pattern
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from domain.gateway.value_objects import AuthenticationCredentials

if TYPE_CHECKING:
    from domain.gateway.models import Gateway
    from domain.shared.events import DomainEvent


class GatewayPort(ABC):
    """
    Port interface for Gateway adapters
    Defines the contract that infrastructure adapters must implement
    """

    @abstractmethod
    async def connect(self, credentials: AuthenticationCredentials | None = None) -> None:
        """
        Establish connection to the exchange gateway

        Args:
            credentials: Optional authentication credentials

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the exchange gateway
        """
        pass

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """
        Subscribe to market data for specified symbols

        Args:
            symbols: List of symbol codes to subscribe

        Raises:
            SubscriptionError: If subscription fails
        """
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from market data for specified symbols

        Args:
            symbols: List of symbol codes to unsubscribe
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if gateway is currently connected

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    async def send_heartbeat(self) -> None:
        """
        Send heartbeat to maintain connection

        Raises:
            ConnectionError: If heartbeat fails
        """
        pass

    @abstractmethod
    async def get_connection_status(self) -> dict:
        """
        Get detailed connection status information

        Returns:
            Dictionary containing connection status details
        """
        pass


class GatewayRepository(ABC):
    """
    Repository interface for Gateway aggregate persistence
    """

    @abstractmethod
    async def save(self, gateway: Gateway) -> None:
        """
        Save gateway state

        Args:
            gateway: Gateway aggregate to save
        """
        pass

    @abstractmethod
    async def get(self, gateway_id: str) -> Gateway | None:
        """
        Retrieve gateway by ID

        Args:
            gateway_id: Gateway identifier

        Returns:
            Gateway aggregate or None if not found
        """
        pass

    @abstractmethod
    async def list_active(self) -> list[Gateway]:
        """
        List all active gateways

        Returns:
            List of active Gateway aggregates
        """
        pass

    @abstractmethod
    async def update_heartbeat(self, gateway_id: str, timestamp: datetime) -> None:
        """
        Update gateway heartbeat timestamp

        Args:
            gateway_id: Gateway identifier
            timestamp: Heartbeat timestamp
        """
        pass


class EventPublisher(ABC):
    """
    Port interface for publishing domain events
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event

        Args:
            event: Domain event to publish
        """
        pass

    @abstractmethod
    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events

        Args:
            events: List of domain events to publish
        """
        pass
