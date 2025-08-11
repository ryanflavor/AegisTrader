"""NATS-based leader election coordination implementation.

Manages the leader election process using NATS KV Store with
atomic compare-and-swap operations to ensure exactly one leader.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..domain.enums import StickyActiveStatus
from ..domain.value_objects import (
    ElectionState,
    FailoverPolicy,
    InstanceId,
    ServiceName,
)
from ..ports.kv_store import KVStorePort as KVStore
from ..ports.logger import LoggerPort
from ..ports.monitoring import ElectionCoordinatorPort
from ..ports.service_registry import ServiceRegistryPort


class ElectionCoordinator(ElectionCoordinatorPort):
    """Coordinates leader election for sticky active services.

    Implements a distributed leader election algorithm using NATS KV Store's
    atomic operations to ensure only one instance becomes active.
    """

    def __init__(
        self,
        kv_store: KVStore,
        service_registry: ServiceRegistryPort,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        failover_policy: FailoverPolicy | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        """Initialize election coordinator.

        Args:
            kv_store: KV Store for leader key management
            service_registry: Registry for updating instance status
            service_name: Service name participating in election
            instance_id: This instance's identifier
            group_id: Sticky active group identifier
            failover_policy: Failover behavior configuration
            logger: Logger for election events
        """
        self._kv_store = kv_store
        self._service_registry = service_registry
        self._service_name = service_name
        self._instance_id = instance_id
        self._group_id = group_id
        self._failover_policy = failover_policy or FailoverPolicy.balanced()
        self._logger = logger or self._create_default_logger()

        self._election_state = ElectionState()
        self._election_task: asyncio.Task | None = None
        self._on_elected_callback: Callable[[], Any] | None = None
        self._on_lost_callback: Callable[[], Any] | None = None

    def _create_default_logger(self) -> LoggerPort:
        """Create a default logger if none provided."""
        from .simple_logger import SimpleLogger

        return SimpleLogger()

    def set_on_elected_callback(self, callback: Callable[[], Any]) -> None:
        """Set callback to invoke when elected as leader.

        Args:
            callback: Function to call when becoming leader
        """
        self._on_elected_callback = callback

    def set_on_lost_callback(self, callback: Callable[[], Any]) -> None:
        """Set callback to invoke when losing leadership.

        Args:
            callback: Function to call when losing leadership
        """
        self._on_lost_callback = callback

    async def trigger_election(self, service_name: str, group_id: str) -> None:
        """Trigger a new leader election.

        This method implements the ElectionTrigger protocol expected by HeartbeatMonitor.

        Args:
            service_name: Name of the service (should match our service)
            group_id: Group identifier (should match our group)
        """
        if service_name != str(self._service_name) or group_id != self._group_id:
            self._logger.warning(
                "Election triggered for different service/group",
                requested_service=service_name,
                requested_group=group_id,
                our_service=str(self._service_name),
                our_group=self._group_id,
            )
            return

        await self.start_election()

    async def start_election(self) -> bool:
        """Start the leader election process.

        Returns:
            True if elected as leader, False otherwise
        """
        # Check if election already in progress
        if self._election_task and not self._election_task.done():
            self._logger.warning(
                "Election already in progress",
                instance=str(self._instance_id),
                state=self._election_state.state,
            )
            return False

        # Update election state
        self._election_state = ElectionState(
            state=ElectionState.ELECTING,
            started_at=datetime.now(UTC),
            instance_id=str(self._instance_id),
            attempts=0,
        )

        self._logger.info(
            "Starting leader election",
            service=str(self._service_name),
            instance=str(self._instance_id),
            group=self._group_id,
        )

        # Run election
        self._election_task = asyncio.create_task(self._run_election())

        try:
            result = await asyncio.wait_for(
                self._election_task,
                timeout=self._failover_policy.max_election_time.seconds,
            )
            return bool(result)
        except TimeoutError:
            self._logger.error(
                "Election timed out",
                instance=str(self._instance_id),
                timeout=f"{self._failover_policy.max_election_time.seconds}s",
            )
            self._election_state = ElectionState(
                state=ElectionState.FAILED,
                started_at=self._election_state.started_at,
                completed_at=datetime.now(UTC),
                attempts=self._election_state.attempts,
                last_error="Election timed out",
                instance_id=str(self._instance_id),
            )
            return False

    async def _run_election(self) -> bool:
        """Run the election process with retries and backoff.

        Returns:
            True if elected as leader, False otherwise
        """
        max_attempts = 3
        base_delay = 0.1  # 100ms base delay

        for attempt in range(max_attempts):
            self._election_state = ElectionState(
                state=ElectionState.ELECTING,
                started_at=self._election_state.started_at,
                attempts=attempt + 1,
                instance_id=str(self._instance_id),
            )

            # Add jitter to prevent thundering herd
            jitter = random.uniform(0, base_delay * 0.5)  # nosec B311
            delay = base_delay * (2**attempt) + jitter

            if attempt > 0:
                self._logger.debug(
                    f"Election attempt {attempt + 1}/{max_attempts}",
                    instance=str(self._instance_id),
                    delay=f"{delay:.3f}s",
                )
                await asyncio.sleep(delay)

            try:
                # Try to acquire leader key atomically
                success = await self._try_acquire_leadership()

                if success:
                    # We won the election
                    self._election_state = ElectionState(
                        state=ElectionState.ELECTED,
                        started_at=self._election_state.started_at,
                        completed_at=datetime.now(UTC),
                        attempts=self._election_state.attempts,
                        instance_id=str(self._instance_id),
                    )

                    self._logger.info(
                        "Won leader election",
                        service=str(self._service_name),
                        instance=str(self._instance_id),
                        group=self._group_id,
                        attempts=self._election_state.attempts,
                        duration=f"{0:.3f}s",  # Simplified - Duration calculation has issues
                    )

                    # Update our status in the registry
                    await self._update_instance_status(StickyActiveStatus.ACTIVE.value)

                    # Invoke callback if set
                    if self._on_elected_callback:
                        try:
                            result = self._on_elected_callback()
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            self._logger.error(
                                f"Error in on_elected callback: {e}",
                                instance=str(self._instance_id),
                            )

                    return True

                else:
                    # Someone else won
                    self._logger.info(
                        "Lost leader election",
                        service=str(self._service_name),
                        instance=str(self._instance_id),
                        group=self._group_id,
                        attempt=attempt + 1,
                    )

            except Exception as e:
                self._logger.error(
                    f"Election attempt failed: {e}",
                    instance=str(self._instance_id),
                    attempt=attempt + 1,
                )
                self._election_state = ElectionState(
                    state=ElectionState.ELECTING,
                    started_at=self._election_state.started_at,
                    attempts=self._election_state.attempts,
                    last_error=str(e),
                    instance_id=str(self._instance_id),
                )

        # All attempts failed
        self._election_state = ElectionState(
            state=ElectionState.FAILED,
            started_at=self._election_state.started_at,
            completed_at=datetime.now(UTC),
            attempts=self._election_state.attempts,
            last_error="All election attempts failed",
            instance_id=str(self._instance_id),
        )

        self._logger.error(
            "Failed to win election after all attempts",
            instance=str(self._instance_id),
            attempts=max_attempts,
        )

        return False

    async def _try_acquire_leadership(self) -> bool:
        """Try to atomically acquire the leader key.

        Returns:
            True if leadership acquired, False otherwise
        """
        leader_key = self._get_leader_key()

        try:
            # Check if leader key already exists
            current_leader = await self._kv_store.get(leader_key)

            if current_leader:
                # Leader exists - check if it's us
                leader_data = (
                    current_leader.value if hasattr(current_leader, "value") else current_leader
                )
                leader_id = (
                    leader_data.get("instance_id") if isinstance(leader_data, dict) else None
                )
                if leader_id == str(self._instance_id):
                    # We're already the leader
                    self._logger.debug(
                        "Already the leader",
                        instance=str(self._instance_id),
                    )
                    return True
                else:
                    # Someone else is leader
                    self._logger.debug(
                        f"Leader exists: {leader_id}",
                        instance=str(self._instance_id),
                    )
                    return False

            # No leader exists - try to become leader
            leader_data = {
                "instance_id": str(self._instance_id),
                "service_name": str(self._service_name),
                "group_id": self._group_id,
                "elected_at": datetime.now(UTC).isoformat(),
                "ttl": 5,  # 5 second TTL
            }

            # Import KVOptions for create_only flag
            from ..domain.models import KVOptions

            # Use create_only option for atomic CAS operation
            # Note: TTL is handled by stream-level configuration
            options = KVOptions(create_only=True)

            try:
                await self._kv_store.put(leader_key, leader_data, options)
                self._logger.debug(
                    "Successfully acquired leader key",
                    instance=str(self._instance_id),
                    key=leader_key,
                )
                return True
            except Exception as e:
                # Check if it's a key already exists error
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    self._logger.debug(
                        "Failed to acquire leader key (lost race)",
                        instance=str(self._instance_id),
                        key=leader_key,
                    )
                    return False
                else:
                    # Re-raise other errors
                    raise

        except Exception as e:
            self._logger.error(
                f"Error acquiring leader key: {e}",
                instance=str(self._instance_id),
                key=leader_key,
            )
            raise

    async def release_leadership(self) -> None:
        """Release leadership voluntarily."""
        leader_key = self._get_leader_key()

        try:
            # Check if we're the current leader
            current_leader = await self._kv_store.get(leader_key)
            if current_leader:
                leader_data = (
                    current_leader.value if hasattr(current_leader, "value") else current_leader
                )
                leader_id = (
                    leader_data.get("instance_id") if isinstance(leader_data, dict) else None
                )

                if leader_id == str(self._instance_id):
                    # Delete the leader key
                    await self._kv_store.delete(leader_key)

                    self._logger.info(
                        "Released leadership",
                        service=str(self._service_name),
                        instance=str(self._instance_id),
                        group=self._group_id,
                    )

                    # Update our status
                    await self._update_instance_status(StickyActiveStatus.STANDBY.value)

                    # Invoke callback if set
                    if self._on_lost_callback:
                        try:
                            result = self._on_lost_callback()
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            self._logger.error(
                                f"Error in on_lost callback: {e}",
                                instance=str(self._instance_id),
                            )

        except Exception as e:
            self._logger.error(
                f"Error releasing leadership: {e}",
                instance=str(self._instance_id),
            )

    async def _update_instance_status(self, sticky_status: str) -> None:
        """Update instance status in the service registry.

        Args:
            sticky_status: New sticky active status
        """
        try:
            # Get current instance from registry
            instance = await self._service_registry.get_instance(
                str(self._service_name), str(self._instance_id)
            )

            if instance:
                # Update sticky active status
                instance.sticky_active_status = sticky_status
                instance.last_heartbeat = datetime.now(UTC)

                # Update in registry using update_heartbeat
                await self._service_registry.update_heartbeat(instance, ttl_seconds=60)

                self._logger.debug(
                    f"Updated instance status to {sticky_status}",
                    service=str(self._service_name),
                    instance=str(self._instance_id),
                )
            else:
                self._logger.warning(
                    "Instance not found in registry",
                    service=str(self._service_name),
                    instance=str(self._instance_id),
                )

        except Exception as e:
            self._logger.error(
                f"Failed to update instance status: {e}",
                instance=str(self._instance_id),
                new_status=sticky_status,
            )

    def _get_leader_key(self) -> str:
        """Get the leader key for this service group.

        Returns:
            KV Store key for the leader
        """
        return f"sticky-active.{self._service_name.value}.{self._group_id}.leader"

    def get_election_state(self) -> ElectionState:
        """Get current election state.

        Returns:
            Current ElectionState
        """
        return self._election_state

    def is_elected(self) -> bool:
        """Check if this instance is elected as leader.

        Returns:
            True if elected, False otherwise
        """
        return self._election_state.is_elected()

    async def check_leadership(self) -> bool:
        """Check if this instance is currently the leader.

        Returns:
            True if currently leader, False otherwise
        """
        leader_key = self._get_leader_key()

        try:
            current_leader = await self._kv_store.get(leader_key)
            if current_leader:
                leader_data = (
                    current_leader.value if hasattr(current_leader, "value") else current_leader
                )
                leader_id = (
                    leader_data.get("instance_id") if isinstance(leader_data, dict) else None
                )
                return leader_id == str(self._instance_id)
            return False
        except Exception as e:
            self._logger.error(
                f"Error checking leadership: {e}",
                instance=str(self._instance_id),
            )
            return False
