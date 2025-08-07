"""Environment port for system environment operations."""

from __future__ import annotations

from typing import Protocol


class EnvironmentPort(Protocol):
    """Port for environment detection and configuration."""

    def get_environment_variable(self, name: str, default: str | None = None) -> str | None:
        """Get an environment variable value.

        Args:
            name: Environment variable name
            default: Default value if not found

        Returns:
            Environment variable value or default
        """
        ...

    def set_environment_variable(self, name: str, value: str) -> None:
        """Set an environment variable.

        Args:
            name: Environment variable name
            value: Value to set
        """
        ...

    def is_kubernetes_environment(self) -> bool:
        """Check if running in Kubernetes environment.

        Returns:
            True if in Kubernetes, False otherwise
        """
        ...

    def is_docker_environment(self) -> bool:
        """Check if running in Docker container.

        Returns:
            True if in Docker, False otherwise
        """
        ...

    def detect_environment(self) -> str:
        """Detect the current runtime environment.

        Returns:
            Environment name (e.g., "local", "kubernetes", "docker")
        """
        ...

    def get_service_account_path(self) -> str | None:
        """Get Kubernetes service account path if available.

        Returns:
            Service account path or None
        """
        ...

    def get_namespace(self) -> str | None:
        """Get Kubernetes namespace if available.

        Returns:
            Namespace name or None
        """
        ...
