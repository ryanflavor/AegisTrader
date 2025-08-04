"""Repository implementations for Order Service."""

from __future__ import annotations

from .domain_models import Order
from .ports import OrderRepositoryPort


class InMemoryOrderRepository(OrderRepositoryPort):
    """In-memory implementation of order repository for demo purposes."""

    def __init__(self) -> None:
        """Initialize the repository."""
        self._orders: dict[str, Order] = {}
        self._order_counter = 0

    async def save(self, order: Order) -> None:
        """Save or update an order."""
        self._orders[order.order_id] = order

    async def get(self, order_id: str) -> Order | None:
        """Get an order by ID."""
        return self._orders.get(order_id)

    async def list(self, limit: int = 100) -> list[Order]:
        """List orders with optional limit."""
        orders = list(self._orders.values())
        return orders[:limit]

    async def count(self) -> int:
        """Count total orders."""
        return len(self._orders)

    async def get_next_order_id(self) -> str:
        """Generate the next order ID."""
        self._order_counter += 1
        return f"ORD-{self._order_counter:06d}"
