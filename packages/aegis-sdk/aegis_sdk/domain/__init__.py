"""Domain layer - Core business logic and entities."""

from .exceptions import (
    AegisError,
    CommandError,
    ConnectionError,
    EventError,
    MessageBusError,
    RPCError,
    SerializationError,
    ServiceError,
    TimeoutError,
    ValidationError,
)
from .models import Command, Event, Message, RPCRequest, RPCResponse, ServiceInfo
from .patterns import SubjectPatterns

__all__ = [
    # Models
    "Message",
    "RPCRequest",
    "RPCResponse",
    "Event",
    "Command",
    "ServiceInfo",
    # Patterns
    "SubjectPatterns",
    # Exceptions
    "AegisError",
    "ServiceError",
    "MessageBusError",
    "ConnectionError",
    "TimeoutError",
    "SerializationError",
    "ValidationError",
    "RPCError",
    "CommandError",
    "EventError",
]
