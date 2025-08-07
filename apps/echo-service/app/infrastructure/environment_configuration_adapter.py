"""Infrastructure adapter for environment-based configuration.

This adapter implements the ConfigurationPort interface using environment
variables and defaults, providing configuration in a testable way.
"""

from __future__ import annotations

import os
from typing import Any

from ..ports.configuration import ConfigurationPort


class EnvironmentConfigurationAdapter(ConfigurationPort):
    """Environment-based implementation of the configuration port."""

    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        """Initialize the configuration adapter.

        Args:
            defaults: Default configuration values
        """
        self._defaults = defaults or {}
        self._cache: dict[str, Any] = {}

    def get_instance_id(self) -> str:
        """Get the service instance ID.

        Returns:
            Unique instance identifier from environment or hostname
        """
        return os.getenv("INSTANCE_ID", os.getenv("HOSTNAME", "echo-local"))

    def get_service_name(self) -> str:
        """Get the service name.

        Returns:
            Service name for registration
        """
        return os.getenv("SERVICE_NAME", self._defaults.get("service_name", "echo-service"))

    def get_service_version(self) -> str:
        """Get the service version.

        Returns:
            Service version string
        """
        return os.getenv("SERVICE_VERSION", self._defaults.get("version", "1.0.0"))

    def get_service_type(self) -> str:
        """Get the service type.

        Returns:
            Service type (e.g., 'service', 'worker')
        """
        return os.getenv("SERVICE_TYPE", self._defaults.get("service_type", "service"))

    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if debug mode is enabled
        """
        debug_value = os.getenv("DEBUG", str(self._defaults.get("debug", False)))
        return debug_value.lower() in ("true", "1", "yes", "on")

    def get_nats_url(self) -> str | None:
        """Get NATS URL if configured.

        Returns:
            NATS URL or None for auto-detection
        """
        url = os.getenv("NATS_URL")
        if url and url.lower() == "auto-detect":
            return None
        return url

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key (environment variable name)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Check environment
        value = os.getenv(key)
        if value is not None:
            self._cache[key] = value
            return value

        # Check defaults
        if key in self._defaults:
            return self._defaults[key]

        return default

    def is_kubernetes_environment(self) -> bool:
        """Check if running in Kubernetes.

        Returns:
            True if running in Kubernetes
        """
        return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")
