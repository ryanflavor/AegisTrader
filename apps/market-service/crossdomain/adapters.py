"""
Adapters for cross-domain communication.

These adapters facilitate communication between bounded contexts
while maintaining clean boundaries and preventing coupling.
"""

from typing import Any


class ContextAdapter:
    """Base adapter for context communication."""

    def __init__(self, context_name: str):
        """Initialize with context name."""
        self.context_name = context_name

    async def send(self, message: Any) -> None:
        """Send message to context."""
        pass

    async def receive(self) -> Any | None:
        """Receive message from context."""
        return None


class MarketDataAdapter(ContextAdapter):
    """Adapter for market data context."""

    def __init__(self):
        """Initialize market data adapter."""
        super().__init__("market_data")


class GatewayAdapter(ContextAdapter):
    """Adapter for gateway context."""

    def __init__(self):
        """Initialize gateway adapter."""
        super().__init__("gateway")


class SubscriptionAdapter(ContextAdapter):
    """Adapter for subscription context."""

    def __init__(self):
        """Initialize subscription adapter."""
        super().__init__("subscription")
