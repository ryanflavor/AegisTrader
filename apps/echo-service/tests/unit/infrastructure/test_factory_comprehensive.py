"""Comprehensive unit tests for the Echo Service Factory.

Testing all factory methods including production service creation,
test service creation, and custom adapter injection.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.echo_service import EchoApplicationService
from app.infrastructure.factory import EchoServiceFactory
from app.ports.configuration import ConfigurationPort
from app.ports.service_bus import ServiceBusPort
from app.ports.service_registry import ServiceRegistryPort


class TestEchoServiceFactory:
    """Test EchoServiceFactory functionality."""

    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.ServiceRegistryAdapter")
    @patch("app.infrastructure.factory.ServiceBusAdapter")
    @patch("app.infrastructure.factory.NATSConnectionAdapter")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_success(
        self,
        mock_config_class,
        mock_nats_class,
        mock_bus_class,
        mock_registry_class,
    ):
        """Test successful production service creation."""
        # Setup configuration mock
        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = True
        mock_config.get_instance_id.return_value = "prod-instance-123"
        mock_config.get_nats_url.return_value = "nats://nats.prod:4222"
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_version.return_value = "2.0.0"
        mock_config_class.return_value = mock_config

        # Setup NATS adapter mock
        mock_nats = AsyncMock()
        mock_nats.connect = AsyncMock()
        mock_nats_class.return_value = mock_nats

        # Setup service bus mock
        mock_bus = MagicMock(spec=ServiceBusPort)
        mock_bus_class.return_value = mock_bus

        # Setup service registry mock
        mock_registry = AsyncMock(spec=ServiceRegistryPort)
        mock_registry.register_service_definition = AsyncMock(return_value=True)
        mock_registry.register_service_instance = AsyncMock(return_value=True)
        mock_registry_class.return_value = mock_registry

        # Create production service
        service = await EchoServiceFactory.create_production_service()

        # Verify service was created
        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_bus
        assert service._configuration == mock_config
        assert service._service_registry == mock_registry

        # Verify NATS connection was established
        mock_nats.connect.assert_called_once()

        # Verify service was registered
        mock_registry.register_service_definition.assert_called_once_with(
            service_name="echo-service",
            owner="Echo Team",
            description="Echo service for testing and demonstration",
            version="2.0.0",
        )

        mock_registry.register_service_instance.assert_called_once_with(
            service_name="echo-service",
            instance_id="prod-instance-123",
            version="2.0.0",
            status="ACTIVE",
            metadata={
                "environment": "kubernetes",
                "nats_url": "nats://nats.prod:4222",
            },
        )

    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.NATSConnectionAdapter")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_connection_failure(
        self,
        mock_config_class,
        mock_nats_class,
    ):
        """Test production service creation with connection failure."""
        # Setup configuration mock
        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = False
        mock_config.get_instance_id.return_value = "local-123"
        mock_config.get_nats_url.return_value = "nats://localhost:4222"
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_version.return_value = "1.0.0"
        mock_config_class.return_value = mock_config

        # Setup NATS to fail connection
        mock_nats = AsyncMock()
        mock_nats.connect.side_effect = ConnectionError("Unable to connect to NATS")
        mock_nats_class.return_value = mock_nats

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await EchoServiceFactory.create_production_service()

        assert "Unable to create echo service" in str(exc_info.value)
        assert "Unable to connect to NATS" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.ServiceRegistryAdapter")
    @patch("app.infrastructure.factory.ServiceBusAdapter")
    @patch("app.infrastructure.factory.NATSConnectionAdapter")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_registry_failure(
        self,
        mock_config_class,
        mock_nats_class,
        mock_bus_class,
        mock_registry_class,
    ):
        """Test production service creation with registry failure."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = False
        mock_config.get_instance_id.return_value = "test-456"
        mock_config.get_nats_url.return_value = "nats://localhost:4222"
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_version.return_value = "1.0.0"
        mock_config_class.return_value = mock_config

        mock_nats = AsyncMock()
        mock_nats.connect = AsyncMock()
        mock_nats_class.return_value = mock_nats

        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        # Registry fails to register
        mock_registry = AsyncMock()
        mock_registry.register_service_definition.side_effect = Exception("Registry error")
        mock_registry_class.return_value = mock_registry

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await EchoServiceFactory.create_production_service()

        assert "Unable to create echo service" in str(exc_info.value)

    def test_create_test_service_with_all_dependencies(self):
        """Test creating test service with all dependencies provided."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_registry = MagicMock(spec=ServiceRegistryPort)

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=mock_config,
            service_registry=mock_registry,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config
        assert service._service_registry == mock_registry

    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    def test_create_test_service_with_default_config(self, mock_config_class):
        """Test creating test service with default configuration."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_config_class.return_value = mock_config

        # Clear any existing environment variables
        env_vars = ["SERVICE_NAME", "VERSION", "SERVICE_TYPE", "DEBUG", "INSTANCE_ID", "NATS_URL"]
        for var in env_vars:
            os.environ.pop(var, None)

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=None,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config

        # Verify default environment variables were set
        assert os.environ["SERVICE_NAME"] == "echo-service-test"
        assert os.environ["VERSION"] == "1.0.0"
        assert os.environ["SERVICE_TYPE"] == "service"
        assert os.environ["DEBUG"] == "True"
        assert "test-" in os.environ["INSTANCE_ID"]
        assert os.environ["NATS_URL"] == "nats://localhost:4222"

        # Clean up
        for var in env_vars:
            os.environ.pop(var, None)

    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    def test_create_test_service_with_custom_defaults(self, mock_config_class):
        """Test creating test service with custom default values."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_config_class.return_value = mock_config

        custom_defaults = {
            "service_name": "custom-echo",
            "version": "3.0.0",
            "debug": False,
            "custom_key": "custom_value",
        }

        service = EchoServiceFactory.create_test_service(
            service_bus=mock_service_bus,
            configuration=None,
            config_defaults=custom_defaults,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus

        # Verify custom values override defaults
        assert os.environ["SERVICE_NAME"] == "custom-echo"
        assert os.environ["VERSION"] == "3.0.0"
        assert os.environ["DEBUG"] == "False"
        assert os.environ["CUSTOM_KEY"] == "custom_value"

        # Clean up
        for key in [
            "SERVICE_NAME",
            "VERSION",
            "DEBUG",
            "CUSTOM_KEY",
            "SERVICE_TYPE",
            "INSTANCE_ID",
            "NATS_URL",
        ]:
            os.environ.pop(key, None)

    def test_create_test_service_without_service_bus_raises_error(self):
        """Test that create_test_service requires service_bus."""
        with pytest.raises(TypeError):
            EchoServiceFactory.create_test_service()

    @pytest.mark.asyncio
    async def test_create_with_custom_adapters(self):
        """Test creating service with fully custom adapters."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)
        mock_registry = MagicMock(spec=ServiceRegistryPort)

        service = await EchoServiceFactory.create_with_custom_adapters(
            service_bus=mock_service_bus,
            configuration=mock_config,
            service_registry=mock_registry,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config
        assert service._service_registry == mock_registry

    @pytest.mark.asyncio
    async def test_create_with_custom_adapters_no_registry(self):
        """Test creating service without registry adapter."""
        mock_service_bus = MagicMock(spec=ServiceBusPort)
        mock_config = MagicMock(spec=ConfigurationPort)

        service = await EchoServiceFactory.create_with_custom_adapters(
            service_bus=mock_service_bus,
            configuration=mock_config,
            service_registry=None,
        )

        assert isinstance(service, EchoApplicationService)
        assert service._service_bus == mock_service_bus
        assert service._configuration == mock_config
        assert service._service_registry is None

    @pytest.mark.asyncio
    @patch("app.infrastructure.factory.logger")
    @patch("app.infrastructure.factory.ServiceRegistryAdapter")
    @patch("app.infrastructure.factory.ServiceBusAdapter")
    @patch("app.infrastructure.factory.NATSConnectionAdapter")
    @patch("app.infrastructure.factory.EnvironmentConfigurationAdapter")
    async def test_create_production_service_logging(
        self,
        mock_config_class,
        mock_nats_class,
        mock_bus_class,
        mock_registry_class,
        mock_logger,
    ):
        """Test that production service creation logs properly."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.is_kubernetes_environment.return_value = True
        mock_config.get_instance_id.return_value = "log-test-123"
        mock_config.get_nats_url.return_value = "nats://nats.test:4222"
        mock_config.get_service_name.return_value = "echo-service"
        mock_config.get_service_version.return_value = "1.5.0"
        mock_config_class.return_value = mock_config

        mock_nats = AsyncMock()
        mock_nats.connect = AsyncMock()
        mock_nats_class.return_value = mock_nats

        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        mock_registry = AsyncMock()
        mock_registry.register_service_definition = AsyncMock(return_value=True)
        mock_registry.register_service_instance = AsyncMock(return_value=True)
        mock_registry_class.return_value = mock_registry

        # Create service
        await EchoServiceFactory.create_production_service()

        # Verify logging
        assert mock_logger.info.call_count >= 3
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]

        # Check for expected log messages
        assert any("Environment Detection" in msg for msg in log_messages)
        assert any("NATS connection established" in msg for msg in log_messages)
        assert any("Service registered successfully" in msg for msg in log_messages)
