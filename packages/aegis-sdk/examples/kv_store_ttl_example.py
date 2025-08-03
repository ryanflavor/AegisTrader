#!/usr/bin/env python3
"""Example: Using NATS KV Store with per-message TTL."""

import asyncio
import os
from datetime import datetime

from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


async def main():
    """Demonstrate KV Store with TTL functionality."""
    # Create NATS adapter
    adapter = NATSAdapter()

    # Connect to NATS
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    await adapter.connect([nats_url])

    # Create KV store instance
    kv_store = NATSKVStore(nats_adapter=adapter)

    # Connect to a bucket with TTL support enabled
    await kv_store.connect("ttl-example-bucket", enable_ttl=True)

    print("=== NATS KV Store TTL Example ===\n")

    # Example 1: Store temporary session data (expires in 30 seconds)
    session_data = {
        "user_id": "user123",
        "login_time": datetime.now().isoformat(),
        "ip": "192.168.1.100",
    }
    await kv_store.put("session:user123", session_data, KVOptions(ttl=30))
    print("✓ Stored session data with 30-second TTL")

    # Example 2: Store temporary verification code (expires in 5 minutes)
    verification_code = {
        "code": "ABC123",
        "created_at": datetime.now().isoformat(),
        "purpose": "email_verification",
    }
    await kv_store.put("verify:email:user123", verification_code, KVOptions(ttl=300))
    print("✓ Stored verification code with 5-minute TTL")

    # Example 3: Store permanent configuration (no TTL)
    config_data = {"api_version": "v1", "features": ["trading", "monitoring", "alerts"]}
    await kv_store.put("config:global", config_data)
    print("✓ Stored permanent configuration (no TTL)")

    # Check all values
    print("\nChecking stored values:")
    for key in ["session:user123", "verify:email:user123", "config:global"]:
        entry = await kv_store.get(key)
        if entry:
            ttl_info = (
                f" (expires in ~{entry.ttl}s)"
                if hasattr(entry, "ttl") and entry.ttl
                else " (permanent)"
            )
            print(f"  - {key}: exists{ttl_info}")

    # Example 4: Update TTL by overwriting with new value
    print("\nExtending session TTL to 60 seconds...")
    session_data["extended"] = True
    await kv_store.put("session:user123", session_data, KVOptions(ttl=60))
    print("✓ Session TTL extended")

    # Example 5: Handling TTL errors when not supported
    print("\nTesting TTL on non-TTL bucket...")
    kv_store_no_ttl = NATSKVStore(nats_adapter=adapter)
    await kv_store_no_ttl.connect("no-ttl-bucket", enable_ttl=False)

    try:
        await kv_store_no_ttl.put("test", "value", KVOptions(ttl=10))
    except ValueError as e:
        print(f"✓ Expected error: {e}")

    await kv_store_no_ttl.disconnect()

    # Cleanup
    await kv_store.disconnect()
    await adapter.disconnect()

    print("\n✅ Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
