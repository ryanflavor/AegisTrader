#!/usr/bin/env python3
"""EchoService - Load-Balanced Service Pattern Example.

This example demonstrates the Load-Balanced Service Pattern using the base Service class.
Multiple instances can run simultaneously, and requests are automatically load-balanced
across all healthy instances by the SDK.

Usage:
    # Start multiple instances in different terminals:
    python echo_service.py --instance 1
    python echo_service.py --instance 2
    python echo_service.py --instance 3

    # Test with the client:
    python echo_client.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime

from aegis_sdk.developer import quick_setup

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class EchoService:
    """Example service demonstrating load-balanced RPC pattern."""

    def __init__(self, instance_num: int):
        """Initialize the echo service.

        Args:
            instance_num: Instance number for identification
        """
        self.instance_num = instance_num
        self.request_count = 0
        self.service = None
        self.shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the echo service."""
        logger.info(f"🚀 Starting EchoService instance #{self.instance_num}")

        # Create service with auto-configuration
        self.service = await quick_setup(
            service_name="echo-service",
            service_type="service",  # Use base Service for load balancing
            debug=False,  # We're handling logging ourselves
        )

        # Register RPC handlers
        @self.service.rpc("echo")
        async def handle_echo(params: dict) -> dict:
            """Echo back the message with instance info."""
            self.request_count += 1
            message = params.get("message", "")

            response = {
                "echo": message,
                "instance": self.instance_num,
                "request_count": self.request_count,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            logger.info(
                f"📨 Instance #{self.instance_num} handled echo request "
                f"#{self.request_count}: '{message}'"
            )

            return response

        @self.service.rpc("status")
        async def handle_status(params: dict) -> dict:
            """Return service status."""
            return {
                "instance": self.instance_num,
                "status": "healthy",
                "request_count": self.request_count,
                "uptime_seconds": (
                    self.service.get_uptime_seconds()
                    if hasattr(self.service, "get_uptime_seconds")
                    else 0
                ),
            }

        @self.service.rpc("delay_echo")
        async def handle_delay_echo(params: dict) -> dict:
            """Echo with configurable delay to simulate processing."""
            delay = params.get("delay", 1.0)
            message = params.get("message", "")

            logger.info(
                f"⏳ Instance #{self.instance_num} processing delayed echo (delay: {delay}s)"
            )

            await asyncio.sleep(delay)

            self.request_count += 1
            return {
                "echo": message,
                "instance": self.instance_num,
                "delay": delay,
                "request_count": self.request_count,
            }

        # Note: Event handling would be registered here if needed
        # For this demo, we focus on RPC functionality

        # Start the service
        await self.service.start()

        logger.info(
            f"✅ EchoService instance #{self.instance_num} started successfully\n"
            f"   Service: echo-service\n"
            f"   Instance ID: {self.service.instance_id}\n"
            f"   Pattern: Load-Balanced (multiple active instances)\n"
            f"   RPC Methods: echo, status, delay_echo"
        )

    async def stop(self) -> None:
        """Stop the echo service."""
        if self.service:
            logger.info(f"🛑 Stopping EchoService instance #{self.instance_num}")
            await self.service.stop()
            logger.info(
                f"📊 Final stats for instance #{self.instance_num}: "
                f"Handled {self.request_count} requests"
            )

    async def run(self) -> None:
        """Run the service until shutdown signal."""
        await self.start()

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        await self.stop()

    def signal_handler(self, sig, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"📡 Received signal {sig}, initiating graceful shutdown...")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EchoService - Load-Balanced Service Pattern Example"
    )
    parser.add_argument(
        "--instance",
        type=int,
        default=1,
        help="Instance number for identification (default: 1)",
    )

    args = parser.parse_args()

    # Create and run service
    service = EchoService(args.instance)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, service.signal_handler)
    signal.signal(signal.SIGTERM, service.signal_handler)

    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
