"""Bootstrap utilities for SDK initialization."""

from __future__ import annotations

from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.infrastructure.system_clock import SystemClock
from aegis_sdk.infrastructure.watchable_cached_service_discovery import (
    WatchableCachedServiceDiscovery,
)


async def bootstrap_sdk(nats_url: str, service_name: str) -> dict:
    """Bootstrap SDK with all necessary components.

    Args:
        nats_url: NATS connection URL
        service_name: Name of the service

    Returns:
        Dict with bootstrapped components
    """
    # Bootstrap defaults
    bootstrap_defaults()

    # Create NATS adapter and connect
    nats = NATSAdapter()
    await nats.connect(nats_url)

    # Create KV store for service registry
    kv_store = NATSKVStore(nats)
    await kv_store.connect("service_registry")

    # Create registry and discovery
    clock = SystemClock()
    logger = SimpleLogger()
    registry = KVServiceRegistry(kv_store, logger)  # KVServiceRegistry takes logger, not clock
    discovery = WatchableCachedServiceDiscovery(registry, clock)

    # Return components dict
    return {
        "message_bus": nats,
        "service_registry": registry,
        "service_discovery": discovery,
        "logger": logger,
        "clock": clock,
    }
