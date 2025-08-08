#!/usr/bin/env python3
"""
Order Processing Service - Sticky Single-Active Pattern Example.

This example demonstrates:
- SingleActiveService pattern for stateful order processing
- Client-side retry mechanism for NOT_ACTIVE errors
- Exactly-once processing with order state management
- Automatic failover with state consistency

Run multiple instances to see failover behavior:
    python order_service.py --instance 1
    python order_service.py --instance 2

Then use the order client to submit orders and observe processing.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aegis_sdk.application.services import SingleActiveService
from aegis_sdk.developer.bootstrap import quick_setup
from aegis_sdk.domain.enums import RPCErrorCode, ServiceStatus
from aegis_sdk.domain.models import RPCError

# Configure logging for visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [INSTANCE %(instance)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)


# Domain Models following DDD principles
class OrderStatus(str, Enum):
    """Order lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Order(BaseModel):
    """Order domain entity with unique identity."""

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Customer who placed the order")
    items: list[dict[str, Any]] = Field(default_factory=list, description="Order items")
    total_amount: float = Field(..., description="Total order amount")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current order status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = Field(default=None)
    processed_by: str | None = Field(default=None, description="Instance that processed the order")


class OrderRepository:
    """In-memory order repository for demo purposes."""

    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.orders: dict[str, Order] = {}
        self.logger = logging.getLogger(f"OrderRepo-{instance_id}")

    async def save(self, order: Order) -> None:
        """Persist order to repository."""
        self.orders[order.order_id] = order
        self.logger.info(f"Saved order {order.order_id} with status {order.status}")

    async def find_by_id(self, order_id: str) -> Order | None:
        """Retrieve order by ID."""
        return self.orders.get(order_id)

    async def find_pending(self) -> list[Order]:
        """Find all pending orders."""
        return [o for o in self.orders.values() if o.status == OrderStatus.PENDING]

    async def count_by_status(self) -> dict[str, int]:
        """Get order counts by status."""
        counts = {}
        for order in self.orders.values():
            counts[order.status] = counts.get(order.status, 0) + 1
        return counts


class OrderProcessingService(SingleActiveService):
    """
    Order processing service using Sticky Single-Active pattern.

    Only the active leader processes orders, ensuring consistency.
    Clients automatically retry on NOT_ACTIVE errors.
    """

    def __init__(self, instance_id: int):
        self.instance_id = str(instance_id)
        self.repository = OrderRepository(self.instance_id)
        self.processing_delay = 2.0  # Simulate processing time
        self.logger = logging.getLogger(f"OrderService-{instance_id}")

        # Add instance ID to log adapter
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.instance = instance_id
            return record

        logging.setLogRecordFactory(record_factory)

        super().__init__(
            name=f"order-service-{instance_id}",
            service_type="order-processor",
            instance_id=self.instance_id,
        )

    async def on_startup(self) -> None:
        """Initialize service on startup."""
        await super().on_startup()
        self.logger.info(f"🚀 Order service instance {self.instance_id} started")
        self.logger.info(f"Initial role: {self.failover_policy.current_status}")

        # Start background order processor if we're active
        if self.failover_policy.current_status == ServiceStatus.ACTIVE:
            asyncio.create_task(self._process_pending_orders())

    async def on_become_active(self) -> None:
        """Handle becoming the active leader."""
        self.logger.info(
            f"👑 Instance {self.instance_id} is now ACTIVE leader - starting order processing"
        )
        # Start processing pending orders
        asyncio.create_task(self._process_pending_orders())

    async def on_become_standby(self) -> None:
        """Handle becoming standby."""
        self.logger.info(
            f"💤 Instance {self.instance_id} is now STANDBY - stopping order processing"
        )

    async def _process_pending_orders(self) -> None:
        """Background task to process pending orders."""
        while self.failover_policy.current_status == ServiceStatus.ACTIVE:
            try:
                pending = await self.repository.find_pending()
                for order in pending:
                    if self.failover_policy.current_status != ServiceStatus.ACTIVE:
                        break

                    self.logger.info(f"📦 Processing order {order.order_id}")
                    order.status = OrderStatus.PROCESSING
                    order.processed_by = self.instance_id
                    await self.repository.save(order)

                    # Simulate processing work
                    await asyncio.sleep(self.processing_delay)

                    # Complete the order
                    order.status = OrderStatus.COMPLETED
                    order.processed_at = datetime.utcnow()
                    await self.repository.save(order)

                    self.logger.info(f"✅ Completed order {order.order_id}")

            except Exception as e:
                self.logger.error(f"Error processing orders: {e}")

            await asyncio.sleep(1)  # Check for new orders every second

    async def create_order(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new order - only processes if active leader.

        RPC handler that returns NOT_ACTIVE if this instance is standby.
        Clients should retry with service discovery to find the active instance.
        """
        # Check if we're the active instance
        if self.failover_policy.current_status != ServiceStatus.ACTIVE:
            self.logger.warning(
                f"Rejecting order creation - instance is {self.failover_policy.current_status}"
            )
            raise RPCError(
                code=RPCErrorCode.NOT_ACTIVE,
                message=f"Instance {self.instance_id} is not active leader",
            )

        # Create and save the order
        order = Order(
            order_id=params.get("order_id", f"ORD-{random.randint(1000, 9999)}"),
            customer_id=params["customer_id"],
            items=params.get("items", []),
            total_amount=params["total_amount"],
        )

        await self.repository.save(order)
        self.logger.info(f"📝 Created order {order.order_id} for customer {order.customer_id}")

        return {
            "order_id": order.order_id,
            "status": order.status,
            "processed_by": self.instance_id,
            "message": f"Order created and will be processed by instance {self.instance_id}",
        }

    async def get_order_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Get order status - can be handled by any instance.

        Read operations don't require active leader status.
        """
        order_id = params["order_id"]
        order = await self.repository.find_by_id(order_id)

        if not order:
            return {"order_id": order_id, "status": "not_found", "instance": self.instance_id}

        return {
            "order_id": order.order_id,
            "status": order.status,
            "processed_by": order.processed_by,
            "created_at": order.created_at.isoformat(),
            "processed_at": order.processed_at.isoformat() if order.processed_at else None,
            "queried_from": self.instance_id,
        }

    async def get_statistics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get order processing statistics from this instance."""
        counts = await self.repository.count_by_status()

        return {
            "instance_id": self.instance_id,
            "role": self.failover_policy.current_status,
            "total_orders": len(self.repository.orders),
            "orders_by_status": counts,
            "is_leader": self.failover_policy.current_status == ServiceStatus.ACTIVE,
        }

    async def cancel_order(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Cancel an order - only allowed by active leader.

        Write operations require active leader status.
        """
        if self.failover_policy.current_status != ServiceStatus.ACTIVE:
            raise RPCError(
                code=RPCErrorCode.NOT_ACTIVE,
                message=f"Instance {self.instance_id} is not active - cannot cancel orders",
            )

        order_id = params["order_id"]
        order = await self.repository.find_by_id(order_id)

        if not order:
            return {"order_id": order_id, "status": "not_found", "success": False}

        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            return {
                "order_id": order_id,
                "status": order.status,
                "success": False,
                "message": f"Cannot cancel order in {order.status} status",
            }

        order.status = OrderStatus.CANCELLED
        await self.repository.save(order)

        self.logger.info(f"❌ Cancelled order {order_id}")

        return {
            "order_id": order_id,
            "status": order.status,
            "success": True,
            "cancelled_by": self.instance_id,
        }


async def main():
    """Run the order processing service."""
    import argparse

    parser = argparse.ArgumentParser(description="Order Processing Service")
    parser.add_argument("--instance", type=int, default=1, help="Instance number (default: 1)")
    args = parser.parse_args()

    # Create and configure the service
    service = OrderProcessingService(args.instance)

    # Use quick_setup for auto-configuration
    configured_service = await quick_setup(
        f"order-service-{args.instance}", service_instance=service
    )

    # Register RPC handlers
    configured_service.register_rpc_handler("create_order", service.create_order)
    configured_service.register_rpc_handler("get_order_status", service.get_order_status)
    configured_service.register_rpc_handler("get_statistics", service.get_statistics)
    configured_service.register_rpc_handler("cancel_order", service.cancel_order)

    # Start the service
    try:
        print(f"\n🏪 Starting Order Processing Service - Instance {args.instance}")
        print("📍 Pattern: Sticky Single-Active with automatic failover")
        print("💡 Only the active leader processes orders")
        print("🔄 Clients automatically retry on NOT_ACTIVE errors")
        print("\nPress Ctrl+C to stop...\n")

        await configured_service.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print(f"\n⏹️  Stopping instance {args.instance}...")
        await configured_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
