"""Unit tests for Order repository implementations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from order_service.domain_models import Order, OrderSide, OrderStatus
from order_service.repositories import InMemoryOrderRepository


@pytest.mark.asyncio
class TestInMemoryOrderRepository:
    """Test InMemoryOrderRepository implementation."""

    async def test_save_and_get_order(self):
        """Test saving and retrieving an order."""
        repo = InMemoryOrderRepository()

        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="test-instance",
        )

        # Save order
        await repo.save(order)

        # Retrieve order
        retrieved = await repo.get("ORD-000001")

        assert retrieved is not None
        assert retrieved.order_id == "ORD-000001"
        assert retrieved.symbol == "AAPL"
        assert retrieved.quantity == 100.0

    async def test_get_nonexistent_order(self):
        """Test retrieving a non-existent order returns None."""
        repo = InMemoryOrderRepository()

        result = await repo.get("ORD-999999")

        assert result is None

    async def test_update_existing_order(self):
        """Test updating an existing order."""
        repo = InMemoryOrderRepository()

        # Create and save initial order
        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="test-instance",
        )
        await repo.save(order)

        # Update order status
        order.status = OrderStatus.APPROVED
        await repo.save(order)

        # Retrieve and verify
        retrieved = await repo.get("ORD-000001")
        assert retrieved is not None
        assert retrieved.status == OrderStatus.APPROVED

    async def test_list_orders(self):
        """Test listing orders with limit."""
        repo = InMemoryOrderRepository()

        # Save multiple orders
        for i in range(5):
            order = Order(
                order_id=f"ORD-{i:06d}",
                symbol="AAPL",
                quantity=100.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="test-instance",
            )
            await repo.save(order)

        # List all orders
        all_orders = await repo.list()
        assert len(all_orders) == 5

        # List with limit
        limited = await repo.list(limit=3)
        assert len(limited) == 3

    async def test_count_orders(self):
        """Test counting orders."""
        repo = InMemoryOrderRepository()

        # Initially empty
        assert await repo.count() == 0

        # Add orders
        for i in range(3):
            order = Order(
                order_id=f"ORD-{i:06d}",
                symbol="AAPL",
                quantity=100.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="test-instance",
            )
            await repo.save(order)

        assert await repo.count() == 3

    async def test_get_next_order_id(self):
        """Test order ID generation."""
        repo = InMemoryOrderRepository()

        # Get sequential IDs
        id1 = await repo.get_next_order_id()
        id2 = await repo.get_next_order_id()
        id3 = await repo.get_next_order_id()

        assert id1 == "ORD-000001"
        assert id2 == "ORD-000002"
        assert id3 == "ORD-000003"

    async def test_concurrent_order_id_generation(self):
        """Test that order ID generation is safe for concurrent use."""
        repo = InMemoryOrderRepository()

        # Simulate concurrent ID generation
        import asyncio

        ids = await asyncio.gather(
            repo.get_next_order_id(),
            repo.get_next_order_id(),
            repo.get_next_order_id(),
            repo.get_next_order_id(),
            repo.get_next_order_id(),
        )

        # All IDs should be unique
        assert len(set(ids)) == 5

        # IDs should be sequential
        expected_ids = [f"ORD-{i:06d}" for i in range(1, 6)]
        assert sorted(ids) == expected_ids
