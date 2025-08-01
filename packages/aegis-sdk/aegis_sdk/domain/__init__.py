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
    # Exceptions
    "AegisError",
    "Command",
    "CommandError",
    "ConnectionError",
    "Event",
    "EventError",
    # Models
    "Message",
    "MessageBusError",
    "RPCError",
    "RPCRequest",
    "RPCResponse",
    "SerializationError",
    "ServiceError",
    "ServiceInfo",
    # Patterns
    "SubjectPatterns",
    "TimeoutError",
    "ValidationError",
]
