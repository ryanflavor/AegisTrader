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

    def __init__(self, message: str, service: str | None = None, method: str | None = None):
        super().__init__(message)
        self.service = service
        self.method = method
        if service:
            self.details["service"] = service
        if method:
            self.details["method"] = method


class ServiceUnavailableError(ServiceError):
    """Raised when a service is unavailable or has no healthy instances."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Service '{service_name}' is unavailable - no healthy instances found",
            details={"service_name": service_name},
        )
        self.service_name = service_name


class DiscoveryError(ServiceError):
    """Base exception for service discovery errors."""

    def __init__(self, message: str, service_name: str | None = None):
        super().__init__(message)
        self.service_name = service_name
        if service_name:
            self.details["service_name"] = service_name


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


class KVStoreError(AegisError):
    """Base exception for KV Store operations."""

    def __init__(
        self,
        message: str,
        key: str | None = None,
        bucket: str | None = None,
        operation: str | None = None,
    ):
        super().__init__(message)
        self.key = key
        self.bucket = bucket
        self.operation = operation
        if key:
            self.details["key"] = key
        if bucket:
            self.details["bucket"] = bucket
        if operation:
            self.details["operation"] = operation


class KVNotConnectedError(KVStoreError):
    """Raised when KV store operation is attempted without connection."""

    def __init__(self, operation: str):
        super().__init__(
            f"KV store not connected. Cannot perform '{operation}' operation.",
            operation=operation,
        )


class KVKeyNotFoundError(KVStoreError):
    """Raised when a key is not found in the KV store."""

    def __init__(self, key: str, bucket: str | None = None):
        super().__init__(f"Key '{key}' not found", key=key, bucket=bucket)


class KVRevisionMismatchError(KVStoreError):
    """Raised when optimistic concurrency check fails."""

    def __init__(self, key: str, expected: int, actual: int):
        super().__init__(
            f"Revision mismatch for key '{key}': expected {expected}, got {actual}",
            key=key,
        )
        self.expected_revision = expected
        self.actual_revision = actual
        self.details["expected_revision"] = expected
        self.details["actual_revision"] = actual


class KVKeyAlreadyExistsError(KVStoreError):
    """Raised when trying to create a key that already exists."""

    def __init__(self, key: str):
        super().__init__(f"Key '{key}' already exists", key=key, operation="create")


class KVTTLNotSupportedError(KVStoreError):
    """Raised when per-message TTL is not supported by the server."""

    def __init__(self):
        super().__init__(
            "Per-message TTL is not enabled on NATS server. "
            "Please configure the server with 'allow_msg_ttl: true' in the JetStream configuration."
        )
