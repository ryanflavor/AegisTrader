#!/usr/bin/env python3
"""
Event Publisher Service - Demonstrates event publishing patterns.

This example shows:
- Publishing domain events to topics
- Different event types and payloads
- Event routing patterns
- Observable event flow with logging

Run the publisher:
    python event_publisher.py --mode continuous
    python event_publisher.py --mode single --event order
    python event_publisher.py --mode burst --count 10
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aegis_sdk.application.services import Service
from aegis_sdk.developer.bootstrap import quick_setup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("EventPublisher")


# Domain Events following DDD principles
class OrderCreatedEvent(BaseModel):
    """Event emitted when a new order is created."""

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Customer who placed the order")
    total_amount: float = Field(..., description="Total order amount")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(..., description="Service instance that created the order")


class PaymentProcessedEvent(BaseModel):
    """Event emitted when a payment is processed."""

    payment_id: str = Field(..., description="Unique payment identifier")
    order_id: str = Field(..., description="Associated order ID")
    amount: float = Field(..., description="Payment amount")
    status: str = Field(..., description="Payment status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processed_by: str = Field(..., description="Service instance that processed payment")


class InventoryUpdatedEvent(BaseModel):
    """Event emitted when inventory levels change."""

    product_id: str = Field(..., description="Product identifier")
    quantity_change: int = Field(..., description="Change in quantity (negative for decrease)")
    new_quantity: int = Field(..., description="New total quantity")
    reason: str = Field(..., description="Reason for update")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = Field(..., description="Service instance that updated inventory")


class SystemAlertEvent(BaseModel):
    """Event emitted for system-wide alerts."""

    alert_level: str = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    source: str = Field(..., description="Source of the alert")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EventPublisherService(Service):
    """
    Event publisher service demonstrating various event patterns.

    Shows how to publish different types of domain events
    that can be consumed by subscribers in different modes.
    """

    def __init__(self, instance_id: int = 1):
        self.instance_id = str(instance_id)
        self.event_counter = 0
        self.logger = logging.getLogger(f"Publisher-{instance_id}")

        super().__init__(
            name=f"event-publisher-{instance_id}",
            service_type="event-publisher",
            instance_id=self.instance_id,
        )

    async def on_startup(self) -> None:
        """Initialize service on startup."""
        await super().on_startup()
        self.logger.info(f"🚀 Event Publisher {self.instance_id} started")

    async def publish_order_created(self) -> None:
        """Publish an order created event."""
        self.event_counter += 1

        event = OrderCreatedEvent(
            order_id=f"ORD-{random.randint(1000, 9999)}",
            customer_id=f"CUST-{random.randint(100, 999)}",
            total_amount=round(random.uniform(10.0, 500.0), 2),
            created_by=self.instance_id,
        )

        # Publish to orders topic
        topic = "events.orders.created"
        await self.publish_event(topic, event.model_dump())

        self.logger.info(
            f"📦 Published OrderCreated event #{self.event_counter}: "
            f"Order {event.order_id} for ${event.total_amount}"
        )

    async def publish_payment_processed(self) -> None:
        """Publish a payment processed event."""
        self.event_counter += 1

        event = PaymentProcessedEvent(
            payment_id=f"PAY-{random.randint(10000, 99999)}",
            order_id=f"ORD-{random.randint(1000, 9999)}",
            amount=round(random.uniform(10.0, 500.0), 2),
            status=random.choice(["SUCCESS", "PENDING", "FAILED"]),
            processed_by=self.instance_id,
        )

        # Publish to payments topic
        topic = "events.payments.processed"
        await self.publish_event(topic, event.model_dump())

        self.logger.info(
            f"💳 Published PaymentProcessed event #{self.event_counter}: "
            f"Payment {event.payment_id} - {event.status}"
        )

    async def publish_inventory_updated(self) -> None:
        """Publish an inventory updated event."""
        self.event_counter += 1

        quantity_change = random.randint(-50, 100)
        event = InventoryUpdatedEvent(
            product_id=f"PROD-{random.randint(100, 999)}",
            quantity_change=quantity_change,
            new_quantity=random.randint(0, 1000),
            reason=random.choice(["SALE", "RESTOCK", "ADJUSTMENT", "RETURN"]),
            updated_by=self.instance_id,
        )

        # Publish to inventory topic
        topic = "events.inventory.updated"
        await self.publish_event(topic, event.model_dump())

        symbol = "📈" if quantity_change > 0 else "📉"
        self.logger.info(
            f"{symbol} Published InventoryUpdated event #{self.event_counter}: "
            f"Product {event.product_id} {event.reason} ({quantity_change:+d})"
        )

    async def publish_system_alert(self, level: str = "INFO", message: str | None = None) -> None:
        """Publish a system alert event."""
        self.event_counter += 1

        if not message:
            messages = {
                "INFO": "System operating normally",
                "WARNING": "High memory usage detected",
                "ERROR": "Connection timeout to external service",
                "CRITICAL": "Database connection lost",
            }
            message = messages.get(level, "System event occurred")

        event = SystemAlertEvent(
            alert_level=level,
            message=message,
            source=f"publisher-{self.instance_id}",
            metadata={
                "event_count": self.event_counter,
                "publisher_uptime": time.time(),
            },
        )

        # Publish to alerts topic - these should broadcast to all subscribers
        topic = "events.system.alerts"
        await self.publish_event(topic, event.model_dump())

        icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}
        icon = icons.get(level, "📢")
        self.logger.info(
            f"{icon} Published SystemAlert event #{self.event_counter}: {level} - {message}"
        )

    async def publish_event(self, topic: str, data: dict[str, Any]) -> None:
        """
        Publish an event to a topic.

        Events can be consumed by subscribers in different modes:
        - COMPETE: Only one subscriber receives each event
        - BROADCAST: All subscribers receive all events
        - EXCLUSIVE: Only one specific subscriber receives events
        """

        # Serialize datetime objects for JSON
        def serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        # Publish the event
        payload = json.dumps(data, default=serialize).encode()
        await self.message_bus.publish(topic, payload)

    async def run_continuous_mode(self, interval: float = 2.0) -> None:
        """Continuously publish random events."""
        self.logger.info(f"🔄 Starting continuous event publishing (interval: {interval}s)")
        self.logger.info("Press Ctrl+C to stop")

        event_types = [
            self.publish_order_created,
            self.publish_payment_processed,
            self.publish_inventory_updated,
            lambda: self.publish_system_alert(random.choice(["INFO", "WARNING", "ERROR"])),
        ]

        while True:
            # Randomly select an event type to publish
            event_func = random.choice(event_types)
            await event_func()

            await asyncio.sleep(interval)

    async def run_burst_mode(self, count: int = 10) -> None:
        """Publish a burst of events."""
        self.logger.info(f"💥 Publishing burst of {count} events")

        event_types = [
            self.publish_order_created,
            self.publish_payment_processed,
            self.publish_inventory_updated,
        ]

        for _i in range(count):
            event_func = random.choice(event_types)
            await event_func()

            # Small delay between events
            await asyncio.sleep(0.1)

        self.logger.info(f"✅ Burst complete: {count} events published")

    async def run_single_mode(self, event_type: str) -> None:
        """Publish a single event of specified type."""
        event_map = {
            "order": self.publish_order_created,
            "payment": self.publish_payment_processed,
            "inventory": self.publish_inventory_updated,
            "alert": lambda: self.publish_system_alert("WARNING", "Test alert from publisher"),
        }

        if event_type not in event_map:
            self.logger.error(f"Unknown event type: {event_type}")
            self.logger.info(f"Available types: {', '.join(event_map.keys())}")
            return

        await event_map[event_type]()
        self.logger.info(f"✅ Single {event_type} event published")


async def main():
    """Run the event publisher."""
    import argparse

    parser = argparse.ArgumentParser(description="Event Publisher Service")
    parser.add_argument(
        "--mode",
        choices=["continuous", "burst", "single"],
        default="continuous",
        help="Publishing mode",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Interval for continuous mode")
    parser.add_argument("--count", type=int, default=10, help="Number of events for burst mode")
    parser.add_argument(
        "--event",
        choices=["order", "payment", "inventory", "alert"],
        default="order",
        help="Event type for single mode",
    )
    parser.add_argument("--instance", type=int, default=1, help="Instance number")

    args = parser.parse_args()

    # Create and configure the service
    service = EventPublisherService(args.instance)

    # Use quick_setup for auto-configuration
    configured_service = await quick_setup(
        f"event-publisher-{args.instance}", service_instance=service
    )

    # Start the service
    try:
        print(f"\n📡 Starting Event Publisher - Instance {args.instance}")
        print(f"🎯 Mode: {args.mode}")
        print("📊 Events will be published to topics:")
        print("  - events.orders.created")
        print("  - events.payments.processed")
        print("  - events.inventory.updated")
        print("  - events.system.alerts")
        print("\nRun event_subscriber.py to consume these events\n")

        await configured_service.start()

        # Run the selected mode
        if args.mode == "continuous":
            await service.run_continuous_mode(args.interval)
        elif args.mode == "burst":
            await service.run_burst_mode(args.count)
        elif args.mode == "single":
            await service.run_single_mode(args.event)

        # Keep service running for a moment to ensure events are sent
        await asyncio.sleep(1)

    except KeyboardInterrupt:
        print(f"\n⏹️  Stopping publisher {args.instance}...")
    finally:
        await configured_service.stop()
        print(f"📊 Total events published: {service.event_counter}")


if __name__ == "__main__":
    asyncio.run(main())
