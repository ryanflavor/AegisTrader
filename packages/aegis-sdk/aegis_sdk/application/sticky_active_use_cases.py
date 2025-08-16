"""Application use cases for sticky active service pattern.

This module contains application services that orchestrate sticky active
leader election and service registration with appropriate status updates.
"""

from __future__ import annotations

import asyncio
import builtins
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.aggregates import StickyActiveElection
from ..domain.events import (
    ElectionFailedEvent,
    LeaderElectedEvent,
    LeaderLostEvent,
)
from ..domain.models import Event, ServiceInstance
from ..domain.value_objects import InstanceId, ServiceName
from ..ports.election_repository import ElectionRepository
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from ..ports.service_registry import ServiceRegistryPort


class StickyActiveRegistrationRequest(BaseModel):
    """Request model for sticky active service registration with strict validation."""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    service_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Name of the service",
    )
    instance_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Instance identifier",
    )
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Service version in semantic versioning format",
    )
    group_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        description="Sticky active group",
    )
    ttl_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Registration TTL in seconds",
    )
    leader_ttl_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Leader key TTL in seconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Service metadata",
    )

    @field_validator("service_name", "group_id")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Validate name format."""
        import re

        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-_.]*$", v):
            raise ValueError(
                f"Invalid format: {v}. Must start with alphanumeric and contain only "
                "letters, numbers, hyphens, underscores, and dots."
            )
        return v


class StickyActiveRegistrationResponse(BaseModel):
    """Response model for sticky active service registration with strict validation."""

    model_config = ConfigDict(strict=True)

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    is_leader: bool = Field(..., description="Whether this instance is the leader")
    sticky_active_status: str = Field(
        ...,
        pattern="^(ACTIVE|STANDBY)$",
        description="Current sticky active status",
    )
    group_id: str = Field(..., description="Sticky active group")


class StickyActiveRegistrationUseCase:
    """Use case for registering a service with sticky active election.

    This orchestrates both leader election and service registration,
    ensuring the ServiceInstance status reflects the election outcome.
    """

    def __init__(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ):
        """Initialize the use case with required dependencies."""
        self._election_repo = election_repository
        self._service_registry = service_registry
        self._message_bus = message_bus
        self._metrics = metrics
        self._logger = logger
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    async def execute(
        self, request: StickyActiveRegistrationRequest
    ) -> StickyActiveRegistrationResponse:
        """Register service and participate in sticky active election.

        Args:
            request: Registration request with validated parameters

        Returns:
            Registration response with election results

        Raises:
            ValueError: If request validation fails
            RuntimeError: If election or registration fails
        """
        try:
            # Create value objects
            service_name = ServiceName(value=request.service_name)
            instance_id = InstanceId(value=request.instance_id)
        except ValueError as e:
            self._logger.error(f"Invalid request parameters: {e}")
            raise ValueError(f"Invalid registration request: {e}") from e

        # Create or restore election aggregate
        election = await self._election_repo.get_election_state(
            service_name, instance_id, request.group_id
        )

        if not election:
            # Create new election aggregate
            election = StickyActiveElection(
                service_name=service_name,
                instance_id=instance_id,
                group_id=request.group_id,
                leader_ttl_seconds=request.leader_ttl_seconds,
                heartbeat_interval_seconds=max(1, request.leader_ttl_seconds // 3),
            )

        # Check if already leader or need to start election
        if election.is_leader:
            # Already leader, just update heartbeat
            acquired = True
        else:
            # Start election process
            election.start_election()

            # Attempt to acquire leadership
            acquired = await self._election_repo.attempt_leadership(
                service_name=service_name,
                instance_id=instance_id,
                group_id=request.group_id,
                ttl_seconds=request.leader_ttl_seconds,
                metadata=request.metadata,
            )

        if acquired:
            if not election.is_leader:
                # Only call win_election if we weren't already the leader
                election.win_election()
                self._metrics.increment("sticky_active.election.won")
                if self._logger:
                    self._logger.info(
                        f"Won election for {service_name}/{instance_id} in group {request.group_id}"
                    )

                # Start heartbeat task to maintain leadership TTL
                heartbeat_key = f"{service_name}/{instance_id}/{request.group_id}"
                if heartbeat_key in self._heartbeat_tasks:
                    self._heartbeat_tasks[heartbeat_key].cancel()

                # Start heartbeat task directly with shared election repo
                self._heartbeat_tasks[heartbeat_key] = asyncio.create_task(
                    self._maintain_leadership_heartbeat(
                        service_name,
                        instance_id,
                        request.group_id,
                        request.leader_ttl_seconds,
                    )
                )
        elif not election.is_leader:
            # Lost the election (and not already leader)
            leader_id, _ = await self._election_repo.get_current_leader(
                service_name, request.group_id
            )
            if leader_id:
                election.lose_election(leader_id)
            self._metrics.increment("sticky_active.election.lost")
            if self._logger:
                self._logger.info(
                    f"Lost election for {service_name}/{instance_id} in group {request.group_id}"
                )

        # Save election state
        try:
            await self._election_repo.save_election_state(election)
        except Exception as e:
            self._logger.exception(f"Failed to save election state: {e}")
            # Non-critical, continue execution

        # Create service instance with sticky active status
        sticky_status = "ACTIVE" if election.is_leader else "STANDBY"
        service_instance = ServiceInstance(
            service_name=request.service_name,
            instance_id=request.instance_id,
            version=request.version,
            status="ACTIVE",  # Service status (different from sticky status)
            sticky_active_group=request.group_id,
            sticky_active_status=sticky_status,
            metadata=request.metadata,
        )

        # Register in service registry
        try:
            await self._service_registry.register(service_instance, request.ttl_seconds)
        except Exception as e:
            self._logger.exception(f"Failed to register service instance: {e}")
            self._metrics.increment("sticky_active.registration.error")
            raise RuntimeError(f"Service registration failed: {e}") from e

        # Publish domain events
        for event in election.get_uncommitted_events():
            if event.event_type == "election.won":
                domain_event = LeaderElectedEvent(
                    aggregate_id=f"{service_name}/{instance_id}",
                    service_name=request.service_name,
                    instance_id=request.instance_id,
                    group_id=request.group_id,
                    elected_at=event.timestamp,
                )
            elif event.event_type == "election.lost":
                domain_event = ElectionFailedEvent(
                    aggregate_id=f"{service_name}/{instance_id}",
                    service_name=request.service_name,
                    instance_id=request.instance_id,
                    group_id=request.group_id,
                    reason="Another instance is already leader",
                )
            else:
                continue  # Skip other internal events

            # Convert DomainEvent to Event for message bus
            event = Event(
                domain="sticky_active",
                event_type=domain_event.event_type,
                payload=domain_event.model_dump(
                    exclude={
                        "event_id",
                        "occurred_at",
                        "aggregate_id",
                        "aggregate_type",
                        "event_type",
                        "event_version",
                    }
                ),
            )
            await self._message_bus.publish_event(event)

        election.mark_events_committed()

        return StickyActiveRegistrationResponse(
            service_name=request.service_name,
            instance_id=request.instance_id,
            is_leader=election.is_leader,
            sticky_active_status=sticky_status,
            group_id=request.group_id,
        )

    async def _maintain_leadership_heartbeat(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
    ) -> None:
        """Maintain leadership heartbeat by periodically updating TTL."""
        # Update interval should be less than TTL to prevent expiration
        # Update at the configured heartbeat interval
        # Use 1/3 of TTL for better safety margin (was 1/2)
        update_interval = max(0.5, ttl_seconds / 3)  # More frequent updates for safety

        if self._logger:
            self._logger.info(
                f"Starting heartbeat maintenance for {service_name}/{instance_id}, "
                f"interval={update_interval}s, ttl={ttl_seconds}s"
            )

        heartbeat_count = 0
        while True:
            try:
                await asyncio.sleep(update_interval)
                heartbeat_count += 1

                if self._logger:
                    self._logger.debug(
                        f"Heartbeat attempt #{heartbeat_count} for {service_name}/{instance_id}"
                    )

                # Update leadership TTL using self's repo
                updated = await self._election_repo.update_leadership(
                    service_name,
                    instance_id,
                    group_id,
                    ttl_seconds,
                )

                if not updated:
                    if self._logger:
                        self._logger.warning(
                            f"Failed to update leadership heartbeat for {service_name}/{instance_id}"
                        )
                    # Immediately cancel this heartbeat task to prevent further attempts
                    self._metrics.increment("sticky_active.heartbeat.lost_leadership")
                    return  # Exit immediately, we're no longer the leader

                if self._logger:
                    self._logger.debug(
                        f"✓ Updated leadership heartbeat #{heartbeat_count} for {service_name}/{instance_id}"
                    )

            except asyncio.CancelledError:
                if self._logger:
                    self._logger.info(f"Heartbeat task cancelled for {service_name}/{instance_id}")
                break
            except Exception as e:
                if self._logger:
                    self._logger.error(f"HEARTBEAT ERROR: {e}", exc_info=True)
                # Continue trying to update heartbeat
                await asyncio.sleep(1)


class StickyActiveHeartbeatRequest(BaseModel):
    """Request model for sticky active heartbeat with strict validation."""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    service_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Name of the service",
    )
    instance_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Instance identifier",
    )
    group_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        description="Sticky active group",
    )
    ttl_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Registration TTL in seconds",
    )
    leader_ttl_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Leader key TTL in seconds",
    )


class StickyActiveHeartbeatUseCase:
    """Use case for updating heartbeat with sticky active status.

    This ensures both service registration and leader key are refreshed,
    maintaining the sticky active pattern consistency.
    """

    def __init__(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ):
        """Initialize the use case with required dependencies."""
        self._election_repo = election_repository
        self._service_registry = service_registry
        self._metrics = metrics
        self._logger = logger

    async def execute(self, request: StickyActiveHeartbeatRequest) -> bool:
        """Update heartbeat for both service instance and leader key.

        Args:
            request: Heartbeat request with validated parameters

        Returns:
            True if heartbeat was successful, False otherwise

        Raises:
            ValueError: If request validation fails
        """
        try:
            # Create value objects
            service_name = ServiceName(value=request.service_name)
            instance_id = InstanceId(value=request.instance_id)
        except ValueError as e:
            self._logger.error(f"Invalid heartbeat request: {e}")
            self._metrics.increment("sticky_active.heartbeat.validation_error")
            return False

        # Load election state
        election = await self._election_repo.get_election_state(
            service_name, instance_id, request.group_id
        )

        if not election:
            if self._logger:
                self._logger.warning(f"No election state found for {service_name}/{instance_id}")
            return False

        # Update leader heartbeat if we are the leader
        if election.is_leader:
            updated = await self._election_repo.update_leadership(
                service_name=service_name,
                instance_id=instance_id,
                group_id=request.group_id,
                ttl_seconds=request.leader_ttl_seconds,
            )

            if updated:
                election.update_leader_heartbeat()
                self._metrics.increment("sticky_active.leader.heartbeat")
            else:
                # Lost leadership
                if self._logger:
                    self._logger.warning(
                        f"Failed to update leader heartbeat for {service_name}/{instance_id}"
                    )
                election.step_down("Failed to update heartbeat")
                self._metrics.increment("sticky_active.leader.lost")

        # Get current leader for status update
        leader_id, _ = await self._election_repo.get_current_leader(service_name, request.group_id)

        # Update service instance
        try:
            # Get current instance from registry with proper error handling
            current_instance = await self._service_registry.get_instance(
                request.service_name, request.instance_id
            )

            if current_instance:
                # Update sticky active status based on current state
                if election.is_leader and leader_id == instance_id:
                    current_instance.sticky_active_status = "ACTIVE"
                else:
                    current_instance.sticky_active_status = "STANDBY"

                # Update heartbeat
                await self._service_registry.update_heartbeat(current_instance, request.ttl_seconds)

                self._metrics.increment("sticky_active.heartbeat.success")
                return True
            else:
                if self._logger:
                    self._logger.error(
                        f"Service instance not found in registry: {service_name}/{instance_id}"
                    )
                return False

        except Exception as e:
            if self._logger:
                self._logger.exception(f"Failed to update heartbeat: {e}")
            self._metrics.increment("sticky_active.heartbeat.error")
            return False
        finally:
            # Always save election state, even on error
            try:
                await self._election_repo.save_election_state(election)
            except Exception as save_error:
                if self._logger:
                    self._logger.error(f"Failed to save election state: {save_error}")
                # Don't fail the heartbeat if save fails


class StickyActiveMonitoringUseCase:
    """Use case for monitoring sticky active leadership changes.

    This watches for leadership changes and triggers new elections
    when the leader fails or expires.
    """

    def __init__(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
        status_callback: Callable[[bool], None] | None = None,
    ):
        """Initialize the use case with required dependencies.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            message_bus: Message bus for publishing events
            metrics: Metrics port
            logger: Logger port
            status_callback: Optional callback for status changes (True=active, False=standby)
        """
        self._election_repo = election_repository
        self._service_registry = service_registry
        self._message_bus = message_bus
        self._metrics = metrics
        self._logger = logger
        self._status_callback = status_callback
        self._monitoring_tasks: dict[str, asyncio.Task] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    async def start_monitoring(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
        ttl_seconds: int = 5,
    ) -> None:
        """Start monitoring leadership changes for a service."""
        key = f"{service_name}/{instance_id}/{group_id}"

        # Cancel existing task if any
        if key in self._monitoring_tasks:
            self._monitoring_tasks[key].cancel()

        # Create monitoring task
        task = asyncio.create_task(
            self._monitor_leadership(
                ServiceName(value=service_name),
                InstanceId(value=instance_id),
                group_id,
                ttl_seconds,
            )
        )
        self._monitoring_tasks[key] = task

    async def stop_monitoring(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
    ) -> None:
        """Stop monitoring leadership changes."""
        key = f"{service_name}/{instance_id}/{group_id}"
        if key in self._monitoring_tasks:
            self._monitoring_tasks[key].cancel()
            del self._monitoring_tasks[key]

    async def _maintain_leadership_heartbeat(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
    ) -> None:
        """Maintain leadership heartbeat by periodically updating TTL."""
        # Update interval should be less than TTL to prevent expiration
        # Update at the configured heartbeat interval
        # Use 1/3 of TTL for better safety margin (was 1/2)
        update_interval = max(0.5, ttl_seconds / 3)  # More frequent updates for safety

        if self._logger:
            self._logger.info(
                f"Starting heartbeat maintenance for {service_name}/{instance_id}, "
                f"interval={update_interval}s, ttl={ttl_seconds}s"
            )

        heartbeat_count = 0
        while True:
            try:
                await asyncio.sleep(update_interval)
                heartbeat_count += 1

                if self._logger:
                    self._logger.info(
                        f"Heartbeat attempt #{heartbeat_count} for {service_name}/{instance_id}"
                    )

                # Update leadership TTL
                updated = await self._election_repo.update_leadership(
                    service_name,
                    instance_id,
                    group_id,
                    ttl_seconds,
                )

                if not updated:
                    if self._logger:
                        self._logger.warning(
                            f"Failed to update leadership heartbeat for {service_name}/{instance_id}"
                        )
                    # Immediately cancel this heartbeat task to prevent further attempts
                    self._metrics.increment("sticky_active.heartbeat.lost_leadership")
                    return  # Exit immediately, we're no longer the leader

                if self._logger:
                    self._logger.info(
                        f"✓ Updated leadership heartbeat #{heartbeat_count} for {service_name}/{instance_id}"
                    )

            except asyncio.CancelledError:
                if self._logger:
                    self._logger.info(f"Heartbeat task cancelled for {service_name}/{instance_id}")
                raise
            except Exception as e:
                if self._logger:
                    self._logger.exception(f"Error updating leadership heartbeat: {e}")
                # Continue trying to update heartbeat
                await asyncio.sleep(1)

    async def _monitor_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int = 5,
    ) -> None:
        """Monitor leadership changes and handle failover.

        Args:
            service_name: Service name value object
            instance_id: Instance ID value object
            group_id: Sticky active group identifier
        """
        consecutive_errors = 0
        max_consecutive_errors = 3

        try:
            # Create a queue to merge events from multiple sources
            event_queue = asyncio.Queue()

            # Task to consume watch events and put them in the queue
            async def watch_consumer():
                """Consume watch events and put them in the queue."""
                try:
                    async for event in self._election_repo.watch_leadership(service_name, group_id):  # type: ignore[attr-defined]
                        await event_queue.put(("watch", event))
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"Error in watch consumer: {e}")
                    await event_queue.put(("error", e))

            # Task for periodic leader checks
            async def periodic_checker():
                """Periodically check if current leader is stale."""
                import time

                if self._logger:
                    self._logger.debug("Periodic checker starting for leader monitoring")

                check_count = 0
                while True:
                    try:
                        await asyncio.sleep(
                            1.0
                        )  # Check every 1 second (minimum meaningful interval)
                        check_count += 1

                        # Get current leader status
                        leader_id, metadata = await self._election_repo.get_current_leader(
                            service_name, group_id
                        )

                        if self._logger:
                            self._logger.info(
                                f"Periodic check #{check_count}: leader_id={leader_id}, metadata={metadata}"
                            )

                        if leader_id:
                            # Check if leader is stale
                            last_heartbeat = metadata.get("last_heartbeat") if metadata else None
                            if self._logger:
                                self._logger.info(
                                    f"Periodic check #{check_count}: last_heartbeat={last_heartbeat}, current_time={time.time()}"
                                )

                            if last_heartbeat:
                                age = time.time() - last_heartbeat
                                if self._logger:
                                    self._logger.info(
                                        f"Periodic check #{check_count}: Leader {leader_id} heartbeat age: {age:.1f}s (threshold: {ttl_seconds}s)"
                                    )
                                # If leader is stale (no heartbeat for > ttl_seconds), trigger expired event
                                if age > ttl_seconds:
                                    if self._logger:
                                        self._logger.info(
                                            f"Periodic check: Leader {leader_id} is STALE (age: {age:.1f}s), triggering expired event"
                                        )
                                    await event_queue.put(
                                        (
                                            "periodic",
                                            {
                                                "type": "expired",
                                                "leader_id": leader_id,
                                                "age": age,
                                                "source": "periodic_check",
                                            },
                                        )
                                    )
                            else:
                                if self._logger:
                                    self._logger.info(
                                        f"Periodic check #{check_count}: Leader {leader_id} has no heartbeat metadata"
                                    )
                        else:
                            if self._logger:
                                self._logger.debug(
                                    f"Periodic check #{check_count}: No leader found"
                                )
                            # No leader, check if we should try to become leader
                            election = await self._election_repo.get_election_state(
                                service_name, instance_id, group_id
                            )
                            if election:
                                is_leader = (
                                    election.get("is_leader", False)
                                    if isinstance(election, dict)
                                    else getattr(election, "is_leader", False)
                                )
                                if not is_leader:
                                    if self._logger:
                                        self._logger.info(
                                            "Periodic check: No leader exists, triggering takeover"
                                        )
                                    await event_queue.put(
                                        (
                                            "periodic",
                                            {"type": "expired", "source": "periodic_check"},
                                        )
                                    )

                    except asyncio.CancelledError:
                        if self._logger:
                            self._logger.debug("Periodic checker cancelled")
                        break
                    except Exception as e:
                        if self._logger:
                            self._logger.error(f"Error in periodic check: {e}", exc_info=True)
                        await asyncio.sleep(1.0)

            # Start both tasks
            watch_task = asyncio.create_task(watch_consumer())
            periodic_task = asyncio.create_task(periodic_checker())

            try:
                # Process events from the queue
                while True:
                    # Use timeout to prevent blocking forever when no events
                    try:
                        source, event = await asyncio.wait_for(event_queue.get(), timeout=5.0)
                    except builtins.TimeoutError:
                        # No event received, continue loop to check again
                        if self._logger:
                            self._logger.info(
                                "No event received in 5 seconds, checking for stale leaders..."
                            )
                        continue

                    # Handle errors from watch consumer
                    if source == "error":
                        raise event

                    if self._logger:
                        # More descriptive logging based on event type and leader
                        event_type = event.get("type", "unknown")
                        leader_id = event.get("leader_id")

                        if source == "periodic":
                            self._logger.debug(f"Periodic check event: {event_type}")
                        else:
                            self._logger.debug(f"Watch event: {event_type}")

                    if event_type == "elected":
                        if leader_id == str(instance_id):
                            self._logger.info(
                                f"This instance ({instance_id}) was elected as leader for {service_name}/{group_id}"
                            )
                        elif leader_id:
                            self._logger.debug(
                                f"Another instance ({leader_id}) was elected as leader for {service_name}/{group_id}"
                            )
                        else:
                            self._logger.debug(
                                f"Leadership election detected for {service_name}/{group_id}"
                            )
                    elif event_type == "expired":
                        # Enhanced logging for expired events
                        event_age = event.get("age", "unknown")
                        event_source = event.get("source", source)
                        self._logger.warning(
                            f"EXPIRED EVENT RECEIVED: source={event_source}, leader_id={event.get('leader_id')}, "
                            f"age={event_age}, from_queue={source}"
                        )
                    elif event_type == "lost":
                        self._logger.info(f"Leadership lost for {service_name}/{group_id}")
                    else:
                        self._logger.debug(
                            f"Leadership event: {event_type} for {service_name}/{group_id}"
                        )

                    # Load election state
                    election = await self._election_repo.get_election_state(
                        service_name, instance_id, group_id
                    )

                    if not election:
                        continue

                    # Handle dict or object from election state
                    is_leader = (
                        election.get("is_leader", False)
                        if isinstance(election, dict)
                        else getattr(election, "is_leader", False)
                    )

                    if event.get("type") == "expired" and not is_leader:
                        # Only handle expired events from periodic checker, not from watch
                        # Watch events can be stale or incorrect, periodic checker is the source of truth
                        if source == "periodic" or event.get("source") == "periodic_check":
                            # Only trust expiration detection from periodic checker
                            await self._handle_leader_expired(
                                service_name, instance_id, group_id, election
                            )
                            consecutive_errors = 0  # Reset error counter on successful handling
                        else:
                            # Log but ignore expired events from watch
                            if self._logger:
                                self._logger.info(
                                    "Ignoring expired event from watch (not from periodic checker). "
                                    "Will wait for periodic check to confirm expiration."
                                )

                    elif event.get("type") == "elected" and event.get("leader_id") != str(
                        instance_id
                    ):
                        # Check if the leader is actually still alive
                        # This handles the case where a leader crashes without cleanly releasing leadership
                        if not is_leader:
                            # Check heartbeat timestamp to see if leader is stale
                            metadata = event.get("metadata", {})
                            last_heartbeat = metadata.get("last_heartbeat", 0)

                            if self._logger:
                                self._logger.debug(
                                    f"Checking leader {event.get('leader_id')} health - "
                                    f"last_heartbeat={last_heartbeat}, metadata={metadata}"
                                )

                            if last_heartbeat:
                                import time

                                time_since_heartbeat = time.time() - last_heartbeat
                                # Use 1s threshold (minimum meaningful with 1s heartbeat)
                                expiry_threshold = 1.0

                                if self._logger:
                                    self._logger.debug(
                                        f"Leader heartbeat age: {time_since_heartbeat:.1f}s "
                                        f"(threshold: {expiry_threshold}s)"
                                    )

                                # If heartbeat is stale, treat as expired and attempt takeover
                                if time_since_heartbeat > expiry_threshold:
                                    if self._logger:
                                        self._logger.info(
                                            f"Detected stale leader {event.get('leader_id')} "
                                            f"(last heartbeat {time_since_heartbeat:.1f}s ago), attempting takeover"
                                        )
                                    await self._handle_leader_expired(
                                        service_name, instance_id, group_id, election
                                    )
                                    consecutive_errors = 0
                                    continue

                        # Another instance became leader (and is alive)
                        if is_leader:
                            if hasattr(election, "step_down"):
                                election.step_down("Another instance elected")
                            await self._update_instance_status(service_name, instance_id, "STANDBY")

                            # Notify status change via callback
                            if self._status_callback:
                                self._status_callback(False)

                            # Publish event
                            last_heartbeat = (
                                election.get("last_leader_heartbeat")
                                if isinstance(election, dict)
                                else getattr(election, "last_leader_heartbeat", None)
                            )
                            domain_event = LeaderLostEvent(
                                aggregate_id=f"{service_name}/{instance_id}",
                                service_name=str(service_name),
                                instance_id=str(instance_id),
                                group_id=group_id,
                                reason="Another instance elected",
                                lost_at=last_heartbeat,
                            )
                            # Convert DomainEvent to Event for message bus
                            event = Event(
                                domain="sticky_active",
                                event_type=domain_event.event_type,
                                payload=domain_event.model_dump(
                                    exclude={
                                        "event_id",
                                        "occurred_at",
                                        "aggregate_id",
                                        "aggregate_type",
                                        "event_type",
                                        "event_version",
                                    }
                                ),
                            )
                            await self._message_bus.publish_event(event)

                        # Save state only if election is not a dict (already stored)
                        if not isinstance(election, dict):
                            await self._election_repo.save_election_state(election)
            finally:
                # Always cancel both tasks
                watch_task.cancel()
                periodic_task.cancel()
                try:
                    await asyncio.gather(watch_task, periodic_task, return_exceptions=True)
                except asyncio.CancelledError:
                    pass

        except asyncio.CancelledError:
            if self._logger:
                self._logger.info(f"Monitoring cancelled for {service_name}/{instance_id}")
            raise
        except Exception as e:
            consecutive_errors += 1
            if self._logger:
                self._logger.exception(
                    f"Error in leadership monitoring (error {consecutive_errors}/{max_consecutive_errors}): {e}"
                )
            self._metrics.increment("sticky_active.monitoring.error")

            # If too many consecutive errors, stop monitoring
            if consecutive_errors >= max_consecutive_errors:
                if self._logger:
                    self._logger.error(
                        f"Too many consecutive monitoring errors for {service_name}/{instance_id}, stopping monitoring"
                    )
                self._metrics.increment("sticky_active.monitoring.stopped")
                raise RuntimeError(
                    f"Monitoring failed after {consecutive_errors} consecutive errors"
                ) from e

            # Otherwise, wait before retrying
            await asyncio.sleep(min(2**consecutive_errors, 30))  # Exponential backoff with max 30s

    async def _handle_leader_expired(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        election: StickyActiveElection,
    ) -> None:
        """Handle leader expiration and attempt failover."""
        # Leader expired, attempt to take over
        if self._logger:
            self._logger.warning(
                f"Leader expired for {service_name}/{group_id}, attempting takeover"
            )

        election.handle_leader_expired()

        # No delay - attempt immediate takeover for faster failover
        # await asyncio.sleep(1.0)  # Removed for sub-2s failover

        # Attempt election
        election.start_election()
        acquired = await self._election_repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            ttl_seconds=(
                election.leader_ttl_seconds if hasattr(election, "leader_ttl_seconds") else 2
            ),  # Use configured TTL or default to 2s
        )

        if acquired:
            election.win_election()
            self._metrics.increment("sticky_active.failover.success")

            # Start heartbeat immediately after becoming leader for fast TTL maintenance
            heartbeat_key = f"{service_name}/{instance_id}/{group_id}"
            if heartbeat_key in self._heartbeat_tasks:
                self._heartbeat_tasks[heartbeat_key].cancel()

            self._heartbeat_tasks[heartbeat_key] = asyncio.create_task(
                self._maintain_leadership_heartbeat(
                    service_name,
                    instance_id,
                    group_id,
                    (
                        election.leader_ttl_seconds
                        if hasattr(election, "leader_ttl_seconds")
                        else 2
                    ),  # Use configured TTL
                )
            )

            # Update service instance status
            await self._update_instance_status(service_name, instance_id, "ACTIVE")

            # Notify status change via callback
            if self._status_callback:
                self._status_callback(True)

            # Publish event
            await self._publish_leader_elected_event(service_name, instance_id, group_id, election)
        else:
            # Someone else won
            leader_id, _ = await self._election_repo.get_current_leader(service_name, group_id)
            if leader_id:
                election.lose_election(leader_id)
            self._metrics.increment("sticky_active.failover.lost")

        # Save state
        await self._election_repo.save_election_state(election)

    async def _publish_leader_elected_event(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        election: StickyActiveElection,
    ) -> None:
        """Publish leader elected event."""
        domain_event = LeaderElectedEvent(
            aggregate_id=f"{service_name}/{instance_id}",
            service_name=str(service_name),
            instance_id=str(instance_id),
            group_id=group_id,
            elected_at=election.became_leader_at,
        )
        # Convert DomainEvent to Event for message bus
        event = Event(
            domain="sticky_active",
            event_type=domain_event.event_type,
            payload=domain_event.model_dump(
                exclude={
                    "event_id",
                    "occurred_at",
                    "aggregate_id",
                    "aggregate_type",
                    "event_type",
                    "event_version",
                }
            ),
        )
        await self._message_bus.publish_event(event)

    async def _update_instance_status(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        status: str,
    ) -> None:
        """Update service instance sticky active status."""
        try:
            # Get current instance from registry
            instance = await self._service_registry.get_instance(
                str(service_name), str(instance_id)
            )

            if instance:
                instance.sticky_active_status = status
                # Re-register with updated status
                await self._service_registry.register(instance, 30)
        except Exception as e:
            if self._logger:
                self._logger.exception(f"Failed to update instance status: {e}")
            self._metrics.increment("sticky_active.status_update.error")
            # Non-critical error, don't propagate
