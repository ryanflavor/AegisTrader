"""Unit tests for FastAPI dependency injection setup.

These tests verify that dependency injection functions correctly
instantiate and cache the appropriate service instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from app.application.monitoring_service import MonitoringService
from app.application.service_registry_service import ServiceRegistryService
from app.domain.models import ServiceConfiguration
from app.infrastructure.api.dependencies import (
    get_configuration_port,
    get_kv_store,
    get_monitoring_port,
    get_monitoring_service,
    get_service_configuration,
    get_service_registry,
)
from app.infrastructure.configuration_adapter import EnvironmentConfigurationAdapter
from app.infrastructure.monitoring_adapter import MonitoringAdapter

if TYPE_CHECKING:
    pass


class TestDependencies:
    """Test cases for dependency injection functions."""

    @pytest.fixture(autouse=True)
    def clear_lru_cache(self):
        """Clear LRU cache before each test to ensure test isolation."""
        # Clear all cached functions
        get_configuration_port.cache_clear()
        get_service_configuration.cache_clear()
        get_monitoring_port.cache_clear()
        get_monitoring_service.cache_clear()
        yield
        # Clean up after test
        get_configuration_port.cache_clear()
        get_service_configuration.cache_clear()
        get_monitoring_port.cache_clear()
        get_monitoring_service.cache_clear()

    def test_get_configuration_port(self) -> None:
        """Test getting configuration port returns EnvironmentConfigurationAdapter."""
        # Act
        port = get_configuration_port()

        # Assert
        assert isinstance(port, EnvironmentConfigurationAdapter)

        # Test caching - should return same instance
        port2 = get_configuration_port()
        assert port is port2

    def test_get_configuration_port_caching(self) -> None:
        """Test that configuration port is properly cached."""
        # Act
        port1 = get_configuration_port()
        port2 = get_configuration_port()
        port3 = get_configuration_port()

        # Assert - All should be the same instance
        assert port1 is port2
        assert port2 is port3

        # Check cache info
        cache_info = get_configuration_port.cache_info()
        assert cache_info.hits == 2  # First call is a miss, next two are hits
        assert cache_info.misses == 1

    @patch("app.infrastructure.api.dependencies.get_configuration_port")
    def test_get_service_configuration(self, mock_get_config_port: Mock) -> None:
        """Test getting service configuration."""
        # Arrange
        mock_config = ServiceConfiguration(
            nats_url="nats://test:4222",
            api_port=8100,
            log_level="INFO",
            environment="development",
        )
        mock_port = Mock()
        mock_port.load_configuration.return_value = mock_config
        mock_get_config_port.return_value = mock_port

        # Act
        config = get_service_configuration()

        # Assert
        assert config == mock_config
        mock_get_config_port.assert_called_once()
        mock_port.load_configuration.assert_called_once()

    def test_get_service_configuration_caching(self) -> None:
        """Test that service configuration is properly cached."""
        # Arrange
        with patch(
            "app.infrastructure.api.dependencies.get_configuration_port"
        ) as mock_get_config_port:
            mock_config = ServiceConfiguration(
                nats_url="nats://test:4222",
                api_port=8100,
                log_level="INFO",
                environment="development",
            )
            mock_port = Mock()
            mock_port.load_configuration.return_value = mock_config
            mock_get_config_port.return_value = mock_port

            # Act
            config1 = get_service_configuration()
            config2 = get_service_configuration()
            config3 = get_service_configuration()

            # Assert - All should be the same instance
            assert config1 is config2
            assert config2 is config3

            # Configuration should only be loaded once due to caching
            mock_port.load_configuration.assert_called_once()

            # Check cache info
            cache_info = get_service_configuration.cache_info()
            assert cache_info.hits == 2
            assert cache_info.misses == 1

    @patch("app.infrastructure.api.dependencies.get_service_configuration")
    def test_get_monitoring_port(self, mock_get_config: Mock) -> None:
        """Test getting monitoring port."""
        # Arrange
        mock_config = ServiceConfiguration(
            nats_url="nats://test:4222",
            api_port=8100,
            log_level="INFO",
            environment="development",
        )
        mock_get_config.return_value = mock_config

        # Act
        port = get_monitoring_port()

        # Assert
        assert isinstance(port, MonitoringAdapter)
        mock_get_config.assert_called_once()

    def test_get_monitoring_port_caching(self) -> None:
        """Test that monitoring port is properly cached."""
        # Arrange
        with patch(
            "app.infrastructure.api.dependencies.get_service_configuration"
        ) as mock_get_config:
            mock_config = ServiceConfiguration(
                nats_url="nats://test:4222",
                api_port=8100,
                log_level="INFO",
                environment="development",
            )
            mock_get_config.return_value = mock_config

            # Act
            port1 = get_monitoring_port()
            port2 = get_monitoring_port()

            # Assert - Should be the same instance
            assert port1 is port2

            # Configuration should only be retrieved once
            mock_get_config.assert_called_once()

    @patch("app.infrastructure.api.dependencies.get_monitoring_port")
    @patch("app.infrastructure.api.dependencies.get_configuration_port")
    def test_get_monitoring_service(
        self,
        mock_get_config_port: Mock,
        mock_get_monitoring_port: Mock,
    ) -> None:
        """Test getting monitoring service."""
        # Arrange
        mock_monitoring_port = Mock()
        mock_config_port = Mock()
        mock_get_monitoring_port.return_value = mock_monitoring_port
        mock_get_config_port.return_value = mock_config_port

        # Act
        service = get_monitoring_service()

        # Assert
        assert isinstance(service, MonitoringService)
        assert service._monitoring_port == mock_monitoring_port
        assert service._configuration_port == mock_config_port
        mock_get_monitoring_port.assert_called_once()
        mock_get_config_port.assert_called_once()

    def test_get_monitoring_service_caching(self) -> None:
        """Test that monitoring service is properly cached."""
        # Arrange
        with (
            patch(
                "app.infrastructure.api.dependencies.get_monitoring_port"
            ) as mock_get_monitoring_port,
            patch(
                "app.infrastructure.api.dependencies.get_configuration_port"
            ) as mock_get_config_port,
        ):
            mock_monitoring_port = Mock()
            mock_config_port = Mock()
            mock_get_monitoring_port.return_value = mock_monitoring_port
            mock_get_config_port.return_value = mock_config_port

            # Act
            service1 = get_monitoring_service()
            service2 = get_monitoring_service()
            service3 = get_monitoring_service()

            # Assert - All should be the same instance
            assert service1 is service2
            assert service2 is service3

            # Dependencies should only be retrieved once
            mock_get_monitoring_port.assert_called_once()
            mock_get_config_port.assert_called_once()

    @patch("app.infrastructure.connection_manager.get_connection_manager")
    def test_get_kv_store(self, mock_get_connection_manager: Mock) -> None:
        """Test getting KV store from connection manager."""
        # Arrange
        mock_kv_store = Mock()
        mock_manager = Mock()
        mock_manager.kv_store = mock_kv_store
        mock_get_connection_manager.return_value = mock_manager

        # Act
        kv_store = get_kv_store()

        # Assert
        assert kv_store == mock_kv_store
        mock_get_connection_manager.assert_called_once()

    @patch("app.infrastructure.api.dependencies.get_kv_store")
    def test_get_service_registry(self, mock_get_kv_store: Mock) -> None:
        """Test getting service registry."""
        # Arrange
        mock_kv_store = Mock()
        mock_get_kv_store.return_value = mock_kv_store

        # Act
        service = get_service_registry()

        # Assert
        assert isinstance(service, ServiceRegistryService)
        assert service._kv_store == mock_kv_store
        mock_get_kv_store.assert_called_once()

    def test_get_kv_store_not_cached(self) -> None:
        """Test that KV store is not cached (no @lru_cache)."""
        # Arrange
        with patch(
            "app.infrastructure.connection_manager.get_connection_manager"
        ) as mock_get_connection_manager:
            mock_kv_store1 = Mock()
            mock_kv_store2 = Mock()
            mock_manager1 = Mock()
            mock_manager1.kv_store = mock_kv_store1
            mock_manager2 = Mock()
            mock_manager2.kv_store = mock_kv_store2

            # Return different managers on each call
            mock_get_connection_manager.side_effect = [mock_manager1, mock_manager2]

            # Act
            kv_store1 = get_kv_store()
            kv_store2 = get_kv_store()

            # Assert - Should get different instances since not cached
            assert kv_store1 == mock_kv_store1
            assert kv_store2 == mock_kv_store2
            assert kv_store1 != kv_store2
            assert mock_get_connection_manager.call_count == 2

    def test_get_service_registry_not_cached(self) -> None:
        """Test that service registry is not cached (no @lru_cache)."""
        # Arrange
        with patch("app.infrastructure.api.dependencies.get_kv_store") as mock_get_kv_store:
            mock_kv_store = Mock()
            mock_get_kv_store.return_value = mock_kv_store

            # Act
            service1 = get_service_registry()
            service2 = get_service_registry()

            # Assert - Should get different instances since not cached
            assert isinstance(service1, ServiceRegistryService)
            assert isinstance(service2, ServiceRegistryService)
            assert service1 is not service2
            assert mock_get_kv_store.call_count == 2

    @patch("app.infrastructure.connection_manager.get_connection_manager")
    def test_get_kv_store_connection_manager_error(self, mock_get_connection_manager: Mock) -> None:
        """Test error handling when connection manager raises error."""
        # Arrange
        mock_get_connection_manager.side_effect = RuntimeError("Connection manager not initialized")

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            get_kv_store()

        assert "Connection manager not initialized" in str(exc_info.value)

    def test_cache_isolation_between_tests(self) -> None:
        """Test that cache is properly cleared between tests."""
        # This test verifies that our autouse fixture works correctly

        # Check all caches are empty at start
        assert get_configuration_port.cache_info().currsize == 0
        assert get_service_configuration.cache_info().currsize == 0
        assert get_monitoring_port.cache_info().currsize == 0
        assert get_monitoring_service.cache_info().currsize == 0

        # Call functions to populate cache
        get_configuration_port()

        # Verify cache is populated
        assert get_configuration_port.cache_info().currsize == 1
