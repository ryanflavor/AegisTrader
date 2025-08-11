"""NATS KV Store-based implementation of ElectionRepository.

This implementation uses NATS JetStream Key-Value store with atomic
operations to implement distributed leader election.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from ..domain.aggregates import StickyActiveElection
from ..domain.exceptions import KVKeyAlreadyExistsError
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
    distributed leader election with automatic failover.
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

    async def attempt_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Attempt to acquire leadership using atomic create-or-get operation.

        Uses NATS KV create operation which only succeeds if the key doesn't exist.
        This provides the atomic "create-or-get" semantics required for leader election.
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

        try:
            # Try to create the leader key
            # This will only succeed if the key doesn't exist
            # Note: TTL is handled by stream-level configuration, not per-message
            options = KVOptions(create_only=True)
            await self._kv_store.put(leader_key, leader_value, options)

            self._metrics.increment("election.leadership.acquired")
            self._logger.info(
                f"Leadership acquired: {service_name}/{instance_id} in group {group_id}",
                extra=log_ctx.to_dict(),
            )
            return True

        except KVKeyAlreadyExistsError:
            # Another instance is already the leader
            self._metrics.increment("election.leadership.exists")
            self._logger.debug(
                f"Leadership already exists for {service_name} in group {group_id}",
                extra=log_ctx.to_dict(),
            )
            return False

        except Exception as e:
            self._metrics.increment("election.leadership.error")
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Failed to attempt leadership: {e}",
                extra=error_ctx.to_dict(),
            )
            raise

    async def update_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update existing leadership with heartbeat.

        This refreshes the TTL and updates the last_heartbeat timestamp.
        Only succeeds if the instance is the current leader.
        """
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

            # Update with revision check to ensure atomicity
            options = KVOptions(
                revision=current_entry.revision,
            )
            await self._kv_store.put(leader_key, updated_value, options)

            self._metrics.increment("election.leadership.updated")
            self._logger.debug(
                f"Leadership updated: {service_name}/{instance_id} in group {group_id}",
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

            # Check if leader is expired
            if self._election_service.is_leader_expired(last_heartbeat, time.time()):
                self._logger.info(f"Leader {leader_id} is expired for {service_name}/{group_id}")
                return None, {}

            return InstanceId(value=leader_id), metadata

        except Exception as e:
            self._logger.exception(f"Failed to get current leader: {e}")
            return None, {}

    async def release_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> bool:
        """Release leadership voluntarily."""
        leader_key = self._election_service.create_leader_key(str(service_name), group_id)

        log_ctx = LogContext(
            operation="release_leadership",
            component="NatsKvElectionRepository",
            service_name=str(service_name),
            instance_id=str(instance_id),
            group_id=group_id,
        )

        try:
            # Get current leader to verify we own it
            current_entry = await self._kv_store.get(leader_key)
            if not current_entry:
                return False

            leader_id, _, _ = self._election_service.parse_leader_value(
                json.dumps(current_entry.value)
            )

            if leader_id != str(instance_id):
                self._logger.warning(
                    f"Cannot release leadership - not the leader: {instance_id} != {leader_id}",
                    extra=log_ctx.to_dict(),
                )
                return False

            # Delete with revision check
            success = await self._kv_store.delete(leader_key, current_entry.revision)

            if success:
                self._metrics.increment("election.leadership.released")
                self._logger.info(
                    f"Leadership released: {service_name}/{instance_id} in group {group_id}",
                    extra=log_ctx.to_dict(),
                )

            return success

        except Exception as e:
            self._metrics.increment("election.leadership.release_error")
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Failed to release leadership: {e}",
                extra=error_ctx.to_dict(),
            )
            return False

    async def watch_leadership(  # type: ignore[override]
        self,
        service_name: ServiceName,
        group_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Watch for leadership changes."""
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
            watch_iter = await self._kv_store.watch(leader_key)
            async for event in watch_iter:
                self._logger.debug(
                    f"Leadership event: {event.operation} for {leader_key}",
                    extra=log_ctx.to_dict(),
                )

                # Map KV watch events to leadership events
                if event.operation == "PUT":
                    if event.entry and event.entry.value:
                        leader_id, _, metadata = self._election_service.parse_leader_value(
                            json.dumps(event.entry.value)
                        )
                        yield {
                            "type": "elected",
                            "leader_id": leader_id,
                            "metadata": metadata,
                            "timestamp": time.time(),
                        }
                elif event.operation == "DELETE" or event.operation == "PURGE":
                    yield {
                        "type": "lost" if event.entry and event.entry.value else "expired",
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

    async def save_election_state(
        self,
        election: StickyActiveElection,
    ) -> None:
        """Save the election aggregate state."""
        # Create state key for this instance using underscores to comply with NATS KV
        state_key = f"election-state__{election.service_name.value}__{election.instance_id.value}__{election.group_id}"

        # Serialize the election state
        state_data = {
            "service_name": str(election.service_name),
            "instance_id": str(election.instance_id),
            "group_id": election.group_id,
            "status": election.status.value,
            "leader_instance_id": (
                str(election.leader_instance_id) if election.leader_instance_id else None
            ),
            "last_leader_heartbeat": (
                election.last_leader_heartbeat.isoformat()
                if election.last_leader_heartbeat
                else None
            ),
            "leader_ttl_seconds": election.leader_ttl_seconds,
            "heartbeat_interval_seconds": election.heartbeat_interval_seconds,
            "election_timeout_seconds": election.election_timeout_seconds,
            "started_at": election.started_at.isoformat(),
            "last_election_attempt": (
                election.last_election_attempt.isoformat()
                if election.last_election_attempt
                else None
            ),
            "became_leader_at": (
                election.became_leader_at.isoformat() if election.became_leader_at else None
            ),
        }

        await self._kv_store.put(state_key, state_data)
        self._logger.debug(f"Saved election state for {state_key}")

    async def get_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> StickyActiveElection | None:
        """Retrieve the election aggregate state."""
        state_key = f"election-state__{service_name.value}__{instance_id.value}__{group_id}"

        try:
            entry = await self._kv_store.get(state_key)
            if not entry:
                return None

            # Deserialize state
            from datetime import datetime

            state_data = entry.value

            # Convert ISO strings back to datetime objects
            def parse_datetime(iso_str: str | None) -> datetime | None:
                if iso_str:
                    return datetime.fromisoformat(iso_str)
                return None

            # Reconstruct the election aggregate
            from ..domain.aggregates import StickyActiveElectionState

            election = StickyActiveElection(
                service_name=ServiceName(value=state_data["service_name"]),
                instance_id=InstanceId(value=state_data["instance_id"]),
                group_id=state_data["group_id"],
                status=StickyActiveElectionState(state_data["status"]),
                leader_instance_id=(
                    InstanceId(value=state_data["leader_instance_id"])
                    if state_data["leader_instance_id"]
                    else None
                ),
                last_leader_heartbeat=parse_datetime(state_data.get("last_leader_heartbeat")),
                leader_ttl_seconds=state_data["leader_ttl_seconds"],
                heartbeat_interval_seconds=state_data["heartbeat_interval_seconds"],
                election_timeout_seconds=state_data["election_timeout_seconds"],
                started_at=parse_datetime(state_data["started_at"]) or datetime.now(),
                last_election_attempt=parse_datetime(state_data.get("last_election_attempt")),
                became_leader_at=parse_datetime(state_data.get("became_leader_at")),
            )

            # Clear initialization event since we're loading from storage
            election.mark_events_committed()

            return election

        except Exception as e:
            self._logger.exception(f"Failed to get election state: {e}")
            return None

    async def delete_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> None:
        """Delete the election aggregate state."""
        state_key = f"election-state__{service_name.value}__{instance_id.value}__{group_id}"

        try:
            await self._kv_store.delete(state_key)
            self._logger.debug(f"Deleted election state for {state_key}")
        except Exception as e:
            self._logger.exception(f"Failed to delete election state: {e}")
