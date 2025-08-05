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
    # Enums
    "CommandPriority",
    "ServiceStatus",
    "StickyActiveStatus",
    "SubscriptionMode",
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
    "SerializationError",
    "ServiceError",
    "ServiceInfo",
    "ServiceInstance",
    # Patterns
    "SubjectPatterns",
    "TimeoutError",
    "ValidationError",
    # Types
    "CommandHandler",
    "EventHandler",
    "ProgressCallback",
    "RPCHandler",
]
