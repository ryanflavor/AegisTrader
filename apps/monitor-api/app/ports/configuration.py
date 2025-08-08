"""Configuration port interface.

Defines the protocol interface for configuration management.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.models import ServiceConfiguration, ValidationResult


class ConfigurationPort(Protocol):
    """Protocol interface for configuration operations."""

    def load_configuration(self) -> ServiceConfiguration:
        """Load service configuration from external sources.

        Returns:
            ServiceConfiguration: Validated service configuration

        Raises:
            ConfigurationException: If configuration is invalid or missing
        """
        ...

    def validate_configuration(self, config: ServiceConfiguration) -> ValidationResult:
        """Validate a configuration object.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult: Result with validation status and any issues
        """
        ...
