"""Domain-specific exceptions following DDD principles."""


class AegisError(Exception):
    """Base exception for all Aegis SDK errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ServiceError(AegisError):
    """Service-related errors."""

    pass


class MessageBusError(AegisError):
    """Message bus communication errors."""

    pass


class ConnectionError(MessageBusError):
    """Connection-related errors."""

    pass


class TimeoutError(MessageBusError):
    """Operation timeout errors."""

    pass


class SerializationError(MessageBusError):
    """Serialization/deserialization errors."""

    pass


class ValidationError(AegisError):
    """Domain validation errors."""

    pass


class RPCError(AegisError):
    """RPC-specific errors."""

    def __init__(
        self, message: str, service: str | None = None, method: str | None = None
    ):
        super().__init__(message)
        self.service = service
        self.method = method
        if service:
            self.details["service"] = service
        if method:
            self.details["method"] = method


class CommandError(AegisError):
    """Command processing errors."""

    def __init__(self, message: str, command_id: str | None = None):
        super().__init__(message)
        self.command_id = command_id
        if command_id:
            self.details["command_id"] = command_id


class EventError(AegisError):
    """Event processing errors."""

    def __init__(self, message: str, event_type: str | None = None):
        super().__init__(message)
        self.event_type = event_type
        if event_type:
            self.details["event_type"] = event_type
