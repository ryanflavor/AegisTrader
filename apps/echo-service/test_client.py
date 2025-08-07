#!/usr/bin/env python3
"""Simple test client for echo-service."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aegis_sdk.developer import quick_setup


async def main():
    """Test echo-service endpoints."""
    print("🚀 Echo Service Test Client")
    print("=" * 40)

    # Create client service
    service = await quick_setup(
        service_name="test-client",
        service_type="service",
        debug=False,
    )

    try:
        # Start the service to establish connection
        await service.start()
        print("✅ Connected to NATS")

        # Test 1: Ping
        print("\n1️⃣ Testing ping...")
        from aegis_sdk.domain.models import RPCRequest

        request = RPCRequest(target="echo-service", method="ping", params={}, timeout=5.0)
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 2: Simple echo
        print("\n2️⃣ Testing echo...")
        request = RPCRequest(
            target="echo-service",
            method="echo",
            params={"message": "Hello from test client!", "mode": "simple"},
            timeout=5.0,
        )
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 3: Transform echo
        print("\n3️⃣ Testing transform mode...")
        request = RPCRequest(
            target="echo-service",
            method="echo",
            params={"message": "Hello World", "mode": "transform"},
            timeout=5.0,
        )
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 4: Delayed echo
        print("\n4️⃣ Testing delayed mode...")
        request = RPCRequest(
            target="echo-service",
            method="echo",
            params={"message": "wait for me", "mode": "delayed"},
            timeout=5.0,
        )
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 5: Batch echo
        print("\n5️⃣ Testing batch echo...")
        request = RPCRequest(
            target="echo-service",
            method="batch_echo",
            params={"messages": ["First", "Second", "Third"]},
            timeout=5.0,
        )
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 6: Health check
        print("\n6️⃣ Testing health...")
        request = RPCRequest(target="echo-service", method="health", params={}, timeout=5.0)
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        # Test 7: Metrics
        print("\n7️⃣ Testing metrics...")
        request = RPCRequest(target="echo-service", method="metrics", params={}, timeout=5.0)
        response = await service._bus.call_rpc(request)
        if response.error:
            print(f"❌ Error: {response.error}")
        else:
            print(f"✅ Response: {json.dumps(response.result, indent=2)}")

        print("\n" + "=" * 40)
        print("✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await service.stop()
        print("\n👋 Client disconnected")


if __name__ == "__main__":
    asyncio.run(main())
