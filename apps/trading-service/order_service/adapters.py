"""Adapters for external service integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared_contracts import ServiceNames

if TYPE_CHECKING:
    from aegis_sdk.application import Service
    from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort


class RemotePricingServiceAdapter:
    """Adapter to integrate with remote pricing service via RPC."""

    def __init__(self, service: Service, discovery: ServiceDiscoveryPort | None = None) -> None:
        """Initialize the adapter."""
        self._service = service
        self._discovery = discovery or service._discovery

    async def get_price(self, symbol: str) -> float:
        """Get current price for a symbol via RPC."""
        if not self._discovery:
            raise RuntimeError("Service discovery not available")

        try:
            result = await self._service.call_rpc(
                ServiceNames.PRICING_SERVICE, "get_price", {"symbol": symbol}
            )
            return float(result.get("price", 100.0))
        except Exception:
            # Return default price on failure
            return 100.0
