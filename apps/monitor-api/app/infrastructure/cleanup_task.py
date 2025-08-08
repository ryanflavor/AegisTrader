"""Background task for periodic cleanup of stale service entries.

This module provides a background task that periodically cleans up
stale service entries that don't have TTL metadata (pre-TTL era entries).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from aegis_sdk.domain.enums import ServiceStatus

if TYPE_CHECKING:
    from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort

logger = logging.getLogger(__name__)


class StaleEntryCleanupTask:
    """Background task for cleaning up stale service entries."""

    def __init__(
        self,
        kv_store: ServiceRegistryKVStorePort,
        cleanup_interval: int = 300,  # 5 minutes
        stale_threshold: int = 35,  # seconds (TTL + buffer)
    ):
        """Initialize the cleanup task.

        Args:
            kv_store: KV store port for accessing service registry
            cleanup_interval: Interval between cleanup runs in seconds (default: 5 minutes)
            stale_threshold: Age in seconds after which an entry is considered stale (default: 35)
        """
        self.kv_store = kv_store
        self.cleanup_interval = cleanup_interval
        self.stale_threshold = timedelta(seconds=stale_threshold)
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def _cleanup_stale_entries(self) -> int:
        """Perform cleanup of stale entries.

        Returns:
            Number of entries cleaned up
        """
        cleaned_count = 0
        now = datetime.now(UTC)

        try:
            # Get all service definitions from the registry
            all_services = await self.kv_store.list_all()

            for service in all_services:
                try:
                    # Service definitions don't have a value attribute
                    # They are already parsed domain objects
                    if not service:
                        continue

                    # Service definitions have updated_at for staleness check
                    data = service.model_dump()
                    if isinstance(data, dict):
                        # Normalize field names
                        if "serviceName" in data and "service_name" not in data:
                            data["service_name"] = data.pop("serviceName")
                        if "instanceId" in data and "instance_id" not in data:
                            data["instance_id"] = data.pop("instanceId")
                        if "lastHeartbeat" in data and "last_heartbeat" not in data:
                            data["last_heartbeat"] = data.pop("lastHeartbeat")

                        # Check if entry should be cleaned
                        should_clean = False
                        reason = ""

                        # Parse last heartbeat
                        last_heartbeat_str = data.get("last_heartbeat")
                        if last_heartbeat_str:
                            # Parse ISO format timestamp
                            if isinstance(last_heartbeat_str, str):
                                # Remove timezone info if present for parsing
                                if "+" in last_heartbeat_str:
                                    last_heartbeat_str = last_heartbeat_str.split("+")[0]
                                if "Z" in last_heartbeat_str:
                                    last_heartbeat_str = last_heartbeat_str.replace("Z", "")

                                # Parse and make timezone-aware
                                from datetime import datetime as dt

                                last_heartbeat = dt.fromisoformat(last_heartbeat_str)
                                if last_heartbeat.tzinfo is None:
                                    last_heartbeat = last_heartbeat.replace(tzinfo=UTC)

                                # Check heartbeat age
                                heartbeat_age = now - last_heartbeat
                                if heartbeat_age > self.stale_threshold:
                                    should_clean = True
                                    reason = (
                                        f"heartbeat too old ({heartbeat_age.total_seconds():.1f}s)"
                                    )

                        # Check status
                        status = data.get("status")
                        if status in (
                            ServiceStatus.UNHEALTHY,
                            ServiceStatus.SHUTDOWN,
                            "UNHEALTHY",
                            "SHUTDOWN",
                        ):
                            should_clean = True
                            reason = f"status is {status}"

                        # Check if service is stale based on updated_at
                        if should_clean:
                            # Clean stale service definitions
                            logger.info(
                                f"Cleaning stale service: {service.service_name} - {reason}"
                            )
                            try:
                                await self.kv_store.delete(service.service_name)
                                cleaned_count += 1
                            except Exception:
                                pass  # Service might not exist anymore

                except Exception as e:
                    logger.error(f"Error processing entry {key}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale entries")

        return cleaned_count

    async def _run_periodic_cleanup(self) -> None:
        """Run the cleanup task periodically."""
        logger.info(
            f"Starting periodic cleanup task (interval: {self.cleanup_interval}s, "
            f"stale threshold: {self.stale_threshold.total_seconds()}s)"
        )

        while not self._stop_event.is_set():
            try:
                # Wait for the interval or stop event
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.cleanup_interval)
            except TimeoutError:
                # Timeout means we should run cleanup
                try:
                    await self._cleanup_stale_entries()
                except Exception as e:
                    logger.error(f"Unexpected error in cleanup task: {e}")

        logger.info("Periodic cleanup task stopped")

    def start(self) -> None:
        """Start the background cleanup task."""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_periodic_cleanup())
            logger.info("Background cleanup task started")

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        if self._task and not self._task.done():
            self._stop_event.set()
            await self._task
            self._task = None
            logger.info("Background cleanup task stopped")

    async def run_once(self) -> int:
        """Run cleanup once immediately.

        Returns:
            Number of entries cleaned up
        """
        logger.info("Running manual cleanup")
        return await self._cleanup_stale_entries()
