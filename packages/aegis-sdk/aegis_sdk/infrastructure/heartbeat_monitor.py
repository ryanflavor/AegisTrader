"""NATS-based heartbeat monitoring implementation.

Monitors the health of active service instances by watching their
heartbeat keys in NATS KV Store and detecting TTL expiration.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Protocol

from ..domain.value_objects import (
    Duration,
    FailoverPolicy,
    HeartbeatStatus,
    InstanceId,
    ServiceName,
)
from ..ports.kv_store import KVStorePort as KVStore
from ..ports.logger import LoggerPort
from ..ports.monitoring import HeartbeatMonitorPort


class ElectionTrigger(Protocol):
    """Protocol for triggering leader election."""

    async def trigger_election(self, service_name: str, group_id: str) -> None:
        """Trigger a new leader election.

        Args:
            service_name: Name of the service
            group_id: Sticky active group identifier
        """
        ...


class HeartbeatMonitor(HeartbeatMonitorPort):
    """Monitors heartbeats of active service instances.

    Watches the KV Store for heartbeat key expiration and triggers
    failover when the active instance is detected as failed.
    """

    def __init__(
        self,
        kv_store: KVStore,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        failover_policy: FailoverPolicy | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize heartbeat monitor.

        Args:
            kv_store: KV Store interface for watching keys
            service_name: Service name being monitored
            instance_id: This instance's identifier
            group_id: Sticky active group identifier
            failover_policy: Failover behavior configuration
            logger: Logger for monitoring events
        """
        self._kv_store = kv_store
        self._service_name = service_name
        self._instance_id = instance_id
        self._group_id = group_id
        self._failover_policy = failover_policy or FailoverPolicy.balanced()
        self._logger = logger or self._create_default_logger()

        self._monitor_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._election_trigger: ElectionTrigger | None = None
        self._current_leader: str | None = None
        self._last_heartbeat: datetime | None = None
        self._heartbeat_interval = Duration(seconds=0.5)  # Default 500ms

    def _create_default_logger(self) -> LoggerPort:
        """Create a default logger if none provided."""
        from .simple_logger import SimpleLogger

        return SimpleLogger()

    def set_election_trigger(self, trigger: ElectionTrigger) -> None:  # type: ignore[override]
        """Set the election trigger callback.

        Args:
            trigger: Object that can trigger elections
        """
        self._election_trigger = trigger

    def set_heartbeat_interval(self, interval: Duration) -> None:
        """Configure the heartbeat check interval.

        Args:
            interval: Duration between heartbeat checks
        """
        if interval.seconds < 0.1:
            raise ValueError("Heartbeat interval must be at least 100ms")
        if interval.seconds > 10:
            raise ValueError("Heartbeat interval must not exceed 10 seconds")
        self._heartbeat_interval = interval

    async def start_monitoring(self) -> None:
        """Start monitoring the active instance's heartbeat.

        Begins watching the leader's heartbeat key and will trigger
        election if the heartbeat expires or key is deleted.
        """
        if self._monitor_task and not self._monitor_task.done():
            self._logger.warning(
                "Heartbeat monitor already running",
                instance_id=str(self._instance_id),
            )
            return

        self._stop_event.clear()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        self._logger.info(
            "Started heartbeat monitoring",
            service=str(self._service_name),
            instance=str(self._instance_id),
            group=self._group_id,
            check_interval=f"{self._heartbeat_interval.seconds}s",
        )

    async def stop_monitoring(self) -> None:
        """Stop monitoring heartbeats.

        Gracefully stops the monitoring loop and cleans up resources.
        """
        self._stop_event.set()

        if self._monitor_task and not self._monitor_task.done():
            try:
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
            except TimeoutError:
                self._monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._monitor_task

        self._logger.info(
            "Stopped heartbeat monitoring",
            service=str(self._service_name),
            instance=str(self._instance_id),
        )

    async def _monitor_loop(self) -> None:
        """Main monitoring loop that watches for heartbeat expiration."""
        consecutive_failures = 0
        max_consecutive_failures = 3

        while not self._stop_event.is_set():
            try:
                # Check current leader
                leader_key = self._get_leader_key()
                leader_info = await self._kv_store.get(leader_key)

                if not leader_info:
                    # No leader exists
                    if self._current_leader:
                        await self._handle_leader_loss(self._current_leader)
                    self._current_leader = None
                else:
                    # Leader exists - check heartbeat
                    current_leader_id = leader_info.get("instance_id")

                    if current_leader_id != str(self._instance_id):
                        # We're not the leader - monitor their heartbeat
                        heartbeat_status = await self._check_heartbeat(current_leader_id)

                        if heartbeat_status and not heartbeat_status.is_healthy():
                            # Heartbeat expired
                            await self._handle_heartbeat_expiration(heartbeat_status)
                        elif heartbeat_status:
                            # Update tracking
                            self._current_leader = current_leader_id
                            self._last_heartbeat = heartbeat_status.last_seen
                            consecutive_failures = 0

                # Wait before next check
                await asyncio.sleep(self._heartbeat_interval.seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                self._logger.error(
                    f"Error in heartbeat monitor loop: {e}",
                    service=str(self._service_name),
                    instance=str(self._instance_id),
                    consecutive_failures=consecutive_failures,
                )

                if consecutive_failures >= max_consecutive_failures:
                    self._logger.error(
                        "Too many consecutive monitoring failures, stopping monitor",
                        service=str(self._service_name),
                        instance=str(self._instance_id),
                    )
                    break

                # Exponential backoff on errors
                await asyncio.sleep(min(2**consecutive_failures, 30))

    async def _check_heartbeat(self, leader_id: str) -> HeartbeatStatus | None:
        """Check the heartbeat status of the current leader.

        Args:
            leader_id: Instance ID of the current leader

        Returns:
            HeartbeatStatus if found, None otherwise
        """
        try:
            # Get heartbeat key
            heartbeat_key = f"service.{self._service_name.value}.{leader_id}.heartbeat"
            heartbeat_data = await self._kv_store.get(heartbeat_key)

            if not heartbeat_data:
                # No heartbeat key found
                return HeartbeatStatus(
                    instance_id=leader_id,
                    last_seen=datetime.now(UTC),
                    ttl_seconds=5,
                    is_expired=True,
                    time_since_last=float("inf"),
                )

            # Parse heartbeat timestamp
            last_heartbeat_str = heartbeat_data.get("timestamp")
            if not last_heartbeat_str:
                return None

            last_heartbeat = datetime.fromisoformat(last_heartbeat_str)
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=UTC)

            # Calculate time since last heartbeat
            now = datetime.now(UTC)
            time_since_last = (now - last_heartbeat).total_seconds()

            # Get TTL from heartbeat data
            ttl_seconds = heartbeat_data.get("ttl", 5)

            # Check if expired
            is_expired = time_since_last > ttl_seconds

            return HeartbeatStatus(
                instance_id=leader_id,
                last_seen=last_heartbeat,
                ttl_seconds=ttl_seconds,
                is_expired=is_expired,
                time_since_last=time_since_last,
            )

        except Exception as e:
            self._logger.error(
                f"Failed to check heartbeat: {e}",
                service=str(self._service_name),
                leader_id=leader_id,
            )
            return None

    async def _handle_heartbeat_expiration(self, heartbeat_status: HeartbeatStatus) -> None:
        """Handle detection of expired heartbeat.

        Args:
            heartbeat_status: Status of the expired heartbeat
        """
        self._logger.warning(
            "Heartbeat expired for active instance",
            service=str(self._service_name),
            expired_instance=heartbeat_status.instance_id,
            time_since_last=f"{heartbeat_status.time_since_last:.2f}s",
            ttl=f"{heartbeat_status.ttl_seconds}s",
        )

        # Apply detection threshold from failover policy
        await asyncio.sleep(self._failover_policy.detection_threshold.seconds)

        # Re-check to avoid false positive
        recheck = await self._check_heartbeat(heartbeat_status.instance_id)
        if recheck and recheck.is_healthy():
            self._logger.info(
                "Heartbeat recovered during detection threshold",
                service=str(self._service_name),
                instance=heartbeat_status.instance_id,
            )
            return

        # Apply election delay from failover policy
        await asyncio.sleep(self._failover_policy.election_delay.seconds)

        # Trigger election
        await self._trigger_election_if_configured()

    async def _handle_leader_loss(self, previous_leader: str) -> None:
        """Handle loss of leader (key deleted or missing).

        Args:
            previous_leader: ID of the previous leader
        """
        self._logger.warning(
            "Leader key lost",
            service=str(self._service_name),
            previous_leader=previous_leader,
            group=self._group_id,
        )

        # Apply election delay
        await asyncio.sleep(self._failover_policy.election_delay.seconds)

        # Trigger election
        await self._trigger_election_if_configured()

    async def _trigger_election_if_configured(self) -> None:
        """Trigger election if an election trigger is configured."""
        if self._election_trigger:
            self._logger.info(
                "Triggering leader election",
                service=str(self._service_name),
                instance=str(self._instance_id),
                group=self._group_id,
            )
            try:
                await self._election_trigger.trigger_election(
                    str(self._service_name), self._group_id
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to trigger election: {e}",
                    service=str(self._service_name),
                    instance=str(self._instance_id),
                )
        else:
            self._logger.warning(
                "No election trigger configured, cannot initiate failover",
                service=str(self._service_name),
                instance=str(self._instance_id),
            )

    def _get_leader_key(self) -> str:
        """Get the leader key for this service group.

        Returns:
            KV Store key for the leader
        """
        return f"sticky-active.{self._service_name.value}.{self._group_id}.leader"

    def get_status(self) -> dict:
        """Get current monitoring status.

        Returns:
            Dictionary with monitoring status information
        """
        return {
            "monitoring": self._monitor_task is not None and not self._monitor_task.done(),
            "service": str(self._service_name),
            "instance": str(self._instance_id),
            "group": self._group_id,
            "current_leader": self._current_leader,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "check_interval": self._heartbeat_interval.seconds,
            "failover_policy": self._failover_policy.mode,
        }
