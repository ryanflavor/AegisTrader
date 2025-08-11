"""Domain layer - Core business logic and entities."""

from .enums import CommandPriority, ServiceStatus, StickyActiveStatus, SubscriptionMode
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
    ServiceInstance,
)
from .patterns import SubjectPatterns
from .types import CommandHandler, EventHandler, ProgressCallback, RPCHandler

__all__ = [
    # Exceptions
    "AegisError",
    "Command",
    "CommandError",
    # Types
    "CommandHandler",
    # Enums
    "CommandPriority",
    "ConnectionError",
    "Event",
    "EventError",
    "EventHandler",
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
    "ProgressCallback",
    "RPCError",
    "RPCHandler",
    "RPCRequest",
    "RPCResponse",
    "SerializationError",
    "ServiceError",
    "ServiceInfo",
    "ServiceInstance",
    "ServiceStatus",
    "StickyActiveStatus",
    # Patterns
    "SubjectPatterns",
    "SubscriptionMode",
    "TimeoutError",
    "ValidationError",
]
