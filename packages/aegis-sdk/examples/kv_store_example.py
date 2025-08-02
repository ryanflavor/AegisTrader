"""Example demonstrating NATS KV Store usage in AegisSDK."""

import asyncio
import json

from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure import NATSAdapter, NATSKVStore


async def main():
    """Demonstrate KV Store functionality."""
    # Create NATS adapter and connect
    nats_adapter = NATSAdapter()
    await nats_adapter.connect(["nats://localhost:4222"])

    # Create KV Store instance
    kv_store = NATSKVStore(nats_adapter=nats_adapter)

    try:
        # Connect to a KV bucket (creates if doesn't exist)
        await kv_store.connect("aegis-example-bucket")
        print("✅ Connected to KV Store bucket: aegis-example-bucket")

        # 1. Basic Put/Get operations
        print("\n📝 Basic Put/Get Operations:")
        await kv_store.put("user:123", {"name": "John Doe", "email": "john@example.com"})
        user = await kv_store.get("user:123")
        if user:
            print(f"  Retrieved user: {user.value}")
            print(f"  Revision: {user.revision}")

        # 2. Create-only operation (fails if exists)
        print("\n🔒 Create-Only Operation:")
        try:
            options = KVOptions(create_only=True)
            await kv_store.put("user:123", {"name": "Jane Doe"}, options)
            print("  ❌ Should not reach here - key already exists")
        except Exception as e:
            print(f"  ✅ Expected error: {e}")

        # 3. Update with revision check
        print("\n🔄 Update with Revision Check:")
        if user:
            current_revision = user.revision
            options = KVOptions(revision=current_revision)
            new_revision = await kv_store.put(
                "user:123",
                {"name": "John Doe", "email": "john@example.com", "updated": True},
                options,
            )
            print(f"  Updated successfully, new revision: {new_revision}")

        # 4. Batch operations
        print("\n📦 Batch Operations:")
        services = {
            "service:auth": {"type": "authentication", "port": 8080},
            "service:api": {"type": "api-gateway", "port": 8081},
            "service:worker": {"type": "background-worker", "port": 8082},
        }

        # Batch put
        revisions = await kv_store.put_many(services)
        print(f"  Stored {len(revisions)} services")

        # List keys
        service_keys = await kv_store.keys("service:")
        print(f"  Found service keys: {service_keys}")

        # Batch get
        retrieved = await kv_store.get_many(service_keys)
        for key, entry in retrieved.items():
            print(f"    {key}: {entry.value}")

        # 5. Key existence check
        print("\n🔍 Existence Check:")
        exists = await kv_store.exists("service:auth")
        print(f"  service:auth exists: {exists}")
        exists = await kv_store.exists("service:nonexistent")
        print(f"  service:nonexistent exists: {exists}")

        # 6. History tracking
        print("\n📜 History Tracking:")
        # Make multiple updates
        for i in range(3):
            await kv_store.put("config:version", {"version": f"1.0.{i}"})

        history = await kv_store.history("config:version", limit=5)
        print(f"  Found {len(history)} revisions:")
        for entry in history:
            print(f"    Revision {entry.revision}: {entry.value}")

        # 7. Clear with prefix
        print("\n🧹 Clear with Prefix:")
        # Add some temp keys
        await kv_store.put("temp:key1", "value1")
        await kv_store.put("temp:key2", "value2")
        await kv_store.put("temp:key3", "value3")

        # Clear all temp keys
        cleared = await kv_store.clear("temp:")
        print(f"  Cleared {cleared} temporary keys")

        # 8. Status information
        print("\n📊 Bucket Status:")
        status = await kv_store.status()
        print(f"  Status: {json.dumps(status, indent=2)}")

        # 9. Watch for changes (demonstration)
        print("\n👁️ Watch Demonstration:")
        print("  Setting up watcher for 'watched:key'...")

        async def watch_changes():
            """Watch for changes to a specific key."""
            event_count = 0
            async for event in kv_store.watch(key="watched:key"):
                print(f"  Event: {event.operation}")
                if event.entry:
                    print(f"    Value: {event.entry.value}")
                event_count += 1
                if event_count >= 3:
                    break

        # Start watching in background
        watch_task = asyncio.create_task(watch_changes())
        await asyncio.sleep(0.1)  # Let watcher initialize

        # Make changes
        await kv_store.put("watched:key", {"status": "created"})
        await asyncio.sleep(0.1)
        await kv_store.put("watched:key", {"status": "updated"})
        await asyncio.sleep(0.1)
        await kv_store.delete("watched:key")

        # Wait for watcher to complete
        try:
            await asyncio.wait_for(watch_task, timeout=2.0)
        except asyncio.TimeoutError:
            watch_task.cancel()

        print("\n✅ Example completed successfully!")

    finally:
        # Cleanup
        await kv_store.disconnect()
        await nats_adapter.disconnect()
        print("🔌 Disconnected from NATS")


if __name__ == "__main__":
    asyncio.run(main())
