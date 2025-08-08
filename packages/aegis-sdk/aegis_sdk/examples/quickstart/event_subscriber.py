#!/usr/bin/env python3
"""
Event Subscriber Service - Demonstrates event subscription patterns.

This example shows:
- Different subscription modes (COMPETE, BROADCAST, EXCLUSIVE)
- Event filtering and processing
- Multiple subscribers handling events differently
- Observable event consumption with logging

Run subscribers with different modes:
    # COMPETE mode - load balance events across instances
    python event_subscriber.py --mode compete --instance 1
    python event_subscriber.py --mode compete --instance 2

    # BROADCAST mode - all instances receive all events
    python event_subscriber.py --mode broadcast --instance 1
    python event_subscriber.py --mode broadcast --instance 2

    # EXCLUSIVE mode - only one instance can subscribe
    python event_subscriber.py --mode exclusive --instance 1

    # Subscribe to specific topics
    python event_subscriber.py --topics orders payments
"""

from __future__ import annotations

import asyncio
import json
import logging

from aegis_sdk.application.services import Service
from aegis_sdk.developer.bootstrap import quick_setup
from aegis_sdk.domain.enums import SubscriptionMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [%(instance)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)


class EventSubscriberService(Service):
    """
    Event subscriber service demonstrating various subscription patterns.

    Shows how different subscription modes affect event delivery:
    - COMPETE: Events are load-balanced across subscribers
    - BROADCAST: All subscribers receive all events
    - EXCLUSIVE: Only one subscriber can be active
    """

    def __init__(self, instance_id: int, subscription_mode: SubscriptionMode):
        self.instance_id = str(instance_id)
        self.subscription_mode = subscription_mode
        self.event_counter = 0
        self.event_stats = {}
        self.logger = logging.getLogger(f"Subscriber-{instance_id}")

        # Add instance to log records
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.instance = f"{subscription_mode.value}-{instance_id}"
            return record

        logging.setLogRecordFactory(record_factory)

        super().__init__(
            name=f"event-subscriber-{subscription_mode.value}-{instance_id}",
            service_type="event-subscriber",
            instance_id=self.instance_id,
        )

    async def on_startup(self) -> None:
        """Initialize service on startup."""
        await super().on_startup()
        self.logger.info(
            f"🚀 Event Subscriber {self.instance_id} started in {self.subscription_mode.value} mode"
        )

    async def handle_order_event(self, data: bytes) -> None:
        """Handle order created events."""
        self.event_counter += 1
        self.event_stats["orders"] = self.event_stats.get("orders", 0) + 1

        try:
            event = json.loads(data.decode())
            self.logger.info(
                f"📦 Received OrderCreated #{self.event_counter}: "
                f"Order {event['order_id']} for ${event['total_amount']} "
                f"(created by {event.get('created_by', 'unknown')})"
            )

            # Simulate processing time
            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error processing order event: {e}")

    async def handle_payment_event(self, data: bytes) -> None:
        """Handle payment processed events."""
        self.event_counter += 1
        self.event_stats["payments"] = self.event_stats.get("payments", 0) + 1

        try:
            event = json.loads(data.decode())

            # Different handling based on payment status
            if event["status"] == "SUCCESS":
                icon = "✅"
            elif event["status"] == "PENDING":
                icon = "⏳"
            else:
                icon = "❌"

            self.logger.info(
                f"💳 Received PaymentProcessed #{self.event_counter}: "
                f"{icon} Payment {event['payment_id']} - {event['status']} "
                f"(${event['amount']})"
            )

            # Simulate processing time
            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error processing payment event: {e}")

    async def handle_inventory_event(self, data: bytes) -> None:
        """Handle inventory updated events."""
        self.event_counter += 1
        self.event_stats["inventory"] = self.event_stats.get("inventory", 0) + 1

        try:
            event = json.loads(data.decode())

            change = event["quantity_change"]
            symbol = "📈" if change > 0 else "📉"

            self.logger.info(
                f"{symbol} Received InventoryUpdated #{self.event_counter}: "
                f"Product {event['product_id']} {event['reason']} "
                f"({change:+d} units, new total: {event['new_quantity']})"
            )

            # Simulate processing time
            await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error processing inventory event: {e}")

    async def handle_alert_event(self, data: bytes) -> None:
        """Handle system alert events."""
        self.event_counter += 1
        self.event_stats["alerts"] = self.event_stats.get("alerts", 0) + 1

        try:
            event = json.loads(data.decode())

            icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}
            icon = icons.get(event["alert_level"], "📢")

            self.logger.info(
                f"{icon} Received SystemAlert #{self.event_counter}: "
                f"{event['alert_level']} from {event['source']} - "
                f"{event['message']}"
            )

            # Alert events should be processed quickly
            await asyncio.sleep(0.01)

        except Exception as e:
            self.logger.error(f"Error processing alert event: {e}")

    async def subscribe_to_events(self, topics: list[str]) -> None:
        """
        Subscribe to specified event topics.

        Subscription behavior depends on the mode:
        - COMPETE: Load balance with other subscribers
        - BROADCAST: Receive all events
        - EXCLUSIVE: Be the only subscriber
        """
        # Topic to handler mapping
        topic_handlers = {
            "orders": ("events.orders.created", self.handle_order_event),
            "payments": ("events.payments.processed", self.handle_payment_event),
            "inventory": ("events.inventory.updated", self.handle_inventory_event),
            "alerts": ("events.system.alerts", self.handle_alert_event),
        }

        for topic_key in topics:
            if topic_key not in topic_handlers:
                self.logger.warning(f"Unknown topic: {topic_key}")
                continue

            topic, handler = topic_handlers[topic_key]

            # Subscribe with the configured mode
            await self.subscribe(subject=topic, handler=handler, mode=self.subscription_mode)

            self.logger.info(f"📥 Subscribed to {topic} in {self.subscription_mode.value} mode")

    def print_statistics(self) -> None:
        """Print event processing statistics."""
        print(f"\n📊 Event Statistics for Instance {self.instance_id}:")
        print(f"   Mode: {self.subscription_mode.value}")
        print(f"   Total Events: {self.event_counter}")

        if self.event_stats:
            print("   Events by Type:")
            for event_type, count in self.event_stats.items():
                percentage = (count / self.event_counter * 100) if self.event_counter > 0 else 0
                print(f"     - {event_type}: {count} ({percentage:.1f}%)")
        print()


async def main():
    """Run the event subscriber."""
    import argparse

    parser = argparse.ArgumentParser(description="Event Subscriber Service")
    parser.add_argument(
        "--mode",
        choices=["compete", "broadcast", "exclusive"],
        default="compete",
        help="Subscription mode",
    )
    parser.add_argument("--instance", type=int, default=1, help="Instance number")
    parser.add_argument(
        "--topics",
        nargs="+",
        choices=["orders", "payments", "inventory", "alerts"],
        default=["orders", "payments", "inventory", "alerts"],
        help="Topics to subscribe to",
    )

    args = parser.parse_args()

    # Map mode string to enum
    mode_map = {
        "compete": SubscriptionMode.COMPETE,
        "broadcast": SubscriptionMode.BROADCAST,
        "exclusive": SubscriptionMode.EXCLUSIVE,
    }
    subscription_mode = mode_map[args.mode]

    # Create and configure the service
    service = EventSubscriberService(args.instance, subscription_mode)

    # Use quick_setup for auto-configuration
    configured_service = await quick_setup(
        f"event-subscriber-{args.mode}-{args.instance}", service_instance=service
    )

    # Start the service
    try:
        print(f"\n📡 Starting Event Subscriber - Instance {args.instance}")
        print(f"🎯 Mode: {subscription_mode.value}")
        print(f"📊 Subscribing to topics: {', '.join(args.topics)}")
        print("\n💡 Subscription Modes Explained:")
        print("  - COMPETE: Events load-balanced across instances")
        print("  - BROADCAST: All instances receive all events")
        print("  - EXCLUSIVE: Only one instance can subscribe")
        print("\nRun event_publisher.py to generate events")
        print("Press Ctrl+C to stop...\n")

        await configured_service.start()

        # Subscribe to selected topics
        await service.subscribe_to_events(args.topics)

        # Keep running and processing events
        try:
            while True:
                await asyncio.sleep(10)
                # Periodically print statistics
                service.print_statistics()

        except KeyboardInterrupt:
            pass

    except KeyboardInterrupt:
        print(f"\n⏹️  Stopping subscriber {args.instance}...")
    finally:
        service.print_statistics()
        await configured_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
