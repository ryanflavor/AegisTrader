"""Dependency provider for application layer.

This module provides a clean way to access default implementations without
the application layer directly importing from infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ..ports.factory_ports import (
        ElectionRepositoryFactory,
        KVStoreFactory,
        UseCaseFactory,
    )
    from ..ports.metrics import MetricsPort


class DependencyProvider:
    """Registry for default dependency implementations.

    This class acts as a service locator that allows the infrastructure layer
    to register default implementations that the application layer can use
    without directly importing from infrastructure.
    """

    _default_election_factory: ClassVar[ElectionRepositoryFactory | None] = None
    _default_use_case_factory: ClassVar[UseCaseFactory | None] = None
    _default_kv_store_factory: ClassVar[KVStoreFactory | None] = None
    _default_metrics: ClassVar[type[MetricsPort] | None] = None

    @classmethod
    def register_defaults(
        cls,
        election_factory: ElectionRepositoryFactory | None = None,
        use_case_factory: UseCaseFactory | None = None,
        kv_store_factory: KVStoreFactory | None = None,
        metrics_class: type[MetricsPort] | None = None,
    ) -> None:
        """Register default implementations.

        This method should be called by the infrastructure layer during
        application initialization.

        Args:
            election_factory: Default election repository factory
            use_case_factory: Default use case factory
            kv_store_factory: Default KV store factory
            metrics_class: Default metrics class
        """
        if election_factory:
            cls._default_election_factory = election_factory
        if use_case_factory:
            cls._default_use_case_factory = use_case_factory
        if kv_store_factory:
            cls._default_kv_store_factory = kv_store_factory
        if metrics_class:
            cls._default_metrics = metrics_class

    @classmethod
    def get_default_election_factory(cls) -> ElectionRepositoryFactory:
        """Get the default election repository factory.

        Returns:
            The registered default election factory

        Raises:
            RuntimeError: If no default factory has been registered
        """
        if cls._default_election_factory is None:
            raise RuntimeError(
                "No default election factory registered. "
                "Call DependencyProvider.register_defaults() during application initialization."
            )
        return cls._default_election_factory

    @classmethod
    def get_default_use_case_factory(cls) -> UseCaseFactory:
        """Get the default use case factory.

        Returns:
            The registered default use case factory

        Raises:
            RuntimeError: If no default factory has been registered
        """
        if cls._default_use_case_factory is None:
            raise RuntimeError(
                "No default use case factory registered. "
                "Call DependencyProvider.register_defaults() during application initialization."
            )
        return cls._default_use_case_factory

    @classmethod
    def get_default_kv_store_factory(cls) -> KVStoreFactory:
        """Get the default KV store factory.

        Returns:
            The registered default KV store factory

        Raises:
            RuntimeError: If no default factory has been registered
        """
        if cls._default_kv_store_factory is None:
            raise RuntimeError(
                "No default KV store factory registered. "
                "Call DependencyProvider.register_defaults() during application initialization."
            )
        return cls._default_kv_store_factory

    @classmethod
    def get_default_metrics(cls) -> MetricsPort:
        """Get a default metrics instance.

        Returns:
            A new instance of the registered default metrics class

        Raises:
            RuntimeError: If no default metrics class has been registered
        """
        if cls._default_metrics is None:
            raise RuntimeError(
                "No default metrics class registered. "
                "Call DependencyProvider.register_defaults() during application initialization."
            )
        return cls._default_metrics()

    @classmethod
    def reset(cls) -> None:
        """Reset all registered defaults.

        This is mainly useful for testing.
        """
        cls._default_election_factory = None
        cls._default_use_case_factory = None
        cls._default_kv_store_factory = None
        cls._default_metrics = None
