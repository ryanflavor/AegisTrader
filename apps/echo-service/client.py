#!/usr/bin/env python3
"""Echo Service Client - Test client for echo-service RPC endpoints.

This client demonstrates how to interact with the echo-service
using the AegisSDK RPC capabilities.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class EchoServiceClient:
    """Client for testing echo-service RPC endpoints."""

    def __init__(self):
        """Initialize the client."""
        self.deps = None
        self.client = None

    async def setup(self) -> None:
        """Setup the client connection."""
        print("🔌 Connecting to NATS...")

        # Import quick_setup here to avoid import issues
        from aegis_sdk.developer import quick_setup

        # Create a temporary service for RPC client
        self.service = await quick_setup(
            service_name="echo-client",
            service_type="service",
            debug=False,
        )

        # Get the message bus from the service
        self.client = self.service._bus  # Access internal message bus for RPC
        print("✅ Connected to NATS")

    async def test_echo(self, message: str) -> dict[str, Any]:
        """Test the echo endpoint."""
        print(f"\n📤 Testing echo with message: '{message}'")

        request = {"message": message, "mode": "simple"}

        try:
            response = await self.client.request("echo-service.echo", request, timeout=5.0)
            print(f"📥 Response: {json.dumps(response, indent=2)}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_batch_echo(self, messages: list) -> dict[str, Any]:
        """Test the batch_echo endpoint."""
        print(f"\n📤 Testing batch_echo with {len(messages)} messages")

        request = {"messages": messages}

        try:
            response = await self.client.request("echo-service.batch_echo", request, timeout=5.0)
            print(f"📥 Response: {json.dumps(response, indent=2)}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_ping(self) -> dict[str, Any]:
        """Test the ping endpoint."""
        print("\n🏓 Testing ping...")

        try:
            response = await self.client.request("echo-service.ping", {}, timeout=2.0)
            print(f"📥 Response: {json.dumps(response, indent=2)}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_health(self) -> dict[str, Any]:
        """Test the health endpoint."""
        print("\n💊 Testing health check...")

        try:
            response = await self.client.request("echo-service.health", {}, timeout=2.0)
            print(f"📥 Response: {json.dumps(response, indent=2)}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_metrics(self) -> dict[str, Any]:
        """Test the metrics endpoint."""
        print("\n📊 Testing metrics...")

        try:
            response = await self.client.request("echo-service.metrics", {}, timeout=2.0)
            print(f"📥 Response: {json.dumps(response, indent=2)}")
            return response
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_all_modes(self) -> None:
        """Test echo with all available modes."""
        print("\n🎭 Testing all echo modes...")

        modes = ["simple", "reverse", "uppercase", "timestamp", "json"]
        test_message = "Hello AegisSDK!"

        for mode in modes:
            print(f"\n--- Mode: {mode} ---")
            request = {"message": test_message, "mode": mode}

            try:
                response = await self.client.request("echo-service.echo", request, timeout=5.0)
                print(f"📥 Response: {json.dumps(response, indent=2)}")
            except Exception as e:
                print(f"❌ Error: {e}")

    async def performance_test(self, num_requests: int = 100) -> None:
        """Run a performance test."""
        print(f"\n⚡ Running performance test with {num_requests} requests...")

        start_time = datetime.now()
        success_count = 0
        error_count = 0

        tasks = []
        for i in range(num_requests):
            request = {"message": f"Performance test message {i}", "mode": "simple"}
            task = self.client.request("echo-service.echo", request, timeout=10.0)
            tasks.append(task)

        # Run all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                error_count += 1
            else:
                success_count += 1

        elapsed = (datetime.now() - start_time).total_seconds()
        rps = num_requests / elapsed if elapsed > 0 else 0

        print("\n📈 Performance Results:")
        print(f"  Total Requests: {num_requests}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {error_count}")
        print(f"  Time Elapsed: {elapsed:.2f}s")
        print(f"  Requests/Second: {rps:.2f}")

    async def cleanup(self) -> None:
        """Cleanup client resources."""
        if hasattr(self, "service") and self.service:
            await self.service.stop()
            print("\n🧹 Client cleaned up")


async def main():
    """Main function to run the client tests."""
    print("=" * 60)
    print("Echo Service Client Test Suite")
    print("=" * 60)

    client = EchoServiceClient()

    try:
        # Setup client
        await client.setup()

        # Run basic tests
        print("\n" + "=" * 60)
        print("BASIC TESTS")
        print("=" * 60)

        # Test ping
        await client.test_ping()

        # Test health
        await client.test_health()

        # Test simple echo
        await client.test_echo("Hello from client!")

        # Test batch echo
        await client.test_batch_echo(["Message 1", "Message 2", "Message 3"])

        # Test metrics
        await client.test_metrics()

        # Test all modes
        print("\n" + "=" * 60)
        print("MODE TESTS")
        print("=" * 60)
        await client.test_all_modes()

        # Run performance test
        print("\n" + "=" * 60)
        print("PERFORMANCE TEST")
        print("=" * 60)

        # Ask user if they want to run performance test
        user_input = input("\n🤔 Run performance test? (y/n): ")
        if user_input.lower() == "y":
            num_requests = input("How many requests? (default 100): ")
            num_requests = int(num_requests) if num_requests else 100
            await client.performance_test(num_requests)

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        await client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Client interrupted by user")
