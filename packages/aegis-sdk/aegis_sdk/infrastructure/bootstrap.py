"""Bootstrap module for initializing default dependencies.

This module is responsible for registering default implementations
with the application layer's DependencyProvider.
"""

from ..application.dependency_provider import DependencyProvider
from .application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultKVStoreFactory,
    DefaultUseCaseFactory,
)
from .in_memory_metrics import InMemoryMetrics


def bootstrap_defaults() -> None:
    """Bootstrap default dependency implementations.

    This function should be called during application initialization
    to register default implementations that the application layer can use.
    """
    DependencyProvider.register_defaults(
        election_factory=DefaultElectionRepositoryFactory(),
        use_case_factory=DefaultUseCaseFactory(),
        kv_store_factory=DefaultKVStoreFactory(),
        metrics_class=InMemoryMetrics,
    )


def reset_defaults() -> None:
    """Reset all registered defaults.

    This is mainly useful for testing.
    """
    DependencyProvider.reset()
