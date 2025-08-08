"""Unit tests for configuration helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk.developer.config_helper import (
    K8sNATSConfig,
    SDKConfig,
    create_external_client,
    create_service,
    discover_k8s_config,
    quick_setup,
)
from aegis_sdk.developer.environment import Environment


class TestSDKConfig:
    """Test SDKConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SDKConfig(service_name="test-service")
        assert config.service_name == "test-service"
        assert config.nats_url == "auto"
        assert config.environment == Environment.LOCAL_K8S
        assert config.debug is True
        assert config.version == "1.0.0"
        assert config.namespace == "aegis-trader"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = SDKConfig(
            service_name="custom-service",
            nats_url="nats://custom:4222",
            environment=Environment.DOCKER,
            debug=False,
            version="2.0.0",
            namespace="custom-ns",
        )
        assert config.service_name == "custom-service"
        assert config.nats_url == "nats://custom:4222"
        assert config.environment == Environment.DOCKER
        assert config.debug is False
        assert config.version == "2.0.0"
        assert config.namespace == "custom-ns"


class TestK8sNATSConfig:
    """Test K8sNATSConfig model."""

    def test_default_values(self) -> None:
        """Test default K8s configuration values."""
        config = K8sNATSConfig()
        assert config.namespace == "aegis-trader"
        assert config.service_name == "aegis-trader-nats"
        assert config.port == 4222
        assert config.use_port_forward is True

    def test_custom_values(self) -> None:
        """Test custom K8s configuration values."""
        config = K8sNATSConfig(
            namespace="custom-ns",
            service_name="custom-nats",
            port=5222,
            use_port_forward=False,
        )
        assert config.namespace == "custom-ns"
        assert config.service_name == "custom-nats"
        assert config.port == 5222
        assert config.use_port_forward is False


@pytest.mark.asyncio
class TestDiscoverK8sConfig:
    """Test K8s configuration discovery."""

    @patch("aegis_sdk.developer.config_helper.get_nats_url_with_retry")
    async def test_discover_with_port_forward(self, mock_get_url: AsyncMock) -> None:
        """Test discovery with port forwarding."""
        mock_get_url.return_value = "nats://localhost:4222"

        config = await discover_k8s_config()

        assert config.use_port_forward is True
        mock_get_url.assert_called_once_with(
            namespace="aegis-trader",
            service_name="aegis-trader-nats",
            use_port_forward=True,
        )

    @patch("aegis_sdk.developer.config_helper.get_nats_url_with_retry")
    async def test_discover_without_port_forward(self, mock_get_url: AsyncMock) -> None:
        """Test discovery without port forwarding."""
        mock_get_url.return_value = "nats://10.0.0.1:4222"

        config = await discover_k8s_config()

        # Port forward flag remains as default
        assert config.use_port_forward is True


@pytest.mark.asyncio
class TestQuickSetup:
    """Test quick setup helper."""

    @patch("aegis_sdk.developer.config_helper.bootstrap_sdk")
    @patch("aegis_sdk.developer.config_helper.get_nats_url_with_retry")
    @patch("aegis_sdk.developer.config_helper.detect_environment")
    async def test_quick_setup_local_k8s(
        self,
        mock_detect_env: MagicMock,
        mock_get_url: AsyncMock,
        mock_bootstrap: AsyncMock,
    ) -> None:
        """Test quick setup for local K8s environment."""
        mock_detect_env.return_value = Environment.LOCAL_K8S
        mock_get_url.return_value = "nats://localhost:4222"
        mock_provider = MagicMock()
        mock_bootstrap.return_value = mock_provider

        service = await quick_setup("test-service")

        assert service is not None
        mock_detect_env.assert_called_once()
        mock_get_url.assert_called()
        mock_bootstrap.assert_called_once_with("nats://localhost:4222", "test-service")

    @patch("aegis_sdk.developer.config_helper.bootstrap_sdk")
    @patch("aegis_sdk.developer.config_helper.detect_environment")
    async def test_quick_setup_docker(
        self,
        mock_detect_env: MagicMock,
        mock_bootstrap: AsyncMock,
    ) -> None:
        """Test quick setup for Docker environment."""
        mock_detect_env.return_value = Environment.DOCKER
        mock_provider = MagicMock()
        mock_bootstrap.return_value = mock_provider

        service = await quick_setup("test-service")

        assert service is not None
        mock_detect_env.assert_called_once()
        # Should use Docker internal host
        mock_bootstrap.assert_called_once_with("nats://host.docker.internal:4222", "test-service")

    @patch("aegis_sdk.developer.config_helper.bootstrap_sdk")
    @patch("aegis_sdk.developer.config_helper.detect_environment")
    async def test_quick_setup_production(
        self,
        mock_detect_env: MagicMock,
        mock_bootstrap: AsyncMock,
    ) -> None:
        """Test quick setup for production environment."""
        mock_detect_env.return_value = Environment.PRODUCTION
        mock_provider = MagicMock()
        mock_bootstrap.return_value = mock_provider

        service = await quick_setup("test-service")

        assert service is not None
        mock_detect_env.assert_called_once()
        # Should use K8s service name
        mock_bootstrap.assert_called_once_with("nats://aegis-trader-nats:4222", "test-service")

    @patch("aegis_sdk.developer.config_helper.bootstrap_sdk")
    @patch("aegis_sdk.developer.config_helper.detect_environment")
    async def test_quick_setup_single_active(
        self,
        mock_detect_env: MagicMock,
        mock_bootstrap: AsyncMock,
    ) -> None:
        """Test quick setup for single-active service."""
        mock_detect_env.return_value = Environment.UNKNOWN
        mock_provider = MagicMock()
        mock_bootstrap.return_value = mock_provider

        service = await quick_setup("test-service", service_type="single-active")

        assert service is not None
        mock_bootstrap.assert_called_once_with("nats://localhost:4222", "test-service")
        # Should create SingleActiveService
        from aegis_sdk.application.single_active_service import SingleActiveService

        assert isinstance(service, SingleActiveService)


@pytest.mark.asyncio
class TestCreateService:
    """Test create_service helper."""

    @patch("aegis_sdk.developer.config_helper.quick_setup")
    async def test_create_service(self, mock_quick_setup: AsyncMock) -> None:
        """Test create_service delegates to quick_setup."""
        mock_service = MagicMock()
        mock_quick_setup.return_value = mock_service

        service = await create_service("test-service", debug=False)

        assert service == mock_service
        mock_quick_setup.assert_called_once_with(
            "test-service",
            "service",
            debug=False,
        )


@pytest.mark.asyncio
class TestCreateExternalClient:
    """Test create_external_client helper."""

    @patch("aegis_sdk.developer.config_helper.bootstrap_sdk")
    @patch("aegis_sdk.developer.config_helper.get_nats_url_with_retry")
    async def test_create_external_client(
        self,
        mock_get_url: AsyncMock,
        mock_bootstrap: AsyncMock,
    ) -> None:
        """Test creating external client."""
        mock_get_url.return_value = "nats://localhost:4222"
        mock_provider = MagicMock()
        mock_bootstrap.return_value = mock_provider

        provider = await create_external_client()

        assert provider == mock_provider
        # get_nats_url_with_retry is called twice (once in discover_k8s_config, once directly)
        assert mock_get_url.call_count == 2
        # Should use "external-client" as name
        mock_bootstrap.assert_called_once_with("nats://localhost:4222", "external-client")
