"""Environment detection utilities for AegisSDK developer tools."""

from __future__ import annotations

import os
import subprocess
from enum import Enum
from pathlib import Path


class Environment(str, Enum):
    """Development environment types."""

    LOCAL_K8S = "local-k8s"
    DOCKER = "docker"
    PRODUCTION = "production"
    UNKNOWN = "unknown"


def is_kubernetes_available() -> bool:
    """Check if Kubernetes API is accessible."""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def is_docker_environment() -> bool:
    """Check if running inside a Docker container."""
    # Check for .dockerenv file
    if Path("/.dockerenv").exists():
        return True

    # Check for Docker in cgroup
    try:
        with open("/proc/self/cgroup") as f:
            return "docker" in f.read()
    except OSError:
        return False


def detect_environment() -> Environment:
    """Detect the current development environment.

    Returns:
        Environment enum indicating the detected environment
    """
    # Check environment variable override first
    env_override = os.getenv("AEGIS_ENVIRONMENT")
    if env_override:
        try:
            return Environment(env_override)
        except ValueError:
            pass

    # Check for production markers
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        # Running inside a K8s pod
        return Environment.PRODUCTION

    # Check for Docker environment
    if is_docker_environment():
        return Environment.DOCKER

    # Check for local K8s availability
    if is_kubernetes_available():
        return Environment.LOCAL_K8S

    return Environment.UNKNOWN


def get_k8s_context() -> str | None:
    """Get the current Kubernetes context name."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None
