"""JetStream Pull Consumer for Single Active Processing."""

import asyncio
import json
import time

import nats


class SingleActiveProcessor:
    """Single active processor using JetStream Pull Consumer."""

    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.nc = None
        self.js = None
        self.order_count = 0

    async def start(self, servers: list[str]):
        """Connect and setup JetStream."""
        self.nc = await nats.connect(servers=servers)
        self.js = self.nc.jetstream()

        # Create stream if not exists
        try:
            await self.js.stream_info("ORDERS")
        except:
            await self.js.add_stream(
                name="ORDERS",
                subjects=["orders.>"],
            )

        # Create durable consumer with MaxAckPending=1
        # This ensures only one message is processed at a time across all instances
        try:
            await self.js.consumer_info("ORDERS", "order-processor")
        except:
            await self.js.add_consumer(
                "ORDERS",
                name="order-processor",
                max_ack_pending=1,  # Key: Only 1 message in flight
                ack_wait=30,  # 30 seconds to process
            )

        print(f"✅ {self.instance_id} connected and ready")

    async def process_orders(self):
        """Pull and process orders - only one instance processes at a time."""
        consumer = await self.js.pull_subscribe(
            "orders.>",
            "order-processor",  # Shared durable consumer
        )

        print(f"👂 {self.instance_id} listening for orders...")

        while True:
            try:
                # Pull one message at a time
                msgs = await consumer.fetch(1, timeout=1)

                for msg in msgs:
                    data = json.loads(msg.data.decode())
                    self.order_count += 1

                    print(
                        f"📦 {self.instance_id} processing order #{self.order_count}: {data}"
                    )

                    # Simulate processing time
                    await asyncio.sleep(2)

                    # Acknowledge when done
                    await msg.ack()
                    print(f"✅ {self.instance_id} completed order")

            except asyncio.TimeoutError:
                # No messages, continue
                pass
            except Exception as e:
                print(f"❌ {self.instance_id} error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """Cleanup."""
        if self.nc:
            await self.nc.close()


async def send_test_orders(servers: list[str], count: int = 10):
    """Send test orders to the stream."""
    nc = await nats.connect(servers=servers)
    js = nc.jetstream()

    print("\n📤 Sending test orders...")

    for i in range(count):
        order = {
            "order_id": f"ORD-{int(time.time() * 1000)}-{i}",
            "item": "laptop" if i % 2 == 0 else "phone",
            "quantity": i + 1,
            "timestamp": time.time(),
        }

        await js.publish("orders.new", json.dumps(order).encode())
        print(f"  → Sent order {i + 1}/{count}")
        await asyncio.sleep(0.5)

    await nc.close()
    print("📤 All orders sent\n")


async def demo():
    """Run demo with 3 instances."""
    servers = ["nats://localhost:4222"]

    # Start 3 processor instances
    processors = []
    for i in range(1, 4):
        processor = SingleActiveProcessor(f"instance-{i}")
        await processor.start(servers)
        processors.append(processor)

    # Start processing in all instances
    # But only one will process each message due to MaxAckPending=1
    tasks = []
    for processor in processors:
        task = asyncio.create_task(processor.process_orders())
        tasks.append(task)

    await asyncio.sleep(2)

    # Send test orders
    await send_test_orders(servers, 15)

    # Let it run for a while
    await asyncio.sleep(40)

    # Cleanup
    for task in tasks:
        task.cancel()

    for processor in processors:
        await processor.stop()


if __name__ == "__main__":
    print("=== JetStream Single Active Demo ===\n")
    print("This demo shows how MaxAckPending=1 ensures only one")
    print("instance processes messages at a time, achieving")
    print("single active consumer pattern.\n")

    asyncio.run(demo())
