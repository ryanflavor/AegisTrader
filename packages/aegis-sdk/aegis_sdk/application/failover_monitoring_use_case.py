"""Enhanced monitoring use case with automatic failover support.

This module provides a monitoring use case that integrates HeartbeatMonitor
and ElectionCoordinator for automatic failover with sub-2-second recovery time.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..domain.enums import StickyActiveStatus
from ..domain.events import LeaderElectedEvent, LeaderLostEvent
from ..domain.models import Event
from ..domain.value_objects import (
    FailoverPolicy,
    InstanceId,
    ServiceName,
)
from ..infrastructure.election_coordinator import ElectionCoordinator
from ..infrastructure.heartbeat_monitor import HeartbeatMonitor
from ..ports.kv_store import KVStorePort
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from ..ports.service_registry import ServiceRegistryPort


class FailoverMonitoringUseCase:
    """Enhanced monitoring use case with automatic failover capabilities.

    Integrates HeartbeatMonitor and ElectionCoordinator to provide:
    - Sub-2-second failover detection and recovery
    - Automatic leader election on failure
    - Split-brain prevention
    - Comprehensive metrics and observability
    """

    def __init__(
        self,
        kv_store: KVStorePort,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
        failover_policy: FailoverPolicy | None = None,
        status_callback: Callable[[bool], None] | None = None,
    ):
        """Initialize the failover monitoring use case.

        Args:
            kv_store: KV Store for leader keys and heartbeats
            service_registry: Service registry port
            message_bus: Message bus for publishing events
            metrics: Metrics port
            logger: Logger port
            failover_policy: Failover behavior configuration
            status_callback: Optional callback for status changes (True=active, False=standby)
        """
        self._kv_store = kv_store
        self._service_registry = service_registry
        self._message_bus = message_bus
        self._metrics = metrics
        self._logger = logger
        self._failover_policy = failover_policy or FailoverPolicy.balanced()
        self._status_callback = status_callback

        # Component instances (created per service)
        self._monitors: dict[str, HeartbeatMonitor] = {}
        self._coordinators: dict[str, ElectionCoordinator] = {}
        self._monitoring_tasks: dict[str, asyncio.Task] = {}

    async def start_monitoring(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
    ) -> None:
        """Start monitoring with automatic failover for a service.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier
        """
        key = f"{service_name}/{instance_id}/{group_id}"

        # Cancel existing monitoring if any
        if key in self._monitoring_tasks:
            await self.stop_monitoring(service_name, instance_id, group_id)

        # Create value objects
        service_name_vo = ServiceName(value=service_name)
        instance_id_vo = InstanceId(value=instance_id)

        # Create HeartbeatMonitor
        heartbeat_monitor = HeartbeatMonitor(
            kv_store=self._kv_store,
            service_name=service_name_vo,
            instance_id=instance_id_vo,
            group_id=group_id,
            failover_policy=self._failover_policy,
            logger=self._logger,
        )

        # Create ElectionCoordinator
        election_coordinator = ElectionCoordinator(
            kv_store=self._kv_store,
            service_registry=self._service_registry,
            service_name=service_name_vo,
            instance_id=instance_id_vo,
            group_id=group_id,
            failover_policy=self._failover_policy,
            logger=self._logger,
        )

        # Connect components
        heartbeat_monitor.set_election_trigger(election_coordinator)
        election_coordinator.set_on_elected_callback(
            lambda: self._on_elected(service_name, instance_id, group_id)
        )
        election_coordinator.set_on_lost_callback(
            lambda: self._on_lost(service_name, instance_id, group_id)
        )

        # Store components
        self._monitors[key] = heartbeat_monitor
        self._coordinators[key] = election_coordinator

        # Start heartbeat monitoring
        await heartbeat_monitor.start_monitoring()

        # Check if we should participate in initial election
        await self._check_initial_election(
            election_coordinator, service_name, instance_id, group_id
        )

        await self._logger.info(
            "Started failover monitoring",
            service=service_name,
            instance=instance_id,
            group=group_id,
            failover_policy=self._failover_policy.mode,
        )

        # Track metrics
        self._metrics.increment("failover.monitoring.started")

    async def stop_monitoring(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
    ) -> None:
        """Stop monitoring for a service.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier
        """
        key = f"{service_name}/{instance_id}/{group_id}"

        # Stop heartbeat monitor
        if key in self._monitors:
            monitor = self._monitors[key]
            await monitor.stop_monitoring()
            del self._monitors[key]

        # Release leadership if held
        if key in self._coordinators:
            coordinator = self._coordinators[key]
            if coordinator.is_elected():
                await coordinator.release_leadership()
            del self._coordinators[key]

        # Cancel monitoring task
        if key in self._monitoring_tasks:
            task = self._monitoring_tasks[key]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._monitoring_tasks[key]

        await self._logger.info(
            "Stopped failover monitoring",
            service=service_name,
            instance=instance_id,
            group=group_id,
        )

        # Track metrics
        self._metrics.increment("failover.monitoring.stopped")

    async def stop_all_monitoring(self) -> None:
        """Stop all monitoring tasks.

        Stops all monitors, releases all held leadership positions,
        and cancels all monitoring tasks.
        """
        # Get all keys to stop
        keys_to_stop = list(self._monitoring_tasks.keys())

        # Stop each monitoring task
        for key in keys_to_stop:
            # Parse key to get components
            parts = key.split("/")
            if len(parts) == 3:
                service_name, instance_id, group_id = parts
                await self.stop_monitoring(service_name, instance_id, group_id)

        await self._logger.info("Stopped all monitoring tasks")

    async def get_status(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
    ) -> StickyActiveStatus:
        """Get the current status of a service instance.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier

        Returns:
            Current status of the service instance
        """
        key = f"{service_name}/{instance_id}/{group_id}"

        # Check if coordinator exists
        coordinator = self._coordinators.get(key)
        if not coordinator:
            return StickyActiveStatus.STANDBY

        # Check if elected as leader
        if (hasattr(coordinator, "is_leader") and coordinator.is_leader()) or (
            hasattr(coordinator, "is_elected") and coordinator.is_elected()
        ):
            return StickyActiveStatus.ACTIVE
        else:
            return StickyActiveStatus.STANDBY

    async def _check_initial_election(
        self,
        coordinator: ElectionCoordinator,
        service_name: str,
        instance_id: str,
        group_id: str,
    ) -> None:
        """Check if we should participate in initial election.

        Args:
            coordinator: Election coordinator
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier
        """
        # Check if there's already a leader
        is_leader_present = await coordinator.check_leadership()

        if not is_leader_present:
            # No leader exists - participate in election
            await self._logger.info(
                "No leader detected, initiating election",
                service=service_name,
                instance=instance_id,
                group=group_id,
            )

            # Start election
            elected = await coordinator.start_election()

            if elected:
                await self._logger.info(
                    "Won initial election",
                    service=service_name,
                    instance=instance_id,
                    group=group_id,
                )
            else:
                await self._logger.info(
                    "Lost initial election",
                    service=service_name,
                    instance=instance_id,
                    group=group_id,
                )

    async def _on_elected(self, service_name: str, instance_id: str, group_id: str) -> None:
        """Handle election as leader.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier
        """
        election_time = datetime.now(UTC)

        # Update service registry
        await self._update_instance_status(
            service_name, instance_id, StickyActiveStatus.ACTIVE.value
        )

        # Notify via callback
        if self._status_callback:
            self._status_callback(True)

        # Publish event
        domain_event = LeaderElectedEvent(
            aggregate_id=f"{service_name}/{instance_id}",
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            elected_at=election_time,
        )

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

        # Track metrics
        self._metrics.increment("failover.election.won")
        self._metrics.gauge("failover.active_instances", 1)

        await self._logger.info(
            "Became active leader",
            service=service_name,
            instance=instance_id,
            group=group_id,
        )

    async def _on_lost(self, service_name: str, instance_id: str, group_id: str) -> None:
        """Handle loss of leadership.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier
        """
        lost_time = datetime.now(UTC)

        # Update service registry
        await self._update_instance_status(
            service_name, instance_id, StickyActiveStatus.STANDBY.value
        )

        # Notify via callback
        if self._status_callback:
            self._status_callback(False)

        # Publish event
        domain_event = LeaderLostEvent(
            aggregate_id=f"{service_name}/{instance_id}",
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            reason="Leadership released",
            lost_at=lost_time,
        )

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

        # Track metrics
        self._metrics.increment("failover.leadership.lost")
        self._metrics.gauge("failover.active_instances", 0)

        await self._logger.info(
            "Lost leadership",
            service=service_name,
            instance=instance_id,
            group=group_id,
        )

    async def _update_instance_status(
        self,
        service_name: str,
        instance_id: str,
        sticky_status: str,
    ) -> None:
        """Update instance status in the service registry.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            sticky_status: New sticky active status
        """
        try:
            instance = await self._service_registry.get_instance(service_name, instance_id)

            if instance:
                instance.sticky_active_status = sticky_status
                instance.last_heartbeat = datetime.now(UTC)
                await self._service_registry.update_instance(instance)

                await self._logger.debug(
                    f"Updated instance status to {sticky_status}",
                    service=service_name,
                    instance=instance_id,
                )
            else:
                await self._logger.warning(
                    "Instance not found in registry",
                    service=service_name,
                    instance=instance_id,
                )
        except Exception as e:
            await self._logger.error(
                f"Failed to update instance status: {e}",
                service=service_name,
                instance=instance_id,
            )

    def get_monitoring_status(self) -> dict[str, Any]:
        """Get status of all monitored services.

        Returns:
            Dictionary with monitoring status for each service
        """
        status = {}

        for key in self._monitors:
            parts = key.split("/")
            if len(parts) == 3:
                service_name, instance_id, group_id = parts

                monitor = self._monitors.get(key)
                coordinator = self._coordinators.get(key)

                status[key] = {
                    "service": service_name,
                    "instance": instance_id,
                    "group": group_id,
                    "monitor_status": monitor.get_status() if monitor else None,
                    "election_state": (
                        coordinator.get_election_state().state if coordinator else None
                    ),
                    "is_leader": coordinator.is_elected() if coordinator else False,
                }

        return status

    async def trigger_manual_election(
        self,
        service_name: str,
        instance_id: str,
        group_id: str = "default",
    ) -> bool:
        """Manually trigger an election for testing purposes.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Sticky active group identifier

        Returns:
            True if elected as leader, False otherwise
        """
        key = f"{service_name}/{instance_id}/{group_id}"

        coordinator = self._coordinators.get(key)
        if not coordinator:
            await self._logger.warning(
                "No coordinator found for manual election",
                service=service_name,
                instance=instance_id,
                group=group_id,
            )
            return False

        await self._logger.info(
            "Manually triggering election",
            service=service_name,
            instance=instance_id,
            group=group_id,
        )

        return await coordinator.start_election()
