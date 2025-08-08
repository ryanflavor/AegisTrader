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
        if not name:
            raise ValueError("Environment variable name cannot be empty")
        os.environ[name] = value

    def is_kubernetes_environment(self) -> bool:
        """Check if running in Kubernetes environment."""
        # Check for Kubernetes service account
        if Path("/var/run/secrets/kubernetes.io").exists():
            return True

        # Check for common K8s environment variables
        # Either KUBERNETES_SERVICE_HOST or both host and port indicate K8s
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            return True

        return False

    def is_docker_environment(self) -> bool:
        """Check if running in Docker container."""
        # Check for .dockerenv file
        if Path("/.dockerenv").exists():
            return True

        # Check cgroup for docker
        cgroup_path = Path("/proc/self/cgroup")
        if cgroup_path.exists():
            try:
                content = cgroup_path.read_text()
                return "docker" in content
            except OSError:
                pass

        return False

    def detect_environment(self) -> str:
        """Detect the current runtime environment.

        Returns:
            String identifying the environment: 'kubernetes', 'docker', or 'local'
        """
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
        namespace_file = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        if namespace_file.exists():
            try:
                return namespace_file.read_text().strip()
            except OSError:
                pass
        return None

    def _check_port_forward(self) -> bool:
        """Check if kubectl port-forward is active for NATS."""
        try:
            import subprocess

            result = subprocess.run(["lsof", "-i:4222"], capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                output = result.stdout.lower()
                return "kubectl" in output and "listen" in output
        except:
            pass
        return False
