"""Unit tests for environment detection."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, mock_open, patch

from aegis_sdk.developer.environment import (
    Environment,
    detect_environment,
    get_k8s_context,
    is_docker_environment,
    is_kubernetes_available,
)


class TestIsKubernetesAvailable:
    """Test Kubernetes availability detection."""

    @patch("subprocess.run")
    def test_kubernetes_available(self, mock_run: MagicMock) -> None:
        """Test when Kubernetes is available."""
        mock_run.return_value.returncode = 0

        result = is_kubernetes_available()

        assert result is True
        mock_run.assert_called_once_with(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    @patch("subprocess.run")
    def test_kubernetes_not_available(self, mock_run: MagicMock) -> None:
        """Test when Kubernetes is not available."""
        mock_run.return_value.returncode = 1

        result = is_kubernetes_available()

        assert result is False

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_kubectl_not_found(self, mock_run: MagicMock) -> None:
        """Test when kubectl is not installed."""
        result = is_kubernetes_available()

        assert result is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5))
    def test_kubectl_timeout(self, mock_run: MagicMock) -> None:
        """Test when kubectl times out."""
        result = is_kubernetes_available()

        assert result is False


class TestIsDockerEnvironment:
    """Test Docker environment detection."""

    @patch("pathlib.Path.exists", return_value=True)
    def test_docker_env_file_exists(self, mock_exists: MagicMock) -> None:
        """Test when /.dockerenv file exists."""
        result = is_docker_environment()

        assert result is True
        mock_exists.assert_called_once()

    @patch("pathlib.Path.exists", return_value=False)
    @patch("builtins.open", mock_open(read_data="13:name=systemd:/docker/abc123"))
    def test_docker_in_cgroup(self, mock_exists: MagicMock) -> None:
        """Test when Docker is detected in cgroup."""
        result = is_docker_environment()

        assert result is True

    @patch("pathlib.Path.exists", return_value=False)
    @patch("builtins.open", mock_open(read_data="13:name=systemd:/"))
    def test_not_docker_environment(self, mock_exists: MagicMock) -> None:
        """Test when not in Docker environment."""
        result = is_docker_environment()

        assert result is False

    @patch("builtins.open", side_effect=IOError)
    @patch("pathlib.Path.exists", return_value=False)
    def test_cgroup_read_error(self, mock_exists: MagicMock, mock_open: MagicMock) -> None:
        """Test when cgroup file cannot be read."""
        result = is_docker_environment()

        assert result is False


class TestDetectEnvironment:
    """Test environment detection."""

    @patch.dict("os.environ", {"AEGIS_ENVIRONMENT": "production"})
    def test_environment_override(self) -> None:
        """Test environment variable override."""
        result = detect_environment()

        assert result == Environment.PRODUCTION

    @patch.dict("os.environ", {"AEGIS_ENVIRONMENT": "invalid"})
    @patch("aegis_sdk.developer.environment.is_kubernetes_available", return_value=True)
    def test_invalid_environment_override(self, mock_k8s: MagicMock) -> None:
        """Test invalid environment override falls back to detection."""
        result = detect_environment()

        assert result == Environment.LOCAL_K8S

    @patch.dict("os.environ", {"KUBERNETES_SERVICE_HOST": "10.0.0.1"})
    def test_production_environment(self) -> None:
        """Test production environment detection."""
        result = detect_environment()

        assert result == Environment.PRODUCTION

    @patch("aegis_sdk.developer.environment.is_docker_environment", return_value=True)
    @patch("aegis_sdk.developer.environment.is_kubernetes_available", return_value=False)
    def test_docker_environment(self, mock_k8s: MagicMock, mock_docker: MagicMock) -> None:
        """Test Docker environment detection."""
        result = detect_environment()

        assert result == Environment.DOCKER

    @patch("aegis_sdk.developer.environment.is_docker_environment", return_value=False)
    @patch("aegis_sdk.developer.environment.is_kubernetes_available", return_value=True)
    def test_local_k8s_environment(self, mock_k8s: MagicMock, mock_docker: MagicMock) -> None:
        """Test local K8s environment detection."""
        result = detect_environment()

        assert result == Environment.LOCAL_K8S

    @patch("aegis_sdk.developer.environment.is_docker_environment", return_value=False)
    @patch("aegis_sdk.developer.environment.is_kubernetes_available", return_value=False)
    def test_unknown_environment(self, mock_k8s: MagicMock, mock_docker: MagicMock) -> None:
        """Test unknown environment detection."""
        result = detect_environment()

        assert result == Environment.UNKNOWN


class TestGetK8sContext:
    """Test Kubernetes context retrieval."""

    @patch("subprocess.run")
    def test_get_context_success(self, mock_run: MagicMock) -> None:
        """Test successful context retrieval."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "  my-context  \n"

        result = get_k8s_context()

        assert result == "my-context"
        mock_run.assert_called_once_with(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    @patch("subprocess.run")
    def test_get_context_failure(self, mock_run: MagicMock) -> None:
        """Test context retrieval failure."""
        mock_run.return_value.returncode = 1

        result = get_k8s_context()

        assert result is None

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_kubectl_not_found(self, mock_run: MagicMock) -> None:
        """Test when kubectl is not installed."""
        result = get_k8s_context()

        assert result is None
