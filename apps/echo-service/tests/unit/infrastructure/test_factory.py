"""Unit tests for EchoServiceFactory following TDD and hexagonal architecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.application.echo_service import EchoApplicationService
from app.infrastructure.factory import EchoServiceFactory
from app.ports.configuration import ConfigurationPort
from app.ports.service_bus import ServiceBusPort


class TestEchoServiceFactory:
    """Test suite for EchoServiceFactory."""

    # Test create_production_service
    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.quick_setup")
    @patch("app.infrastructure.factory.AegisServiceBusAdapter")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_success(
        self, mock_config_class, mock_adapter_class, mock_quick_setup
    ):
        """Test successful production service creation."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = True
        mock_config.get_instance_id.return_value = "prod-instance-123"
        mock_config.get_nats_url.return_value = "nats://localhost:4222"
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_type.return_value = "service"
        mock_config.get_service_version.return_value = "1.0.0"
        mock_config.is_debug_enabled.return_value = False
        mock_config_class.return_value = mock_config

        mock_aegis_service = MagicMock()
        mock_quick_setup.return_value = mock_aegis_service

        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_adapter_class.return_value = mock_service_bus

        # Create production service
        service = await EchoServiceFactory.create_production_service()

        # Verify service was created
        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config

        # Verify quick_setup was called with correct params
        mock_quick_setup.assert_called_once_with(
            service_name="echo-service",
            service_type="service",
            version="1.0.0",
            debug=False,
        )

        # Verify adapter was created with aegis service
        mock_adapter_class.assert_called_once_with(mock_aegis_service)

    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.quick_setup")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_failure(self, mock_config_class, mock_quick_setup):
        """Test production service creation failure."""
        # Setup mock to fail
        mock_quick_setup.side_effect = Exception("Connection failed")

        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = False
        mock_config.get_instance_id.return_value = "test-123"
        mock_config.get_nats_url.return_value = None
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_type.return_value = "service"
        mock_config.get_service_version.return_value = "1.0.0"
        mock_config.is_debug_enabled.return_value = True
        mock_config_class.return_value = mock_config

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await EchoServiceFactory.create_production_service()

        assert "Unable to create echo service" in str(exc_info.value)

    # Test create_test_service
    def test_create_test_service_with_all_dependencies(self):
        """Test creating test service with provided dependencies."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=mock_config,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config

    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    def test_create_test_service_with_default_config(self, mock_config_class):
        """Test creating test service with default configuration."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_config_class.return_value = mock_config

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=None,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config

        # Verify default configuration was created
        mock_config_class.assert_called_once()
        call_args = mock_config_class.call_args[1]
        assert call_args["defaults"]["service_name"] == "echo-service-test"
        assert call_args["defaults"]["version"] == "test"
        assert call_args["defaults"]["service_type"] == "service"
        assert call_args["defaults"]["debug"] is True

    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    def test_create_test_service_with_custom_defaults(self, mock_config_class):
        """Test creating test service with custom default values."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_config_class.return_value = mock_config

        custom_defaults = {
            "service_name": "custom-echo",
            "extra_param": "value",
        }

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=None,
            config_defaults=custom_defaults,
        )

        assert isinstance(service, EchoApplicationService)

        # Verify custom defaults were merged
        call_args = mock_config_class.call_args[1]
        assert call_args["defaults"]["service_name"] == "custom-echo"
        assert call_args["defaults"]["extra_param"] == "value"
        assert call_args["defaults"]["version"] == "test"  # Still has defaults

    # Test create_with_custom_adapters
    @pytest.mark.asyncio
    async def test_create_with_custom_adapters(self):
        """Test creating service with fully custom adapters."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)

        service = await EchoServiceFactory.create_with_custom_adapters(
            service_bus=mock_service_bus,
            configuration=mock_config,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config

    # Test factory pattern compliance
    def test_factory_methods_are_static(self):
        """Test that all factory methods are static."""
        assert isinstance(EchoServiceFactory.__dict__["create_production_service"], staticmethod)
        assert isinstance(EchoServiceFactory.__dict__["create_test_service"], staticmethod)
        assert isinstance(EchoServiceFactory.__dict__["create_with_custom_adapters"], staticmethod)

    def test_factory_has_no_state(self):
        """Test that factory is stateless."""
        factory = EchoServiceFactory()
        # Factory should have no instance attributes
        assert not hasattr(factory, "__dict__") or factory.__dict__ == {}
