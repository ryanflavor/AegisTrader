"""Tests for main app module.

These tests cover the FastAPI application initialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestMainApp:
    """Tests for main app module."""

    @pytest.mark.asyncio
    async def test_app_lifespan_success(self) -> None:
        """Test successful app lifespan management."""
        from app.main import lifespan

        mock_app = Mock()

        # Mock dependencies
        mock_config = Mock()
        mock_config.environment = "development"
        mock_config.api_port = 8100
        mock_config.log_level = "INFO"

        mock_config_port = Mock()
        mock_config_port.load_configuration.return_value = mock_config

        mock_connection_manager = Mock()
        mock_connection_manager.startup = AsyncMock()
        mock_connection_manager.shutdown = AsyncMock()

        with (
            patch("app.main.get_configuration_port", return_value=mock_config_port),
            patch("app.main.ConnectionManager", return_value=mock_connection_manager),
            patch("app.main.set_connection_manager") as mock_set_manager,
            patch("app.main.get_connection_manager", return_value=mock_connection_manager),
        ):
            # Run lifespan
            async with lifespan(mock_app):
                pass

            # Verify startup
            mock_config_port.load_configuration.assert_called_once()
            mock_connection_manager.startup.assert_called_once()
            mock_set_manager.assert_called_once_with(mock_connection_manager)

            # Verify shutdown
            mock_connection_manager.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_app_lifespan_startup_error(self) -> None:
        """Test app lifespan with startup error."""
        from app.main import lifespan

        mock_app = Mock()

        mock_config_port = Mock()
        mock_config_port.load_configuration.side_effect = Exception("Config error")

        with patch("app.main.get_configuration_port", return_value=mock_config_port):
            with pytest.raises(Exception) as exc_info:
                async with lifespan(mock_app):
                    pass

            assert "Config error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_app_lifespan_shutdown_error(self) -> None:
        """Test app lifespan with shutdown error."""
        from app.main import lifespan

        mock_app = Mock()

        # Mock successful startup but failed shutdown
        mock_config = Mock()
        mock_config.environment = "development"
        mock_config.api_port = 8100
        mock_config.log_level = "INFO"

        mock_config_port = Mock()
        mock_config_port.load_configuration.return_value = mock_config

        mock_connection_manager = Mock()
        mock_connection_manager.startup = AsyncMock()
        mock_connection_manager.shutdown = AsyncMock(side_effect=Exception("Shutdown error"))

        with (
            patch("app.main.get_configuration_port", return_value=mock_config_port),
            patch("app.main.ConnectionManager", return_value=mock_connection_manager),
            patch("app.main.set_connection_manager"),
            patch("app.main.get_connection_manager", return_value=mock_connection_manager),
        ):
            # Run lifespan - shutdown error should be suppressed
            async with lifespan(mock_app):
                pass

            # Verify shutdown was attempted
            mock_connection_manager.shutdown.assert_called_once()

    def test_app_instance(self) -> None:
        """Test FastAPI app instance configuration."""
        from app.main import app

        assert app.title == "AegisTrader Management Service"
        assert app.version == "0.1.0"
        assert "Management and monitoring API" in app.description

        # Check that routes are included
        route_paths = [route.path for route in app.routes]
        assert "/" in route_paths
        assert "/health" in route_paths
        assert "/ready" in route_paths

    @pytest.mark.asyncio
    async def test_error_handler_registration(self) -> None:
        """Test that error handlers are properly registered."""
        from app.domain.exceptions import (
            ConfigurationException,
            HealthCheckFailedException,
            KVStoreException,
            ServiceNotFoundException,
            ServiceUnavailableException,
        )
        from app.main import app

        # Check that exception handlers are registered
        exception_handlers = app.exception_handlers

        # These should be registered
        assert ConfigurationException in exception_handlers
        assert HealthCheckFailedException in exception_handlers
        assert KVStoreException in exception_handlers
        assert ServiceNotFoundException in exception_handlers
        assert ServiceUnavailableException in exception_handlers
        assert Exception in exception_handlers  # Generic handler
