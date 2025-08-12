"""Command and query handlers with RPC integration examples.

This is the RIGHT place for RPC calls to other services!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT: The SDK handles ALL serialization automatically!
- RPC uses msgpack by default (NOT JSON)
- You work with Python dicts/objects directly
- Never manually serialize/deserialize
- The SDK handles datetime, complex types, etc.

Application layer coordinates business logic and external services.
"""

from typing import Any

from aegis_sdk.application.use_cases import RPCCallUseCase
from aegis_sdk.domain.models import RPCRequest
from aegis_sdk.domain.services import MessageRoutingService, MetricsNamingService
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


class CommandHandler:
    """Handles commands - coordinates domain logic and external services.

    This is where you make RPC calls to other services when needed!
    The SDK handles all serialization/deserialization automatically.
    """

    def __init__(self, repository, event_bus, nats_adapter: NATSAdapter = None):
        self._repository = repository
        self._event_bus = event_bus
        self._nats = nats_adapter  # For RPC calls to other services

        # Optional: Setup RPC use case for production-ready calls
        if self._nats:
            self._rpc_use_case = RPCCallUseCase(
                message_bus=self._nats,
                metrics=InMemoryMetrics(),
                routing_service=MessageRoutingService(),
                naming_service=MetricsNamingService(),
            )

    async def handle_create_order(self, command) -> str:
        """Example: Create order with external service calls.

        This shows the PROPER way to call other services via RPC.
        """
        # Step 1: Check inventory via RPC (external service)
        if self._nats:
            inventory_request = RPCRequest(
                method="check_availability",
                params={"product_id": command.product_id, "quantity": command.quantity},
                target="inventory-service",  # Target service name
            )

            # SDK handles all serialization automatically!
            inventory_response = await self._nats.call_rpc(inventory_request)

            if not inventory_response.success:
                raise Exception(f"Inventory check failed: {inventory_response.error}")

            if not inventory_response.result.get("available"):
                raise Exception("Product not available")

        # Step 2: Create order in domain
        # ... your domain logic here ...

        # Step 3: Process payment via RPC (external service)
        if self._nats:
            payment_request = RPCRequest(
                method="process_payment",
                params={
                    "amount": command.amount,
                    "currency": command.currency,
                    "customer_id": command.customer_id,
                },
                target="payment-service",
            )

            payment_response = await self._nats.call_rpc(payment_request)

            if not payment_response.success:
                # Compensate: cancel order, restore inventory
                raise Exception(f"Payment failed: {payment_response.error}")

        # Step 4: Save and publish event
        # ... save to repository and publish domain event ...

        return "order_id"

    async def handle_update_status(self, command) -> None:
        """Handle update status command."""
        # Load entity
        # Update status
        # Save changes
        # Publish event
        pass

    async def handle_cancel_order(self, command) -> None:
        """Handle cancel order - may need to call external services."""
        # Coordinate cancellation across services
        pass


class QueryHandler:
    """Handles queries - may aggregate data from multiple services.

    Queries can also make RPC calls to gather data from other services!
    """

    def __init__(self, read_model, nats_adapter: NATSAdapter = None):
        self._read_model = read_model
        self._nats = nats_adapter  # For cross-service queries

    async def handle_get_order_details(self, query) -> dict[str, Any] | None:
        """Get order with enriched data from other services."""
        # Get local order data
        order = await self._read_model.get_order(query.order_id)

        if order and self._nats:
            # Enrich with customer data via RPC
            customer_request = RPCRequest(
                method="get_customer",
                params={"customer_id": order["customer_id"]},
                target="customer-service",
            )

            customer_response = await self._nats.call_rpc(customer_request)
            if customer_response.success:
                order["customer"] = customer_response.result

        return order

    async def handle_search_orders(self, query) -> list[dict[str, Any]]:
        """Search orders across the system."""
        # Search local read model
        # Optionally aggregate with data from other services
        return []


# Production tip: Use dependency injection for the NATS adapter
# so handlers can be tested without real NATS connection
