"""Port interface for configuration management.

This port defines the contract for accessing configuration
values in a way that's decoupled from the source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConfigurationPort(ABC):
    """Port interface for configuration access."""

    @abstractmethod
    def get_instance_id(self) -> str:
        """Get the service instance ID.

        Returns:
            Unique instance identifier
        """
        ...

    @abstractmethod
    def get_service_name(self) -> str:
        """Get the service name.

        Returns:
            Service name for registration
        """
        ...

    @abstractmethod
    def get_service_version(self) -> str:
        """Get the service version.

        Returns:
            Service version string
        """
        ...

    @abstractmethod
    def get_service_type(self) -> str:
        """Get the service type.

        Returns:
            Service type (e.g., 'service', 'worker')
        """
        ...

    @abstractmethod
    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if debug mode is enabled
        """
        ...

    @abstractmethod
    def get_nats_url(self) -> str | None:
        """Get NATS URL if configured.

        Returns:
            NATS URL or None for auto-detection
        """
        ...

    @abstractmethod
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        ...
