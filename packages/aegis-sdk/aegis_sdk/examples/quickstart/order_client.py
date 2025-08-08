#!/usr/bin/env python3
"""
Order Client - Demonstrates client-side retry for Sticky Single-Active services.

This client shows:
- Automatic retry on NOT_ACTIVE errors
- Service discovery to find the active leader
- Order submission and status tracking
- Handling of failover scenarios

Usage:
    python order_client.py create --customer C123 --amount 99.99
    python order_client.py status --order ORD-1234
    python order_client.py stats
    python order_client.py bulk --count 10
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from aegis_sdk.developer.bootstrap import quick_setup
from aegis_sdk.domain.enums import RPCErrorCode
from aegis_sdk.domain.models import RPCError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OrderClient")


class OrderClient:
    """
    Client for interacting with the Order Processing Service.

    Implements retry logic for NOT_ACTIVE errors to handle
    the Sticky Single-Active pattern transparently.
    """

    def __init__(self):
        self.service = None
        self.max_retries = 3
        self.retry_delay = 0.5

    async def connect(self) -> None:
        """Connect to the NATS cluster and setup service discovery."""
        # Use quick_setup to auto-configure connection
        self.service = await quick_setup("order-client", as_client=True)
        logger.info("✅ Connected to NATS cluster")

    async def _call_with_retry(
        self, method: str, params: dict[str, Any], service_type: str = "order-processor"
    ) -> dict[str, Any]:
        """
        Call an RPC method with automatic retry on NOT_ACTIVE errors.

        This is the key pattern for Sticky Single-Active services:
        - Try to call the service
        - If NOT_ACTIVE, rediscover and retry
        - Eventually find the active leader
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Discover available instances
                instances = await self.service.discover_services(service_type)

                if not instances:
                    logger.warning(f"No instances of {service_type} found")
                    await asyncio.sleep(self.retry_delay)
                    continue

                # Try each instance (SDK load balances, but we handle NOT_ACTIVE)
                for instance in instances:
                    try:
                        logger.debug(f"Attempting {method} on instance {instance.instance_id}")

                        # Make the RPC call
                        result = await self.service.call_rpc(
                            service_type=service_type, method=method, params=params
                        )

                        # Success! Return the result
                        logger.info(f"✅ {method} succeeded on attempt {attempt + 1}")
                        return result

                    except RPCError as e:
                        if e.code == RPCErrorCode.NOT_ACTIVE:
                            # This instance is not active, try next one
                            logger.debug("Instance returned NOT_ACTIVE, trying next...")
                            last_error = e
                            continue
                        else:
                            # Other RPC error, propagate it
                            raise

                # If we get here, all instances returned NOT_ACTIVE
                # Wait a bit for leader election
                if attempt < self.max_retries - 1:
                    logger.info(
                        f"⏳ All instances standby, waiting {self.retry_delay}s for leader election..."
                    )
                    await asyncio.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)

        # All retries exhausted
        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    async def create_order(
        self, customer_id: str, amount: float, items: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Create a new order.

        This will automatically retry and find the active leader.
        """
        order_id = f"ORD-{random.randint(1000, 9999)}"

        params = {
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": amount,
            "items": items or [],
        }

        logger.info(f"📝 Creating order {order_id} for customer {customer_id}")

        start_time = time.time()
        result = await self._call_with_retry("create_order", params)
        elapsed = time.time() - start_time

        logger.info(f"✅ Order created in {elapsed:.2f}s: {result}")
        return result

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """
        Get the status of an order.

        Read operations can be handled by any instance.
        """
        params = {"order_id": order_id}

        # For read operations, we don't need to retry on NOT_ACTIVE
        # Any instance can handle it
        result = await self.service.call_rpc(
            service_type="order-processor", method="get_order_status", params=params
        )

        logger.info(
            f"📊 Order {order_id} status: {result.get('status')} (from instance {result.get('queried_from')})"
        )
        return result

    async def get_statistics(self) -> None:
        """
        Get statistics from all instances.

        Shows which instance is the leader and order counts.
        """
        instances = await self.service.discover_services("order-processor")

        if not instances:
            logger.warning("No order service instances found")
            return

        print("\n📊 Order Service Statistics:")
        print("-" * 50)

        for instance in instances:
            try:
                # Call each instance directly to get its stats
                result = await self.service.call_rpc(
                    service_type="order-processor",
                    method="get_statistics",
                    params={},
                    target_instance=instance.instance_id,  # Target specific instance
                )

                role = "👑 LEADER" if result.get("is_leader") else "💤 STANDBY"
                print(f"\nInstance {result['instance_id']} - {role}")
                print(f"  Total Orders: {result['total_orders']}")

                if result.get("orders_by_status"):
                    print("  Orders by Status:")
                    for status, count in result["orders_by_status"].items():
                        print(f"    - {status}: {count}")

            except Exception as e:
                print(f"\nInstance {instance.instance_id} - ❌ ERROR: {e}")

        print("-" * 50)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """
        Cancel an order.

        Write operation that requires the active leader.
        """
        params = {"order_id": order_id}

        logger.info(f"❌ Cancelling order {order_id}")

        result = await self._call_with_retry("cancel_order", params)

        if result.get("success"):
            logger.info(f"✅ Order cancelled by instance {result.get('cancelled_by')}")
        else:
            logger.warning(f"⚠️ Could not cancel order: {result.get('message')}")

        return result

    async def bulk_create_orders(self, count: int) -> None:
        """
        Create multiple orders to demonstrate load handling.

        Shows how the active leader processes all orders.
        """
        logger.info(f"📦 Creating {count} orders...")

        tasks = []
        for _i in range(count):
            customer_id = f"CUST-{random.randint(100, 999)}"
            amount = round(random.uniform(10.0, 500.0), 2)

            task = self.create_order(customer_id, amount)
            tasks.append(task)

            # Small delay between orders
            await asyncio.sleep(0.1)

        # Wait for all orders to be created
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = sum(1 for r in results if isinstance(r, Exception))

        logger.info(f"✅ Bulk creation complete: {successes} succeeded, {failures} failed")

        # Show which instance processed them
        if successes > 0:
            await self.get_statistics()

    async def monitor_failover(self, duration: int = 30) -> None:
        """
        Monitor the system during failover scenarios.

        Continuously creates orders and shows how the system handles
        leader changes transparently.
        """
        logger.info(f"🔄 Monitoring failover behavior for {duration} seconds...")
        logger.info("💡 Try stopping the leader instance to see failover in action!")

        end_time = time.time() + duration
        order_count = 0
        error_count = 0

        while time.time() < end_time:
            try:
                # Create an order
                customer_id = f"MONITOR-{random.randint(100, 999)}"
                amount = round(random.uniform(50.0, 200.0), 2)

                start = time.time()
                result = await self.create_order(customer_id, amount)
                elapsed = time.time() - start

                order_count += 1
                logger.info(
                    f"✅ Order {order_count} created in {elapsed:.2f}s by instance {result.get('processed_by')}"
                )

            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error creating order: {e}")

            # Wait before next order
            await asyncio.sleep(2)

        logger.info("\n📊 Failover monitoring complete:")
        logger.info(f"  - Orders created: {order_count}")
        logger.info(f"  - Errors: {error_count}")
        logger.info(f"  - Success rate: {(order_count / (order_count + error_count) * 100):.1f}%")

        # Show final statistics
        await self.get_statistics()


async def main():
    """Main entry point for the order client."""
    import argparse

    parser = argparse.ArgumentParser(description="Order Service Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create order command
    create_parser = subparsers.add_parser("create", help="Create a new order")
    create_parser.add_argument("--customer", required=True, help="Customer ID")
    create_parser.add_argument("--amount", type=float, required=True, help="Order amount")

    # Get order status
    status_parser = subparsers.add_parser("status", help="Get order status")
    status_parser.add_argument("--order", required=True, help="Order ID")

    # Cancel order
    cancel_parser = subparsers.add_parser("cancel", help="Cancel an order")
    cancel_parser.add_argument("--order", required=True, help="Order ID")

    # Get statistics
    subparsers.add_parser("stats", help="Get service statistics")

    # Bulk create orders
    bulk_parser = subparsers.add_parser("bulk", help="Create multiple orders")
    bulk_parser.add_argument("--count", type=int, default=5, help="Number of orders")

    # Monitor failover
    monitor_parser = subparsers.add_parser("monitor", help="Monitor failover behavior")
    monitor_parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create and connect client
    client = OrderClient()
    await client.connect()

    try:
        # Execute command
        if args.command == "create":
            await client.create_order(args.customer, args.amount)

        elif args.command == "status":
            await client.get_order_status(args.order)

        elif args.command == "cancel":
            await client.cancel_order(args.order)

        elif args.command == "stats":
            await client.get_statistics()

        elif args.command == "bulk":
            await client.bulk_create_orders(args.count)

        elif args.command == "monitor":
            await client.monitor_failover(args.duration)

    finally:
        if client.service:
            await client.service.stop()


if __name__ == "__main__":
    asyncio.run(main())
