"""Domain layer - Core business logic and entities."""

from .exceptions import (
    AegisError,
    CommandError,
    ConnectionError,
    EventError,
    KVKeyAlreadyExistsError,
    KVKeyNotFoundError,
    KVNotConnectedError,
    KVRevisionMismatchError,
    KVStoreError,
    KVTTLNotSupportedError,
    MessageBusError,
    RPCError,
    SerializationError,
    ServiceError,
    TimeoutError,
    ValidationError,
)
from .models import (
    Command,
    Event,
    KVEntry,
    KVOptions,
    KVWatchEvent,
    Message,
    RPCRequest,
    RPCResponse,
    ServiceInfo,
)
from .patterns import SubjectPatterns
from .value_objects import SanitizedKey

__all__ = [
    # Exceptions
    "AegisError",
    "Command",
    "CommandError",
    "ConnectionError",
    "Event",
    "EventError",
    "KVEntry",
    "KVKeyAlreadyExistsError",
    "KVKeyNotFoundError",
    "KVNotConnectedError",
    "KVOptions",
    "KVRevisionMismatchError",
    "KVStoreError",
    "KVTTLNotSupportedError",
    "KVWatchEvent",
    # Models
    "Message",
    "MessageBusError",
    "RPCError",
    "RPCRequest",
    "RPCResponse",
    "SanitizedKey",
    "SerializationError",
    "ServiceError",
    "ServiceInfo",
    # Patterns
    "SubjectPatterns",
    "TimeoutError",
    "ValidationError",
]
