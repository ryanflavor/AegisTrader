"""Unit tests for ConfigurationAdapter following TDD principles."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from aegis_sdk_dev.infrastructure.configuration_adapter import ConfigurationAdapter


class RunConfigurationAdapter:
    """Test ConfigurationAdapter infrastructure implementation."""

    @pytest.fixture
    def adapter(self) -> ConfigurationAdapter:
        """Create ConfigurationAdapter instance."""
        return ConfigurationAdapter()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_load_configuration_yaml(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test loading YAML configuration."""
        # Arrange
        config_data = {
            "service_name": "test-service",
            "nats_url": "nats://localhost:4222",
            "environment": "local",
        }
        config_path = temp_dir / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded == config_data
        assert loaded["service_name"] == "test-service"
        assert loaded["nats_url"] == "nats://localhost:4222"
        assert loaded["environment"] == "local"

    @pytest.mark.asyncio
    async def test_load_configuration_yml(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test loading YML configuration."""
        # Arrange
        config_data = {"service_name": "test-service", "debug": True}
        config_path = temp_dir / "config.yml"
        config_path.write_text(yaml.dump(config_data))

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded == config_data
        assert loaded["debug"] is True

    @pytest.mark.asyncio
    async def test_load_configuration_json(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test loading JSON configuration."""
        # Arrange
        config_data = {
            "service_name": "test-service",
            "port": 8080,
            "features": ["auth", "logging"],
        }
        config_path = temp_dir / "config.json"
        config_path.write_text(json.dumps(config_data))

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded == config_data
        assert loaded["port"] == 8080
        assert loaded["features"] == ["auth", "logging"]

    @pytest.mark.asyncio
    async def test_load_configuration_env(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test loading .env configuration."""
        # Arrange
        env_content = """
        # Comment line
        SERVICE_NAME=test-service
        NATS_URL="nats://localhost:4222"
        DEBUG=true
        PORT=8080
        """
        config_path = temp_dir / ".env"
        config_path.write_text(env_content)

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded["SERVICE_NAME"] == "test-service"
        assert loaded["NATS_URL"] == "nats://localhost:4222"
        assert loaded["DEBUG"] == "true"
        assert loaded["PORT"] == "8080"

    @pytest.mark.asyncio
    async def test_load_configuration_file_not_found(self, adapter: ConfigurationAdapter):
        """Test loading configuration from non-existent file."""
        # Arrange
        non_existent_path = "/non/existent/config.yaml"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            await adapter.load_configuration(non_existent_path)

    @pytest.mark.asyncio
    async def test_load_configuration_invalid_yaml(
        self, adapter: ConfigurationAdapter, temp_dir: Path
    ):
        """Test loading invalid YAML configuration."""
        # Arrange
        config_path = temp_dir / "invalid.yaml"
        config_path.write_text("invalid: yaml: content: ][")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid configuration file"):
            await adapter.load_configuration(str(config_path))

    @pytest.mark.asyncio
    async def test_load_configuration_invalid_json(
        self, adapter: ConfigurationAdapter, temp_dir: Path
    ):
        """Test loading invalid JSON configuration."""
        # Arrange
        config_path = temp_dir / "invalid.json"
        config_path.write_text("{invalid json}")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid configuration file"):
            await adapter.load_configuration(str(config_path))

    @pytest.mark.asyncio
    async def test_load_configuration_empty_yaml(
        self, adapter: ConfigurationAdapter, temp_dir: Path
    ):
        """Test loading empty YAML configuration."""
        # Arrange
        config_path = temp_dir / "empty.yaml"
        config_path.write_text("")

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded == {}

    @pytest.mark.asyncio
    async def test_save_configuration_yaml(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test saving YAML configuration."""
        # Arrange
        config_data = {
            "service_name": "test-service",
            "nats_url": "nats://localhost:4222",
            "environment": "local",
        }
        config_path = temp_dir / "output.yaml"

        # Act
        await adapter.save_configuration(str(config_path), config_data)

        # Assert
        assert config_path.exists()
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded == config_data

    @pytest.mark.asyncio
    async def test_save_configuration_json(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test saving JSON configuration."""
        # Arrange
        config_data = {
            "service_name": "test-service",
            "port": 8080,
            "features": ["auth", "logging"],
        }
        config_path = temp_dir / "output.json"

        # Act
        await adapter.save_configuration(str(config_path), config_data)

        # Assert
        assert config_path.exists()
        loaded = json.loads(config_path.read_text())
        assert loaded == config_data

    @pytest.mark.asyncio
    async def test_save_configuration_env(self, adapter: ConfigurationAdapter, temp_dir: Path):
        """Test saving .env configuration."""
        # Arrange
        config_data = {
            "service-name": "test service",
            "nats_url": "nats://localhost:4222",
            "debug": True,
            "port": 8080,
        }
        config_path = temp_dir / ".env"

        # Act
        await adapter.save_configuration(str(config_path), config_data)

        # Assert
        assert config_path.exists()
        content = config_path.read_text()
        assert 'SERVICE_NAME="test service"' in content
        assert "NATS_URL=nats://localhost:4222" in content
        assert "DEBUG=True" in content
        assert "PORT=8080" in content

    @pytest.mark.asyncio
    async def test_save_configuration_creates_parent_dir(
        self, adapter: ConfigurationAdapter, temp_dir: Path
    ):
        """Test saving configuration creates parent directory if needed."""
        # Arrange
        config_data = {"service_name": "test-service"}
        config_path = temp_dir / "nested" / "path" / "config.yaml"

        # Act
        await adapter.save_configuration(str(config_path), config_data)

        # Assert
        assert config_path.exists()
        assert config_path.parent.exists()

    @pytest.mark.asyncio
    async def test_save_configuration_write_error(self, adapter: ConfigurationAdapter):
        """Test handling write errors when saving configuration."""
        # Arrange
        config_data = {"service_name": "test-service"}
        invalid_path = "/invalid/path/config.yaml"

        # Act & Assert
        with pytest.raises(OSError, match="Unable to save configuration"):
            await adapter.save_configuration(invalid_path, config_data)

    def test_validate_configuration_valid(self, adapter: ConfigurationAdapter):
        """Test validating valid configuration."""
        # Arrange
        config = {
            "service_name": "test-service",
            "nats_url": "nats://localhost:4222",
            "environment": "local",
        }

        # Act
        is_valid, errors = adapter.validate_configuration(config)

        # Assert
        assert is_valid is True
        assert errors == []

    def test_validate_configuration_missing_required(self, adapter: ConfigurationAdapter):
        """Test validating configuration with missing required fields."""
        # Arrange
        config = {"nats_url": "nats://localhost:4222"}

        # Act
        is_valid, errors = adapter.validate_configuration(config)

        # Assert
        assert is_valid is False
        assert len(errors) == 1
        assert "Missing required field: service_name" in errors

    def test_validate_configuration_invalid_service_name(self, adapter: ConfigurationAdapter):
        """Test validating configuration with invalid service name."""
        # Arrange
        test_cases = [
            ({"service_name": ""}, "non-empty string"),
            ({"service_name": "ab"}, "at least 3 characters"),
            ({"service_name": 123}, "non-empty string"),
            ({"service_name": None}, "non-empty string"),
        ]

        # Act & Assert
        for config, expected_error in test_cases:
            is_valid, errors = adapter.validate_configuration(config)
            assert is_valid is False
            assert any(expected_error in error for error in errors)

    def test_validate_configuration_invalid_nats_url(self, adapter: ConfigurationAdapter):
        """Test validating configuration with invalid NATS URL."""
        # Arrange
        config = {
            "service_name": "test-service",
            "nats_url": "http://localhost:4222",  # Invalid protocol
        }

        # Act
        is_valid, errors = adapter.validate_configuration(config)

        # Assert
        assert is_valid is False
        assert any("Invalid NATS URL format" in error for error in errors)

    def test_validate_configuration_valid_nats_urls(self, adapter: ConfigurationAdapter):
        """Test validating configuration with various valid NATS URLs."""
        # Arrange
        valid_urls = [
            "nats://localhost:4222",
            "tls://secure.nats.io:4222",
            "ws://localhost:8080",
            "wss://secure.nats.io:443",
        ]

        # Act & Assert
        for url in valid_urls:
            config = {"service_name": "test-service", "nats_url": url}
            is_valid, errors = adapter.validate_configuration(config)
            assert is_valid is True
            assert errors == []

    def test_validate_configuration_invalid_environment(self, adapter: ConfigurationAdapter):
        """Test validating configuration with invalid environment."""
        # Arrange
        config = {
            "service_name": "test-service",
            "environment": "invalid_env",
        }

        # Act
        is_valid, errors = adapter.validate_configuration(config)

        # Assert
        assert is_valid is False
        assert any("Invalid environment" in error for error in errors)

    def test_validate_configuration_valid_environments(self, adapter: ConfigurationAdapter):
        """Test validating configuration with valid environments."""
        # Arrange
        valid_envs = ["auto", "local", "kubernetes", "development", "staging", "production"]

        # Act & Assert
        for env in valid_envs:
            config = {"service_name": "test-service", "environment": env}
            is_valid, errors = adapter.validate_configuration(config)
            assert is_valid is True
            assert errors == []

    def test_validate_configuration_multiple_errors(self, adapter: ConfigurationAdapter):
        """Test validating configuration with multiple errors."""
        # Arrange
        config = {
            "service_name": "ab",  # Too short
            "nats_url": "http://localhost:4222",  # Invalid protocol
            "environment": "invalid",  # Invalid environment
        }

        # Act
        is_valid, errors = adapter.validate_configuration(config)

        # Assert
        assert is_valid is False
        assert len(errors) >= 3

    def test_parse_env_file_format(self, adapter: ConfigurationAdapter):
        """Test parsing .env file format."""
        # Arrange
        content = """
        # This is a comment
        SERVICE_NAME=test-service
        NATS_URL="nats://localhost:4222"
        DEBUG='true'
        PORT=8080
        EMPTY_LINE

        # Another comment
        FEATURE_FLAG=enabled
        """

        # Act
        result = adapter._parse_env_file(content)

        # Assert
        assert result["SERVICE_NAME"] == "test-service"
        assert result["NATS_URL"] == "nats://localhost:4222"
        assert result["DEBUG"] == "true"
        assert result["PORT"] == "8080"
        assert result["FEATURE_FLAG"] == "enabled"
        assert "EMPTY_LINE" not in result  # Empty values should be excluded

    def test_format_env_file(self, adapter: ConfigurationAdapter):
        """Test formatting configuration as .env file."""
        # Arrange
        config = {
            "service-name": "test service",
            "nats_url": "nats://localhost:4222",
            "debug": True,
            "port": 8080,
        }

        # Act
        result = adapter._format_env_file(config)

        # Assert
        lines = result.split("\n")
        assert 'SERVICE_NAME="test service"' in lines
        assert "NATS_URL=nats://localhost:4222" in lines
        assert "DEBUG=True" in lines
        assert "PORT=8080" in lines

    @pytest.mark.asyncio
    async def test_load_configuration_with_default_extension(
        self, adapter: ConfigurationAdapter, temp_dir: Path
    ):
        """Test loading configuration without explicit extension uses YAML."""
        # Arrange
        config_data = {"service_name": "test-service"}
        config_path = temp_dir / "config"
        config_path.write_text(yaml.dump(config_data))

        # Act
        loaded = await adapter.load_configuration(str(config_path))

        # Assert
        assert loaded == config_data
