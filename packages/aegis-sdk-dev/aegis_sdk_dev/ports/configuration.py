"""Configuration port for external configuration sources."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConfigurationPort(Protocol):
    """Port for reading configuration from external sources."""

    async def load_configuration(self, path: str) -> dict[str, Any]:
        """Load configuration from the specified path.

        Args:
            path: Path to configuration file or resource

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
        """
        ...

    async def save_configuration(self, path: str, config: dict[str, Any]) -> None:
        """Save configuration to the specified path.

        Args:
            path: Path to save configuration
            config: Configuration dictionary to save

        Raises:
            IOError: If unable to write configuration
        """
        ...

    def validate_configuration(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration structure and values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        ...
