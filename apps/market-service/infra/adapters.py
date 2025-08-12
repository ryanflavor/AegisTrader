"""External service adapters - Educational Template.

⚠️ IMPORTANT: Most infrastructure adapters are NOT needed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The AegisSDK already provides these components:
✅ aegis_sdk.infrastructure.nats_adapter.NATSAdapter - Message bus
✅ aegis_sdk.infrastructure.simple_logger.SimpleLogger - Logging
✅ aegis_sdk.infrastructure.kv_service_registry.KVServiceRegistry - Service registry
✅ aegis_sdk.application.service.Service - Complete service infrastructure

You should ONLY create adapters for:
1. External APIs specific to your business (e.g., payment gateways)
2. Custom databases not covered by SDK
3. Third-party services unique to your domain

❌ DON'T create adapters for:
- Logging (use SimpleLogger)
- NATS messaging (use NATSAdapter directly)
- Service registry (use KVServiceRegistry)
- Configuration (use environment variables)

Example of a VALID adapter (business-specific):
"""

from typing import Any

import httpx


class PaymentGatewayAdapter:
    """Adapter for external payment service - this is business-specific."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    async def process_payment(self, amount: float, currency: str) -> dict[str, Any]:
        """Process payment through external gateway."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/payments",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"amount": amount, "currency": currency},
            )
            return response.json()


# TODO: Add your business-specific adapters here
# Remember: Don't wrap SDK components - use them directly!
