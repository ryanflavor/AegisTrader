"""Tests for the configuration adapter.

These tests verify that the configuration adapter correctly
loads and validates configuration from environment variables.
"""

import os
from unittest.mock import Mock, patch

import pytest
from app.domain.exceptions import ConfigurationException
from app.domain.models import ServiceConfiguration
from app.infrastructure.configuration_adapter import EnvironmentConfigurationAdapter


class TestEnvironmentConfigurationAdapter:
    """Test cases for EnvironmentConfigurationAdapter."""

    @pytest.fixture
    def adapter(self) -> EnvironmentConfigurationAdapter:
        """Create a configuration adapter instance."""
        return EnvironmentConfigurationAdapter()

    def test_load_default_configuration(self, adapter: EnvironmentConfigurationAdapter) -> None:
        """Test loading configuration with default values."""
        # Arrange - Use empty environment
        with patch.dict(os.environ, {}, clear=True):
            # Act
            config = adapter.load_configuration()

            # Assert
            assert config.nats_url == "nats://localhost:4222"
            assert config.api_port == 8100
            assert config.log_level == "INFO"
            assert config.environment == "development"

    def test_load_configuration_from_environment(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test loading configuration from environment variables."""
        # Arrange
        env_vars = {
            "NATS_URL": "nats://prod-nats:4222",
            "API_PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "ENVIRONMENT": "production",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Act
            config = adapter.load_configuration()

            # Assert
            assert config.nats_url == "nats://prod-nats:4222"
            assert config.api_port == 9000
            assert config.log_level == "DEBUG"
            assert config.environment == "production"

    def test_invalid_log_level_raises_exception(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that invalid log levels raise ConfigurationException."""
        # Arrange
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}, clear=True):
            # Act & Assert
            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()

            assert "Invalid log level: INVALID" in str(exc_info.value)

    def test_invalid_environment_raises_exception(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that invalid environments raise ConfigurationException."""
        # Arrange
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}, clear=True):
            # Act & Assert
            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()

            assert "Invalid environment: testing" in str(exc_info.value)

    def test_invalid_port_format_raises_exception(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that invalid port formats raise ConfigurationException."""
        # Arrange
        with patch.dict(os.environ, {"API_PORT": "not-a-number"}, clear=True):
            # Act & Assert
            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()

            assert "Failed to load configuration" in str(exc_info.value)

    def test_tls_nats_url_accepted(self, adapter: EnvironmentConfigurationAdapter) -> None:
        """Test that TLS NATS URLs are properly loaded."""
        # Arrange
        with patch.dict(os.environ, {"NATS_URL": "tls://secure-nats:4222"}, clear=True):
            # Act
            config = adapter.load_configuration()

            # Assert
            assert config.nats_url == "tls://secure-nats:4222"

    @patch("os.getuid")
    def test_privileged_port_without_root_raises_exception(
        self, mock_getuid: Mock, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that privileged ports without root access raise exception."""
        # Arrange
        mock_getuid.return_value = 1000  # Non-root user

        with patch.dict(os.environ, {"API_PORT": "80"}, clear=True):
            # Act & Assert
            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()

            assert "Port 80 requires root privileges" in str(exc_info.value)

    @patch("os.getuid")
    def test_privileged_port_with_root_allowed(
        self, mock_getuid: Mock, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that privileged ports are allowed for root user."""
        # Arrange
        mock_getuid.return_value = 0  # Root user

        with patch.dict(os.environ, {"API_PORT": "80"}, clear=True):
            # Act
            config = adapter.load_configuration()

            # Assert
            assert config.api_port == 80

    def test_production_with_localhost_nats_raises_exception(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that production environment with localhost NATS raises exception."""
        # Arrange
        env_vars = {
            "ENVIRONMENT": "production",
            "NATS_URL": "nats://localhost:4222",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Act & Assert
            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()

            assert "Production environment should not use localhost in NATS URL" in str(
                exc_info.value
            )

    def test_validate_configuration_valid(self, adapter: EnvironmentConfigurationAdapter) -> None:
        """Test validating a valid configuration."""
        # Arrange
        config = ServiceConfiguration(
            nats_url="nats://nats-server:4222",
            api_port=8080,
            log_level="INFO",
            environment="development",
        )

        # Act & Assert - Should not raise
        adapter.validate_configuration(config)

    def test_validate_configuration_production_localhost(
        self, adapter: EnvironmentConfigurationAdapter
    ) -> None:
        """Test that validation fails for production with localhost."""
        # Arrange
        config = ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            environment="production",
        )

        # Act & Assert
        with pytest.raises(ConfigurationException) as exc_info:
            adapter.validate_configuration(config)

        assert "Production environment should not use localhost in NATS URL" in str(exc_info.value)
