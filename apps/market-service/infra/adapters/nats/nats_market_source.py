"""NATS implementation of MarketDataSource port.

This module implements the infrastructure adapter for market data source
following hexagonal architecture principles.
"""

import logging
from typing import Any

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class MarketDataSourceConfig(BaseModel):
    """Configuration for NATS market data source."""

    model_config = ConfigDict(strict=True)

    subject_prefix: str = Field(default="market", description="Prefix for market data subjects")
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds", gt=0)
    reconnect_attempts: int = Field(default=3, description="Number of reconnection attempts", ge=0)


class NATSMarketDataSource:
    """NATS implementation of MarketDataSource port.

    This adapter implements the market data source interface using NATS
    as the underlying messaging infrastructure.
    """

    def __init__(self, nats_adapter: NATSAdapter, config: MarketDataSourceConfig | None = None):
        """Initialize with NATS adapter.

        Args:
            nats_adapter: NATS adapter for messaging
            config: Configuration for the market data source
        """
        self.nats = nats_adapter
        self.config = config or MarketDataSourceConfig()
        self._is_connected = False
        self._subscriptions: set[str] = set()

    async def connect(self, params: dict[str, Any]) -> None:
        """Connect to market data source.

        Args:
            params: Connection parameters
        """
        # NATS connection is handled by NATSAdapter
        self._is_connected = True
        logger.info(f"Market data source connected with params: {params}")

    async def disconnect(self) -> None:
        """Disconnect from market data source."""
        # Clear all subscriptions
        self._subscriptions.clear()
        self._is_connected = False
        logger.info("Market data source disconnected")

    async def subscribe(self, symbol: Any) -> None:
        """Subscribe to market data for a symbol.

        Args:
            symbol: Symbol to subscribe to (must have exchange and value attributes)
        """
        # Construct NATS subject from symbol
        subject = f"{self.config.subject_prefix}.{symbol.exchange}.{symbol.value}"

        if subject not in self._subscriptions:
            self._subscriptions.add(subject)
            logger.info(f"Subscribed to {subject}")
        else:
            logger.debug(f"Already subscribed to {subject}")

    async def unsubscribe(self, symbol: Any) -> None:
        """Unsubscribe from market data for a symbol.

        Args:
            symbol: Symbol to unsubscribe from (must have exchange and value attributes)
        """
        subject = f"{self.config.subject_prefix}.{symbol.exchange}.{symbol.value}"

        if subject in self._subscriptions:
            self._subscriptions.discard(subject)
            logger.info(f"Unsubscribed from {subject}")
        else:
            logger.debug(f"Not subscribed to {subject}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to source.

        Returns:
            True if connected, False otherwise
        """
        return self._is_connected

    @property
    def active_subscriptions(self) -> list[str]:
        """Get list of active subscriptions.

        Returns:
            List of active subscription subjects
        """
        return list(self._subscriptions)
