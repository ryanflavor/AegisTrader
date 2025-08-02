"""Sticky Single Active Pattern - Working Implementation."""

import asyncio
import contextlib
import json
import time

import nats
from nats.errors import TimeoutError as NATSTimeoutError


class StickySingleActiveService:
    """Sticky single active service - ensures one instance processes continuously until failure."""

    def __init__(self, service_name: str, instance_id: str):
        self.service_name = service_name
        self.instance_id = instance_id
        self.nc = None
        self.js = None

        # 活跃状态
        self.is_active = False
        self.last_heartbeat = time.time()
        self.active_instance = None

        # 业务计数
        self.processed_count = 0
        self.running = True

    async def connect(self, servers: list[str]):
        """Connect to NATS."""
        self.nc = await nats.connect(servers=servers)
        self.js = self.nc.jetstream()

        # Create command stream
        try:
            await self.js.stream_info(f"{self.service_name}_COMMANDS")
            print(f"✅ Stream {self.service_name}_COMMANDS already exists")
        except Exception:
            await self.js.add_stream(
                name=f"{self.service_name}_COMMANDS",
                subjects=[f"{self.service_name}.commands.>"],
                retention="workqueue",
            )
            print(f"✅ Created stream {self.service_name}_COMMANDS")

        print(f"✅ {self.instance_id} connected")

    async def start(self):
        """Start service and election."""
        # Subscribe to heartbeats
        await self.nc.subscribe(
            f"{self.service_name}.heartbeat", cb=self._handle_heartbeat
        )

        # Start election loop
        election_task = asyncio.create_task(self._election_loop())

        # Start processing loop
        process_task = asyncio.create_task(self._process_loop())

        try:
            await asyncio.gather(election_task, process_task)
        except asyncio.CancelledError:
            print(f"🛑 {self.instance_id} stopped")

    async def stop(self):
        """Stop the service."""
        self.running = False
        if self.nc:
            await self.nc.close()

    async def _handle_heartbeat(self, msg):
        """Handle heartbeat messages."""
        try:
            data = json.loads(msg.data.decode())

            if data["instance_id"] != self.instance_id:
                # Another instance is active
                self.active_instance = data["instance_id"]
                self.last_heartbeat = time.time()

                # If we were active before, yield now
                if self.is_active:
                    print(
                        f"🔄 {self.instance_id} detected {data['instance_id']} is active, yielding"
                    )
                    self.is_active = False
        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

    async def _election_loop(self):
        """Election loop - decide who is the active instance."""
        await asyncio.sleep(2)  # Initial wait

        while self.running:
            try:
                current_time = time.time()

                # If no heartbeat for 5 seconds, try to become active
                if not self.is_active and (current_time - self.last_heartbeat > 5):
                    print(
                        f"🗳️ {self.instance_id} no active instance detected, attempting to become active"
                    )

                    # Wait random time to avoid race conditions
                    await asyncio.sleep(0.1 * hash(self.instance_id) % 10 / 10)

                    # Check again if another instance became active
                    if current_time - self.last_heartbeat > 5:
                        self.is_active = True
                        self.active_instance = self.instance_id
                        print(f"👑 {self.instance_id} became active instance!")

                # If active, send heartbeat
                if self.is_active:
                    heartbeat = {
                        "instance_id": self.instance_id,
                        "timestamp": current_time,
                        "processed": self.processed_count,
                    }
                    await self.nc.publish(
                        f"{self.service_name}.heartbeat", json.dumps(heartbeat).encode()
                    )

                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ Election error: {e}")
                await asyncio.sleep(1)

    async def _process_loop(self):
        """Processing loop - only active instance processes messages."""
        # Use pull_subscribe instead of pull_subscribe_bind
        # This will automatically create consumer if it doesn't exist
        consumer = await self.js.pull_subscribe(
            f"{self.service_name}.commands.>",
            durable=f"{self.service_name}-processor",
            stream=f"{self.service_name}_COMMANDS",
        )

        print(f"🎯 {self.instance_id} ready to process commands")

        while self.running:
            try:
                # Only active instance pulls messages
                if self.is_active:
                    # Pull single message
                    try:
                        msgs = await consumer.fetch(1, timeout=1)

                        for msg in msgs:
                            # Double check if still active
                            if not self.is_active:
                                # No longer active, reject message for other instances to handle
                                await msg.nak()
                                break

                            # Process message
                            data = json.loads(msg.data.decode())
                            self.processed_count += 1

                            print(
                                f"📦 {self.instance_id} processing command #{self.processed_count}: {data}"
                            )

                            # Simulate processing time
                            await asyncio.sleep(0.5)

                            # Acknowledge message
                            await msg.ack()

                    except NATSTimeoutError:
                        # No messages, normal case
                        pass
                else:
                    # Inactive state, wait
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Process error: {e}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(1)


async def send_commands(service_name: str, servers: list[str], count: int = 20):
    """Send test commands."""
    nc = await nats.connect(servers=servers)
    js = nc.jetstream()

    print(f"\n📤 Sending {count} test commands...")

    for i in range(count):
        command = {
            "cmd_id": f"CMD-{int(time.time() * 1000)}-{i}",
            "action": "process_order" if i % 2 == 0 else "check_status",
            "seq": i + 1,
        }

        await js.publish(f"{service_name}.commands.new", json.dumps(command).encode())

        if i < 5 or i % 5 == 0:
            print(f"  → Sent command {i + 1}/{count}")

        await asyncio.sleep(0.1)

    await nc.close()
    print("📤 All commands sent\n")


async def demo():
    """Run the demo."""
    servers = ["nats://localhost:4222"]
    service_name = (
        "sticky-order-service"  # Use different service name to avoid conflicts
    )

    # Clean up old streams
    try:
        nc = await nats.connect(servers=servers)
        js = nc.jetstream()
        try:
            await js.delete_stream(f"{service_name}_COMMANDS")
            print("🧹 Cleaned old stream")
        except Exception:
            pass
        await nc.close()
    except Exception:
        pass

    # Start 2 instances (simplified demo)
    instances = []
    tasks = []

    for i in range(1, 3):
        instance = StickySingleActiveService(service_name, f"instance-{i}")
        await instance.connect(servers)
        instances.append(instance)

        # Start instance
        task = asyncio.create_task(instance.start())
        tasks.append(task)

    print("\n=== Waiting for election to complete ===")
    await asyncio.sleep(8)

    # Show current active instance
    active_count = 0
    for instance in instances:
        if instance.is_active:
            print(f"📍 Current active instance: {instance.instance_id}")
            active_count += 1

    if active_count == 0:
        print("❌ No active instance!")
    elif active_count > 1:
        print(f"⚠️  There are {active_count} active instances!")

    # Send commands
    await send_commands(service_name, servers, 15)

    # Run for a while
    print("\n=== Processing commands... ===")
    await asyncio.sleep(10)

    # Show intermediate statistics
    print("\n=== Intermediate statistics ===")
    for instance in instances:
        if instance.processed_count > 0:
            print(
                f"{instance.instance_id}: Processed {instance.processed_count} commands"
            )

    # Simulate active instance failure
    print("\n=== Simulating active instance failure ===")
    for instance in instances:
        if instance.is_active:
            print(f"💥 Stopping active instance: {instance.instance_id}")
            instance.is_active = False
            instance.running = False
            break

    # Wait for re-election
    await asyncio.sleep(8)

    # Show new active instance
    for instance in instances:
        if instance.is_active:
            print(f"📍 New active instance: {instance.instance_id}")
            break

    # Send more commands
    await send_commands(service_name, servers, 10)

    # Continue running
    await asyncio.sleep(8)

    # Show final statistics
    print("\n=== Final statistics ===")
    total_processed = 0
    for instance in instances:
        print(f"{instance.instance_id}: Processed {instance.processed_count} commands")
        total_processed += instance.processed_count
    print(f"Total processed: {total_processed} commands")
    print("Expected to process: 25 commands")

    # Cleanup
    for instance in instances:
        instance.running = False

    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    for instance in instances:
        await instance.stop()


if __name__ == "__main__":
    print("=== Sticky Single Active Pattern Demo (Working Version) ===\n")
    print("Features:")
    print("1. Only one instance is active")
    print("2. Active instance continuously processes all requests")
    print("3. When active instance fails, another instance takes over")
    print("4. Uses JetStream to ensure messages are not lost\n")

    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\n\nUser interrupted, exiting...")
