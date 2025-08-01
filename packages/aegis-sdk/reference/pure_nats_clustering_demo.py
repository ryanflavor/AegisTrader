#!/usr/bin/env python3
"""
Demonstrate NATS clustering and connection pooling with pure NATS.
Shows how to add these features to the minimal implementation.
"""

import asyncio
import time

import nats
from nats.aio.client import Client as NATSConnection


class SimpleConnectionPool:
    """Minimal connection pool implementation (~100 lines)."""

    def __init__(self, servers: list[str], min_size: int = 2, max_size: int = 5):
        self.servers = servers
        self.min_size = min_size
        self.max_size = max_size
        self.connections: list[tuple[NATSConnection, bool]] = []  # (conn, in_use)
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Create minimum connections."""
        for _ in range(self.min_size):
            conn = await nats.connect(
                servers=self.servers,
                max_reconnect_attempts=10,
                reconnect_time_wait=2.0,
            )
            self.connections.append((conn, False))
        print(f"✅ Pool initialized with {self.min_size} connections")

    async def acquire(self) -> NATSConnection:
        """Get a connection from pool."""
        async with self._lock:
            # Find available connection
            for i, (conn, in_use) in enumerate(self.connections):
                if not in_use and conn.is_connected:
                    self.connections[i] = (conn, True)
                    return conn

            # Create new if under max
            if len(self.connections) < self.max_size:
                conn = await nats.connect(
                    servers=self.servers,
                    max_reconnect_attempts=10,
                    reconnect_time_wait=2.0,
                )
                self.connections.append((conn, True))
                print(f"📈 Pool expanded to {len(self.connections)} connections")
                return conn

        raise Exception("No connections available")

    async def release(self, conn: NATSConnection):
        """Return connection to pool."""
        async with self._lock:
            for i, (c, _) in enumerate(self.connections):
                if c == conn:
                    self.connections[i] = (c, False)
                    break

    async def close(self):
        """Close all connections."""
        for conn, _ in self.connections:
            if conn.is_connected:
                await conn.close()
        print("👋 Pool closed")


class ClusteredNATSDemo:
    """Demo showing clustering and pooling with pure NATS."""

    def __init__(self, cluster_urls: list[str]):
        self.cluster_urls = cluster_urls
        self.pool: SimpleConnectionPool | None = None
        self.single_conn: NATSConnection | None = None

    async def demo_single_connection_clustering(self):
        """Show how NATS handles clustering automatically."""
        print("\n" + "=" * 60)
        print("🔵 DEMO 1: Single Connection with Clustering")
        print("=" * 60)

        # Track connection events
        events = []

        async def disconnected_cb():
            events.append(("disconnected", time.time()))
            print("🔴 Disconnected from NATS")

        async def reconnected_cb():
            events.append(("reconnected", time.time()))
            print("🟢 Reconnected to NATS")

        async def error_cb(e):
            print(f"❌ Error: {e}")

        # Connect with multiple servers
        self.single_conn = await nats.connect(
            servers=self.cluster_urls,
            disconnected_cb=disconnected_cb,
            reconnected_cb=reconnected_cb,
            error_cb=error_cb,
            max_reconnect_attempts=10,
            reconnect_time_wait=2.0,
        )

        print(f"✅ Connected to: {self.single_conn.connected_url}")
        print(f"📊 Cluster info: {len(self.cluster_urls)} servers configured")

        # Publish test messages
        for i in range(5):
            await self.single_conn.publish("test.cluster", f"Message {i}".encode())
            print(f"📤 Published message {i}")
            await asyncio.sleep(0.5)

        print("\n⚡ NATS automatically handles:")
        print("  - Failover to healthy nodes")
        print("  - Message buffering during reconnect")
        print("  - Transparent reconnection")

    async def demo_connection_pooling(self):
        """Show connection pooling benefits."""
        print("\n" + "=" * 60)
        print("🟡 DEMO 2: Connection Pooling")
        print("=" * 60)

        # Initialize pool
        self.pool = SimpleConnectionPool(self.cluster_urls, min_size=2, max_size=5)
        await self.pool.initialize()

        # Simulate concurrent requests
        print("\n📊 Simulating 10 concurrent operations...")

        async def worker(worker_id: int):
            conn = await self.pool.acquire()
            try:
                start = time.time()
                await conn.publish("test.pool", f"Worker {worker_id}".encode())
                latency = (time.time() - start) * 1000
                print(f"  Worker {worker_id}: Published in {latency:.2f}ms")
                await asyncio.sleep(0.1)  # Simulate work
            finally:
                await self.pool.release(conn)

        # Run workers concurrently
        await asyncio.gather(*[worker(i) for i in range(10)])

        print("\n✅ Pool benefits:")
        print("  - No connection setup overhead")
        print("  - Concurrent request handling")
        print("  - Connection reuse")

    async def demo_failover_scenario(self):
        """Simulate failover scenario."""
        print("\n" + "=" * 60)
        print("🔴 DEMO 3: Failover Simulation")
        print("=" * 60)

        if not self.single_conn:
            return

        print(f"📍 Currently connected to: {self.single_conn.connected_url}")
        print("\n⚠️  To test failover:")
        print("  1. Stop the current NATS server")
        print("  2. Watch automatic reconnection")
        print("  3. Messages continue to flow")

        # Subscribe to test failover
        received = []

        async def message_handler(msg):
            received.append(msg.data.decode())
            print(f"📨 Received: {msg.data.decode()}")

        sub = await self.single_conn.subscribe("test.failover", cb=message_handler)

        # Publish messages continuously
        print("\n📤 Publishing messages every 2 seconds...")
        print("   (Stop current NATS server to see failover)")

        for i in range(10):
            try:
                await self.single_conn.publish(
                    "test.failover", f"Failover test {i}".encode()
                )
                await self.single_conn.flush()
                print(f"✓ Message {i} sent via {self.single_conn.connected_url}")
            except Exception as e:
                print(f"✗ Message {i} failed: {e}")

            await asyncio.sleep(2)

        await sub.unsubscribe()
        print(f"\n📊 Messages received: {len(received)}/10")

    async def cleanup(self):
        """Clean up connections."""
        if self.single_conn and self.single_conn.is_connected:
            await self.single_conn.close()
        if self.pool:
            await self.pool.close()


async def main():
    """Run clustering and pooling demos."""
    # Cluster URLs - adjust based on your setup
    cluster_urls = [
        "nats://localhost:4222",
        "nats://localhost:4223",
        "nats://localhost:4224",
    ]

    print("🌟 NATS Clustering & Connection Pooling Demo")
    print("=" * 60)
    print(f"Cluster nodes: {cluster_urls}")

    demo = ClusteredNATSDemo(cluster_urls)

    try:
        # Run demos
        await demo.demo_single_connection_clustering()
        await demo.demo_connection_pooling()
        await demo.demo_failover_scenario()

        print("\n" + "=" * 60)
        print("📊 Summary:")
        print("  - NATS clustering: Built-in, 0 extra code")
        print("  - Connection pooling: ~100 lines for basic pool")
        print("  - Both features: < 200 lines total")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
