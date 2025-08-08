#!/usr/bin/env python3
"""Script to clean up stale service entries from NATS KV store.

This script identifies and removes service instances that:
1. Have heartbeats older than the configured TTL (30 seconds default)
2. Were created before TTL support was enabled (no TTL metadata)
3. Are marked as UNHEALTHY or SHUTDOWN

Usage:
    python cleanup_stale_services.py [--dry-run] [--nats-url nats://localhost:4222]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, "/home/ryan/workspace/github/AegisTrader/packages/aegis-sdk")

from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class StaleServiceCleaner:
    """Cleans up stale service entries from the KV store."""

    def __init__(self, nats_url: str = "nats://localhost:4222", dry_run: bool = False):
        """Initialize the cleaner.

        Args:
            nats_url: NATS server URL
            dry_run: If True, only report what would be deleted without actually deleting
        """
        self.nats_url = nats_url
        self.dry_run = dry_run
        self.logger = SimpleLogger("StaleServiceCleaner")
        self.stale_threshold = timedelta(seconds=35)  # TTL (30s) + buffer (5s)

    async def connect(self) -> None:
        """Connect to NATS and KV store."""
        # Create NATS connection
        self.nats_adapter = NATSAdapter(config=NATSConnectionConfig(servers=[self.nats_url]))
        await self.nats_adapter.connect()

        # Create KV store
        self.kv_store = NATSKVStore(nats_adapter=self.nats_adapter, logger=self.logger)
        await self.kv_store.connect("service_registry", enable_ttl=True)

        self.logger.info(f"Connected to NATS at {self.nats_url}")

    async def identify_stale_entries(self) -> list[tuple[str, ServiceInstance, str]]:
        """Identify stale service entries.

        Returns:
            List of (key, instance, reason) tuples for stale entries
        """
        stale_entries = []
        now = datetime.now(UTC)

        # Get all service registry keys
        all_keys = await self.kv_store.keys("service-instances__")

        self.logger.info(f"Found {len(all_keys)} service entries to check")

        for key in all_keys:
            try:
                # Get the entry
                entry = await self.kv_store.get(key)
                if not entry or not entry.value:
                    continue

                # Parse service instance
                data = entry.value
                if isinstance(data, dict):
                    # Normalize field names to snake_case
                    if "serviceName" in data and "service_name" not in data:
                        data["service_name"] = data.pop("serviceName")
                    if "instanceId" in data and "instance_id" not in data:
                        data["instance_id"] = data.pop("instanceId")
                    if "lastHeartbeat" in data and "last_heartbeat" not in data:
                        data["last_heartbeat"] = data.pop("lastHeartbeat")
                    if "stickyActiveGroup" in data and "sticky_active_group" not in data:
                        data["sticky_active_group"] = data.pop("stickyActiveGroup")

                    instance = ServiceInstance(**data)

                    # Check if entry is stale
                    reasons = []

                    # 1. Check heartbeat age
                    heartbeat_age = now - instance.last_heartbeat
                    if heartbeat_age > self.stale_threshold:
                        reasons.append(
                            f"heartbeat too old ({heartbeat_age.total_seconds():.1f}s > {self.stale_threshold.total_seconds()}s)"
                        )

                    # 2. Check if status is UNHEALTHY or SHUTDOWN
                    if instance.status in (ServiceStatus.UNHEALTHY, ServiceStatus.SHUTDOWN):
                        reasons.append(f"status is {instance.status}")

                    # 3. Check if entry has no TTL (pre-TTL era)
                    if entry.ttl is None:
                        reasons.append("no TTL metadata (pre-TTL entry)")

                    if reasons:
                        stale_entries.append((key, instance, " AND ".join(reasons)))

            except Exception as e:
                self.logger.error(f"Error checking entry {key}: {e}")

        return stale_entries

    async def cleanup_stale_entries(
        self, stale_entries: list[tuple[str, ServiceInstance, str]]
    ) -> int:
        """Remove stale entries from the KV store.

        Args:
            stale_entries: List of (key, instance, reason) tuples

        Returns:
            Number of entries deleted
        """
        deleted_count = 0

        for key, instance, reason in stale_entries:
            self.logger.info(
                f"{'[DRY-RUN] Would delete' if self.dry_run else 'Deleting'} "
                f"{instance.service_name}/{instance.instance_id}: {reason}"
            )

            if not self.dry_run:
                try:
                    success = await self.kv_store.delete(key)
                    if success:
                        deleted_count += 1
                        self.logger.info(f"  ✓ Deleted {key}")
                    else:
                        self.logger.warning(f"  ✗ Failed to delete {key} (already gone?)")
                except Exception as e:
                    self.logger.error(f"  ✗ Error deleting {key}: {e}")
            else:
                deleted_count += 1  # Count what would be deleted

        return deleted_count

    async def verify_ttl_working(self) -> bool:
        """Verify that TTL is working correctly by creating a test entry.

        Returns:
            True if TTL is working, False otherwise
        """
        test_key = "test-ttl-verification"
        test_value = {"test": "ttl", "timestamp": datetime.now(UTC).isoformat()}

        try:
            # Create entry with 2 second TTL
            from aegis_sdk.domain.models import KVOptions

            await self.kv_store.put(test_key, test_value, options=KVOptions(ttl=2))
            self.logger.info("Created test entry with 2 second TTL")

            # Verify it exists immediately
            entry1 = await self.kv_store.get(test_key)
            if not entry1:
                self.logger.error("Test entry not found immediately after creation")
                return False

            # Wait for TTL to expire
            await asyncio.sleep(3)

            # Verify it's gone
            entry2 = await self.kv_store.get(test_key)
            if entry2:
                self.logger.error("Test entry still exists after TTL expiration")
                await self.kv_store.delete(test_key)  # Clean up
                return False

            self.logger.info("✓ TTL verification successful - entries expire as expected")
            return True

        except Exception as e:
            self.logger.error(f"TTL verification failed: {e}")
            return False

    async def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the service registry.

        Returns:
            Dictionary with statistics
        """
        all_keys = await self.kv_store.keys("service-instances__")
        services: dict[str, list[str]] = {}
        entries_with_ttl = 0
        entries_without_ttl = 0

        for key in all_keys:
            try:
                entry = await self.kv_store.get(key)
                if entry:
                    # Track TTL status
                    if entry.ttl is not None:
                        entries_with_ttl += 1
                    else:
                        entries_without_ttl += 1

                    # Extract service name
                    parts = key.split("__")
                    if len(parts) >= 3:
                        service_name = parts[1]
                        instance_id = parts[2]
                        if service_name not in services:
                            services[service_name] = []
                        services[service_name].append(instance_id)
            except Exception as e:
                self.logger.error(f"Error getting stats for {key}: {e}")

        return {
            "total_entries": len(all_keys),
            "unique_services": len(services),
            "entries_with_ttl": entries_with_ttl,
            "entries_without_ttl": entries_without_ttl,
            "services": {name: len(instances) for name, instances in services.items()},
        }

    async def run(self) -> None:
        """Run the cleanup process."""
        try:
            await self.connect()

            # Get initial statistics
            self.logger.info("\n=== Initial Statistics ===")
            stats = await self.get_statistics()
            self.logger.info(f"Total entries: {stats['total_entries']}")
            self.logger.info(f"Unique services: {stats['unique_services']}")
            self.logger.info(f"Entries with TTL: {stats['entries_with_ttl']}")
            self.logger.info(f"Entries without TTL: {stats['entries_without_ttl']}")
            if stats["services"]:
                self.logger.info("Services:")
                for service, count in stats["services"].items():
                    self.logger.info(f"  - {service}: {count} instances")

            # Verify TTL is working
            self.logger.info("\n=== Verifying TTL Support ===")
            ttl_working = await self.verify_ttl_working()
            if not ttl_working:
                self.logger.error("TTL verification failed! Check NATS configuration.")
                if not self.dry_run:
                    self.logger.warning("Continuing with cleanup anyway...")

            # Identify stale entries
            self.logger.info("\n=== Identifying Stale Entries ===")
            stale_entries = await self.identify_stale_entries()

            if not stale_entries:
                self.logger.info("No stale entries found!")
                return

            self.logger.info(f"Found {len(stale_entries)} stale entries")

            # Cleanup stale entries
            self.logger.info(
                f"\n=== {'Dry-Run: Would Delete' if self.dry_run else 'Deleting'} Stale Entries ==="
            )
            deleted_count = await self.cleanup_stale_entries(stale_entries)

            # Get final statistics
            if not self.dry_run:
                self.logger.info("\n=== Final Statistics ===")
                final_stats = await self.get_statistics()
                self.logger.info(f"Total entries: {final_stats['total_entries']}")
                self.logger.info(
                    f"Entries removed: {stats['total_entries'] - final_stats['total_entries']}"
                )
                self.logger.info(f"Entries with TTL: {final_stats['entries_with_ttl']}")
                self.logger.info(f"Entries without TTL: {final_stats['entries_without_ttl']}")

            # Summary
            self.logger.info("\n=== Summary ===")
            if self.dry_run:
                self.logger.info(f"Would delete {deleted_count} stale entries (dry-run mode)")
            else:
                self.logger.info(f"Deleted {deleted_count} stale entries")

        finally:
            # Disconnect
            if hasattr(self, "kv_store"):
                await self.kv_store.disconnect()
            if hasattr(self, "nats_adapter"):
                await self.nats_adapter.disconnect()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up stale service entries from NATS KV store"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--nats-url",
        default="nats://localhost:4222",
        help="NATS server URL (default: nats://localhost:4222)",
    )
    args = parser.parse_args()

    cleaner = StaleServiceCleaner(nats_url=args.nats_url, dry_run=args.dry_run)
    await cleaner.run()


if __name__ == "__main__":
    asyncio.run(main())
