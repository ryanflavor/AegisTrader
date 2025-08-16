"""
Anti-corruption layer for market-service.

Protects the domain from external systems and data sources.
"""

from typing import Any, Protocol


class ExternalService(Protocol):
    """External service interface."""

    async def fetch_data(self, id: str) -> dict:
        """Fetch data from external service."""
        ...


class AntiCorruptionLayer:
    """Protects domain from external systems."""

    def __init__(self, translator, external_service: ExternalService | None = None):
        """Initialize with translator and optional external service."""
        self._translator = translator
        self._external_service = external_service

    async def fetch_and_translate(self, external_id: str) -> Any | None:
        """Fetch from external system and translate to domain model."""
        if not self._external_service:
            # Mock data for demonstration
            raw_data = {
                "external_id": external_id,
                "symbol": "AAPL",
                "exchange": "NASDAQ",
                "last_price": 150.25,
                "volume": 1000000,
            }
        else:
            raw_data = await self._external_service.fetch_data(external_id)

        # Translate to domain model
        return self._translator.translate(raw_data)

    async def save_to_external(self, domain_model: Any) -> bool:
        """Save domain model to external system."""
        # Translate to external format
        _ = self._translator.reverse_translate(domain_model)

        # Send to external system (placeholder)
        if self._external_service:
            # await self._external_service.save(external_data)
            pass

        return True


class BoundedContextAdapter:
    """Adapter for communication between bounded contexts."""

    def __init__(self, context_name: str):
        """Initialize with context name."""
        self._context_name = context_name

    async def send_to_context(self, message: Any) -> None:
        """Send message to another bounded context."""
        # Transform message for target context
        # Send via appropriate channel
        pass

    async def receive_from_context(self) -> Any | None:
        """Receive message from another bounded context."""
        # Receive and transform message
        return None
