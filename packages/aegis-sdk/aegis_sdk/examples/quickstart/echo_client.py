#!/usr/bin/env python3
"""Echo Client - Test client for EchoService and EchoSingleService examples.

This client demonstrates how to call services and handle different patterns:
- Load-balanced calls to multiple instances (EchoService)
- Single-active calls with retry on NOT_ACTIVE errors (EchoSingleService)

Usage:
    # Basic echo test
    python echo_client.py

    # Test specific service
    python echo_client.py --service echo-service
    python echo_client.py --service echo-single-service

    # Send multiple requests
    python echo_client.py --count 10 --delay 1

    # Test failover (for single-active service)
    python echo_client.py --service echo-single-service --trigger-failure
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from aegis_sdk.developer import create_external_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class EchoClient:
    """Client for testing echo services."""

    def __init__(self):
        """Initialize the echo client."""
        self.provider = None
        self.message_bus = None

    async def connect(self) -> None:
        """Connect to NATS and initialize client."""
        logger.info("🔌 Connecting to NATS...")

        # Create external client (like monitor-api pattern)
        self.provider = await create_external_client()
        self.message_bus = self.provider.message_bus()

        logger.info("✅ Connected to NATS successfully")

    async def call_with_retry(
        self,
        service_name: str,
        method: str,
        params: dict,
        max_retries: int = 5,
        retry_delay: float = 0.5,
    ) -> dict:
        """Call a service method with retry logic for NOT_ACTIVE errors.

        This is essential for single-active services during failover.

        Args:
            service_name: Name of the service
            method: RPC method to call
            params: Parameters for the method
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds

        Returns:
            Response from the service
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.message_bus.rpc_call(
                    service_name=service_name,
                    method=method,
                    params=params,
                    timeout=5.0,
                )
                return response

            except Exception as e:
                error_str = str(e)

                # Check if it's a NOT_ACTIVE error (happens during failover)
                if (
                    "NOT_ACTIVE" in error_str or "not the active instance" in error_str
                ) and attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️  Got NOT_ACTIVE error, retrying in {retry_delay}s... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                # Other errors, raise immediately
                last_error = e
                break

        if last_error:
            raise last_error

        raise Exception(f"Failed after {max_retries} retries")

    async def test_echo_service(self, message: str = "Hello, World!") -> None:
        """Test load-balanced echo service."""
        logger.info("\n" + "=" * 60)
        logger.info("📢 Testing Load-Balanced EchoService")
        logger.info("=" * 60)

        try:
            # Call echo method (will be load-balanced across instances)
            response = await self.message_bus.rpc_call(
                service_name="echo-service",
                method="echo",
                params={"message": message},
                timeout=5.0,
            )

            logger.info(f"✅ Response from instance #{response.get('instance', '?')}:")
            logger.info(f"   Echo: {response.get('echo', '')}")
            logger.info(f"   Request count: {response.get('request_count', 0)}")
            logger.info(f"   Timestamp: {response.get('timestamp', '')}")

        except Exception as e:
            logger.error(f"❌ Failed to call echo-service: {e}")

    async def test_single_active_service(self, message: str = "Hello, Leader!") -> None:
        """Test single-active echo service with retry."""
        logger.info("\n" + "=" * 60)
        logger.info("👑 Testing Single-Active EchoSingleService")
        logger.info("=" * 60)

        try:
            # Call with retry logic (essential for single-active pattern)
            response = await self.call_with_retry(
                service_name="echo-single-service",
                method="echo",
                params={"message": message},
            )

            logger.info(
                f"✅ Response from LEADER instance #{response.get('leader_instance', '?')}:"
            )
            logger.info(f"   Echo: {response.get('echo', '')}")
            logger.info(f"   Request count: {response.get('request_count', 0)}")
            logger.info(f"   Leader since: {response.get('leader_since', 'Unknown')}")

        except Exception as e:
            logger.error(f"❌ Failed to call echo-single-service: {e}")

    async def test_service_discovery(self) -> None:
        """Discover and display all registered services."""
        logger.info("\n" + "=" * 60)
        logger.info("🔍 Service Discovery")
        logger.info("=" * 60)

        try:
            discovery = self.provider.service_discovery()

            # Discover echo-service instances
            echo_instances = await discovery.discover("echo-service")
            logger.info(f"\n📦 echo-service instances: {len(echo_instances)}")
            for instance in echo_instances:
                logger.info(f"   - {instance.instance_id} (status: {instance.status})")

            # Discover echo-single-service instances
            single_instances = await discovery.discover("echo-single-service")
            logger.info(f"\n📦 echo-single-service instances: {len(single_instances)}")
            for instance in single_instances:
                leader_marker = " 👑" if instance.metadata.get("is_leader") else ""
                logger.info(
                    f"   - {instance.instance_id} (status: {instance.status}){leader_marker}"
                )

        except Exception as e:
            logger.error(f"❌ Service discovery failed: {e}")

    async def test_failover(self) -> None:
        """Trigger failover test on single-active service."""
        logger.info("\n" + "=" * 60)
        logger.info("💥 Triggering Failover Test")
        logger.info("=" * 60)

        try:
            # Trigger simulated failure
            response = await self.call_with_retry(
                service_name="echo-single-service",
                method="simulate_failure",
                params={"delay": 3},
            )

            logger.info(f"⚠️  {response.get('message', 'Failover triggered')}")
            logger.info("⏳ Waiting for failover to occur...")

            # Wait for failure to happen
            await asyncio.sleep(5)

            # Try calling again - should hit new leader
            logger.info("🔄 Testing service after failover...")
            response = await self.call_with_retry(
                service_name="echo-single-service",
                method="status",
                params={},
            )

            logger.info(f"✅ New leader is instance #{response.get('leader_instance', '?')}")

        except Exception as e:
            logger.error(f"❌ Failover test failed: {e}")

    async def run_continuous_test(self, service: str, count: int, delay: float) -> None:
        """Run continuous tests against a service."""
        logger.info(f"\n🔄 Running {count} requests to {service} with {delay}s delay")

        for i in range(count):
            message = f"Test message #{i + 1}"

            if service == "echo-service":
                await self.test_echo_service(message)
            elif service == "echo-single-service":
                await self.test_single_active_service(message)

            if i < count - 1:
                await asyncio.sleep(delay)

        logger.info(f"\n✅ Completed {count} requests")

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self.message_bus:
            await self.message_bus.disconnect()
            logger.info("🔌 Disconnected from NATS")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Echo Client - Test client for echo services")
    parser.add_argument(
        "--service",
        choices=["echo-service", "echo-single-service", "both"],
        default="both",
        help="Which service to test (default: both)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of requests to send (default: 1)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--trigger-failure",
        action="store_true",
        help="Trigger failover test for single-active service",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Show service discovery information",
    )

    args = parser.parse_args()

    # Create and connect client
    client = EchoClient()

    try:
        await client.connect()

        # Run service discovery if requested
        if args.discover:
            await client.test_service_discovery()

        # Run failover test if requested
        if args.trigger_failure:
            await client.test_failover()
            return

        # Run tests based on service selection
        if args.count > 1:
            await client.run_continuous_test(args.service, args.count, args.delay)
        else:
            if args.service == "both":
                await client.test_echo_service()
                await client.test_single_active_service()
            elif args.service == "echo-service":
                await client.test_echo_service()
            elif args.service == "echo-single-service":
                await client.test_single_active_service()

        # Show discovery info at the end
        if args.service == "both":
            await client.test_service_discovery()

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Client error: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
