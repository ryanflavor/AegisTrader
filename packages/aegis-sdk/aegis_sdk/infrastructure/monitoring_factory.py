"""Concrete factory implementation for monitoring components.

This module provides the concrete implementation of the MonitoringComponentFactory
interface, creating actual HeartbeatMonitor and ElectionCoordinator instances.
"""

from __future__ import annotations

from ..domain.value_objects import FailoverPolicy, InstanceId, ServiceName
from ..ports.factory_ports import MonitoringComponentFactory
from ..ports.kv_store import KVStorePort
from ..ports.logger import LoggerPort
from ..ports.monitoring import ElectionCoordinatorPort, HeartbeatMonitorPort
from ..ports.service_registry import ServiceRegistryPort
from .election_coordinator import ElectionCoordinator
from .heartbeat_monitor import HeartbeatMonitor


class ConcreteMonitoringFactory(MonitoringComponentFactory):
    """Concrete implementation of the monitoring component factory.

    This factory creates actual HeartbeatMonitor and ElectionCoordinator
    instances while maintaining the interface contract.
    """

    def create_heartbeat_monitor(
        self,
        kv_store: KVStorePort,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        failover_policy: FailoverPolicy,
        logger: LoggerPort,
    ) -> HeartbeatMonitorPort:
        """Create a concrete HeartbeatMonitor instance.

        Args:
            kv_store: KV Store for heartbeat storage
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Service group identifier
            failover_policy: Failover behavior configuration
            logger: Logger port

        Returns:
            HeartbeatMonitor instance implementing HeartbeatMonitorPort
        """
        return HeartbeatMonitor(
            kv_store=kv_store,
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            failover_policy=failover_policy,
            logger=logger,
        )

    def create_election_coordinator(
        self,
        kv_store: KVStorePort,
        service_registry: ServiceRegistryPort,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        failover_policy: FailoverPolicy,
        logger: LoggerPort,
    ) -> ElectionCoordinatorPort:
        """Create a concrete ElectionCoordinator instance.

        Args:
            kv_store: KV Store for election state
            service_registry: Service registry port
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Service group identifier
            failover_policy: Failover behavior configuration
            logger: Logger port

        Returns:
            ElectionCoordinator instance implementing ElectionCoordinatorPort
        """
        return ElectionCoordinator(
            kv_store=kv_store,
            service_registry=service_registry,
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            failover_policy=failover_policy,
            logger=logger,
        )
