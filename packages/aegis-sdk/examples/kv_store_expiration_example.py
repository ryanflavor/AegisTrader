#!/usr/bin/env python3
"""Example: KV Store with stream-level expiration.

IMPORTANT: NATS KV store does NOT support per-message TTL reliably.
This example demonstrates the correct approach using stream-level TTL
configuration and client-side filtering based on timestamps.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.config import KVStoreConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


async def main():
    """Demonstrate KV Store with stream-level TTL configuration."""
    # Set up logging to see what's happening
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create NATS adapter
    adapter = NATSAdapter()

    # Connect to NATS
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    await adapter.connect([nats_url])

    # Create KV store with stream-level TTL configuration
    # This will automatically expire old HISTORY entries after 60 seconds
    kv_config = KVStoreConfig(
        bucket="expiration_example",
        stream_max_age_seconds=60,  # Stream-level TTL for history cleanup
    )
    kv_store = NATSKVStore(adapter, config=kv_config)
    await kv_store.connect("expiration_example")

    print("\n=== Stream-Level TTL Configuration ===")
    print("Stream max age: 60 seconds")
    print("This means:")
    print("1. Old history entries are purged after 60 seconds")
    print("2. Current values persist until explicitly deleted")
    print("3. Service expiration must be handled by client-side filtering\n")

    # Example 1: Service registration with heartbeat
    print("=== Example 1: Service Registration ===")
    service = ServiceInstance(
        service_name="example-service",
        instance_id="instance-001",
        version="1.0.0",
        status="ACTIVE",
        last_heartbeat=datetime.now(UTC).isoformat(),
    )

    # Store service (no per-message TTL)
    await kv_store.put(
        f"service__{service.instance_id}",
        service.model_dump(),
    )
    print(f"Registered service: {service.instance_id}")

    # Example 2: Client-side expiration check
    print("\n=== Example 2: Client-Side Expiration ===")

    async def is_service_alive(service_key: str, max_age_seconds: int = 30) -> bool:
        """Check if a service is still alive based on heartbeat."""
        entry = await kv_store.get(service_key)
        if not entry or not entry.value:
            return False

        service_data = entry.value
        last_heartbeat = datetime.fromisoformat(
            service_data.get("last_heartbeat", "").replace("Z", "+00:00")
        )
        age = datetime.now(UTC) - last_heartbeat

        is_alive = age.total_seconds() < max_age_seconds
        print(f"Service age: {age.total_seconds():.1f}s, alive: {is_alive}")
        return is_alive

    # Check if service is alive
    service_key = f"service__{service.instance_id}"
    alive = await is_service_alive(service_key, max_age_seconds=30)
    print(f"Service {service.instance_id} is {'alive' if alive else 'expired'}")

    # Example 3: Manual cleanup of expired entries
    print("\n=== Example 3: Manual Cleanup ===")

    async def cleanup_expired_services(prefix: str = "service__", max_age_seconds: int = 30):
        """Remove expired services based on heartbeat age."""
        keys = await kv_store.keys(prefix)
        expired_count = 0

        for key in keys:
            entry = await kv_store.get(key)
            if entry and entry.value:
                last_heartbeat = datetime.fromisoformat(
                    entry.value.get("last_heartbeat", "").replace("Z", "+00:00")
                )
                age = datetime.now(UTC) - last_heartbeat

                if age.total_seconds() > max_age_seconds:
                    await kv_store.delete(key)
                    print(f"Deleted expired service: {key}")
                    expired_count += 1

        return expired_count

    # Simulate some time passing
    print("Simulating expired service...")
    expired_service = ServiceInstance(
        service_name="old-service",
        instance_id="old-001",
        version="1.0.0",
        status="ACTIVE",
        last_heartbeat=(datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
    )
    await kv_store.put(f"service__{expired_service.instance_id}", expired_service.model_dump())

    # Run cleanup
    expired = await cleanup_expired_services()
    print(f"Cleaned up {expired} expired services")

    # Example 4: History expiration (automatic)
    print("\n=== Example 4: History Expiration ===")
    print("Stream-level TTL automatically removes old history entries")
    print("This keeps the stream size bounded without affecting current values")

    # Update a key multiple times
    for i in range(5):
        await kv_store.put("counter", {"value": i})
        await asyncio.sleep(0.1)

    # Check history
    history = await kv_store.history("counter", limit=10)
    print(f"Current history entries: {len(history)}")
    print("After 60 seconds, old history entries will be automatically purged")

    # Clean up
    await kv_store.disconnect()
    await adapter.disconnect()

    print("\n=== Summary ===")
    print("✓ Use stream-level TTL for history cleanup")
    print("✓ Implement heartbeat mechanism for service liveness")
    print("✓ Use client-side filtering for expiration logic")
    print("✓ Consider periodic cleanup tasks for stale entries")
    print("✗ Do NOT rely on per-message TTL (not supported)")


if __name__ == "__main__":
    asyncio.run(main())
