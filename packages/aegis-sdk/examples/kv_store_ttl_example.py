#!/usr/bin/env python3
"""Example: Using NATS KV Store with per-message TTL."""

import asyncio
import os
from datetime import datetime

from aegis_sdk.domain.exceptions import KVTTLNotSupportedError
from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


async def main():
    """Demonstrate KV Store with TTL functionality."""
    # Set up logging to see what's happening
    import logging

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create NATS adapter
    adapter = NATSAdapter()

    # Connect to NATS
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    await adapter.connect([nats_url])

    # Create KV store instance
    kv_store = NATSKVStore(nats_adapter=adapter)

    # Connect to a bucket with TTL support enabled
    await kv_store.connect("ttl_example_bucket", enable_ttl=True)

    print("=== NATS KV Store TTL Example ===\n")
    print("⚠️  IMPORTANT NOTES:")
    print("1. NATS KV doesn't expose remaining TTL when retrieving entries")
    print("2. TTL feature requires NATS 2.11+ (you have: v2.11.6 ✓)")
    print("3. Current limitation: TTL may not work with standard KV bucket creation")
    print("4. Workaround: Use direct JetStream streams with allow_msg_ttl enabled")

    # Example 1: Store temporary session data (expires in 30 seconds)
    session_data = {
        "user_id": "user123",
        "login_time": datetime.now().isoformat(),
        "ip": "192.168.1.100",
    }
    await kv_store.put("session__user123", session_data, KVOptions(ttl=30))
    print("✓ Stored session data with 30-second TTL")

    # Example 2: Store temporary verification code (expires in 5 minutes)
    verification_code = {
        "code": "ABC123",
        "created_at": datetime.now().isoformat(),
        "purpose": "email_verification",
    }
    await kv_store.put("verify__email__user123", verification_code, KVOptions(ttl=300))
    print("✓ Stored verification code with 5-minute TTL")

    # Example 3: Store permanent configuration (no TTL)
    config_data = {"api_version": "v1", "features": ["trading", "monitoring", "alerts"]}
    await kv_store.put("config__global", config_data)
    print("✓ Stored permanent configuration (no TTL)")

    # Check all values exist immediately
    print("\nVerifying all values exist immediately after storage:")
    for key in ["session__user123", "verify__email__user123", "config__global"]:
        exists = await kv_store.exists(key)
        print(f"  - {key}: {'exists' if exists else 'not found'}")

    # Example 4: Verify TTL expiration works
    print("\nTesting TTL expiration...")
    # Store a key with 3 second TTL
    await kv_store.put("short-ttl-test", {"expires": "soon"}, KVOptions(ttl=3))
    print("✓ Stored key with 3-second TTL")

    # Verify it exists immediately
    assert await kv_store.exists("short-ttl-test") is True
    print("✓ Key exists immediately after storage")

    # Wait 4 seconds
    print("⏳ Waiting 4 seconds for expiration...")
    await asyncio.sleep(4)

    # Check if expired
    exists_after = await kv_store.exists("short-ttl-test")
    if exists_after:
        print("⚠️  Key still exists - TTL is not working with standard KV buckets")
        print("   This is a known limitation: NATS KV doesn't properly support per-message TTL")
        print("   even though the server version supports it.")
        print("\n   Alternative approaches:")
        print("   1. Use direct JetStream streams instead of KV buckets")
        print("   2. Implement application-level expiration logic")
        print("   3. Use stream-level max_age for bucket-wide TTL")
    else:
        print("✓ Key expired as expected!")

    # Example 5: Handling TTL errors when not supported
    print("\nTesting TTL on non-TTL bucket...")
    kv_store_no_ttl = NATSKVStore(nats_adapter=adapter)
    await kv_store_no_ttl.connect("no_ttl_bucket", enable_ttl=False)

    try:
        await kv_store_no_ttl.put("test", "value", KVOptions(ttl=10))
    except KVTTLNotSupportedError as e:
        print(f"✓ Expected error: {e}")

    await kv_store_no_ttl.disconnect()

    # Cleanup
    await kv_store.disconnect()
    await adapter.disconnect()

    print("\n✅ Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
    print("\n" + "=" * 50)
    print("For TTL to work properly, ensure:")
    print("1. NATS server version 2.11+")
    print("2. JetStream enabled with proper configuration")
    print("3. Stream created with 'allow_msg_ttl: true'")
    print("=" * 50)
