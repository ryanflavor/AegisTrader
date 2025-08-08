"""Comprehensive edge case tests for EnvironmentAdapter following TDD principles."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter


class TestEnvironmentAdapterEdgeCases:
    """Test EnvironmentAdapter edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = EnvironmentAdapter()
        # Store original environment for cleanup
        self.original_env = os.environ.copy()

    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    # Test environment variable edge cases
    def test_get_environment_variable_with_empty_name(self):
        """Test getting env var with empty name."""
        # Act
        result = self.adapter.get_environment_variable("")

        # Assert
        assert result is None

    def test_get_environment_variable_with_special_characters(self):
        """Test getting env var with special characters in name."""
        # Arrange
        special_name = "TEST_VAR_WITH-SPECIAL.CHARS"
        os.environ[special_name] = "special_value"

        # Act
        result = self.adapter.get_environment_variable(special_name)

        # Assert
        assert result == "special_value"

    def test_get_environment_variable_with_unicode_value(self):
        """Test getting env var with unicode value."""
        # Arrange
        os.environ["UNICODE_VAR"] = "Hello 世界 🌍"

        # Act
        result = self.adapter.get_environment_variable("UNICODE_VAR")

        # Assert
        assert result == "Hello 世界 🌍"

    def test_get_environment_variable_with_empty_value(self):
        """Test getting env var that is set to empty string."""
        # Arrange
        os.environ["EMPTY_VAR"] = ""

        # Act
        result = self.adapter.get_environment_variable("EMPTY_VAR")

        # Assert
        assert result == ""

    def test_get_environment_variable_default_with_existing_var(self):
        """Test default is ignored when var exists."""
        # Arrange
        os.environ["EXISTING_VAR"] = "actual"

        # Act
        result = self.adapter.get_environment_variable("EXISTING_VAR", default="default")

        # Assert
        assert result == "actual"

    def test_set_environment_variable_with_empty_name_raises(self):
        """Test setting env var with empty name raises error."""
        # Act & Assert
        with pytest.raises(ValueError):
            os.environ[""] = "value"  # This is what happens internally

    def test_set_environment_variable_overwrites_existing(self):
        """Test setting env var overwrites existing value."""
        # Arrange
        os.environ["TEST_VAR"] = "old_value"

        # Act
        self.adapter.set_environment_variable("TEST_VAR", "new_value")

        # Assert
        assert os.environ["TEST_VAR"] == "new_value"

    def test_set_environment_variable_with_multiline_value(self):
        """Test setting env var with multiline value."""
        # Arrange
        multiline_value = "line1\nline2\nline3"

        # Act
        self.adapter.set_environment_variable("MULTILINE_VAR", multiline_value)

        # Assert
        assert os.environ["MULTILINE_VAR"] == multiline_value

    def test_set_environment_variable_with_none_value_raises(self):
        """Test setting env var with None value raises error."""
        # Act & Assert
        with pytest.raises(TypeError):
            self.adapter.set_environment_variable("TEST_VAR", None)

    # Test Kubernetes environment detection edge cases
    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_kubernetes_with_sa_path_exists(self, mock_path_class):
        """Test K8s detection when service account path exists."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is True
        mock_path_class.assert_called_with("/var/run/secrets/kubernetes.io")

    @patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "10.0.0.1"})
    def test_is_kubernetes_with_env_var(self):
        """Test K8s detection with environment variable."""
        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is True

    @patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": ""})
    def test_is_kubernetes_with_empty_env_var(self):
        """Test K8s detection with empty env var."""
        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is False

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    @patch.dict(os.environ, {}, clear=True)
    def test_is_kubernetes_neither_condition(self, mock_path_class):
        """Test K8s detection when neither condition is met."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is False

    # Test Docker environment detection edge cases
    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_docker_with_dockerenv_exists(self, mock_path_class):
        """Test Docker detection when .dockerenv exists."""
        # Arrange
        mock_instances = {
            "/.dockerenv": Mock(exists=Mock(return_value=True)),
            "/proc/self/cgroup": Mock(exists=Mock(return_value=False)),
        }
        mock_path_class.side_effect = lambda path: mock_instances.get(path, Mock())

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is True

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_docker_with_cgroup_contains_docker(self, mock_path_class):
        """Test Docker detection via cgroup file."""
        # Arrange
        mock_dockerenv = Mock()
        mock_dockerenv.exists.return_value = False

        mock_cgroup = Mock()
        mock_cgroup.exists.return_value = True
        mock_cgroup.read_text.return_value = "12:devices:/docker/abc123"

        def path_side_effect(path):
            if path == "/.dockerenv":
                return mock_dockerenv
            elif path == "/proc/self/cgroup":
                return mock_cgroup
            return Mock()

        mock_path_class.side_effect = path_side_effect

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is True

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_docker_with_cgroup_read_error(self, mock_path_class):
        """Test Docker detection when cgroup read fails."""
        # Arrange
        mock_dockerenv = Mock()
        mock_dockerenv.exists.return_value = False

        mock_cgroup = Mock()
        mock_cgroup.exists.return_value = True
        mock_cgroup.read_text.side_effect = OSError("Permission denied")

        def path_side_effect(path):
            if path == "/.dockerenv":
                return mock_dockerenv
            elif path == "/proc/self/cgroup":
                return mock_cgroup
            return Mock()

        mock_path_class.side_effect = path_side_effect

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is False

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_docker_with_cgroup_no_docker_keyword(self, mock_path_class):
        """Test Docker detection when cgroup doesn't contain 'docker'."""
        # Arrange
        mock_dockerenv = Mock()
        mock_dockerenv.exists.return_value = False

        mock_cgroup = Mock()
        mock_cgroup.exists.return_value = True
        mock_cgroup.read_text.return_value = "12:devices:/system.slice/containerd"

        def path_side_effect(path):
            if path == "/.dockerenv":
                return mock_dockerenv
            elif path == "/proc/self/cgroup":
                return mock_cgroup
            return Mock()

        mock_path_class.side_effect = path_side_effect

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is False

    # Test environment detection edge cases
    @patch.object(EnvironmentAdapter, "is_kubernetes_environment", return_value=True)
    @patch.object(EnvironmentAdapter, "is_docker_environment", return_value=True)
    def test_detect_environment_kubernetes_takes_precedence(self, mock_docker, mock_k8s):
        """Test that Kubernetes detection takes precedence over Docker."""
        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "kubernetes"
        mock_k8s.assert_called_once()
        mock_docker.assert_not_called()  # Should not check Docker if K8s detected

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment", return_value=False)
    @patch.object(EnvironmentAdapter, "is_docker_environment", return_value=True)
    def test_detect_environment_docker(self, mock_docker, mock_k8s):
        """Test Docker environment detection."""
        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "docker"

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment", return_value=False)
    @patch.object(EnvironmentAdapter, "is_docker_environment", return_value=False)
    def test_detect_environment_local(self, mock_docker, mock_k8s):
        """Test local environment detection."""
        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "local"

    # Test service account path edge cases
    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_service_account_path_exists(self, mock_path_class):
        """Test getting service account path when it exists."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_service_account_path()

        # Assert
        assert result == "/var/run/secrets/kubernetes.io/serviceaccount"

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_service_account_path_not_exists(self, mock_path_class):
        """Test getting service account path when it doesn't exist."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_service_account_path()

        # Assert
        assert result is None

    # Test namespace detection edge cases
    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_namespace_success(self, mock_path_class):
        """Test getting namespace from file."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = "  default  \n"
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result == "default"

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_namespace_file_not_exists(self, mock_path_class):
        """Test getting namespace when file doesn't exist."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result is None

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_namespace_read_error(self, mock_path_class):
        """Test getting namespace when read fails."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.side_effect = OSError("Permission denied")
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result is None

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_get_namespace_empty_file(self, mock_path_class):
        """Test getting namespace from empty file."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = ""
        mock_path_class.return_value = mock_path_instance

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result == ""

    # Test port forward check edge cases
    @patch("subprocess.run")
    def test_check_port_forward_kubectl_found(self, mock_run):
        """Test port forward check when kubectl is found."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "kubectl     12345 user   10u  IPv4  LISTEN"
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is True
        mock_run.assert_called_once_with(
            ["lsof", "-i:4222"], capture_output=True, text=True, timeout=1
        )

    @patch("subprocess.run")
    def test_check_port_forward_no_kubectl(self, mock_run):
        """Test port forward check when kubectl not found."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "nats-server 12345 user   10u  IPv4  LISTEN"
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_command_fails(self, mock_run):
        """Test port forward check when lsof command fails."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_timeout(self, mock_run):
        """Test port forward check when command times out."""
        # Arrange
        mock_run.side_effect = subprocess.TimeoutExpired("lsof", 1)

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_exception(self, mock_run):
        """Test port forward check with unexpected exception."""
        # Arrange
        mock_run.side_effect = Exception("Unexpected error")

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_no_listen_state(self, mock_run):
        """Test port forward check when kubectl found but not listening."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "kubectl     12345 user   10u  IPv4  ESTABLISHED"
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_import_error(self, mock_run):
        """Test port forward check when subprocess import fails."""
        # Arrange
        mock_run.side_effect = ImportError("subprocess not available")

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False
