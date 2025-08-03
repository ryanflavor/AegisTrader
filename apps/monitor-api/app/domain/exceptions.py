"""Domain exceptions for AegisTrader Monitor API.

Custom exceptions that represent domain-specific errors.
"""


class DomainException(Exception):
    """Base exception for all domain-related errors."""

    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ServiceUnavailableException(DomainException):
    """Raised when the service is unavailable or unhealthy."""

    def __init__(self, message: str = "Service is currently unavailable"):
        super().__init__(message, "SERVICE_UNAVAILABLE")


class ConfigurationException(DomainException):
    """Raised when there's a configuration error."""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")


class HealthCheckFailedException(DomainException):
    """Raised when a health check fails."""

    def __init__(self, message: str = "Health check failed"):
        super().__init__(message, "HEALTH_CHECK_FAILED")


class ServiceNotFoundException(DomainException):
    """Raised when a service definition is not found."""

    def __init__(self, service_name: str):
        super().__init__(f"Service '{service_name}' not found", "SERVICE_NOT_FOUND")
        self.key = service_name


class ServiceAlreadyExistsException(DomainException):
    """Raised when attempting to create a service that already exists."""

    def __init__(self, service_name: str):
        super().__init__(f"Service '{service_name}' already exists", "SERVICE_ALREADY_EXISTS")
        self.key = service_name


class ConcurrentUpdateException(DomainException):
    """Raised when a concurrent update conflict occurs."""

    def __init__(self, service_name: str):
        super().__init__(
            f"Concurrent update detected for service '{service_name}'", "CONCURRENT_UPDATE"
        )
        self.key = service_name


class KVStoreException(DomainException):
    """Raised when a KV Store operation fails."""

    def __init__(self, message: str):
        super().__init__(message, "KV_STORE_ERROR")
