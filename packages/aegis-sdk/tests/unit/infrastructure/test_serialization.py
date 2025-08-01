"""Tests for serialization module."""

import json

import msgpack
import pytest

from aegis_sdk.domain.exceptions import SerializationError
from aegis_sdk.domain.models import Event, Message, RPCRequest
from aegis_sdk.infrastructure.serialization import (
    deserialize_from_json,
    deserialize_from_msgpack,
    deserialize_params,
    detect_and_deserialize,
    is_msgpack,
    serialize_dict,
    serialize_to_json,
    serialize_to_msgpack,
)


class TestSerializeToMsgpack:
    """Test cases for serialize_to_msgpack."""

    def test_serialize_simple_model(self):
        """Test serializing a simple Pydantic model."""
        message = Message(source="test-service")
        data = serialize_to_msgpack(message)

        assert isinstance(data, bytes)
        # Verify it's valid msgpack by unpacking
        unpacked = msgpack.unpackb(data, raw=False)
        assert unpacked["source"] == "test-service"
        assert "message_id" in unpacked
        assert "timestamp" in unpacked

    def test_serialize_complex_model(self):
        """Test serializing a model with nested data."""
        event = Event(
            domain="order",
            event_type="created",
            payload={"order_id": "123", "items": [{"id": "A", "qty": 2}]},
        )
        data = serialize_to_msgpack(event)

        assert isinstance(data, bytes)
        unpacked = msgpack.unpackb(data, raw=False)
        assert unpacked["domain"] == "order"
        assert unpacked["payload"]["order_id"] == "123"
        assert len(unpacked["payload"]["items"]) == 1

    def test_serialize_with_datetime(self):
        """Test that datetime fields are properly handled."""
        message = Message()
        data = serialize_to_msgpack(message)

        unpacked = msgpack.unpackb(data, raw=False)
        # Timestamp should be serialized as ISO string
        assert isinstance(unpacked["timestamp"], str)
        assert "T" in unpacked["timestamp"]  # ISO format indicator


class TestDeserializeFromMsgpack:
    """Test cases for deserialize_from_msgpack."""

    def test_deserialize_simple_model(self):
        """Test deserializing to a Pydantic model."""
        data = msgpack.packb(
            {"message_id": "123", "trace_id": "456", "timestamp": "2025-01-01T00:00:00Z"},
            use_bin_type=True,
        )

        message = deserialize_from_msgpack(data, Message)
        assert isinstance(message, Message)
        assert message.message_id == "123"
        assert message.trace_id == "456"

    def test_deserialize_invalid_data(self):
        """Test deserializing invalid msgpack data."""
        with pytest.raises(SerializationError) as exc_info:
            deserialize_from_msgpack(b"not msgpack", Message)
        assert "Failed to deserialize from msgpack" in str(exc_info.value)

    def test_deserialize_missing_fields(self):
        """Test deserializing with missing required fields."""
        # Message with extra field should fail due to extra="forbid"
        data = msgpack.packb({"some_field": "value"}, use_bin_type=True)
        with pytest.raises(SerializationError) as exc_info:
            deserialize_from_msgpack(data, Message)
        assert "Extra inputs are not permitted" in str(exc_info.value)

        # Message with no fields should work (all have defaults)
        empty_data = msgpack.packb({}, use_bin_type=True)
        message = deserialize_from_msgpack(empty_data, Message)
        assert isinstance(message, Message)

        # RPCRequest requires method field
        with pytest.raises(SerializationError):
            deserialize_from_msgpack(empty_data, RPCRequest)


class TestSerializeToJson:
    """Test cases for serialize_to_json."""

    def test_serialize_simple_model(self):
        """Test serializing a model to JSON."""
        message = Message(source="json-test")
        data = serialize_to_json(message)

        assert isinstance(data, bytes)
        parsed = json.loads(data)
        assert parsed["source"] == "json-test"

    def test_serialize_nested_model(self):
        """Test serializing nested data."""
        request = RPCRequest(
            method="get_user",
            params={"user_id": 123, "include": ["profile", "settings"]},
        )
        data = serialize_to_json(request)

        parsed = json.loads(data)
        assert parsed["method"] == "get_user"
        assert parsed["params"]["user_id"] == 123
        assert len(parsed["params"]["include"]) == 2


class TestDeserializeFromJson:
    """Test cases for deserialize_from_json."""

    def test_deserialize_bytes(self):
        """Test deserializing from bytes."""
        data = b'{"message_id": "123", "trace_id": "456", "timestamp": "2025-01-01T00:00:00Z"}'
        message = deserialize_from_json(data, Message)

        assert isinstance(message, Message)
        assert message.message_id == "123"

    def test_deserialize_string(self):
        """Test deserializing from string (non-bytes)."""
        data = '{"message_id": "789", "trace_id": "012", "timestamp": "2025-01-01T00:00:00Z"}'
        message = deserialize_from_json(data, Message)  # type: ignore

        assert isinstance(message, Message)
        assert message.message_id == "789"

    def test_deserialize_empty_data(self):
        """Test deserializing empty data."""
        with pytest.raises(SerializationError) as exc_info:
            deserialize_from_json(b"", Message)
        assert "Empty or whitespace-only JSON data" in str(exc_info.value)

        with pytest.raises(SerializationError) as exc_info:
            deserialize_from_json(b"   ", Message)
        assert "Empty or whitespace-only JSON data" in str(exc_info.value)

    def test_deserialize_invalid_json(self):
        """Test deserializing invalid JSON."""
        with pytest.raises(SerializationError) as exc_info:
            deserialize_from_json(b"not json", Message)
        assert "Invalid JSON format" in str(exc_info.value)

    def test_deserialize_validation_error(self):
        """Test deserializing with validation errors."""
        # Invalid event version
        data = b'{"domain": "test", "event_type": "test", "version": "invalid"}'
        with pytest.raises(SerializationError):
            deserialize_from_json(data, Event)


class TestIsMsgpack:
    """Test cases for is_msgpack detection."""

    def test_detect_msgpack_formats(self):
        """Test detecting various msgpack formats."""
        # fixmap (0x80-0x8f)
        assert is_msgpack(b"\x81\xa3key\xa5value") is True

        # fixarray (0x90-0x9f)
        assert is_msgpack(b"\x91\xa5hello") is True

        # nil (0xc0)
        assert is_msgpack(b"\xc0") is True

        # true/false (0xc2/0xc3)
        assert is_msgpack(b"\xc2") is True
        assert is_msgpack(b"\xc3") is True

        # map16 (0xde)
        assert is_msgpack(b"\xde\x00\x01") is True

        # map32 (0xdf)
        assert is_msgpack(b"\xdf\x00\x00\x00\x01") is True

    def test_detect_non_msgpack(self):
        """Test detecting non-msgpack data."""
        # JSON
        assert is_msgpack(b'{"key": "value"}') is False

        # Plain text
        assert is_msgpack(b"Hello, World!") is False

        # Empty
        assert is_msgpack(b"") is False

        # Numbers that aren't msgpack markers
        assert is_msgpack(b"\x00") is False
        assert is_msgpack(b"\x7f") is False


class TestDetectAndDeserialize:
    """Test cases for automatic format detection."""

    def test_detect_msgpack(self):
        """Test detecting and deserializing msgpack."""
        original = Message(source="msgpack-test")
        msgpack_data = serialize_to_msgpack(original)

        result = detect_and_deserialize(msgpack_data, Message)
        assert isinstance(result, Message)
        assert result.source == "msgpack-test"

    def test_detect_json(self):
        """Test detecting and deserializing JSON."""
        original = Message(source="json-test")
        json_data = serialize_to_json(original)

        result = detect_and_deserialize(json_data, Message)
        assert isinstance(result, Message)
        assert result.source == "json-test"

    def test_detect_empty_data(self):
        """Test with empty data."""
        with pytest.raises(SerializationError) as exc_info:
            detect_and_deserialize(b"", Message)
        assert "Empty data received" in str(exc_info.value)


class TestSerializeDict:
    """Test cases for serialize_dict."""

    def test_serialize_dict_msgpack(self):
        """Test serializing dict to msgpack."""
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        result = serialize_dict(data, use_msgpack=True)

        assert isinstance(result, bytes)
        unpacked = msgpack.unpackb(result, raw=False)
        assert unpacked == data

    def test_serialize_dict_json(self):
        """Test serializing dict to JSON."""
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        result = serialize_dict(data, use_msgpack=False)

        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert parsed == data

    def test_serialize_dict_with_datetime(self):
        """Test serializing dict with non-serializable objects."""
        from datetime import datetime

        data = {"timestamp": datetime.now(), "value": 123}

        # Msgpack with default=str
        msgpack_result = serialize_dict(data, use_msgpack=True)
        unpacked = msgpack.unpackb(msgpack_result, raw=False)
        assert isinstance(unpacked["timestamp"], str)

        # JSON with default=str
        json_result = serialize_dict(data, use_msgpack=False)
        parsed = json.loads(json_result)
        assert isinstance(parsed["timestamp"], str)


class TestDeserializeParams:
    """Test cases for deserialize_params."""

    def test_deserialize_params_msgpack(self):
        """Test deserializing msgpack params."""
        original = {"param1": "value1", "param2": 42}
        data = msgpack.packb(original, use_bin_type=True)

        result = deserialize_params(data, use_msgpack=True)
        assert result == original

    def test_deserialize_params_json(self):
        """Test deserializing JSON params."""
        original = {"param1": "value1", "param2": 42}
        data = json.dumps(original).encode()

        result = deserialize_params(data, use_msgpack=False)
        assert result == original

    def test_deserialize_params_invalid(self):
        """Test deserializing invalid params."""
        with pytest.raises(SerializationError):
            deserialize_params(b"invalid data", use_msgpack=True)

        with pytest.raises(SerializationError):
            deserialize_params(b"invalid json", use_msgpack=False)
