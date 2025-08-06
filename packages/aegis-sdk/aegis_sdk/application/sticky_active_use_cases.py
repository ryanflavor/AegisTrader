"""Application use cases for sticky active service pattern.

This module contains application services that orchestrate sticky active
leader election and service registration with appropriate status updates.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

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
    """Request model for sticky active service registration."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    version: str = Field(..., description="Service version")
    group_id: str = Field(default="default", description="Sticky active group")
    ttl_seconds: int = Field(default=30, description="Registration TTL")
    leader_ttl_seconds: int = Field(default=5, description="Leader key TTL")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Service metadata")


class StickyActiveRegistrationResponse(BaseModel):
    """Response model for sticky active service registration."""

    service_name: str
    instance_id: str
    is_leader: bool
    sticky_active_status: str
    group_id: str


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

    async def execute(
        self, request: StickyActiveRegistrationRequest
    ) -> StickyActiveRegistrationResponse:
        """Register service and participate in sticky active election."""
        # Create value objects
        service_name = ServiceName(value=request.service_name)
        instance_id = InstanceId(value=request.instance_id)

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
        await self._election_repo.save_election_state(election)

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
        await self._service_registry.register(service_instance, request.ttl_seconds)

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


class StickyActiveHeartbeatRequest(BaseModel):
    """Request model for sticky active heartbeat."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    group_id: str = Field(default="default", description="Sticky active group")
    ttl_seconds: int = Field(default=30, description="Registration TTL")
    leader_ttl_seconds: int = Field(default=5, description="Leader key TTL")


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
        """Update heartbeat for both service instance and leader key."""
        # Create value objects
        service_name = ServiceName(value=request.service_name)
        instance_id = InstanceId(value=request.instance_id)

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
            # Get current instance from registry
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
            # Save election state
            await self._election_repo.save_election_state(election)


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

    async def start_monitoring(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
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

    async def _monitor_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> None:
        """Monitor leadership changes and handle failover."""
        try:
            async for event in self._election_repo.watch_leadership(service_name, group_id):
                if self._logger:
                    self._logger.info(
                        f"Leadership event: {event['type']} for {service_name}/{group_id}"
                    )

                # Load election state
                election = await self._election_repo.get_election_state(
                    service_name, instance_id, group_id
                )

                if not election:
                    continue

                if event["type"] == "expired" and not election.is_leader:
                    await self._handle_leader_expired(service_name, instance_id, group_id, election)

                elif event["type"] == "elected" and event["leader_id"] != str(instance_id):
                    # Another instance became leader
                    if election.is_leader:
                        election.step_down("Another instance elected")
                        await self._update_instance_status(service_name, instance_id, "STANDBY")

                        # Notify status change via callback
                        if self._status_callback:
                            self._status_callback(False)

                        # Publish event
                        domain_event = LeaderLostEvent(
                            aggregate_id=f"{service_name}/{instance_id}",
                            service_name=str(service_name),
                            instance_id=str(instance_id),
                            group_id=group_id,
                            reason="Another instance elected",
                            lost_at=election.last_leader_heartbeat,
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

                    # Save state
                    await self._election_repo.save_election_state(election)

        except asyncio.CancelledError:
            if self._logger:
                self._logger.info(f"Monitoring cancelled for {service_name}/{instance_id}")
            raise
        except Exception as e:
            if self._logger:
                self._logger.exception(f"Error in leadership monitoring: {e}")
            self._metrics.increment("sticky_active.monitoring.error")

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
            self._logger.info(f"Leader expired for {service_name}/{group_id}, attempting takeover")

        election.handle_leader_expired()

        # Wait for failover delay (1 second)
        await asyncio.sleep(1.0)

        # Attempt election
        election.start_election()
        acquired = await self._election_repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            ttl_seconds=election.leader_ttl_seconds,
        )

        if acquired:
            election.win_election()
            self._metrics.increment("sticky_active.failover.success")

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
            self._logger.exception(f"Failed to update instance status: {e}")
