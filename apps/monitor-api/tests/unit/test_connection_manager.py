"""Unit tests for the ConnectionManager.

These tests verify proper lifecycle management of infrastructure connections,
error handling, and dependency injection patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceConfiguration
from app.infrastructure.connection_manager import (
    ConnectionManager,
    get_connection_manager,
    set_connection_manager,
)

if TYPE_CHECKING:
    pass


class TestConnectionManager:
    """Test cases for ConnectionManager."""

    @pytest.fixture
    def mock_config(self) -> ServiceConfiguration:
        """Create a mock service configuration."""
        return ServiceConfiguration(
            nats_url="nats://test-nats:4222",
            api_port=8100,
            log_level="INFO",
            environment="development",
        )

    @pytest.fixture
    def connection_manager(self, mock_config: ServiceConfiguration) -> ConnectionManager:
        """Create a connection manager instance."""
        return ConnectionManager(mock_config)

    @pytest.fixture(autouse=True)
    def reset_global_manager(self):
        """Reset global connection manager before each test."""
        # Arrange - Save current state
        import app.infrastructure.connection_manager

        original = app.infrastructure.connection_manager._connection_manager

        # Reset to None
        app.infrastructure.connection_manager._connection_manager = None

        yield

        # Cleanup - Restore original state
        app.infrastructure.connection_manager._connection_manager = original

    def test_init(
        self, connection_manager: ConnectionManager, mock_config: ServiceConfiguration
    ) -> None:
        """Test ConnectionManager initialization."""
        # Assert
        assert connection_manager.config == mock_config
        assert connection_manager._kv_store is None
        assert connection_manager._instance_repository is None
        assert connection_manager._raw_kv is None

    @pytest.mark.asyncio
    async def test_startup_success(
        self,
        connection_manager: ConnectionManager,
        mock_config: ServiceConfiguration,
    ) -> None:
        """Test successful startup of connections."""
        # Arrange
        with (
            patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDKKVAdapter") as mock_kv_adapter,
            patch(
                "app.infrastructure.service_instance_repository_adapter.ServiceInstanceRepositoryAdapter"
            ) as mock_repository_adapter,
        ):
            mock_kv_instance = Mock()
            mock_kv_instance.connect = AsyncMock()
            mock_kv_instance._kv = Mock()  # Raw KV store
            mock_kv_adapter.return_value = mock_kv_instance

            mock_repo_instance = Mock()
            mock_repository_adapter.return_value = mock_repo_instance

            # Act
            await connection_manager.startup()

            # Assert
            mock_kv_adapter.assert_called_once()
            mock_kv_instance.connect.assert_called_once_with(mock_config.nats_url)
            mock_repository_adapter.assert_called_once_with(mock_kv_instance._kv)

            assert connection_manager._kv_store == mock_kv_instance
            assert connection_manager._instance_repository == mock_repo_instance
            assert connection_manager._raw_kv == mock_kv_instance._kv

    @pytest.mark.asyncio
    async def test_startup_connection_failure(
        self,
        connection_manager: ConnectionManager,
    ) -> None:
        """Test startup failure when connection fails."""
        # Arrange
        with patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDKKVAdapter") as mock_kv_adapter:
            mock_kv_instance = Mock()
            mock_kv_instance.connect = AsyncMock(side_effect=Exception("Connection refused"))
            mock_kv_adapter.return_value = mock_kv_instance

            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await connection_manager.startup()

            assert "Failed to initialize connections" in str(exc_info.value)
            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_startup_repository_initialization_failure(
        self,
        connection_manager: ConnectionManager,
    ) -> None:
        """Test startup failure when repository initialization fails."""
        # Arrange
        with (
            patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDKKVAdapter") as mock_kv_adapter,
            patch(
                "app.infrastructure.service_instance_repository_adapter.ServiceInstanceRepositoryAdapter"
            ) as mock_repository_adapter,
        ):
            mock_kv_instance = Mock()
            mock_kv_instance.connect = AsyncMock()
            mock_kv_instance._kv = Mock()
            mock_kv_adapter.return_value = mock_kv_instance

            mock_repository_adapter.side_effect = Exception("Repository init failed")

            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await connection_manager.startup()

            assert "Failed to initialize connections" in str(exc_info.value)
            assert "Repository init failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shutdown_success(self, connection_manager: ConnectionManager) -> None:
        """Test successful shutdown of connections."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.disconnect = AsyncMock()
        connection_manager._kv_store = mock_kv_store

        # Act
        await connection_manager.shutdown()

        # Assert
        mock_kv_store.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_no_connections(self, connection_manager: ConnectionManager) -> None:
        """Test shutdown when no connections are established."""
        # Act - Should not raise any exceptions
        await connection_manager.shutdown()

        # Assert - No exceptions raised
        assert connection_manager._kv_store is None

    @pytest.mark.asyncio
    async def test_shutdown_disconnect_error(self, connection_manager: ConnectionManager) -> None:
        """Test shutdown handles disconnect errors gracefully."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        connection_manager._kv_store = mock_kv_store

        # Act - Should not raise exception
        await connection_manager.shutdown()

        # Assert
        mock_kv_store.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_no_disconnect_method(
        self, connection_manager: ConnectionManager
    ) -> None:
        """Test shutdown when KV store has no disconnect method."""
        # Arrange
        mock_kv_store = Mock(spec=[])  # No disconnect method
        connection_manager._kv_store = mock_kv_store

        # Act - Should not raise exception
        await connection_manager.shutdown()

        # Assert - No exceptions raised
        assert connection_manager._kv_store == mock_kv_store

    def test_kv_store_property_initialized(self, connection_manager: ConnectionManager) -> None:
        """Test kv_store property when initialized."""
        # Arrange
        mock_kv_store = Mock()
        connection_manager._kv_store = mock_kv_store

        # Act
        result = connection_manager.kv_store

        # Assert
        assert result == mock_kv_store

    def test_kv_store_property_not_initialized(self, connection_manager: ConnectionManager) -> None:
        """Test kv_store property when not initialized."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            _ = connection_manager.kv_store

        assert "KV Store not initialized. Call startup() first." in str(exc_info.value)

    def test_instance_repository_property_initialized(
        self, connection_manager: ConnectionManager
    ) -> None:
        """Test instance_repository property when initialized."""
        # Arrange
        mock_repository = Mock()
        connection_manager._instance_repository = mock_repository

        # Act
        result = connection_manager.instance_repository

        # Assert
        assert result == mock_repository

    def test_instance_repository_property_not_initialized(
        self, connection_manager: ConnectionManager
    ) -> None:
        """Test instance_repository property when not initialized."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            _ = connection_manager.instance_repository

        assert "Instance repository not initialized. Call startup() first." in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_kv_store_initialized(self, connection_manager: ConnectionManager) -> None:
        """Test get_kv_store method when initialized."""
        # Arrange
        mock_raw_kv = Mock()
        connection_manager._raw_kv = mock_raw_kv

        # Act
        result = await connection_manager.get_kv_store()

        # Assert
        assert result == mock_raw_kv

    @pytest.mark.asyncio
    async def test_get_kv_store_not_initialized(
        self, connection_manager: ConnectionManager
    ) -> None:
        """Test get_kv_store method when not initialized."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await connection_manager.get_kv_store()

        assert "KV Store not initialized. Call startup() first." in str(exc_info.value)

    def test_get_connection_manager_initialized(
        self, connection_manager: ConnectionManager
    ) -> None:
        """Test get_connection_manager when manager is set."""
        # Arrange
        set_connection_manager(connection_manager)

        # Act
        result = get_connection_manager()

        # Assert
        assert result == connection_manager

    def test_get_connection_manager_not_initialized(self) -> None:
        """Test get_connection_manager when manager is not set."""
        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            get_connection_manager()

        assert "Connection manager not initialized" in str(exc_info.value)

    def test_set_connection_manager(self, connection_manager: ConnectionManager) -> None:
        """Test setting the global connection manager."""
        # Act
        set_connection_manager(connection_manager)

        # Assert
        import app.infrastructure.connection_manager

        assert app.infrastructure.connection_manager._connection_manager == connection_manager

    @pytest.mark.asyncio
    async def test_startup_logs_success(
        self,
        connection_manager: ConnectionManager,
    ) -> None:
        """Test that successful startup is logged."""
        # Arrange
        with (
            patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDKKVAdapter") as mock_kv_adapter,
            patch(
                "app.infrastructure.service_instance_repository_adapter.ServiceInstanceRepositoryAdapter"
            ),
            patch("app.infrastructure.connection_manager.logger") as mock_logger,
        ):
            mock_kv_instance = Mock()
            mock_kv_instance.connect = AsyncMock()
            mock_kv_instance._kv = Mock()
            mock_kv_adapter.return_value = mock_kv_instance

            # Act
            await connection_manager.startup()

            # Assert
            mock_logger.info.assert_called_with(
                "Successfully connected to NATS KV Store and initialized repositories"
            )

    @pytest.mark.asyncio
    async def test_startup_logs_error(
        self,
        connection_manager: ConnectionManager,
    ) -> None:
        """Test that startup errors are logged."""
        # Arrange
        with (
            patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDKKVAdapter") as mock_kv_adapter,
            patch("app.infrastructure.connection_manager.logger") as mock_logger,
        ):
            error_message = "Connection timeout"
            mock_kv_instance = Mock()
            mock_kv_instance.connect = AsyncMock(side_effect=Exception(error_message))
            mock_kv_adapter.return_value = mock_kv_instance

            # Act
            with pytest.raises(KVStoreException):
                await connection_manager.startup()

            # Assert
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to initialize connections" in error_call
            assert error_message in error_call

    @pytest.mark.asyncio
    @patch("app.infrastructure.connection_manager.logger")
    async def test_shutdown_logs_success(
        self, mock_logger: Mock, connection_manager: ConnectionManager
    ) -> None:
        """Test that successful shutdown is logged."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.disconnect = AsyncMock()
        connection_manager._kv_store = mock_kv_store

        # Act
        await connection_manager.shutdown()

        # Assert
        mock_logger.info.assert_called_with("Disconnected from NATS KV Store")

    @pytest.mark.asyncio
    @patch("app.infrastructure.connection_manager.logger")
    async def test_shutdown_logs_error(
        self, mock_logger: Mock, connection_manager: ConnectionManager
    ) -> None:
        """Test that shutdown errors are logged."""
        # Arrange
        error_message = "Disconnect timeout"
        mock_kv_store = Mock()
        mock_kv_store.disconnect = AsyncMock(side_effect=Exception(error_message))
        connection_manager._kv_store = mock_kv_store

        # Act
        await connection_manager.shutdown()

        # Assert
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error during shutdown" in error_call
        assert error_message in error_call
