"""Unit tests for the environment configuration adapter."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.infrastructure.environment_configuration_adapter import EnvironmentConfigurationAdapter


class TestEnvironmentConfigurationAdapter:
    """Test cases for the EnvironmentConfigurationAdapter."""

    def test_default_instance_id(self):
        """Test getting instance ID with defaults."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            instance_id = adapter.get_instance_id()

            # Assert
            assert instance_id == "echo-local"

    def test_instance_id_from_environment(self):
        """Test getting instance ID from environment variable."""
        # Arrange
        with patch.dict(os.environ, {"INSTANCE_ID": "test-instance-123"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            instance_id = adapter.get_instance_id()

            # Assert
            assert instance_id == "test-instance-123"

    def test_instance_id_from_hostname(self):
        """Test getting instance ID from hostname when INSTANCE_ID not set."""
        # Arrange
        with patch.dict(os.environ, {"HOSTNAME": "pod-abc-123"}, clear=True):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            instance_id = adapter.get_instance_id()

            # Assert
            assert instance_id == "pod-abc-123"

    def test_service_name_default(self):
        """Test getting service name with default."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            service_name = adapter.get_service_name()

            # Assert
            assert service_name == "echo-service"

    def test_service_name_from_environment(self):
        """Test getting service name from environment."""
        # Arrange
        with patch.dict(os.environ, {"SERVICE_NAME": "custom-echo"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            service_name = adapter.get_service_name()

            # Assert
            assert service_name == "custom-echo"

    def test_service_name_from_defaults(self):
        """Test getting service name from provided defaults."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvironmentConfigurationAdapter(defaults={"service_name": "default-echo"})

            # Act
            service_name = adapter.get_service_name()

            # Assert
            assert service_name == "default-echo"

    def test_debug_enabled_true(self):
        """Test debug mode detection when enabled."""
        # Arrange
        test_cases = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]

        for value in test_cases:
            with patch.dict(os.environ, {"DEBUG": value}):
                adapter = EnvironmentConfigurationAdapter()

                # Act & Assert
                assert adapter.is_debug_enabled() is True, f"Failed for value: {value}"

    def test_debug_enabled_false(self):
        """Test debug mode detection when disabled."""
        # Arrange
        test_cases = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", ""]

        for value in test_cases:
            with patch.dict(os.environ, {"DEBUG": value}):
                adapter = EnvironmentConfigurationAdapter()

                # Act & Assert
                assert adapter.is_debug_enabled() is False, f"Failed for value: {value}"

    def test_nats_url_none_for_auto_detect(self):
        """Test NATS URL returns None for auto-detect."""
        # Arrange
        with patch.dict(os.environ, {"NATS_URL": "auto-detect"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            nats_url = adapter.get_nats_url()

            # Assert
            assert nats_url is None

    def test_nats_url_explicit(self):
        """Test NATS URL returns explicit value."""
        # Arrange
        with patch.dict(os.environ, {"NATS_URL": "nats://localhost:4222"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            nats_url = adapter.get_nats_url()

            # Assert
            assert nats_url == "nats://localhost:4222"

    def test_get_config_value_from_environment(self):
        """Test getting arbitrary config value from environment."""
        # Arrange
        with patch.dict(os.environ, {"CUSTOM_KEY": "custom_value"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            value = adapter.get_config_value("CUSTOM_KEY")

            # Assert
            assert value == "custom_value"

    def test_get_config_value_from_defaults(self):
        """Test getting config value from defaults."""
        # Arrange
        adapter = EnvironmentConfigurationAdapter(defaults={"custom_key": "default_value"})

        # Act
        value = adapter.get_config_value("custom_key")

        # Assert
        assert value == "default_value"

    def test_get_config_value_uses_cache(self):
        """Test that config values are cached."""
        # Arrange
        with patch.dict(os.environ, {"CACHED_KEY": "initial_value"}):
            adapter = EnvironmentConfigurationAdapter()

            # Act - Get value first time
            value1 = adapter.get_config_value("CACHED_KEY")

            # Change environment (should not affect cached value)
            os.environ["CACHED_KEY"] = "changed_value"
            value2 = adapter.get_config_value("CACHED_KEY")

            # Assert
            assert value1 == "initial_value"
            assert value2 == "initial_value"  # Should still be cached value

    def test_is_kubernetes_environment_true(self):
        """Test Kubernetes environment detection when in K8s."""
        # Arrange
        with patch("os.path.exists", return_value=True):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            in_k8s = adapter.is_kubernetes_environment()

            # Assert
            assert in_k8s is True

    def test_is_kubernetes_environment_false(self):
        """Test Kubernetes environment detection when not in K8s."""
        # Arrange
        with patch("os.path.exists", return_value=False):
            adapter = EnvironmentConfigurationAdapter()

            # Act
            in_k8s = adapter.is_kubernetes_environment()

            # Assert
            assert in_k8s is False
