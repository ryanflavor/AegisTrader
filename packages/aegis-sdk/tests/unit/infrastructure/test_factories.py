"""Unit tests for infrastructure factory classes."""

from unittest.mock import MagicMock

import pytest

from aegis_sdk.domain.models import Event, KVOptions, RPCRequest
from aegis_sdk.infrastructure.factories import (
    DiscoveryRequestFactory,
    JSONSerializer,
    KVOptionsFactory,
    MessagePackSerializer,
    SerializationFactory,
    create_service_dependencies,
)


class TestSerializationFactory:
    """Tests for serialization factory."""

    def test_create_default_serializer(self):
        """Test creating default serializer (MessagePack)."""
        serializer = SerializationFactory.create_default_serializer()
        assert isinstance(serializer, MessagePackSerializer)

    def test_create_json_serializer(self):
        """Test creating JSON serializer."""
        serializer = SerializationFactory.create_json_serializer()
        assert isinstance(serializer, JSONSerializer)

    def test_create_msgpack_serializer(self):
        """Test creating MessagePack serializer."""
        serializer = SerializationFactory.create_msgpack_serializer()
        assert isinstance(serializer, MessagePackSerializer)

    def test_create_serializer_with_msgpack(self):
        """Test creating serializer with MessagePack option."""
        serializer = SerializationFactory.create_serializer(use_msgpack=True)
        assert isinstance(serializer, MessagePackSerializer)

    def test_create_serializer_with_json(self):
        """Test creating serializer with JSON option."""
        serializer = SerializationFactory.create_serializer(use_msgpack=False)
        assert isinstance(serializer, JSONSerializer)


class TestJSONSerializer:
    """Tests for JSON serializer."""

    def test_serialize_event(self):
        """Test serializing an event to JSON."""
        event = Event(
            domain="test",
            event_type="created",
            payload={"id": 123, "name": "test"},
        )
        serializer = JSONSerializer()
        data = serializer.serialize(event)

        assert isinstance(data, bytes)
        # Check it's valid JSON
        import json

        parsed = json.loads(data.decode())
        assert parsed["domain"] == "test"
        assert parsed["event_type"] == "created"
        assert parsed["payload"] == {"id": 123, "name": "test"}

    def test_deserialize_event(self):
        """Test deserializing JSON to an event."""
        json_data = b'{"domain": "test", "event_type": "updated", "payload": {"value": 42}}'
        serializer = JSONSerializer()
        event = serializer.deserialize(json_data, Event)

        assert isinstance(event, Event)
        assert event.domain == "test"
        assert event.event_type == "updated"
        assert event.payload == {"value": 42}

    def test_round_trip(self):
        """Test serialization round trip."""
        original = RPCRequest(
            method="testMethod",
            params={"param1": "value1", "param2": 123},
            timeout=10.0,
        )
        serializer = JSONSerializer()

        # Serialize and deserialize
        data = serializer.serialize(original)
        result = serializer.deserialize(data, RPCRequest)

        assert result.method == original.method
        assert result.params == original.params
        assert result.timeout == original.timeout
        assert result.message_id == original.message_id


class TestMessagePackSerializer:
    """Tests for MessagePack serializer."""

    def test_serialize_event(self):
        """Test serializing an event to MessagePack."""
        event = Event(
            domain="test",
            event_type="created",
            payload={"id": 123, "name": "test"},
        )
        serializer = MessagePackSerializer()
        data = serializer.serialize(event)

        assert isinstance(data, bytes)
        # Check it's valid MessagePack
        import msgpack

        parsed = msgpack.unpackb(data, raw=False)
        assert parsed["domain"] == "test"
        assert parsed["event_type"] == "created"
        assert parsed["payload"] == {"id": 123, "name": "test"}

    def test_deserialize_event(self):
        """Test deserializing MessagePack to an event."""
        import msgpack

        event_dict = {
            "domain": "test",
            "event_type": "deleted",
            "payload": {"id": 456},
            "message_id": "test-123",
            "trace_id": "trace-456",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
        }
        msgpack_data = msgpack.packb(event_dict, use_bin_type=True)

        serializer = MessagePackSerializer()
        event = serializer.deserialize(msgpack_data, Event)

        assert isinstance(event, Event)
        assert event.domain == "test"
        assert event.event_type == "deleted"
        assert event.payload == {"id": 456}

    def test_round_trip(self):
        """Test serialization round trip."""
        original = RPCRequest(
            method="testMethod",
            params={"param1": "value1", "param2": 123},
            timeout=10.0,
        )
        serializer = MessagePackSerializer()

        # Serialize and deserialize
        data = serializer.serialize(original)
        result = serializer.deserialize(data, RPCRequest)

        assert result.method == original.method
        assert result.params == original.params
        assert result.timeout == original.timeout
        assert result.message_id == original.message_id


class TestKVOptionsFactory:
    """Tests for KV options factory."""

    def test_create_persistent(self):
        """Test creating persistent options (no TTL)."""
        options = KVOptionsFactory.create_persistent()
        # TTL field has been removed - use stream-level TTL instead
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

    def test_create_exclusive(self):
        """Test creating exclusive options."""
        options = KVOptionsFactory.create_exclusive()
        assert options.create_only is True
        assert options.update_only is False
        # TTL field has been removed
        assert options.revision is None

    def test_create_update_only(self):
        """Test creating update-only options."""
        options = KVOptionsFactory.create_update_only()
        assert options.update_only is True
        assert options.create_only is False
        assert options.revision is None

    def test_create_update_only_with_revision(self):
        """Test creating update-only options with revision."""
        options = KVOptionsFactory.create_update_only(revision=42)
        assert options.update_only is True
        assert options.revision == 42

    def test_create_with_revision(self):
        """Test creating options with revision check."""
        options = KVOptionsFactory.create_with_revision(123)
        assert options.revision == 123
        assert options.create_only is False
        assert options.update_only is False

    def test_create_ephemeral(self):
        """Test creating ephemeral options."""
        # TTL parameter is ignored - use stream-level TTL configuration
        options = KVOptionsFactory.create_ephemeral()
        # TTL field has been removed from KVOptions
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

        # Custom TTL parameter is ignored but method still works
        options = KVOptionsFactory.create_ephemeral(ttl_seconds=60)
        # TTL field has been removed from KVOptions
        assert options.revision is None

    def test_create_session(self):
        """Test creating session options."""
        # TTL parameter is ignored - use stream-level TTL configuration
        options = KVOptionsFactory.create_session()
        # TTL field has been removed from KVOptions
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

        # Custom TTL parameter is ignored but method still works
        options = KVOptionsFactory.create_session(session_ttl=7200)
        # TTL field has been removed from KVOptions
        assert options.revision is None

    def test_create_cache(self):
        """Test creating cache options."""
        # TTL parameter is ignored - use stream-level TTL configuration
        options = KVOptionsFactory.create_cache()
        # TTL field has been removed from KVOptions
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

        # Custom TTL parameter is ignored but method still works
        options = KVOptionsFactory.create_cache(cache_ttl=600)
        # TTL field has been removed from KVOptions
        assert options.revision is None

    def test_factory_methods_return_kvoptions(self):
        """Test all factory methods return KVOptions instances."""
        methods = [
            KVOptionsFactory.create_exclusive,
            KVOptionsFactory.create_update_only,
            lambda: KVOptionsFactory.create_with_revision(1),
            KVOptionsFactory.create_ephemeral,
            KVOptionsFactory.create_persistent,
            KVOptionsFactory.create_session,
            KVOptionsFactory.create_cache,
        ]

        for method in methods:
            options = method()
            assert isinstance(options, KVOptions)


class TestDiscoveryRequestFactory:
    """Tests for discovery request factory."""

    def test_create_by_name(self):
        """Test creating discovery request by service name."""
        request = DiscoveryRequestFactory.create_by_name("test-service")
        assert request == {
            "service_name": "test-service",
            "filter": {"status": "ACTIVE"},
        }

    def test_create_by_group(self):
        """Test creating discovery request by sticky group."""
        request = DiscoveryRequestFactory.create_by_group("group-1")
        assert request == {
            "filter": {
                "sticky_active_group": "group-1",
                "status": "ACTIVE",
            }
        }

    def test_create_all_instances(self):
        """Test creating discovery request for all instances."""
        request = DiscoveryRequestFactory.create_all_instances("test-service")
        assert request == {
            "service_name": "test-service",
            "include_unhealthy": True,
        }

    def test_create_healthy_only(self):
        """Test creating discovery request for healthy instances."""
        request = DiscoveryRequestFactory.create_healthy_only("test-service")
        assert request == {
            "service_name": "test-service",
            "filter": {"status": ["ACTIVE", "STANDBY"]},
        }

    def test_create_with_metadata(self):
        """Test creating discovery request with metadata filters."""
        metadata = {
            "region": "us-east-1",
            "version": "2.0.0",
        }
        request = DiscoveryRequestFactory.create_with_metadata("test-service", metadata)
        assert request == {
            "service_name": "test-service",
            "filter": {
                "status": "ACTIVE",
                "metadata": {
                    "region": "us-east-1",
                    "version": "2.0.0",
                },
            },
        }

    def test_factory_methods_return_dicts(self):
        """Test all factory methods return dictionary requests."""
        methods = [
            lambda: DiscoveryRequestFactory.create_by_name("service"),
            lambda: DiscoveryRequestFactory.create_by_group("group"),
            lambda: DiscoveryRequestFactory.create_all_instances("service"),
            lambda: DiscoveryRequestFactory.create_healthy_only("service"),
            lambda: DiscoveryRequestFactory.create_with_metadata("service", {}),
        ]

        for method in methods:
            request = method()
            assert isinstance(request, dict)


class TestCreateServiceDependencies:
    """Tests for create_service_dependencies function."""

    @pytest.fixture
    def mock_message_bus(self):
        """Create mock message bus."""
        return MagicMock()

    def test_create_with_defaults(self, mock_message_bus):
        """Test creating dependencies with all defaults."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=True,
            enable_registry=True,
        )

        # Should have logger, metrics, discovery, registry, and kv_store
        assert "logger" in deps
        assert "metrics" in deps
        assert "service_discovery" in deps
        assert "service_registry" in deps
        assert "kv_store" in deps

        # Check types
        from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
        from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
        from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
        from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
        from aegis_sdk.infrastructure.simple_logger import SimpleLogger

        assert isinstance(deps["logger"], SimpleLogger)
        assert isinstance(deps["metrics"], InMemoryMetrics)
        assert isinstance(deps["service_discovery"], BasicServiceDiscovery)
        assert isinstance(deps["service_registry"], KVServiceRegistry)
        assert isinstance(deps["kv_store"], NATSKVStore)

    def test_create_with_custom_logger(self, mock_message_bus):
        """Test creating dependencies with custom logger."""
        custom_logger = MagicMock()
        deps = create_service_dependencies(
            mock_message_bus,
            logger=custom_logger,
            enable_discovery=False,
            enable_registry=False,
        )

        assert deps["logger"] == custom_logger
        assert "service_discovery" not in deps
        assert "service_registry" not in deps

    def test_create_with_custom_metrics(self, mock_message_bus):
        """Test creating dependencies with custom metrics."""
        custom_metrics = MagicMock()
        deps = create_service_dependencies(
            mock_message_bus,
            metrics=custom_metrics,
            enable_discovery=False,
            enable_registry=False,
        )

        assert deps["metrics"] == custom_metrics

    def test_create_discovery_only(self, mock_message_bus):
        """Test creating dependencies with discovery only."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=True,
            enable_registry=False,
        )

        assert "service_discovery" in deps
        assert "service_registry" not in deps
        assert "kv_store" not in deps

        # Discovery should have a no-op registry
        from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery

        discovery = deps["service_discovery"]
        assert isinstance(discovery, BasicServiceDiscovery)

    def test_create_registry_only(self, mock_message_bus):
        """Test creating dependencies with registry only."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=False,
            enable_registry=True,
        )

        assert "service_discovery" not in deps
        assert "service_registry" in deps
        assert "kv_store" in deps  # Registry needs KV store

    def test_create_minimal(self, mock_message_bus):
        """Test creating minimal dependencies."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=False,
            enable_registry=False,
        )

        # Should only have logger and metrics
        assert "logger" in deps
        assert "metrics" in deps
        assert "service_discovery" not in deps
        assert "service_registry" not in deps
        assert "kv_store" not in deps

    @pytest.mark.asyncio
    async def test_noop_registry_methods(self, mock_message_bus):
        """Test that NoOpRegistry methods work correctly."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=True,
            enable_registry=False,
        )

        # Get the NoOpRegistry from discovery
        discovery = deps["service_discovery"]
        noop_registry = discovery._registry

        # Test all methods return expected values
        await noop_registry.register("service", "instance")
        await noop_registry.deregister("service", "instance")
        result = await noop_registry.get_instance("service", "instance")
        assert result is None
        instances = await noop_registry.list_instances("service")
        assert instances == []

    def test_create_with_all_custom_components(self, mock_message_bus):
        """Test creating dependencies with all custom components."""
        custom_logger = MagicMock()
        custom_metrics = MagicMock()

        deps = create_service_dependencies(
            mock_message_bus,
            logger=custom_logger,
            metrics=custom_metrics,
            enable_discovery=True,
            enable_registry=True,
        )

        # Custom components should be used
        assert deps["logger"] == custom_logger
        assert deps["metrics"] == custom_metrics

        # Other components should be created
        assert "service_discovery" in deps
        assert "service_registry" in deps
        assert "kv_store" in deps

    def test_imports_are_local(self, mock_message_bus):
        """Test that imports inside function don't cause issues."""
        # This tests that the local imports in the function work correctly
        # even when called multiple times
        deps1 = create_service_dependencies(
            mock_message_bus,
            enable_discovery=True,
            enable_registry=True,
        )

        deps2 = create_service_dependencies(
            mock_message_bus,
            enable_discovery=True,
            enable_registry=True,
        )

        # Should create different instances
        assert deps1["logger"] is not deps2["logger"]
        assert deps1["metrics"] is not deps2["metrics"]

    def test_service_discovery_uses_provided_logger(self, mock_message_bus):
        """Test that service discovery uses the provided logger."""
        custom_logger = MagicMock()
        deps = create_service_dependencies(
            mock_message_bus,
            logger=custom_logger,
            enable_discovery=True,
            enable_registry=False,
        )

        discovery = deps["service_discovery"]
        # Check that discovery has the custom logger
        assert discovery._logger == custom_logger

    def test_service_registry_uses_provided_logger(self, mock_message_bus):
        """Test that service registry uses the provided logger."""
        custom_logger = MagicMock()
        deps = create_service_dependencies(
            mock_message_bus,
            logger=custom_logger,
            enable_discovery=False,
            enable_registry=True,
        )

        registry = deps["service_registry"]
        # Check that registry has the custom logger
        assert registry._logger == custom_logger

    def test_kv_store_uses_message_bus(self, mock_message_bus):
        """Test that KV store uses the provided message bus."""
        deps = create_service_dependencies(
            mock_message_bus,
            enable_discovery=False,
            enable_registry=True,
        )

        kv_store = deps["kv_store"]
        # Check that KV store has the message bus as adapter
        assert kv_store._nats_adapter == mock_message_bus
