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
