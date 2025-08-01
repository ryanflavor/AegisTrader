"""Serialization utilities for JSON and MessagePack."""

import json
from typing import Any, TypeVar

import msgpack
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SerializationError(Exception):
    """Raised when serialization/deserialization fails."""

    pass


def serialize_to_msgpack(obj: BaseModel) -> bytes:
    """Serialize a Pydantic model to MessagePack bytes."""
    try:
        # Convert to dict first, handling datetime objects
        data = obj.model_dump(mode="json")
        return msgpack.packb(data, use_bin_type=True)
    except Exception as e:
        raise SerializationError(f"Failed to serialize to msgpack: {e}")


def deserialize_from_msgpack(data: bytes, model_class: type[T]) -> T:
    """Deserialize MessagePack bytes to a Pydantic model."""
    try:
        unpacked = msgpack.unpackb(data, raw=False)
        return model_class(**unpacked)
    except Exception as e:
        raise SerializationError(f"Failed to deserialize from msgpack: {e}")


def serialize_to_json(obj: BaseModel) -> bytes:
    """Serialize a Pydantic model to JSON bytes."""
    try:
        return obj.model_dump_json().encode()
    except Exception as e:
        raise SerializationError(f"Failed to serialize to JSON: {e}")


def deserialize_from_json(data: bytes, model_class: type[T]) -> T:
    """Deserialize JSON bytes to a Pydantic model."""
    try:
        json_str = data.decode() if isinstance(data, bytes) else data
        if not json_str or json_str.isspace():
            raise SerializationError("Empty or whitespace-only JSON data")
        return model_class(**json.loads(json_str))
    except json.JSONDecodeError as e:
        raise SerializationError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise SerializationError(f"Failed to deserialize from JSON: {e}")


def is_msgpack(data: bytes) -> bool:
    """Check if data looks like MessagePack format."""
    if not data:
        return False

    # MessagePack format detection based on first byte
    # 0x80-0x8f: fixmap
    # 0x90-0x9f: fixarray
    # 0xc0-0xdf: various types including nil, bool, bin, ext, etc.
    # 0xde-0xdf: map16/map32
    first_byte = data[0]
    return (
        0x80 <= first_byte <= 0x8F  # fixmap
        or 0x90 <= first_byte <= 0x9F  # fixarray
        or 0xC0 <= first_byte <= 0xDF  # various msgpack types
        or first_byte in (0xDE, 0xDF)
    )  # map16/map32


def detect_and_deserialize(data: bytes, model_class: type[T]) -> T:
    """Automatically detect format and deserialize."""
    if not data:
        raise SerializationError("Empty data received")

    if is_msgpack(data):
        return deserialize_from_msgpack(data, model_class)
    else:
        return deserialize_from_json(data, model_class)


def serialize_dict(data: dict[str, Any], use_msgpack: bool = True) -> bytes:
    """Serialize a dictionary, handling Python objects."""
    try:
        if use_msgpack:
            # Use default=str to handle datetime and other non-serializable objects
            return msgpack.packb(data, use_bin_type=True, default=str)
        else:
            # For JSON, we need to handle non-serializable objects
            return json.dumps(data, default=str).encode()
    except Exception as e:
        raise SerializationError(f"Failed to serialize dict: {e}")


def deserialize_params(data: bytes, use_msgpack: bool = True) -> dict[str, Any]:
    """Deserialize method parameters."""
    try:
        if use_msgpack:
            return msgpack.unpackb(data, raw=False)
        else:
            return json.loads(data.decode())
    except Exception as e:
        raise SerializationError(f"Failed to deserialize params: {e}")
