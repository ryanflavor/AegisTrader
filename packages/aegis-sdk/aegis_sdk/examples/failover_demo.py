#!/usr/bin/env python3
"""Demonstration of automatic failover with sub-2-second recovery.

This example shows how the AegisSDK automatic failover system works:
1. Multiple instances compete for leadership
2. Only one instance becomes active (leader)
3. When the leader fails, a standby takes over within 2 seconds
4. The system prevents split-brain scenarios
5. Comprehensive observability through logging and metrics

Usage:
    python failover_demo.py [--instances N] [--policy POLICY] [--failure-after SECONDS]

    Options:
        --instances N: Number of instances to run (default: 3)
        --policy POLICY: Failover policy - aggressive/balanced/conservative (default: aggressive)
        --failure-after SECONDS: Simulate failure after N seconds (default: 15)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys
import time
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy
from aegis_sdk.infrastructure.application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultUseCaseFactory,
)
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Register default dependencies
bootstrap_defaults()


class FailoverDemoService:
    """Demo service that showcases automatic failover capabilities."""

    def __init__(
        self,
        instance_id: str,
        nats_urls: list[str] | None = None,
        failover_policy: str = "aggressive",
    ):
        """Initialize the demo service.

        Args:
            instance_id: Unique identifier for this instance
            nats_urls: NATS server URLs (defaults to localhost)
            failover_policy: Failover policy ("aggressive", "balanced", or "conservative")
        """
        self.instance_id = instance_id
        self.nats_urls = nats_urls or ["nats://localhost:4222"]
        self.service_name = "failover-demo"
        self.group_id = "demo-group"

        # Select failover policy
        if failover_policy == "aggressive":
            self.failover_policy = FailoverPolicy.aggressive()
        elif failover_policy == "conservative":
            self.failover_policy = FailoverPolicy.conservative()
        else:
            self.failover_policy = FailoverPolicy.balanced()

        # Initialize components
        self.logger = SimpleLogger(f"demo.{instance_id}")
        self.nats_adapter: NATSAdapter | None = None
        self.service_registry: KVServiceRegistry | None = None
        self.service_discovery: BasicServiceDiscovery | None = None
        self.single_active_service: SingleActiveService | None = None

        # State tracking
        self.is_active = False
        self.status_changes: list[dict[str, Any]] = []
        self.start_time: datetime | None = None
        self.work_counter = 0
        self.running = False
        self.status_check_task: asyncio.Task[None] | None = None
        self.work_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the demo service with automatic failover."""
        self.start_time = datetime.now(UTC)
        self.running = True

        print(f"\n{'=' * 60}")
        print(f"Starting Instance: {self.instance_id}")
        print(f"Failover Policy: {self.failover_policy.mode}")
        print(f"Detection Threshold: {self.failover_policy.detection_threshold.seconds}s")
        print(f"Election Delay: {self.failover_policy.election_delay.seconds}s")
        print(f"Max Election Time: {self.failover_policy.max_election_time.seconds}s")
        print(f"{'=' * 60}\n")

        # Connect to NATS
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect(servers=self.nats_urls)
        assert self.nats_adapter is not None

        # Create KV Store for service registry
        kv_store = NATSKVStore(self.nats_adapter)
        await kv_store.connect("service_registry", enable_ttl=True)

        # Create Service Registry
        self.service_registry = KVServiceRegistry(kv_store)

        # Create Service Discovery (using JetStream context)
        # Get JetStream context from NATS adapter
        import nats

        nc = nats.NATS()
        await nc.connect(servers=self.nats_urls)
        js = nc.jetstream()
        self.service_discovery = BasicServiceDiscovery(js)
        self._nc = nc  # Store for cleanup

        # Configure single active service
        config = SingleActiveConfig(
            service_name=self.service_name,
            instance_id=self.instance_id,
            group_id=self.group_id,
            registry_ttl=30,
            heartbeat_interval=5,  # 5 seconds heartbeat
            leader_ttl_seconds=3,  # Leader TTL must be less than or equal to heartbeat interval
        )

        # Create factories
        election_factory = DefaultElectionRepositoryFactory()
        use_case_factory = DefaultUseCaseFactory()

        # Create single active service
        assert self.nats_adapter is not None
        assert self.service_registry is not None
        assert self.service_discovery is not None

        self.single_active_service = SingleActiveService(
            config=config,
            message_bus=self.nats_adapter,
            service_registry=self.service_registry,
            service_discovery=self.service_discovery,
            election_repository_factory=election_factory,
            use_case_factory=use_case_factory,
            logger=self.logger,
        )

        # Set failover policy if we have access to the failover use case
        if (
            self.single_active_service
            and hasattr(self.single_active_service, "_failover_use_case")
            and self.single_active_service._failover_use_case
        ):
            self.single_active_service._failover_use_case._failover_policy = self.failover_policy

        # Start the single active service
        await self.single_active_service.start()

        print(f"[{self.instance_id}] Started - waiting for election...")

        # Start status monitoring
        self.status_check_task = asyncio.create_task(self._monitor_status())

        # Start work loop
        self.work_task = asyncio.create_task(self._work_loop())

    async def stop(self) -> None:
        """Stop the demo service gracefully."""
        self.running = False

        print(f"\n[{self.instance_id}] Shutting down...")

        # Cancel tasks
        if self.status_check_task and not self.status_check_task.done():
            self.status_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.status_check_task

        if self.work_task and not self.work_task.done():
            self.work_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.work_task

        # Stop single active service
        if self.single_active_service:
            await self.single_active_service.stop()

        # Disconnect from NATS
        if self.nats_adapter:
            await self.nats_adapter.disconnect()

        # Close additional NATS connection
        if hasattr(self, "_nc") and self._nc:
            await self._nc.close()

        # Print summary
        self._print_summary()

    async def _monitor_status(self) -> None:
        """Monitor and report status changes."""
        last_status = None

        while self.running:
            try:
                if self.single_active_service:
                    status = await self.single_active_service.get_status()

                    if status.is_active != last_status:
                        last_status = status.is_active
                        self._on_status_change(status.is_active)

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.instance_id}] Error monitoring status: {e}")
                await asyncio.sleep(1.0)

    def _on_status_change(self, is_active: bool) -> None:
        """Handle status change callbacks.

        Args:
            is_active: True if became active, False if became standby
        """
        self.is_active = is_active
        timestamp = datetime.now(UTC)

        self.status_changes.append(
            {
                "timestamp": timestamp,
                "is_active": is_active,
                "work_done": self.work_counter,
            }
        )

        status = "ACTIVE ✓" if is_active else "STANDBY"
        print(f"\n[{self.instance_id}] Status changed to: {status}")

        if is_active:
            print(f"[{self.instance_id}] 🎯 Now processing exclusive work")
        else:
            print(f"[{self.instance_id}] ⏸️  Standing by for failover")

    async def _work_loop(self) -> None:
        """Simulate work that only the active instance performs."""
        while self.running:
            try:
                if self.is_active:
                    # Simulate exclusive work
                    self.work_counter += 1

                    # Show work progress every 10 units
                    if self.work_counter % 10 == 0:
                        print(f"[{self.instance_id}] Processing work unit #{self.work_counter}")

                    # Simulate work taking time
                    await asyncio.sleep(0.5)
                else:
                    # Standby - just wait
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.instance_id}] Error in work loop: {e}")
                await asyncio.sleep(1.0)

    def _print_summary(self) -> None:
        """Print summary statistics."""
        if not self.start_time:
            return

        runtime = (datetime.now(UTC) - self.start_time).total_seconds()

        print(f"\n{'=' * 60}")
        print(f"Instance {self.instance_id} Summary:")
        print(f"  - Total Runtime: {runtime:.1f} seconds")
        print(f"  - Work Units Completed: {self.work_counter}")
        print(f"  - Status Changes: {len(self.status_changes)}")

        if self.status_changes:
            active_time = 0
            last_active_start = None

            for change in self.status_changes:
                if change["is_active"]:
                    last_active_start = change["timestamp"]
                elif last_active_start:
                    active_time += (change["timestamp"] - last_active_start).total_seconds()
                    last_active_start = None

            # Add remaining active time if still active
            if last_active_start and self.is_active:
                active_time += (datetime.now(UTC) - last_active_start).total_seconds()

            if active_time > 0:
                print(f"  - Total Active Time: {active_time:.1f} seconds")
                print(f"  - Work Rate: {self.work_counter / active_time:.1f} units/second")

        print(f"{'=' * 60}\n")


async def simulate_failover(instances: list[FailoverDemoService], failure_after: float = 10.0):
    """Simulate a failover scenario by stopping the active instance.

    Args:
        instances: List of demo service instances
        failure_after: Seconds to wait before simulating failure
    """
    await asyncio.sleep(failure_after)

    # Find the active instance
    active_instance = None
    for instance in instances:
        if instance.is_active:
            active_instance = instance
            break

    if active_instance:
        print(f"\n{'=' * 60}")
        print(f"🔴 SIMULATING FAILURE OF ACTIVE INSTANCE: {active_instance.instance_id}")
        print(f"{'=' * 60}\n")

        # Record time before failure
        failure_time = time.time()

        # Stop the active instance (simulates crash)
        await active_instance.stop()
        instances.remove(active_instance)

        # Wait for failover to complete
        print("⏳ Waiting for automatic failover...")

        # Check for new leader
        new_leader = None
        election_time = None

        for _ in range(40):  # Check for up to 4 seconds
            await asyncio.sleep(0.1)

            for instance in instances:
                if instance.is_active:
                    new_leader = instance
                    election_time = time.time()
                    break

            if new_leader:
                break

        if new_leader and election_time:
            failover_duration = election_time - failure_time
            print("\n✅ FAILOVER COMPLETE!")
            print(f"  - New Leader: {new_leader.instance_id}")
            print(f"  - Failover Time: {failover_duration:.3f} seconds")

            if failover_duration < 2.0:
                print("  - Result: PASSED ✓ (under 2-second target)")
            else:
                print("  - Result: FAILED ✗ (exceeded 2-second target)")
        else:
            print("\n❌ FAILOVER FAILED - No new leader elected")


async def main():
    """Run the failover demonstration."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AegisSDK Automatic Failover Demo")
    parser.add_argument("--instances", type=int, default=3, help="Number of instances to run")
    parser.add_argument(
        "--policy",
        choices=["aggressive", "balanced", "conservative"],
        default="aggressive",
        help="Failover policy",
    )
    parser.add_argument(
        "--failure-after", type=float, default=15.0, help="Simulate failure after N seconds"
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print(" AEGIS SDK - AUTOMATIC FAILOVER DEMONSTRATION")
    print(" Demonstrating sub-2-second failover with split-brain prevention")
    print("=" * 80)
    print("\nConfiguration:")
    print(f"  - Instances: {args.instances}")
    print(f"  - Failover Policy: {args.policy}")
    print(f"  - Failure Simulation: After {args.failure_after} seconds")

    # Create instances
    instances = []
    for i in range(1, args.instances + 1):
        instance = FailoverDemoService(
            instance_id=f"instance-{i}",
            failover_policy=args.policy,
        )
        instances.append(instance)

    # Start all instances
    print(f"\nStarting {args.instances} instances...")
    start_tasks = [instance.start() for instance in instances]
    await asyncio.gather(*start_tasks)

    # Wait for initial election
    await asyncio.sleep(3.0)

    # Check initial state
    leader_count = sum(1 for inst in instances if inst.is_active)
    print(f"\n✓ Initial election complete: {leader_count} leader(s)")

    if leader_count != 1:
        print("⚠️  WARNING: Expected exactly 1 leader!")

    # Create failover simulation task
    failover_task = asyncio.create_task(
        simulate_failover(instances, failure_after=args.failure_after)
    )

    # Handle graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\n\nReceived shutdown signal...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    pending: set[asyncio.Task[Any]] = set()
    try:
        # Create shutdown task
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either shutdown or failover completion
        done, pending = await asyncio.wait(
            [shutdown_task, failover_task], return_when=asyncio.FIRST_COMPLETED
        )

        # If failover completed, wait a bit more to show work continuing
        if failover_task in done:
            print("\n📊 Observing continued operation after failover...")
            await asyncio.sleep(5.0)

    except KeyboardInterrupt:
        pass
    finally:
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Stop all instances
        print("\nStopping all instances...")
        stop_tasks = [instance.stop() for instance in instances if instance.running]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        print("\n" + "=" * 80)
        print(" Demo completed successfully!")
        print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        sys.exit(1)
