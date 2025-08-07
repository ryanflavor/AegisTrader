"""Tests for quickstart module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from aegis_sdk_dev.quickstart import (
    ProjectConfig,
    ServiceConfig,
    ServiceTemplate,
    bootstrap_service,
)


class TestProjectConfig:
    """Test ProjectConfig model."""

    def test_valid_config(self):
        """Test creating a valid project configuration."""
        config = ProjectConfig(
            name="test-service",
            description="Test service description",
            template=ServiceTemplate.BASIC,
            service_name="test-svc",
        )
        assert config.name == "test-service"
        assert config.template == ServiceTemplate.BASIC
        assert config.include_tests is True  # Default value

    def test_invalid_name(self):
        """Test that invalid names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectConfig(
                name="Test Service",  # Spaces not allowed
                description="Test",
                template=ServiceTemplate.BASIC,
                service_name="test",
            )
        assert "name" in str(exc_info.value)

    def test_template_enum_values(self):
        """Test all template enum values."""
        templates = [
            ServiceTemplate.BASIC,
            ServiceTemplate.SINGLE_ACTIVE,
            ServiceTemplate.EVENT_DRIVEN,
            ServiceTemplate.FULL_FEATURED,
        ]
        for template in templates:
            config = ProjectConfig(
                name="test", description="Test", template=template, service_name="test"
            )
            assert config.template == template


class TestServiceConfig:
    """Test ServiceConfig model."""

    def test_valid_service_config(self):
        """Test creating valid service configuration."""
        config = ServiceConfig(
            service_name="test-service", service_type="basic", nats_url="nats://localhost:4222"
        )
        assert config.service_name == "test-service"
        assert config.service_type == "basic"
        assert config.nats_url == "nats://localhost:4222"

    def test_optional_fields(self):
        """Test optional fields have proper defaults."""
        config = ServiceConfig(service_name="test", service_type="basic")
        assert config.nats_url is None
        assert config.environment == "development"
        assert config.debug is False

    def test_invalid_url(self):
        """Test that invalid NATS URLs are rejected."""
        with pytest.raises(ValidationError):
            ServiceConfig(
                service_name="test",
                service_type="basic",
                nats_url="invalid-url",  # Not a valid URL
            )


class TestBootstrapService:
    """Test bootstrap_service function."""

    @patch("aegis_sdk_dev.quickstart.sys")
    @patch("aegis_sdk_dev.quickstart.Path")
    def test_bootstrap_service_imports(self, mock_path, mock_sys):
        """Test that bootstrap adds correct paths to sys.path."""
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.parent = Path("/test/path")

        config = ServiceConfig(service_name="test", service_type="basic")

        # Should not raise
        bootstrap_service(config)

        # Verify sys.path was modified
        assert mock_sys.path.insert.called

    def test_bootstrap_with_invalid_config(self):
        """Test bootstrap with invalid configuration."""
        with pytest.raises(TypeError):
            bootstrap_service(None)  # Invalid config

    @patch.dict("sys.modules", {"aegis_sdk": Mock()})
    def test_bootstrap_returns_service(self):
        """Test that bootstrap returns a service instance."""
        config = ServiceConfig(service_name="test", service_type="basic")

        with patch("aegis_sdk_dev.quickstart.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            # Mock the aegis_sdk import
            mock_service = Mock()
            with patch("aegis_sdk_dev.quickstart.create_service", return_value=mock_service):
                result = bootstrap_service(config)
                assert result == mock_service


class TestServiceTemplate:
    """Test ServiceTemplate enum."""

    def test_all_templates_defined(self):
        """Test that all expected templates are defined."""
        expected = {"BASIC", "SINGLE_ACTIVE", "EVENT_DRIVEN", "FULL_FEATURED"}
        actual = {t.name for t in ServiceTemplate}
        assert actual == expected

    def test_template_values(self):
        """Test template string values."""
        assert ServiceTemplate.BASIC.value == "basic"
        assert ServiceTemplate.SINGLE_ACTIVE.value == "single_active"
        assert ServiceTemplate.EVENT_DRIVEN.value == "event_driven"
        assert ServiceTemplate.FULL_FEATURED.value == "full_featured"

    def test_template_from_string(self):
        """Test creating template from string value."""
        template = ServiceTemplate("basic")
        assert template == ServiceTemplate.BASIC

        with pytest.raises(ValueError):
            ServiceTemplate("invalid_template")
