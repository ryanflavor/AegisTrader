"""Unit tests for quickstart bootstrap module following TDD principles."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk_dev.quickstart.bootstrap import (
    BootstrapConfig,
    ServiceContext,
    bootstrap_sdk,
    cleanup_service_context,
    create_service_context,
)


class TestBootstrapConfig:
    """Test BootstrapConfig model."""

    def test_valid_config_creation(self):
        """Test creating a valid bootstrap configuration."""
        # Act
        config = BootstrapConfig(nats_url="nats://localhost:4222", service_name="test-service")

        # Assert
        assert config.nats_url == "nats://localhost:4222"
        assert config.service_name == "test-service"
        assert config.kv_bucket == "service_registry"
        assert config.enable_watchable is True

    def test_config_with_all_fields(self):
        """Test config with all fields specified."""
        # Act
        config = BootstrapConfig(
            nats_url="nats://localhost:4222",
            service_name="test-service",
            kv_bucket="custom_bucket",
            enable_watchable=False,
        )

        # Assert
        assert config.kv_bucket == "custom_bucket"
        assert config.enable_watchable is False

    def test_invalid_nats_url_raises_error(self):
        """Test that invalid NATS URL raises validation error."""
        # Act & Assert
        with pytest.raises(ValueError, match="NATS URL must start with"):
            BootstrapConfig(nats_url="http://localhost:4222", service_name="test-service")

    def test_valid_nats_url_protocols(self):
        """Test various valid NATS URL protocols."""
        # Arrange
        valid_urls = [
            "nats://localhost:4222",
            "tls://secure.nats:4222",
            "ws://websocket.nats:80",
            "wss://secure-websocket.nats:443",
        ]

        # Act & Assert
        for url in valid_urls:
            config = BootstrapConfig(nats_url=url, service_name="test")
            assert config.nats_url == url

    def test_empty_service_name_raises_error(self):
        """Test that empty service name raises validation error."""
        # Act & Assert
        with pytest.raises(ValueError):
            BootstrapConfig(nats_url="nats://localhost:4222", service_name="")

    def test_config_is_frozen(self):
        """Test that config is immutable after creation."""
        # Arrange
        config = BootstrapConfig(nats_url="nats://localhost:4222", service_name="test-service")

        # Act & Assert
        with pytest.raises(AttributeError):
            config.service_name = "new-name"


class TestServiceContext:
    """Test ServiceContext model."""

    def test_service_context_creation(self):
        """Test creating a service context with mock components."""
        # Arrange
        mock_bus = MagicMock()
        mock_registry = MagicMock()
        mock_discovery = MagicMock()
        mock_logger = MagicMock()
        mock_clock = MagicMock()
        config = BootstrapConfig(nats_url="nats://localhost:4222", service_name="test")

        # Act
        context = ServiceContext(
            message_bus=mock_bus,
            service_registry=mock_registry,
            service_discovery=mock_discovery,
            logger=mock_logger,
            clock=mock_clock,
            config=config,
        )

        # Assert
        assert context.message_bus == mock_bus
        assert context.service_registry == mock_registry
        assert context.service_discovery == mock_discovery
        assert context.logger == mock_logger
        assert context.clock == mock_clock
        assert context.config == config


class TestBootstrapSDK:
    """Test bootstrap_sdk function."""

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.quickstart.bootstrap.bootstrap_defaults")
    @patch("aegis_sdk_dev.quickstart.bootstrap.NATSAdapter")
    @patch("aegis_sdk_dev.quickstart.bootstrap.NATSKVStore")
    @patch("aegis_sdk_dev.quickstart.bootstrap.SystemClock")
    @patch("aegis_sdk_dev.quickstart.bootstrap.SimpleLogger")
    @patch("aegis_sdk_dev.quickstart.bootstrap.KVServiceRegistry")
    @patch("aegis_sdk_dev.quickstart.bootstrap.WatchableCachedServiceDiscovery")
    async def test_bootstrap_sdk_with_watchable(
        self,
        MockWatchableDiscovery,
        MockRegistry,
        MockLogger,
        MockClock,
        MockKVStore,
        MockNATSAdapter,
        mock_defaults,
    ):
        """Test bootstrapping SDK with watchable discovery."""
        # Arrange
        config = BootstrapConfig(
            nats_url="nats://localhost:4222", service_name="test-service", enable_watchable=True
        )

        # Setup mocks
        mock_nats = AsyncMock()
        MockNATSAdapter.return_value = mock_nats

        mock_kv = AsyncMock()
        MockKVStore.return_value = mock_kv

        mock_clock = MagicMock()
        MockClock.return_value = mock_clock

        mock_logger = MagicMock()
        MockLogger.return_value = mock_logger

        mock_registry = MagicMock()
        MockRegistry.return_value = mock_registry

        mock_discovery = MagicMock()
        MockWatchableDiscovery.return_value = mock_discovery

        # Act
        context = await bootstrap_sdk(config)

        # Assert
        mock_defaults.assert_called_once()
        mock_nats.connect.assert_called_once_with("nats://localhost:4222")
        mock_kv.connect.assert_called_once_with("service_registry")
        MockRegistry.assert_called_once_with(mock_kv, mock_logger)
        MockWatchableDiscovery.assert_called_once_with(mock_registry, mock_clock)

        assert context.message_bus == mock_nats
        assert context.service_registry == mock_registry
        assert context.service_discovery == mock_discovery
        assert context.logger == mock_logger
        assert context.clock == mock_clock
        assert context.config == config

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.quickstart.bootstrap.bootstrap_defaults")
    @patch("aegis_sdk_dev.quickstart.bootstrap.NATSAdapter")
    @patch("aegis_sdk_dev.quickstart.bootstrap.NATSKVStore")
    @patch("aegis_sdk_dev.quickstart.bootstrap.SystemClock")
    @patch("aegis_sdk_dev.quickstart.bootstrap.SimpleLogger")
    @patch("aegis_sdk_dev.quickstart.bootstrap.KVServiceRegistry")
    @patch("aegis_sdk_dev.quickstart.bootstrap.CachedServiceDiscovery")
    async def test_bootstrap_sdk_without_watchable(
        self,
        MockCachedDiscovery,
        MockRegistry,
        MockLogger,
        MockClock,
        MockKVStore,
        MockNATSAdapter,
        mock_defaults,
    ):
        """Test bootstrapping SDK without watchable discovery."""
        # Arrange
        config = BootstrapConfig(
            nats_url="nats://localhost:4222", service_name="test-service", enable_watchable=False
        )

        # Setup mocks
        mock_nats = AsyncMock()
        MockNATSAdapter.return_value = mock_nats

        mock_kv = AsyncMock()
        MockKVStore.return_value = mock_kv

        mock_clock = MagicMock()
        MockClock.return_value = mock_clock

        mock_logger = MagicMock()
        MockLogger.return_value = mock_logger

        mock_registry = MagicMock()
        MockRegistry.return_value = mock_registry

        mock_discovery = MagicMock()
        MockCachedDiscovery.return_value = mock_discovery

        # Act
        context = await bootstrap_sdk(config)

        # Assert
        MockCachedDiscovery.assert_called_once_with(mock_registry, mock_clock)
        assert context.service_discovery == mock_discovery


class TestCreateServiceContext:
    """Test create_service_context convenience function."""

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.quickstart.bootstrap.bootstrap_sdk")
    async def test_create_service_context_minimal(self, mock_bootstrap):
        """Test creating service context with minimal config."""
        # Arrange
        mock_context = MagicMock()
        mock_bootstrap.return_value = mock_context

        # Act
        context = await create_service_context(
            nats_url="nats://localhost:4222", service_name="test-service"
        )

        # Assert
        assert context == mock_context
        mock_bootstrap.assert_called_once()
        call_config = mock_bootstrap.call_args[0][0]
        assert call_config.nats_url == "nats://localhost:4222"
        assert call_config.service_name == "test-service"
        assert call_config.kv_bucket == "service_registry"
        assert call_config.enable_watchable is True

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.quickstart.bootstrap.bootstrap_sdk")
    async def test_create_service_context_with_kwargs(self, mock_bootstrap):
        """Test creating service context with additional kwargs."""
        # Arrange
        mock_context = MagicMock()
        mock_bootstrap.return_value = mock_context

        # Act
        context = await create_service_context(
            nats_url="nats://localhost:4222",
            service_name="test-service",
            kv_bucket="custom_bucket",
            enable_watchable=False,
        )

        # Assert
        assert context == mock_context
        call_config = mock_bootstrap.call_args[0][0]
        assert call_config.kv_bucket == "custom_bucket"
        assert call_config.enable_watchable is False


class TestCleanupServiceContext:
    """Test cleanup_service_context function."""

    @pytest.mark.asyncio
    async def test_cleanup_with_closeable_components(self):
        """Test cleanup when components have close methods."""
        # Arrange
        mock_bus = AsyncMock()
        mock_bus.close = AsyncMock()

        mock_discovery = AsyncMock()
        mock_discovery.close = AsyncMock()

        context = ServiceContext(
            message_bus=mock_bus,
            service_registry=MagicMock(),
            service_discovery=mock_discovery,
            logger=MagicMock(),
            clock=MagicMock(),
            config=BootstrapConfig(nats_url="nats://localhost:4222", service_name="test"),
        )

        # Act
        await cleanup_service_context(context)

        # Assert
        mock_bus.close.assert_called_once()
        mock_discovery.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_closeable_components(self):
        """Test cleanup when components don't have close methods."""
        # Arrange
        context = ServiceContext(
            message_bus=MagicMock(),
            service_registry=MagicMock(),
            service_discovery=MagicMock(),
            logger=MagicMock(),
            clock=MagicMock(),
            config=BootstrapConfig(nats_url="nats://localhost:4222", service_name="test"),
        )

        # Act - should not raise
        await cleanup_service_context(context)

        # Assert - no exceptions raised
        assert True
