"""Bootstrap utilities for SDK initialization with hexagonal architecture."""

from __future__ import annotations

from typing import Any

from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.infrastructure.system_clock import SystemClock
from aegis_sdk.infrastructure.watchable_cached_service_discovery import (
    WatchableCachedServiceDiscovery,
)
from aegis_sdk.ports.clock import ClockPort
from aegis_sdk.ports.logger import LoggerPort as Logger
from aegis_sdk.ports.message_bus import MessageBusPort as MessageBus
from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort as ServiceDiscovery
from aegis_sdk.ports.service_registry import ServiceRegistryPort as ServiceRegistry
from pydantic import BaseModel, Field, field_validator


class BootstrapConfig(BaseModel):
    """Configuration for SDK bootstrap with strict validation."""

    nats_url: str = Field(..., description="NATS connection URL")
    service_name: str = Field(..., min_length=1, description="Name of the service")
    kv_bucket: str = Field(default="service_registry", description="KV bucket name")
    enable_watchable: bool = Field(default=True, description="Enable watchable discovery")

    @field_validator("nats_url")
    @classmethod
    def validate_nats_url(cls, v: str) -> str:
        """Validate NATS URL format."""
        if not v.startswith(("nats://", "tls://", "ws://", "wss://")):
            raise ValueError("NATS URL must start with nats://, tls://, ws://, or wss://")
        return v

    model_config = {"strict": True, "frozen": True}


class ServiceContext(BaseModel):
    """Service context with all bootstrapped components."""

    message_bus: MessageBus
    service_registry: ServiceRegistry
    service_discovery: ServiceDiscovery
    logger: Logger
    clock: ClockPort
    config: BootstrapConfig

    model_config = {"arbitrary_types_allowed": True}


async def bootstrap_sdk(config: BootstrapConfig) -> ServiceContext:
    """Bootstrap SDK with all necessary components following hexagonal architecture.

    This function initializes all infrastructure adapters and returns a context
    with properly typed ports that can be used by the application layer.

    Args:
        config: Bootstrap configuration with validated parameters

    Returns:
        ServiceContext with all bootstrapped components

    Raises:
        ConnectionError: If unable to connect to NATS
        ValueError: If configuration is invalid
    """
    # Bootstrap defaults
    bootstrap_defaults()

    # Create infrastructure adapters
    nats_adapter = NATSAdapter()
    await nats_adapter.connect(config.nats_url)

    # Create KV store for service registry
    kv_store = NATSKVStore(nats_adapter)
    await kv_store.connect(config.kv_bucket)

    # Create supporting infrastructure
    clock = SystemClock()
    logger = SimpleLogger()

    # Create registry and discovery
    registry = KVServiceRegistry(kv_store, logger)

    # Use appropriate discovery based on configuration
    if config.enable_watchable:
        discovery = WatchableCachedServiceDiscovery(registry, clock)
    else:
        from aegis_sdk.infrastructure.cached_service_discovery import (
            CachedServiceDiscovery,
        )

        discovery = CachedServiceDiscovery(registry, clock)

    # Return context with properly typed ports
    return ServiceContext(
        message_bus=nats_adapter,
        service_registry=registry,
        service_discovery=discovery,
        logger=logger,
        clock=clock,
        config=config,
    )


async def create_service_context(nats_url: str, service_name: str, **kwargs: Any) -> ServiceContext:
    """Convenience function to create a service context with minimal configuration.

    Args:
        nats_url: NATS connection URL
        service_name: Name of the service
        **kwargs: Additional configuration options

    Returns:
        ServiceContext with all bootstrapped components
    """
    config = BootstrapConfig(nats_url=nats_url, service_name=service_name, **kwargs)
    return await bootstrap_sdk(config)


async def cleanup_service_context(context: ServiceContext) -> None:
    """Clean up all resources in the service context.

    Args:
        context: Service context to clean up
    """
    if hasattr(context.message_bus, "close"):
        await context.message_bus.close()

    if hasattr(context.service_discovery, "close"):
        await context.service_discovery.close()
