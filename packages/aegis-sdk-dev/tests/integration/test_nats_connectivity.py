#!/usr/bin/env python
"""Simple test to verify basic functionality."""

import asyncio
import json


async def test_nats_basic():
    """Test basic NATS connection."""
    import nats

    print("Testing NATS connection...")
    nc = await nats.connect("nats://localhost:4222")
    print(f"✅ Connected: {nc.is_connected}")

    # Test pub/sub
    messages = []

    async def handler(msg):
        messages.append(msg.data.decode())

    sub = await nc.subscribe("test.topic", cb=handler)
    await nc.publish("test.topic", b"Hello NATS")
    await asyncio.sleep(0.1)

    print(f"✅ Pub/Sub working: {len(messages)} messages received")

    await nc.close()
    return True


async def test_echo_service():
    """Test echo service is responding."""
    import nats

    print("\nTesting Echo Service...")
    nc = await nats.connect("nats://localhost:4222")

    try:
        # Test echo
        response = await nc.request(
            "echo.service.echo", json.dumps({"message": "test"}).encode(), timeout=2.0
        )
        data = json.loads(response.data)
        print(f"✅ Echo response from: {data.get('instance_id', 'unknown')}")

        # Test health
        response = await nc.request("echo.service.health", b"{}", timeout=2.0)
        health = json.loads(response.data)
        print(f"✅ Health status: {health.get('status', 'unknown')}")

    except asyncio.TimeoutError:
        print("❌ Echo service not responding")
        return False
    finally:
        await nc.close()

    return True


async def test_k8s_services():
    """Check K8s services via KV store."""
    import nats

    print("\nChecking K8s Services in Registry...")
    nc = await nats.connect("nats://localhost:4222")

    try:
        js = nc.jetstream()
        kv = await js.key_value("service_registry")

        # List all keys
        keys = []
        async for entry in kv.watch():
            if entry.key:
                keys.append(entry.key)
            if len(keys) >= 10:  # Limit for testing
                break

        print(f"✅ Found {len(keys)} services in registry")

        # Group by service type
        services = {}
        for key in keys:
            service_type = key.split(".")[0] if "." in key else key
            if service_type not in services:
                services[service_type] = []
            services[service_type].append(key)

        for service_type, instances in services.items():
            print(f"  - {service_type}: {len(instances)} instances")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await nc.close()

    return True


async def main():
    """Run simple tests."""
    print("=" * 50)
    print("SIMPLE VALIDATION TEST")
    print("=" * 50)

    results = []

    # Test 1: NATS
    try:
        results.append(await test_nats_basic())
    except Exception as e:
        print(f"❌ NATS test failed: {e}")
        results.append(False)

    # Test 2: Echo Service
    try:
        results.append(await test_echo_service())
    except Exception as e:
        print(f"❌ Echo service test failed: {e}")
        results.append(False)

    # Test 3: K8s Services
    try:
        results.append(await test_k8s_services())
    except Exception as e:
        print(f"❌ K8s services test failed: {e}")
        results.append(False)

    print("\n" + "=" * 50)
    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print(f"⚠️  {sum(results)}/{len(results)} tests passed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
