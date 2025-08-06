"""Ports layer - Interfaces for external communication."""

from .factory_ports import ElectionRepositoryFactory, KVStoreFactory, UseCaseFactory
from .kv_store import KVStorePort
from .logger import LoggerPort
from .message_bus import MessageBusPort
from .metrics import MetricsPort
from .service_discovery import InstanceSelector, SelectionStrategy, ServiceDiscoveryPort
from .service_registry import ServiceRegistryPort

__all__ = [
    "ElectionRepositoryFactory",
    "InstanceSelector",
    "KVStoreFactory",
    "KVStorePort",
    "LoggerPort",
    "MessageBusPort",
    "MetricsPort",
    "SelectionStrategy",
    "ServiceDiscoveryPort",
    "ServiceRegistryPort",
    "UseCaseFactory",
]
