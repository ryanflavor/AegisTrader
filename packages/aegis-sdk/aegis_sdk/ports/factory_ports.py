"""Factory interface definitions for the ports layer.

This module defines abstract factory interfaces following the Abstract Factory pattern.
These interfaces decouple the application layer from concrete infrastructure implementations,
ensuring proper dependency inversion in hexagonal architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..application.sticky_active_use_cases import (
        StickyActiveHeartbeatUseCase,
        StickyActiveMonitoringUseCase,
        StickyActiveRegistrationUseCase,
    )
    from .election_repository import ElectionRepository
    from .kv_store import KVStorePort
    from .logger import LoggerPort
    from .message_bus import MessageBusPort
    from .metrics import MetricsPort
    from .service_registry import ServiceRegistryPort


class ElectionRepositoryFactory(ABC):
    """Factory interface for creating election repositories.

    This factory abstracts the creation of election repository instances,
    allowing the application layer to remain independent of specific
    infrastructure implementations (e.g., NATS KV, Redis, etcd).
    """

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
    """Factory interface for creating KV stores.

    This factory abstracts the creation of key-value store instances,
    enabling the application to work with different KV store backends
    without coupling to specific implementations.
    """

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
    """Factory interface for creating use cases.

    This factory abstracts the creation of use case instances,
    allowing for different implementations and configurations
    without affecting the application layer's core logic.
    """

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
