#!/usr/bin/env python3
"""EchoSingleService - Single-Active Pattern Example with Automatic Failover.

This example demonstrates the Single-Active Pattern using the SingleActiveService class.
Only one instance (the leader) processes requests at a time. If the leader fails,
another instance automatically takes over within seconds (sub-2 second failover).

The client must implement retry logic to handle NOT_ACTIVE errors during failover.

Usage:
    # Start multiple instances (only one will be active):
    python echo_single_service.py --instance 1
    python echo_single_service.py --instance 2
    python echo_single_service.py --instance 3

    # Test failover by stopping the active instance (Ctrl+C)
    # Watch another instance automatically take over!
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from datetime import UTC, datetime

from aegis_sdk.developer import quick_setup
from aegis_sdk.domain.value_objects import FailoverPolicy

# Configure logging to see failover behavior
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class EchoSingleService:
    """Example service demonstrating single-active pattern with failover."""

    def __init__(self, instance_num: int):
        """Initialize the single-active echo service.

        Args:
            instance_num: Instance number for identification
        """
        self.instance_num = instance_num
        self.request_count = 0
        self.service = None
        self.shutdown_event = asyncio.Event()
        self.is_leader = False
        self.became_leader_at = None

    async def start(self) -> None:
        """Start the single-active echo service."""
        logger.info(f"🚀 Starting EchoSingleService instance #{self.instance_num}")

        # Create single-active service with aggressive failover (<2 seconds)
        self.service = await quick_setup(
            service_name="echo-single-service",
            service_type="single-active",
            failover_policy=FailoverPolicy.aggressive(),  # Sub-2 second failover
            debug=False,
        )

        # Register RPC handlers (only leader will process these)
        @self.service.rpc("echo")
        async def handle_echo(params: dict) -> dict:
            """Echo back the message (only when leader)."""
            self.request_count += 1
            message = params.get("message", "")

            response = {
                "echo": message,
                "leader_instance": self.instance_num,
                "request_count": self.request_count,
                "leader_since": (
                    self.became_leader_at.isoformat() if self.became_leader_at else None
                ),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            logger.info(
                f"👑 Leader instance #{self.instance_num} handled echo request "
                f"#{self.request_count}: '{message}'"
            )

            return response

        @self.service.rpc("status")
        async def handle_status(params: dict) -> dict:
            """Return service status (only when leader)."""
            return {
                "leader_instance": self.instance_num,
                "is_leader": self.is_leader,
                "status": "active" if self.is_leader else "standby",
                "request_count": self.request_count,
                "leader_since": (
                    self.became_leader_at.isoformat() if self.became_leader_at else None
                ),
            }

        @self.service.rpc("simulate_failure")
        async def handle_simulate_failure(params: dict) -> dict:
            """Simulate a failure to trigger failover."""
            delay = params.get("delay", 5)
            logger.warning(
                f"💥 Simulating failure on leader instance #{self.instance_num} "
                f"in {delay} seconds..."
            )

            async def delayed_shutdown():
                await asyncio.sleep(delay)
                logger.error(f"💀 Instance #{self.instance_num} simulating crash!")
                self.shutdown_event.set()

            asyncio.create_task(delayed_shutdown())

            return {
                "message": f"Leader instance #{self.instance_num} will fail in {delay} seconds",
                "watch_for_failover": True,
            }

        # Register leadership change callbacks
        @self.service.on_became_leader
        async def became_leader():
            """Called when this instance becomes the leader."""
            self.is_leader = True
            self.became_leader_at = datetime.now(UTC)
            logger.warning(
                f"🎉 Instance #{self.instance_num} BECAME THE LEADER! Now processing all requests."
            )

        @self.service.on_lost_leadership
        async def lost_leadership():
            """Called when this instance loses leadership."""
            self.is_leader = False
            logger.warning(f"😔 Instance #{self.instance_num} LOST LEADERSHIP. Standing by...")

        # Start the service
        await self.service.start()

        # Check initial leadership status
        await asyncio.sleep(1)  # Give election time to complete

        status = "LEADER 👑" if self.is_leader else "STANDBY"
        logger.info(
            f"✅ EchoSingleService instance #{self.instance_num} started successfully\n"
            f"   Service: echo-single-service\n"
            f"   Instance ID: {self.service.instance_id}\n"
            f"   Pattern: Single-Active (only leader processes requests)\n"
            f"   Status: {status}\n"
            f"   Failover Policy: Aggressive (<2 second failover)\n"
            f"   RPC Methods: echo, status, simulate_failure"
        )

    async def stop(self) -> None:
        """Stop the single-active echo service."""
        if self.service:
            logger.info(f"🛑 Stopping EchoSingleService instance #{self.instance_num}")

            if self.is_leader:
                logger.warning(
                    f"⚠️  Leader instance #{self.instance_num} shutting down - FAILOVER WILL OCCUR!"
                )

            await self.service.stop()

            logger.info(
                f"📊 Final stats for instance #{self.instance_num}: "
                f"Handled {self.request_count} requests as leader"
            )

    async def run(self) -> None:
        """Run the service until shutdown signal."""
        await self.start()

        # Periodic status logging
        async def log_status():
            while not self.shutdown_event.is_set():
                await asyncio.sleep(10)
                if not self.shutdown_event.is_set():
                    status = "LEADER 👑" if self.is_leader else "STANDBY"
                    logger.info(f"💓 Instance #{self.instance_num} heartbeat - Status: {status}")

        status_task = asyncio.create_task(log_status())

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        status_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await status_task

        await self.stop()

    def signal_handler(self, sig, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"📡 Received signal {sig}, initiating graceful shutdown...")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EchoSingleService - Single-Active Pattern with Automatic Failover"
    )
    parser.add_argument(
        "--instance",
        type=int,
        default=1,
        help="Instance number for identification (default: 1)",
    )

    args = parser.parse_args()

    logger.info(
        "=" * 60 + "\n"
        "🔥 SINGLE-ACTIVE PATTERN DEMONSTRATION\n"
        "=" * 60 + "\n"
        "This example shows automatic leader election and failover.\n"
        "Start multiple instances - only ONE will be the leader.\n"
        "Stop the leader (Ctrl+C) to see automatic failover!\n"
        "=" * 60
    )

    # Create and run service
    service = EchoSingleService(args.instance)

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
