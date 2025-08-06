"""Concrete factory implementations for the infrastructure layer.

This module provides concrete implementations of the factory interfaces
defined in the ports layer. These implementations create actual infrastructure
components while respecting the dependency inversion principle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..ports.factory_ports import ElectionRepositoryFactory, KVStoreFactory, UseCaseFactory

if TYPE_CHECKING:
    from ..application.sticky_active_use_cases import (
        StickyActiveHeartbeatUseCase,
        StickyActiveMonitoringUseCase,
        StickyActiveRegistrationUseCase,
    )
    from ..ports.election_repository import ElectionRepository
    from ..ports.kv_store import KVStorePort
    from ..ports.logger import LoggerPort
    from ..ports.message_bus import MessageBusPort
    from ..ports.metrics import MetricsPort
    from ..ports.service_registry import ServiceRegistryPort


class DefaultElectionRepositoryFactory(ElectionRepositoryFactory):
    """Default implementation of ElectionRepositoryFactory using NATS KV.

    This concrete factory creates NATS-based election repositories,
    providing the infrastructure-specific implementation while
    adhering to the port interface contract.
    """

    async def create_election_repository(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        logger: LoggerPort | None = None,
    ) -> ElectionRepository:
        """Create a NATS-based election repository.

        Args:
            service_name: Name of the service for the election
            message_bus: Message bus for KV store operations
            logger: Optional logger instance

        Returns:
            NATS KV-based election repository instance
        """
        from .nats_kv_election_repository import NatsKvElectionRepository
        from .nats_kv_store import NATSKVStore

        kv_store = NATSKVStore(nats_adapter=message_bus)
        # Replace hyphens with underscores for valid bucket name
        bucket_name = f"election_{service_name}".replace("-", "_")
        await kv_store.connect(bucket_name, enable_ttl=True)

        return NatsKvElectionRepository(
            kv_store=kv_store,
            logger=logger,
        )


class DefaultKVStoreFactory(KVStoreFactory):
    """Default implementation of KVStoreFactory using NATS KV.

    This concrete factory creates NATS-based KV stores,
    providing the infrastructure-specific implementation.
    """

    async def create_kv_store(
        self,
        bucket_name: str,
        message_bus: MessageBusPort,
        enable_ttl: bool = True,
    ) -> KVStorePort:
        """Create a NATS-based KV store.

        Args:
            bucket_name: Name of the KV bucket
            message_bus: Message bus for KV operations
            enable_ttl: Whether to enable TTL support

        Returns:
            Connected NATS KV store instance
        """
        from .nats_kv_store import NATSKVStore

        kv_store = NATSKVStore(nats_adapter=message_bus)
        # Ensure bucket name is valid (replace hyphens with underscores)
        safe_bucket_name = bucket_name.replace("-", "_")
        await kv_store.connect(safe_bucket_name, enable_ttl=enable_ttl)
        return kv_store


class DefaultUseCaseFactory(UseCaseFactory):
    """Default implementation of UseCaseFactory.

    This concrete factory creates standard use case instances,
    wiring them with the provided dependencies while keeping
    the application layer decoupled from infrastructure concerns.
    """

    def create_registration_use_case(
        self,
        election_repository: ElectionRepository,
        service_registry: ServiceRegistryPort,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        logger: LoggerPort,
    ) -> StickyActiveRegistrationUseCase:
        """Create a default registration use case.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            message_bus: Message bus for events
            metrics: Metrics port
            logger: Logger port

        Returns:
            Configured registration use case instance
        """
        from ..application.sticky_active_use_cases import StickyActiveRegistrationUseCase

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
        """Create a default heartbeat use case.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            metrics: Metrics port
            logger: Logger port

        Returns:
            Configured heartbeat use case instance
        """
        from ..application.sticky_active_use_cases import StickyActiveHeartbeatUseCase

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
        """Create a default monitoring use case.

        Args:
            election_repository: Repository for election state
            service_registry: Service registry port
            message_bus: Message bus for events
            metrics: Metrics port
            logger: Logger port
            status_callback: Optional callback for status changes

        Returns:
            Configured monitoring use case instance
        """
        from ..application.sticky_active_use_cases import StickyActiveMonitoringUseCase

        return StickyActiveMonitoringUseCase(
            election_repository=election_repository,
            service_registry=service_registry,
            message_bus=message_bus,
            metrics=metrics,
            logger=logger,
            status_callback=status_callback,
        )


class RedisElectionRepositoryFactory(ElectionRepositoryFactory):
    """Redis implementation of ElectionRepositoryFactory.

    This is an example of how alternative infrastructure implementations
    can be provided while maintaining the same interface contract.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize the Redis factory.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url

    async def create_election_repository(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        logger: LoggerPort | None = None,
    ) -> ElectionRepository:
        """Create a Redis-based election repository.

        This is a placeholder implementation showing how alternative
        backends could be integrated.

        Args:
            service_name: Name of the service for the election
            message_bus: Message bus (may not be used for Redis)
            logger: Optional logger instance

        Returns:
            Redis-based election repository instance

        Raises:
            NotImplementedError: Redis implementation not yet available
        """
        # This would create a Redis-based implementation
        # For now, raise NotImplementedError to show the pattern
        raise NotImplementedError(
            "Redis election repository not yet implemented. "
            "This factory demonstrates how alternative implementations "
            "can be provided while maintaining the same interface."
        )
