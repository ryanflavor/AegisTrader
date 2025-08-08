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
        self.adapter = None

    async def setup(self) -> None:
        """Setup the client connection."""
        print("🔌 Connecting to NATS...")

        from aegis_sdk.domain.models import RPCRequest
        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter, NATSConnectionConfig

        # Create NATS adapter configuration
        config = NATSConnectionConfig(service_name="echo-client", servers=["nats://localhost:4222"])

        # Create and connect adapter
        self.adapter = NATSAdapter(config=config)
        await self.adapter.connect()

        # Store RPCRequest class for later use
        self.RPCRequest = RPCRequest

        print("✅ Connected to NATS")

    async def test_echo(self, message: str) -> dict[str, Any]:
        """Test the echo endpoint."""
        print(f"\n📤 Testing echo with message: '{message}'")

        request = self.RPCRequest(
            method="echo", params={"message": message, "mode": "simple"}, target="echo-service"
        )

        try:
            response = await self.adapter.call_rpc(request)
            result = response.result if response.success else {"error": response.error}
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_batch_echo(self, messages: list) -> dict[str, Any]:
        """Test the batch_echo endpoint."""
        print(f"\n📤 Testing batch_echo with {len(messages)} messages")

        request = self.RPCRequest(
            method="batch_echo", params={"messages": messages}, target="echo-service"
        )

        try:
            response = await self.adapter.call_rpc(request)
            result = response.result if response.success else {"error": response.error}
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_ping(self) -> dict[str, Any]:
        """Test the ping endpoint."""
        print("\n🏓 Testing ping...")

        request = self.RPCRequest(method="ping", params={}, target="echo-service")

        try:
            response = await self.adapter.call_rpc(request)
            result = response.result if response.success else {"error": response.error}
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_health(self) -> dict[str, Any]:
        """Test the health endpoint."""
        print("\n💊 Testing health check...")

        request = self.RPCRequest(method="health", params={}, target="echo-service")

        try:
            response = await self.adapter.call_rpc(request)
            result = response.result if response.success else {"error": response.error}
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_metrics(self) -> dict[str, Any]:
        """Test the metrics endpoint."""
        print("\n📊 Testing metrics...")

        request = self.RPCRequest(method="metrics", params={}, target="echo-service")

        try:
            response = await self.adapter.call_rpc(request)
            result = response.result if response.success else {"error": response.error}
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"error": str(e)}

    async def test_all_modes(self) -> None:
        """Test echo with all available modes."""
        print("\n🎭 Testing all echo modes...")

        # Use the actual modes supported by the server
        modes = ["simple", "delayed", "transform", "batch"]
        test_message = "Hello AegisSDK!"

        for mode in modes:
            print(f"\n--- Mode: {mode} ---")
            request = self.RPCRequest(
                method="echo", params={"message": test_message, "mode": mode}, target="echo-service"
            )

            try:
                response = await self.adapter.call_rpc(request)
                result = response.result if response.success else {"error": response.error}
                print(f"📥 Response: {json.dumps(result, indent=2)}")
            except Exception as e:
                print(f"❌ Error: {e}")

    async def performance_test(self, num_requests: int = 100) -> None:
        """Run a performance test."""
        print(f"\n⚡ Running performance test with {num_requests} requests...")

        # Limit concurrent requests to avoid overwhelming NATS
        max_concurrent = 50  # Reasonable limit for concurrent requests

        start_time = datetime.now()
        success_count = 0
        error_count = 0

        # Process requests in batches
        batch_size = min(max_concurrent, num_requests)
        total_processed = 0

        while total_processed < num_requests:
            # Create batch of requests
            batch_tasks = []
            batch_end = min(total_processed + batch_size, num_requests)

            for i in range(total_processed, batch_end):
                request = self.RPCRequest(
                    method="echo",
                    params={"message": f"Performance test message {i}", "mode": "simple"},
                    target="echo-service",
                )
                task = self.adapter.call_rpc(request)
                batch_tasks.append(task)

            # Run batch concurrently
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Count results
            for result in results:
                if isinstance(result, Exception):
                    error_count += 1
                    print(f"  ❌ Request failed: {str(result)[:50]}")
                elif hasattr(result, "success") and result.success:
                    success_count += 1
                else:
                    error_count += 1

            total_processed = batch_end

            # Show progress for large tests
            if num_requests > 100 and total_processed % 100 == 0:
                print(f"  📊 Progress: {total_processed}/{num_requests} requests processed...")

            # Small delay between batches to avoid overwhelming the connection
            if total_processed < num_requests:
                await asyncio.sleep(0.01)

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
        if self.adapter:
            await self.adapter.disconnect()
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
        try:
            user_input = input("\n🤔 Run performance test? (y/n): ")
            if user_input.lower() == "y":
                num_requests = input("How many requests? (default 100): ")
                num_requests = int(num_requests) if num_requests else 100
                await client.performance_test(num_requests)
        except EOFError:
            # Handle non-interactive mode
            print("Skipping performance test (non-interactive mode)")

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Client interrupted by user")
