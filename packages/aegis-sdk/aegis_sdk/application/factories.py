"""Factory interfaces for creating application dependencies.

This module defines factory interfaces following the Abstract Factory pattern
to decouple the application layer from concrete infrastructure implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports.election_repository import ElectionRepository
    from ..ports.kv_store import KVStorePort
    from ..ports.logger import LoggerPort
    from ..ports.message_bus import MessageBusPort
    from ..ports.metrics import MetricsPort
    from ..ports.service_registry import ServiceRegistryPort
    from .sticky_active_use_cases import (
        StickyActiveHeartbeatUseCase,
        StickyActiveMonitoringUseCase,
        StickyActiveRegistrationUseCase,
    )


class ElectionRepositoryFactory(ABC):
    """Factory interface for creating election repositories."""

    @abstractmethod
    async def create_election_repository(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        logger: LoggerPort | None = None,
    ) -> ElectionRepository:
        """Create an election repository instance.

        Args:
            service_name: Name of the service for the election
            message_bus: Message bus for KV store operations
            logger: Optional logger instance

        Returns:
            Configured election repository instance
        """
        ...


class KVStoreFactory(ABC):
    """Factory interface for creating KV stores."""

    @abstractmethod
    async def create_kv_store(
        self,
        bucket_name: str,
        message_bus: MessageBusPort,
        enable_ttl: bool = True,
    ) -> KVStorePort:
        """Create a KV store instance.

        Args:
            bucket_name: Name of the KV bucket
            message_bus: Message bus for KV operations
            enable_ttl: Whether to enable TTL support

        Returns:
            Connected KV store instance
        """
        ...


class UseCaseFactory(ABC):
    """Factory interface for creating use cases."""

    @abstractmethod
    def create_registration_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ) -> StickyActiveRegistrationUseCase:
        """Create a registration use case instance.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            message_bus: Message bus for events
            metrics: Metrics port
            logger: Logger port

        Returns:
            Registration use case instance
        """
        ...

    @abstractmethod
    def create_heartbeat_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ) -> StickyActiveHeartbeatUseCase:
        """Create a heartbeat use case instance.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            metrics: Metrics port
            logger: Logger port

        Returns:
            Heartbeat use case instance
        """
        ...

    @abstractmethod
    def create_monitoring_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
        status_callback: Callable[[bool], None] | None = None,
    ) -> StickyActiveMonitoringUseCase:
        """Create a monitoring use case instance.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            message_bus: Message bus for events
            metrics: Metrics port
            logger: Logger port
            status_callback: Optional callback for status changes

        Returns:
            Monitoring use case instance
        """
        ...


class DefaultElectionRepositoryFactory(ElectionRepositoryFactory):
    """Default implementation of ElectionRepositoryFactory using NATS KV."""

    async def create_election_repository(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        logger: LoggerPort | None = None,
    ) -> ElectionRepository:
        """Create a NATS-based election repository."""
        from ..infrastructure.nats_kv_election_repository import NatsKvElectionRepository
        from ..infrastructure.nats_kv_store import NATSKVStore

        kv_store = NATSKVStore(nats_adapter=message_bus)
        # Replace hyphens with underscores for valid bucket name
        bucket_name = f"election_{service_name}".replace("-", "_")
        await kv_store.connect(bucket_name, enable_ttl=True)

        return NatsKvElectionRepository(
            kv_store=kv_store,
            logger=logger,
        )


class DefaultUseCaseFactory(UseCaseFactory):
    """Default implementation of UseCaseFactory."""

    def create_registration_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ) -> StickyActiveRegistrationUseCase:
        """Create a default registration use case."""
        from .sticky_active_use_cases import StickyActiveRegistrationUseCase

        return StickyActiveRegistrationUseCase(
            election_repository=election_repository,
            service_registry=service_registry,
            message_bus=message_bus,
            metrics=metrics,
            logger=logger,
        )

    def create_heartbeat_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ) -> StickyActiveHeartbeatUseCase:
        """Create a default heartbeat use case."""
        from .sticky_active_use_cases import StickyActiveHeartbeatUseCase

        return StickyActiveHeartbeatUseCase(
            election_repository=election_repository,
            service_registry=service_registry,
            metrics=metrics,
            logger=logger,
        )

    def create_monitoring_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
        status_callback: Callable[[bool], None] | None = None,
    ) -> StickyActiveMonitoringUseCase:
        """Create a default monitoring use case."""
        from .sticky_active_use_cases import StickyActiveMonitoringUseCase

        return StickyActiveMonitoringUseCase(
            election_repository=election_repository,
            service_registry=service_registry,
            message_bus=message_bus,
            metrics=metrics,
            logger=logger,
            status_callback=status_callback,
        )
