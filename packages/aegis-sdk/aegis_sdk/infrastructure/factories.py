"""Factory classes for infrastructure layer following factory pattern."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from ..domain.models import KVOptions
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from .serialization import (
    deserialize_from_json,
    deserialize_from_msgpack,
    serialize_to_json,
    serialize_to_msgpack,
)

T = TypeVar("T", bound=BaseModel)


class Serializer(Protocol):
    """Protocol for serializers."""

    def serialize(self, obj: BaseModel) -> bytes:
        """Serialize a Pydantic model to bytes."""
        ...

    def deserialize(self, data: bytes, model_class: type[T]) -> T:
        """Deserialize bytes to a Pydantic model."""
        ...


class JSONSerializer:
    """JSON serializer implementation."""

    def serialize(self, obj: BaseModel) -> bytes:
        """Serialize using JSON."""
        return serialize_to_json(obj)

    def deserialize(self, data: bytes, model_class: type[T]) -> T:
        """Deserialize from JSON."""
        return deserialize_from_json(data, model_class)


class MessagePackSerializer:
    """MessagePack serializer implementation."""

    def serialize(self, obj: BaseModel) -> bytes:
        """Serialize using MessagePack."""
        return serialize_to_msgpack(obj)

    def deserialize(self, data: bytes, model_class: type[T]) -> T:
        """Deserialize from MessagePack."""
        return deserialize_from_msgpack(data, model_class)


class SerializationFactory:
    """Factory for creating serializers with consistent configuration.

    This factory ensures that serialization is handled consistently
    across the infrastructure layer, providing a single point of
    configuration for serialization strategies.
    """

    @staticmethod
    def create_serializer(use_msgpack: bool = True) -> Serializer:
        """Create a serializer based on configuration.

        Args:
            use_msgpack: Whether to use MessagePack (True) or JSON (False)

        Returns:
            Configured serializer instance
        """
        if use_msgpack:
            return MessagePackSerializer()
        return JSONSerializer()

    @staticmethod
    def create_default_serializer() -> Serializer:
        """Create the default serializer (MessagePack)."""
        return MessagePackSerializer()

    @staticmethod
    def create_json_serializer() -> Serializer:
        """Create a JSON serializer."""
        return JSONSerializer()

    @staticmethod
    def create_msgpack_serializer() -> Serializer:
        """Create a MessagePack serializer."""
        return MessagePackSerializer()


class KVOptionsFactory:
    """Factory for creating common KV operation options.

    Provides convenient methods for creating KVOptions with
    common configurations, reducing boilerplate and ensuring
    consistency in KV operations.
    """

    @staticmethod
    def create_with_ttl(ttl_seconds: int) -> KVOptions:
        """Create options with TTL only.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            KVOptions configured with TTL
        """
        return KVOptions(ttl=ttl_seconds)

    @staticmethod
    def create_exclusive() -> KVOptions:
        """Create options for exclusive creation (fail if exists)."""
        return KVOptions(create_only=True)

    @staticmethod
    def create_update_only(revision: int | None = None) -> KVOptions:
        """Create options for update only (fail if doesn't exist).

        Args:
            revision: Optional revision for optimistic concurrency control

        Returns:
            KVOptions configured for update only
        """
        return KVOptions(update_only=True, revision=revision)

    @staticmethod
    def create_with_revision(revision: int) -> KVOptions:
        """Create options with revision check for optimistic concurrency.

        Args:
            revision: Expected revision number

        Returns:
            KVOptions configured with revision check
        """
        return KVOptions(revision=revision)

    @staticmethod
    def create_ephemeral(ttl_seconds: int = 30) -> KVOptions:
        """Create options for ephemeral entries with short TTL.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 30)

        Returns:
            KVOptions configured for ephemeral storage
        """
        return KVOptions(ttl=ttl_seconds)

    @staticmethod
    def create_persistent() -> KVOptions:
        """Create options for persistent storage (no TTL)."""
        return KVOptions()

    @staticmethod
    def create_session(session_ttl: int = 3600) -> KVOptions:
        """Create options for session storage with appropriate TTL.

        Args:
            session_ttl: Session TTL in seconds (default: 1 hour)

        Returns:
            KVOptions configured for session storage
        """
        return KVOptions(ttl=session_ttl)

    @staticmethod
    def create_cache(cache_ttl: int = 300) -> KVOptions:
        """Create options for cache entries with moderate TTL.

        Args:
            cache_ttl: Cache TTL in seconds (default: 5 minutes)

        Returns:
            KVOptions configured for caching
        """
        return KVOptions(ttl=cache_ttl)


class DiscoveryRequestFactory:
    """Factory for creating service discovery requests.

    Provides consistent ways to create discovery requests for
    different use cases in the service discovery system.
    """

    @staticmethod
    def create_by_name(service_name: str) -> dict[str, Any]:
        """Create a discovery request by service name.

        Args:
            service_name: Name of the service to discover

        Returns:
            Discovery request parameters
        """
        return {
            "service_name": service_name,
            "filter": {"status": "ACTIVE"},
        }

    @staticmethod
    def create_by_group(sticky_group: str) -> dict[str, Any]:
        """Create a discovery request by sticky active group.

        Args:
            sticky_group: Sticky active group identifier

        Returns:
            Discovery request parameters
        """
        return {
            "filter": {
                "sticky_active_group": sticky_group,
                "status": "ACTIVE",
            }
        }

    @staticmethod
    def create_all_instances(service_name: str) -> dict[str, Any]:
        """Create a discovery request for all instances (including unhealthy).

        Args:
            service_name: Name of the service to discover

        Returns:
            Discovery request parameters
        """
        return {
            "service_name": service_name,
            "include_unhealthy": True,
        }

    @staticmethod
    def create_healthy_only(service_name: str) -> dict[str, Any]:
        """Create a discovery request for healthy instances only.

        Args:
            service_name: Name of the service to discover

        Returns:
            Discovery request parameters
        """
        return {
            "service_name": service_name,
            "filter": {"status": ["ACTIVE", "STANDBY"]},
        }

    @staticmethod
    def create_with_metadata(service_name: str, metadata_filters: dict[str, Any]) -> dict[str, Any]:
        """Create a discovery request with metadata filters.

        Args:
            service_name: Name of the service to discover
            metadata_filters: Metadata key-value pairs to filter by

        Returns:
            Discovery request parameters
        """
        return {
            "service_name": service_name,
            "filter": {
                "status": "ACTIVE",
                "metadata": metadata_filters,
            },
        }


def create_service_dependencies(
    message_bus: MessageBusPort,
    *,
    logger: LoggerPort | None = None,
    metrics: MetricsPort | None = None,
    enable_discovery: bool = True,
    enable_registry: bool = True,
) -> dict[str, Any]:
    """Create common service dependencies with sensible defaults.

    Args:
        message_bus: The message bus adapter
        logger: Optional logger (creates SimpleLogger if None)
        metrics: Optional metrics (creates InMemoryMetrics if None)
        enable_discovery: Whether to create service discovery
        enable_registry: Whether to create service registry

    Returns:
        Dictionary with configured dependencies
    """
    from .basic_service_discovery import BasicServiceDiscovery
    from .kv_service_registry import KVServiceRegistry
    from .logger import SimpleLogger
    from .metrics import InMemoryMetrics
    from .nats_kv_store import NATSKVStore

    deps: dict[str, Any] = {}

    # Create default logger if not provided
    if logger is None:
        logger = SimpleLogger("aegis_sdk")
    deps["logger"] = logger

    # Create default metrics if not provided
    if metrics is None:
        metrics = InMemoryMetrics()
    deps["metrics"] = metrics

    # Create service discovery if enabled
    if enable_discovery:
        deps["service_discovery"] = BasicServiceDiscovery(service_registry=None, logger=logger)

    # Create service registry if enabled
    if enable_registry:
        # Registry needs a KV store
        kv_store = NATSKVStore(nats_adapter=message_bus)
        deps["kv_store"] = kv_store
        deps["service_registry"] = KVServiceRegistry(kv_store, logger=logger)

    return deps
