"""Environment adapter implementation."""

from __future__ import annotations

import os
from pathlib import Path


class EnvironmentAdapter:
    """Adapter for environment detection and configuration."""

    def get_environment_variable(self, name: str, default: str | None = None) -> str | None:
        """Get an environment variable value."""
        return os.environ.get(name, default)

    def set_environment_variable(self, name: str, value: str) -> None:
        """Set an environment variable."""
        os.environ[name] = value

    def is_kubernetes_environment(self) -> bool:
        """Check if running in Kubernetes environment."""
        # Check for Kubernetes service account
        if Path("/var/run/secrets/kubernetes.io").exists():
            return True

        # Check for common K8s environment variables
        k8s_vars = ["KUBERNETES_SERVICE_HOST", "KUBERNETES_SERVICE_PORT"]
        return all(os.getenv(var) for var in k8s_vars)

    def is_docker_environment(self) -> bool:
        """Check if running in Docker container."""
        # Check for .dockerenv file
        if Path("/.dockerenv").exists():
            return True

        # Check cgroup for docker
        try:
            with open("/proc/1/cgroup") as f:
                return "docker" in f.read()
        except FileNotFoundError:
            return False

    def detect_environment(self) -> str:
        """Detect the current runtime environment."""
        if self.is_kubernetes_environment():
            return "kubernetes"
        elif self.is_docker_environment():
            return "docker"
        else:
            return "local"

    def get_service_account_path(self) -> str | None:
        """Get Kubernetes service account path if available."""
        sa_path = "/var/run/secrets/kubernetes.io/serviceaccount"
        if Path(sa_path).exists():
            return sa_path
        return None

    def get_namespace(self) -> str | None:
        """Get Kubernetes namespace if available."""
        namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if Path(namespace_file).exists():
            try:
                with open(namespace_file) as f:
                    return f.read().strip()
            except OSError:
                pass
        return None
