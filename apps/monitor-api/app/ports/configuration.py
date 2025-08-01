"""Configuration port interface.

Defines the abstract interface for configuration management.
"""

from abc import ABC, abstractmethod

from ..domain.models import ServiceConfiguration


class ConfigurationPort(ABC):
    """Abstract interface for configuration operations."""

    @abstractmethod
    def load_configuration(self) -> ServiceConfiguration:
        """Load service configuration from external sources.

        Returns:
            ServiceConfiguration: Validated service configuration

        Raises:
            ConfigurationException: If configuration is invalid or missing
        """
        pass

    @abstractmethod
    def validate_configuration(self, config: ServiceConfiguration) -> None:
        """Validate a configuration object.

        Args:
            config: Configuration to validate

        Raises:
            ConfigurationException: If configuration is invalid
        """
        pass
