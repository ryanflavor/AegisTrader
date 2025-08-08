"""Comprehensive tests for EnvironmentAdapter following TDD and hexagonal architecture.

These tests verify the adapter's implementation of the EnvironmentPort interface,
following TDD principles with proper AAA pattern and focusing on behavior testing
rather than implementation details.
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest

from aegis_sdk_dev.domain.models import ServiceConfiguration, ValidationIssue, ValidationLevel
from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter
from aegis_sdk_dev.infrastructure.factory import InfrastructureFactory
from aegis_sdk_dev.ports.environment import EnvironmentPort


class TestEnvironmentAdapterArchitecture:
    """Test EnvironmentAdapter's adherence to hexagonal architecture principles."""

    def test_adapter_implements_port_interface(self):
        """Test that EnvironmentAdapter correctly implements EnvironmentPort.

        This ensures proper separation between ports and adapters.
        """
        # Arrange & Act: Create adapter through factory
        adapter = InfrastructureFactory.create_environment()

        # Assert: Verify port implementation
        assert isinstance(adapter, EnvironmentPort)

        # Verify all required methods are present
        required_methods = [
            "get_environment_variable",
            "set_environment_variable",
            "is_kubernetes_environment",
            "is_docker_environment",
            "detect_environment",
            "get_service_account_path",
            "get_namespace",
        ]
        for method in required_methods:
            assert hasattr(adapter, method)

    def test_adapter_is_stateless(self):
        """Test that EnvironmentAdapter maintains no state between calls.

        Stateless adapters are easier to test and maintain.
        """
        # Arrange: Create multiple adapter instances
        adapter1 = InfrastructureFactory.create_environment()
        adapter2 = InfrastructureFactory.create_environment()

        # Act: Perform operations on adapter1
        with patch.dict(os.environ, {"TEST_VAR": "value1"}):
            result1 = adapter1.get_environment_variable("TEST_VAR")

        # Assert: Verify adapters are independent
        assert adapter1 is not adapter2
        assert result1 == "value1"

        # Verify adapter2 is not affected
        with patch.dict(os.environ, {"TEST_VAR": "value2"}):
            result2 = adapter2.get_environment_variable("TEST_VAR")
            assert result2 == "value2"


class TestEnvironmentVariableOperations:
    """Test environment variable operations with proper isolation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Arrange: Create adapter through factory for dependency injection
        self.adapter = InfrastructureFactory.create_environment()

    def test_get_environment_variable_existing(self):
        """Test retrieving an existing environment variable."""
        # Arrange: Set up environment
        with patch.dict(os.environ, {"EXISTING_VAR": "test_value"}):
            # Act
            result = self.adapter.get_environment_variable("EXISTING_VAR")

            # Assert
            assert result == "test_value"

    def test_get_environment_variable_missing_with_default(self):
        """Test retrieving missing variable returns default."""
        # Arrange: Ensure variable doesn't exist
        with patch.dict(os.environ, {}, clear=True):
            # Act
            result = self.adapter.get_environment_variable("MISSING_VAR", default="default_value")

            # Assert
            assert result == "default_value"

    def test_get_environment_variable_missing_without_default(self):
        """Test retrieving missing variable without default returns None."""
        # Arrange: Ensure variable doesn't exist
        with patch.dict(os.environ, {}, clear=True):
            # Act
            result = self.adapter.get_environment_variable("MISSING_VAR")

            # Assert
            assert result is None

    def test_set_environment_variable_valid(self):
        """Test setting environment variable with valid input."""
        # Arrange: Start with clean environment
        with patch.dict(os.environ, {}, clear=True):
            # Act
            self.adapter.set_environment_variable("NEW_VAR", "new_value")

            # Assert: Verify variable was set
            assert os.environ.get("NEW_VAR") == "new_value"

    def test_set_environment_variable_empty_name_raises(self):
        """Test setting variable with empty name raises ValueError.

        Input validation at the port boundary.
        """
        # Act & Assert
        with pytest.raises(ValueError, match="Environment variable name cannot be empty"):
            self.adapter.set_environment_variable("", "value")

    def test_set_environment_variable_overwrites_existing(self):
        """Test that setting existing variable overwrites it."""
        # Arrange: Set initial value
        with patch.dict(os.environ, {"EXISTING": "old_value"}):
            # Act
            self.adapter.set_environment_variable("EXISTING", "new_value")

            # Assert
            assert os.environ.get("EXISTING") == "new_value"


class TestEnvironmentDetection:
    """Test environment detection capabilities."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = InfrastructureFactory.create_environment()

    @patch("pathlib.Path.exists")
    def test_is_kubernetes_environment_with_service_account(self, mock_exists):
        """Test Kubernetes detection via service account directory."""
        # Arrange: Mock service account directory exists
        mock_exists.return_value = True

        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is True
        mock_exists.assert_called_with()

    @patch("pathlib.Path.exists")
    @patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "k8s.local"})
    def test_is_kubernetes_environment_with_env_var(self, mock_exists):
        """Test Kubernetes detection via environment variable."""
        # Arrange: Service account doesn't exist but env var is set
        mock_exists.return_value = False

        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is True

    @patch("pathlib.Path.exists")
    @patch.dict(os.environ, {}, clear=True)
    def test_is_kubernetes_environment_false(self, mock_exists):
        """Test Kubernetes detection returns False when not in K8s."""
        # Arrange: No K8s indicators
        mock_exists.return_value = False

        # Act
        result = self.adapter.is_kubernetes_environment()

        # Assert
        assert result is False

    def test_is_docker_environment_with_dockerenv(self):
        """Test Docker detection via .dockerenv file."""
        # Arrange: Mock .dockerenv exists
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            # Act
            result = self.adapter.is_docker_environment()

            # Assert
            assert result is True

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_is_docker_environment_with_cgroup(self, mock_path_class):
        """Test Docker detection via cgroup file."""
        # Arrange: .dockerenv doesn't exist but cgroup contains docker
        mock_dockerenv = Mock()
        mock_dockerenv.exists.return_value = False

        mock_cgroup = Mock()
        mock_cgroup.exists.return_value = True
        mock_cgroup.read_text.return_value = "12:devices:/docker/container_id"

        def path_side_effect(path_str):
            if path_str == "/.dockerenv":
                return mock_dockerenv
            elif path_str == "/proc/self/cgroup":
                return mock_cgroup
            return Mock()

        mock_path_class.side_effect = path_side_effect

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is True

    @patch("pathlib.Path.exists")
    def test_is_docker_environment_false(self, mock_exists):
        """Test Docker detection returns False when not in Docker."""
        # Arrange: No Docker indicators
        mock_exists.return_value = False

        # Act
        result = self.adapter.is_docker_environment()

        # Assert
        assert result is False

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment")
    @patch.object(EnvironmentAdapter, "is_docker_environment")
    def test_detect_environment_kubernetes(self, mock_docker, mock_k8s):
        """Test environment detection returns 'kubernetes'."""
        # Arrange
        mock_k8s.return_value = True
        mock_docker.return_value = False

        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "kubernetes"

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment")
    @patch.object(EnvironmentAdapter, "is_docker_environment")
    def test_detect_environment_docker(self, mock_docker, mock_k8s):
        """Test environment detection returns 'docker'."""
        # Arrange
        mock_k8s.return_value = False
        mock_docker.return_value = True

        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "docker"

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment")
    @patch.object(EnvironmentAdapter, "is_docker_environment")
    def test_detect_environment_local(self, mock_docker, mock_k8s):
        """Test environment detection returns 'local'."""
        # Arrange
        mock_k8s.return_value = False
        mock_docker.return_value = False

        # Act
        result = self.adapter.detect_environment()

        # Assert
        assert result == "local"


class TestKubernetesSpecificOperations:
    """Test Kubernetes-specific operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = InfrastructureFactory.create_environment()

    @patch("pathlib.Path.exists")
    def test_get_service_account_path_exists(self, mock_exists):
        """Test getting service account path when it exists."""
        # Arrange
        mock_exists.return_value = True

        # Act
        result = self.adapter.get_service_account_path()

        # Assert
        assert result == "/var/run/secrets/kubernetes.io/serviceaccount"

    @patch("pathlib.Path.exists")
    def test_get_service_account_path_not_exists(self, mock_exists):
        """Test getting service account path when it doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.adapter.get_service_account_path()

        # Assert
        assert result is None

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_get_namespace_exists(self, mock_read_text, mock_exists):
        """Test getting namespace when file exists."""
        # Arrange
        mock_exists.return_value = True
        mock_read_text.return_value = "  default  \n"

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result == "default"

    @patch("pathlib.Path.exists")
    def test_get_namespace_not_exists(self, mock_exists):
        """Test getting namespace when file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result is None

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_get_namespace_read_error(self, mock_read_text, mock_exists):
        """Test namespace returns None on read error."""
        # Arrange
        mock_exists.return_value = True
        mock_read_text.side_effect = OSError("Permission denied")

        # Act
        result = self.adapter.get_namespace()

        # Assert
        assert result is None


class TestPortForwardDetection:
    """Test kubectl port-forward detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = InfrastructureFactory.create_environment()

    @patch("subprocess.run")
    def test_check_port_forward_active(self, mock_run):
        """Test port-forward detection when active."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "kubectl port-forward LISTEN"
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_check_port_forward_not_active(self, mock_run):
        """Test port-forward detection when not active."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False

    @patch("subprocess.run")
    def test_check_port_forward_error_handling(self, mock_run):
        """Test port-forward detection handles errors gracefully."""
        # Arrange
        mock_run.side_effect = Exception("Command failed")

        # Act
        result = self.adapter._check_port_forward()

        # Assert
        assert result is False


class TestIntegrationWithDomainModels:
    """Test integration with Pydantic domain models."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = InfrastructureFactory.create_environment()

    def test_environment_validation_with_service_configuration(self):
        """Test environment detection integrates with ServiceConfiguration model."""
        # Arrange: Create a service configuration
        config = ServiceConfiguration(
            service_name="test-service", nats_url="nats://localhost:4222", environment="auto"
        )

        # Act: Detect environment and update config
        detected_env = self.adapter.detect_environment()

        # Assert: Verify environment can be used with Pydantic model
        assert detected_env in ["local", "docker", "kubernetes"]

        # Update config based on detected environment
        if detected_env == "kubernetes":
            updated_config = config.model_copy(update={"environment": "kubernetes"})
        else:
            updated_config = config.model_copy(update={"environment": detected_env})

        assert updated_config.environment in ["local", "docker", "kubernetes"]

    @patch.object(EnvironmentAdapter, "is_kubernetes_environment")
    def test_create_validation_issue_for_k8s_detection(self, mock_k8s):
        """Test creating ValidationIssue when K8s detection fails."""
        # Arrange
        mock_k8s.return_value = False

        # Act: Attempt K8s-specific operation
        namespace = self.adapter.get_namespace()

        # Create validation issue if namespace not available
        if namespace is None and not self.adapter.is_kubernetes_environment():
            issue = ValidationIssue(
                level=ValidationLevel.WARNING,
                category="K8S",
                message="Not running in Kubernetes environment",
                resolution="Deploy to Kubernetes cluster or use port-forwarding for local development",
                details={"environment": self.adapter.detect_environment()},
            )

        # Assert
        assert issue.level == ValidationLevel.WARNING
        assert issue.category == "K8S"
        assert "details" in issue.model_dump()


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = InfrastructureFactory.create_environment()

    def test_set_environment_variable_with_special_characters(self):
        """Test setting environment variable with special characters."""
        # Arrange
        special_value = "value!@#$%^&*(){}[]|\\:;\"'<>,.?/"

        with patch.dict(os.environ, {}, clear=True):
            # Act
            self.adapter.set_environment_variable("SPECIAL_VAR", special_value)

            # Assert
            assert os.environ.get("SPECIAL_VAR") == special_value

    def test_set_environment_variable_with_unicode(self):
        """Test setting environment variable with unicode characters."""
        # Arrange
        unicode_value = "Hello 世界 🌍 مرحبا"

        with patch.dict(os.environ, {}, clear=True):
            # Act
            self.adapter.set_environment_variable("UNICODE_VAR", unicode_value)

            # Assert
            assert os.environ.get("UNICODE_VAR") == unicode_value

    @patch("aegis_sdk_dev.infrastructure.environment_adapter.Path")
    def test_cgroup_read_permission_error(self, mock_path_class):
        """Test handling permission errors when reading cgroup."""
        # Arrange
        mock_dockerenv = Mock()
        mock_dockerenv.exists.return_value = False

        mock_cgroup = Mock()
        mock_cgroup.exists.return_value = True
        mock_cgroup.read_text.side_effect = PermissionError("Access denied")

        def path_side_effect(path_str):
            if path_str == "/.dockerenv":
                return mock_dockerenv
            elif path_str == "/proc/self/cgroup":
                return mock_cgroup
            return Mock()

        mock_path_class.side_effect = path_side_effect

        # Act
        result = self.adapter.is_docker_environment()

        # Assert: Should handle error gracefully
        assert result is False

    def test_environment_variable_name_validation(self):
        """Test environment variable name validation."""
        # Arrange: Test empty name specifically (others are valid but whitespace)
        # Act & Assert: Only empty string raises ValueError
        with pytest.raises(ValueError, match="Environment variable name cannot be empty"):
            self.adapter.set_environment_variable("", "value")

        # Whitespace names are technically valid for os.environ
        # but may not be meaningful - they don't raise ValueError
        whitespace_names = ["  ", "\t", "\n"]
        for name in whitespace_names:
            # These should work without raising
            self.adapter.set_environment_variable(name, "value")


class TestFactoryIntegration:
    """Test factory pattern integration."""

    def test_factory_creates_correct_adapter_type(self):
        """Test factory creates EnvironmentAdapter instance."""
        # Act
        adapter = InfrastructureFactory.create_environment()

        # Assert
        assert isinstance(adapter, EnvironmentAdapter)
        assert isinstance(adapter, EnvironmentPort)

    def test_factory_creates_independent_instances(self):
        """Test factory creates independent adapter instances."""
        # Act
        adapter1 = InfrastructureFactory.create_environment()
        adapter2 = InfrastructureFactory.create_environment()

        # Assert
        assert adapter1 is not adapter2

        # Verify both work independently
        with patch.dict(os.environ, {"TEST": "value1"}):
            result1 = adapter1.get_environment_variable("TEST")

        with patch.dict(os.environ, {"TEST": "value2"}):
            result2 = adapter2.get_environment_variable("TEST")

        assert result1 == "value1"
        assert result2 == "value2"
