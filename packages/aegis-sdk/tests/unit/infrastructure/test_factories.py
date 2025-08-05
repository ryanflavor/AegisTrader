"""Unit tests for infrastructure factory classes."""

from aegis_sdk.domain.models import Event, KVOptions, RPCRequest
from aegis_sdk.infrastructure.factories import (
    DiscoveryRequestFactory,
    JSONSerializer,
    KVOptionsFactory,
    MessagePackSerializer,
    SerializationFactory,
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

    def test_create_with_ttl(self):
        """Test creating options with TTL."""
        options = KVOptionsFactory.create_with_ttl(300)
        assert options.ttl == 300
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

    def test_create_exclusive(self):
        """Test creating exclusive options."""
        options = KVOptionsFactory.create_exclusive()
        assert options.create_only is True
        assert options.update_only is False
        assert options.ttl is None
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
        # Default TTL
        options = KVOptionsFactory.create_ephemeral()
        assert options.ttl == 30

        # Custom TTL
        options = KVOptionsFactory.create_ephemeral(ttl_seconds=60)
        assert options.ttl == 60

    def test_create_persistent(self):
        """Test creating persistent options."""
        options = KVOptionsFactory.create_persistent()
        assert options.ttl is None
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

    def test_create_session(self):
        """Test creating session options."""
        # Default TTL
        options = KVOptionsFactory.create_session()
        assert options.ttl == 3600  # 1 hour

        # Custom TTL
        options = KVOptionsFactory.create_session(session_ttl=7200)
        assert options.ttl == 7200

    def test_create_cache(self):
        """Test creating cache options."""
        # Default TTL
        options = KVOptionsFactory.create_cache()
        assert options.ttl == 300  # 5 minutes

        # Custom TTL
        options = KVOptionsFactory.create_cache(cache_ttl=600)
        assert options.ttl == 600

    def test_factory_methods_return_kvoptions(self):
        """Test all factory methods return KVOptions instances."""
        methods = [
            lambda: KVOptionsFactory.create_with_ttl(60),
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
