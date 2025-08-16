"""NATS KV Store-based implementation of ElectionRepository.

This implementation uses NATS JetStream Key-Value store with atomic
operations to implement distributed leader election with automatic failover.

Critical fixes included:
1. Handles expired keys properly by checking and purging them
2. Fixes async generator watch bug (don't await watch() call)
3. Uses purge instead of delete for expired leaders
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from ..domain.exceptions import KVKeyAlreadyExistsError, KVKeyNotFoundError
from ..domain.models import KVOptions
from ..domain.services import StickyActiveElectionService
from ..domain.value_objects import InstanceId, ServiceName
from ..ports.election_repository import ElectionRepository
from ..ports.kv_store import KVStorePort
from ..ports.logger import LoggerPort
from ..ports.metrics import MetricsPort
from .config import LogContext
from .in_memory_metrics import InMemoryMetrics
from .simple_logger import SimpleLogger


class NatsKvElectionRepository(ElectionRepository):
    """NATS KV Store implementation of the election repository.

    Uses atomic Compare-And-Set (CAS) operations and TTL to implement
    distributed leader election with automatic failover. Includes critical
    fixes for expired key handling and async generator issues.
    """

    def __init__(
        self,
        kv_store: KVStorePort,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize the NATS KV election repository.

        Args:
            kv_store: KV store port for persistence
            logger: Optional logger port
            metrics: Optional metrics port
        """
        self._kv_store = kv_store
        self._logger = logger or SimpleLogger("aegis_sdk.election_repository")
        self._metrics = metrics or InMemoryMetrics()
        self._election_service = StickyActiveElectionService()
        self._watch_tasks: dict[str, asyncio.Task] = {}

        # Configuration for retry logic
        self._max_retries = 3
        self._retry_delay = 0.1  # seconds - reasonable retry delay

    async def attempt_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Attempt to acquire leadership with expired key detection.

        The critical bug: When a key expires, NATS KV still returns it as existing
        for create_only operations, causing permanent election failure.

        Fix: Check if existing key is actually valid (not expired), and if expired,
        purge it before attempting to create new leader key.
        """
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)
        leader_value = self._election_service.create_leader_value(str(instance_id), metadata)

        log_ctx = LogContext(
            operation="attempt_leadership",
            component="NatsKvElectionRepository",
            service_name=str(service_name),
            instance_id=str(instance_id),
            group_id=group_id,
        )

        for attempt in range(self._max_retries):
            try:
                # Try to create the leader key with timeout
                options = KVOptions(create_only=True)
                await asyncio.wait_for(
                    self._kv_store.put(leader_key, leader_value, options),
                    timeout=0.5,  # 500ms timeout
                )

                self._metrics.increment("election.leadership.acquired")
                self._logger.info(
                    f"Leadership acquired: {service_name}/{instance_id} in group {group_id}",
                    extra=log_ctx.to_dict(),
                )
                return True

            except KVKeyAlreadyExistsError:
                # Key exists - but it might be expired!
                self._logger.debug(
                    f"ATTEMPT #{attempt + 1}: Key already exists, checking if expired",
                    extra=log_ctx.to_dict(),
                )
                # Check if the existing leader is actually valid
                try:
                    # Add timeout to prevent blocking
                    current_entry = await asyncio.wait_for(
                        self._kv_store.get(leader_key),
                        timeout=1.0,  # 1 second timeout
                    )

                    if current_entry and current_entry.value:
                        # Key exists and has valid data
                        try:
                            leader_id, last_heartbeat, _ = (
                                self._election_service.parse_leader_value(
                                    json.dumps(current_entry.value)
                                )
                            )

                            # Check if leader is expired based on heartbeat
                            # Always check expiry, even if last_heartbeat is 0 or None
                            if last_heartbeat is None:
                                # No heartbeat recorded, consider it expired
                                time_since_heartbeat = float("inf")
                            else:
                                time_since_heartbeat = time.time() - last_heartbeat

                            # Use the TTL passed to this method for consistency
                            if time_since_heartbeat > ttl_seconds:
                                # Add random delay to reduce collision probability
                                import random

                                random_delay = random.uniform(0, 0.5)  # 0-500ms random delay
                                self._logger.info(
                                    f"Adding {random_delay:.3f}s random delay before takeover attempt",
                                    extra=log_ctx.to_dict(),
                                )
                                await asyncio.sleep(random_delay)

                                # Leader is expired, take over by deleting and recreating
                                self._logger.warning(
                                    f"ATTEMPT #{attempt + 1}: Found EXPIRED leader {leader_id} (age={time_since_heartbeat:.1f}s > {ttl_seconds}s TTL), attempting purge and takeover",
                                    extra=log_ctx.to_dict(),
                                )

                                # Purge the expired key completely, then create new one
                                # Use purge instead of delete to avoid tombstone issues
                                try:
                                    # Step 1: Purge the expired key (removes all history)
                                    self._logger.info(
                                        f"Purging expired leader key with revision {current_entry.revision}",
                                        extra=log_ctx.to_dict(),
                                    )
                                    # Use the port interface for purge with timeout
                                    await asyncio.wait_for(
                                        self._kv_store.purge(leader_key),
                                        timeout=0.5,  # 500ms timeout for purge
                                    )

                                    # Step 2: Increased delay for purge to propagate in cluster
                                    await asyncio.sleep(
                                        0.3
                                    )  # Allow purge to fully propagate (was 0.1)

                                    # Step 3: Create new leader key with create_only
                                    options = KVOptions(create_only=True)
                                    await asyncio.wait_for(
                                        self._kv_store.put(leader_key, leader_value, options),
                                        timeout=0.5,  # 500ms timeout for put
                                    )

                                    self._metrics.increment("election.leadership.acquired.takeover")
                                    self._logger.info(
                                        f"Successfully took over from expired leader: {service_name}/{instance_id} in group {group_id}",
                                        extra=log_ctx.to_dict(),
                                    )
                                    return True
                                except KVKeyAlreadyExistsError:
                                    # Someone else took over first
                                    self._logger.info(
                                        "Another instance took over leadership first",
                                        extra=log_ctx.to_dict(),
                                    )
                                    return False
                                except TimeoutError:
                                    # Operation timed out, likely due to network issues
                                    self._logger.warning(
                                        "Takeover operation timed out, retrying",
                                        extra=log_ctx.to_dict(),
                                    )
                                    await asyncio.sleep(self._retry_delay)
                                    continue
                                except Exception as takeover_error:
                                    self._logger.error(
                                        f"Failed to take over from expired leader: {takeover_error.__class__.__name__}: {takeover_error}",
                                        extra=log_ctx.to_dict(),
                                    )
                                    # Someone else might have taken over, continue retrying
                                    await asyncio.sleep(self._retry_delay)
                                    continue

                            # Valid leader exists
                            self._logger.debug(
                                f"ATTEMPT #{attempt + 1}: Valid leader exists: {leader_id}, age={time_since_heartbeat:.1f}s < {ttl_seconds}s TTL",
                                extra=log_ctx.to_dict(),
                            )
                            return False

                        except Exception as parse_error:
                            # Corrupted data, purge and retry
                            self._logger.warning(
                                f"Corrupted leader data, purging: {parse_error}",
                                extra=log_ctx.to_dict(),
                            )
                            await self._purge_key(leader_key)
                            await asyncio.sleep(self._retry_delay)
                            continue
                    else:
                        # Key exists but no value - this is a deleted/expired key
                        # NATS KV returns deleted keys, we need to purge them
                        self._logger.info(
                            "Found deleted/expired leader key, purging",
                            extra=log_ctx.to_dict(),
                        )
                        await self._purge_key(leader_key)
                        await asyncio.sleep(self._retry_delay)
                        continue

                except KVKeyNotFoundError:
                    # Key was deleted between operations, try to become leader
                    self._logger.info(
                        "Leader key not found, attempting to become leader",
                        extra=log_ctx.to_dict(),
                    )
                    # The key doesn't exist, so we should try to create it
                    # Continue to next iteration which will attempt create_only
                    continue
                except Exception as check_error:
                    self._logger.error(
                        f"Error checking existing leader: {check_error}",
                        extra=log_ctx.to_dict(),
                    )
                    # Assume leader exists if we can't check
                    return False

            except Exception as e:
                self._metrics.increment("election.leadership.error")
                error_ctx = log_ctx.with_error(e)
                self._logger.exception(
                    f"Failed to attempt leadership: {e}",
                    extra=error_ctx.to_dict(),
                )

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)  # Fixed delay, not incremental
                else:
                    raise

        return False

    async def _purge_key(self, key: str) -> None:
        """Purge a key completely from KV store.

        Unlike delete which leaves a tombstone, purge completely removes
        the key and all its history, allowing create_only to succeed.
        """
        try:
            # Use the port's purge method which removes all history
            await self._kv_store.purge(key)
            self._logger.debug(f"Successfully purged key {key}")

        except Exception as e:
            self._logger.debug(f"Error purging key {key}: {e}")
            # Ignore errors, key might already be gone

    async def watch_leadership(
        self,
        service_name: ServiceName,
        group_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Watch for leadership changes.

        Original bug: watch() returns an AsyncIterator, not a coroutine.
        Fix: Remove the await, just call watch() directly.
        """
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)

        log_ctx = LogContext(
            operation="watch_leadership",
            component="NatsKvElectionRepository",
            service_name=str(service_name),
            group_id=group_id,
        )

        self._logger.info(
            f"Starting leadership watch for {service_name}/{group_id}",
            extra=log_ctx.to_dict(),
        )

        try:
            # FIX: Don't await the watch() call - it returns an AsyncIterator
            watch_iter = self._kv_store.watch(leader_key)  # No await here!

            async for event in watch_iter:
                # Enhanced logging for watch events
                self._logger.info(
                    f"WATCH EVENT: operation={event.operation}, key={leader_key}, "
                    f"has_entry={event.entry is not None}, has_value={event.entry.value if event.entry else None}, "
                    f"revision={event.entry.revision if event.entry else None}",
                    extra=log_ctx.to_dict(),
                )

                # Map KV watch events to leadership events
                if event.operation == "PUT":
                    if event.entry and event.entry.value:
                        leader_id, last_heartbeat, metadata = (
                            self._election_service.parse_leader_value(json.dumps(event.entry.value))
                        )
                        # Include heartbeat in metadata for monitoring
                        if last_heartbeat is not None:
                            metadata["last_heartbeat"] = last_heartbeat

                        # Calculate heartbeat age for debugging
                        import time as time_module

                        current_time = time_module.time()
                        age = current_time - last_heartbeat if last_heartbeat else float("inf")

                        self._logger.info(
                            f"WATCH: Leader PUT event - leader={leader_id}, heartbeat_age={age:.1f}s, revision={event.entry.revision}",
                            extra=log_ctx.to_dict(),
                        )

                        yield {
                            "type": "elected",
                            "leader_id": leader_id,
                            "metadata": metadata,
                            "timestamp": current_time,
                        }
                elif event.operation == "DELETE" or event.operation == "PURGE":
                    # Important: Don't generate "expired" events from watch
                    # Expiration should only be detected by periodic checker based on heartbeat age
                    # Watch DELETE/PURGE events can be stale or from other operations
                    self._logger.info(
                        f"WATCH: {event.operation} event detected - generating 'lost' event (not expired). "
                        f"has_entry={event.entry is not None}, has_value={event.entry.value is not None if event.entry else False}",
                        extra=log_ctx.to_dict(),
                    )

                    # Always generate "lost" event, never "expired" from watch
                    # Expiration detection is handled by periodic checker
                    yield {
                        "type": "lost",
                        "leader_id": None,
                        "metadata": {},
                        "timestamp": time.time(),
                    }

        except Exception as e:
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Error in leadership watch: {e}",
                extra=error_ctx.to_dict(),
            )
            raise

    async def release_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> bool:
        """Release leadership with purge instead of delete.

        Using purge ensures the key is completely removed, allowing
        immediate re-election instead of waiting for TTL expiry.
        """
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)

        log_ctx = LogContext(
            operation="release_leadership",
            component="NatsKvElectionRepository",
            service_name=str(service_name),
            instance_id=str(instance_id),
            group_id=group_id,
        )

        try:
            # Verify we are the current leader
            current_entry = await self._kv_store.get(leader_key)
            if current_entry and current_entry.value:
                leader_id, _, _ = self._election_service.parse_leader_value(
                    json.dumps(current_entry.value)
                )

                if leader_id != str(instance_id):
                    self._logger.warning(
                        "Cannot release leadership - not the current leader",
                        extra=log_ctx.to_dict(),
                    )
                    return False

            # Purge the key completely
            await self._purge_key(leader_key)

            self._metrics.increment("election.leadership.released")
            self._logger.info(
                f"Leadership released: {service_name}/{instance_id} in group {group_id}",
                extra=log_ctx.to_dict(),
            )
            return True

        except Exception as e:
            self._metrics.increment("election.leadership.release_error")
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Failed to release leadership: {e}",
                extra=error_ctx.to_dict(),
            )
            return False

    async def update_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update existing leadership with heartbeat."""
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)

        log_ctx = LogContext(
            operation="update_leadership",
            component="NatsKvElectionRepository",
            service_name=str(service_name),
            instance_id=str(instance_id),
            group_id=group_id,
        )

        try:
            # Get current leader value
            current_entry = await self._kv_store.get(leader_key)
            if not current_entry:
                self._logger.warning(
                    f"No leader found when updating: {service_name}/{group_id}",
                    extra=log_ctx.to_dict(),
                )
                return False

            # Parse and verify we are the leader
            current_leader_id, _, current_metadata = self._election_service.parse_leader_value(
                json.dumps(current_entry.value)
            )

            if current_leader_id != str(instance_id):
                self._logger.warning(
                    f"Not the current leader: expected {instance_id}, found {current_leader_id}",
                    extra=log_ctx.to_dict(),
                )
                return False

            # Update with new heartbeat
            updated_value = self._election_service.create_leader_value(
                str(instance_id),
                metadata or current_metadata,
            )

            # Debug logging
            import time

            self._logger.info(
                f"UPDATING HEARTBEAT: key={leader_key}, new_heartbeat={updated_value.get('last_heartbeat')}, current_time={time.time()}"
            )

            # Update with revision check to ensure atomicity
            options = KVOptions(
                revision=current_entry.revision,
            )
            new_revision = await self._kv_store.put(leader_key, updated_value, options)

            self._metrics.increment("election.leadership.updated")
            self._logger.info(
                f"Leadership updated: {service_name}/{instance_id} in group {group_id}, "
                f"old_revision={current_entry.revision}, new_revision={new_revision}, "
                f"heartbeat={updated_value.get('last_heartbeat')}",
                extra=log_ctx.to_dict(),
            )
            return True

        except Exception as e:
            self._metrics.increment("election.leadership.update_error")
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Failed to update leadership: {e}",
                extra=error_ctx.to_dict(),
            )
            return False

    async def get_current_leader(
        self,
        service_name: ServiceName,
        group_id: str,
    ) -> tuple[InstanceId | None, dict[str, Any]]:
        """Get the current leader information."""
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)

        try:
            entry = await self._kv_store.get(leader_key)
            if not entry:
                return None, {}

            # Parse leader value
            leader_id, last_heartbeat, metadata = self._election_service.parse_leader_value(
                json.dumps(entry.value)
            )

            # Don't check expiry here - let the caller decide based on their TTL
            # The TTL is context-specific and should be handled by attempt_leadership
            # which knows the actual TTL being used

            # Include last_heartbeat in the metadata so monitors can check staleness
            return InstanceId(value=leader_id), {**metadata, "last_heartbeat": last_heartbeat}

        except Exception as e:
            self._logger.exception(f"Failed to get current leader: {e}")
            return None, {}

    async def save_election_state(
        self,
        election: Any,  # StickyActiveElection
    ) -> None:
        """Save the election aggregate state."""
        # Create state key for this instance using underscores to comply with NATS KV
        state_key = f"election_state_{election.service_name}_{election.instance_id}_{election.group_id}".replace(
            "-", "_"
        ).replace(".", "_")

        try:
            # Serialize election state
            state_data = {
                "service_name": str(election.service_name),
                "instance_id": str(election.instance_id),
                "group_id": election.group_id,
                "is_leader": election.is_leader,
                "leader_instance_id": (
                    str(election.leader_instance_id) if election.leader_instance_id else None
                ),
                "leader_key": election.leader_key,
                "last_leader_heartbeat": (
                    election.last_leader_heartbeat.isoformat()
                    if election.last_leader_heartbeat
                    else None
                ),
                "status": (
                    election.status.value
                    if hasattr(election.status, "value")
                    else str(election.status)
                ),
                "leader_ttl_seconds": election.leader_ttl_seconds,
                "heartbeat_interval_seconds": election.heartbeat_interval_seconds,
            }

            await self._kv_store.put(state_key, state_data)
            self._metrics.increment("election.state.saved")

        except Exception as e:
            self._logger.exception(f"Failed to save election state: {e}")
            raise

    async def get_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> Any | None:  # StickyActiveElection | None
        """Load the election aggregate state."""
        state_key = f"election_state_{service_name}_{instance_id}_{group_id}".replace(
            "-", "_"
        ).replace(".", "_")

        try:
            entry = await self._kv_store.get(state_key)
            if not entry:
                return None

            # Reconstruct StickyActiveElection from saved state
            from datetime import datetime

            from ..domain.aggregates import StickyActiveElection, StickyActiveElectionState

            state_data = entry.value

            # Convert status string back to enum
            status_str = state_data.get("status", "STANDBY")
            try:
                status = StickyActiveElectionState(status_str)
            except ValueError:
                status = StickyActiveElectionState.STANDBY

            # Reconstruct the election aggregate
            election = StickyActiveElection(
                service_name=service_name,
                instance_id=instance_id,
                group_id=group_id,
                status=status,
                leader_instance_id=(
                    InstanceId(value=state_data["leader_instance_id"])
                    if state_data.get("leader_instance_id")
                    else None
                ),
                last_leader_heartbeat=(
                    datetime.fromisoformat(state_data["last_leader_heartbeat"])
                    if state_data.get("last_leader_heartbeat")
                    else None
                ),
                leader_ttl_seconds=state_data.get(
                    "leader_ttl_seconds", 5
                ),  # Use saved TTL or default to 5
                heartbeat_interval_seconds=state_data.get("heartbeat_interval_seconds", 2),
            )

            # Also restore the is_leader flag
            if state_data.get("is_leader"):
                election.status = StickyActiveElectionState.ACTIVE

            return election

        except Exception as e:
            self._logger.exception(f"Failed to get election state: {e}")
            return None

    async def delete_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> bool:
        """Delete the election aggregate state."""
        state_key = f"election_state_{service_name}_{instance_id}_{group_id}".replace(
            "-", "_"
        ).replace(".", "_")

        try:
            return await self._kv_store.delete(state_key)

        except Exception as e:
            self._logger.exception(f"Failed to delete election state: {e}")
            return False
