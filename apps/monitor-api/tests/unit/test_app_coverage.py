"""Tests to improve coverage of main app and error handlers.

These tests exercise the FastAPI application setup,
error handling, and infrastructure components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import (
    ConfigurationException,
    HealthCheckFailedException,
    KVStoreException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
    ServiceUnavailableException,
)

if TYPE_CHECKING:
    pass


class TestAppCoverage:
    """Tests to boost app coverage."""

    @pytest.mark.asyncio
    async def test_error_handlers(self) -> None:
        """Test error handler registration and responses."""
        from app.infrastructure.api.error_handlers import (
            configuration_exception_handler,
            generic_exception_handler,
            health_check_exception_handler,
            kv_store_exception_handler,
            service_not_found_handler,
            service_unavailable_handler,
            validation_exception_handler,
        )
        from fastapi import Request
        from fastapi.exceptions import RequestValidationError

        # Mock request
        mock_request = Mock(spec=Request)

        # Test configuration exception handler
        exc = ConfigurationException("Config error")
        response = await configuration_exception_handler(mock_request, exc)
        assert response.status_code == 500
        assert b"Configuration error" in response.body

        # Test health check exception handler
        exc = HealthCheckFailedException("Health check failed")
        response = await health_check_exception_handler(mock_request, exc)
        assert response.status_code == 503
        assert b"Health check failed" in response.body

        # Test KV store exception handler
        exc = KVStoreException("KV error")
        response = await kv_store_exception_handler(mock_request, exc)
        assert response.status_code == 503
        assert b"Storage service unavailable" in response.body

        # Test service not found handler
        exc = ServiceNotFoundException("Service not found")
        response = await service_not_found_handler(mock_request, exc)
        assert response.status_code == 404
        assert b"Service not found" in response.body

        # Test service already exists exception handler (use generic handler)
        exc = ServiceAlreadyExistsException("test-service")
        response = await generic_exception_handler(mock_request, exc)
        assert response.status_code == 500

        # Test service unavailable handler
        exc = ServiceUnavailableException("Service unavailable")
        response = await service_unavailable_handler(mock_request, exc)
        assert response.status_code == 503
        assert b"Service temporarily unavailable" in response.body

        # Test validation exception handler
        errors = [{"loc": ("field",), "msg": "invalid", "type": "value_error"}]
        exc = RequestValidationError(errors=errors)
        response = await validation_exception_handler(mock_request, exc)
        assert response.status_code == 422

        # Test generic exception handler
        exc = Exception("Generic error")
        response = await generic_exception_handler(mock_request, exc)
        assert response.status_code == 500
        assert b"Internal server error" in response.body

    @pytest.mark.asyncio
    async def test_main_app_lifespan(self) -> None:
        """Test main app initialization and lifespan."""
        with (
            patch("app.main.get_configuration_port") as mock_get_config,
            patch("app.main.ConnectionManager") as mock_cm_class,
            patch("app.main.set_connection_manager") as mock_set_cm,
        ):
            # Mock configuration
            mock_config_port = Mock()
            mock_config = Mock()
            mock_config.environment = "test"
            mock_config.api_port = 8100
            mock_config.log_level = "INFO"
            mock_config_port.load_configuration.return_value = mock_config
            mock_get_config.return_value = mock_config_port

            # Mock connection manager
            mock_cm = Mock()
            mock_cm.startup = AsyncMock()
            mock_cm.shutdown = AsyncMock()
            mock_cm_class.return_value = mock_cm

            # Import and test lifespan
            from app.main import app, lifespan

            # Test startup
            async with lifespan(app):
                # Verify startup was called
                mock_config_port.load_configuration.assert_called_once()
                mock_cm.startup.assert_called_once()
                mock_set_cm.assert_called_once_with(mock_cm)

            # Verify shutdown was called
            mock_cm.shutdown.assert_called_once()

    def test_app_metadata(self) -> None:
        """Test FastAPI app metadata."""
        from app.main import app

        assert app.title == "AegisTrader Management Service"
        assert app.version == "0.1.0"
        assert "Management and monitoring API" in app.description

    @pytest.mark.asyncio
    async def test_connection_manager_coverage(self) -> None:
        """Test connection manager edge cases."""
        from app.domain.models import ServiceConfiguration
        from app.infrastructure.connection_manager import ConnectionManager

        config = ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8100,
            log_level="INFO",
            environment="development",
        )

        manager = ConnectionManager(config)

        # Test get_kv_store before initialization
        from app.domain.exceptions import KVStoreException

        with pytest.raises(KVStoreException) as exc_info:
            await manager.get_kv_store()
        assert "KV Store not initialized" in str(exc_info.value)

    def test_port_interfaces(self) -> None:
        """Test port interface definitions."""
        from app.ports.service_instance_repository import ServiceInstanceRepositoryPort
        from app.ports.service_registry_kv_store import ServiceRegistryKVStorePort

        # These are abstract classes, just verify they can be imported
        assert ServiceInstanceRepositoryPort is not None
        assert ServiceRegistryKVStorePort is not None

    @pytest.mark.asyncio
    async def test_service_registry_service_error_paths(self) -> None:
        """Test service registry service error handling."""
        from app.application.service_registry_service import ServiceRegistryService
        from app.domain.exceptions import KVStoreException
        from app.domain.models import ServiceDefinition

        mock_kv = Mock()
        service = ServiceRegistryService(mock_kv)

        # Test list_services error
        mock_kv.ls = AsyncMock(side_effect=Exception("List error"))
        with pytest.raises(KVStoreException):
            await service.list_services()

        # Test get_service_definition error
        mock_kv.get = AsyncMock(side_effect=Exception("Get error"))
        with pytest.raises(KVStoreException):
            await service.get_service_definition("test")

        # Test create_or_update_service error
        definition = ServiceDefinition(
            service_name="test",
            description="Test",
            version="1.0.0",
            endpoints=["test"],
            metadata={},
        )
        mock_kv.put = AsyncMock(side_effect=Exception("Put error"))
        with pytest.raises(KVStoreException):
            await service.create_or_update_service(definition)

        # Test update_service_metadata error
        mock_kv.get = AsyncMock(return_value=None)
        result = await service.update_service_metadata("test", {"key": "value"})
        assert result is None

        # Test validate_service_name with reserved name
        with pytest.raises(ValueError):
            await service.validate_service_name("system")

    def test_model_coverage(self) -> None:
        """Test model edge cases for coverage."""
        from datetime import datetime

        from app.domain.models import EventType, ServiceEvent

        # Test ServiceEvent
        event = ServiceEvent(
            event_type=EventType.SERVICE_REGISTERED,
            service_name="test",
            instance_id="123",
            timestamp=datetime.now(),
            details={"key": "value"},
        )
        assert event.event_type == EventType.SERVICE_REGISTERED

        # Test model_dump_json
        json_str = event.model_dump_json()
        assert "SERVICE_REGISTERED" in json_str

    @pytest.mark.asyncio
    async def test_service_routes_additional_coverage(self) -> None:
        """Test additional service routes for coverage."""
        from app.domain.exceptions import KVStoreException
        from app.domain.models import ServiceDefinition
        from app.infrastructure.api.service_routes import (
            check_service_health,
            create_service,
            get_service_instances,
            list_services,
            update_service,
            update_service_metadata,
        )
        from fastapi import HTTPException

        mock_registry = Mock()

        # Test list_services error
        mock_registry.list_services = AsyncMock(side_effect=KVStoreException("List error"))
        with pytest.raises(HTTPException) as exc_info:
            await list_services(service_registry=mock_registry)
        assert exc_info.value.status_code == 503

        # Test create_service
        definition = ServiceDefinition(
            service_name="test",
            description="Test",
            version="1.0.0",
            endpoints=["test"],
            metadata={},
        )
        mock_registry.create_or_update_service = AsyncMock(return_value=definition)
        result = await create_service(definition, service_registry=mock_registry)
        assert result == definition

        # Test update_service error
        mock_registry.update_service_metadata = AsyncMock(
            side_effect=KVStoreException("Update error")
        )
        with pytest.raises(HTTPException) as exc_info:
            await update_service("test", {"key": "value"}, service_registry=mock_registry)
        assert exc_info.value.status_code == 500

        # Test check_service_health
        mock_registry.check_service_health = AsyncMock(return_value={"status": "healthy"})
        result = await check_service_health("test", service_registry=mock_registry)
        assert result == {"status": "healthy"}

        # Test get_service_instances
        mock_registry.get_service_instances = AsyncMock(return_value=[])
        result = await get_service_instances("test", service_registry=mock_registry)
        assert result == []

        # Test update_service_metadata not found
        mock_registry.update_service_metadata = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await update_service_metadata("test", {"key": "value"}, service_registry=mock_registry)
        assert exc_info.value.status_code == 404

    def test_timezone_additional_coverage(self) -> None:
        """Test timezone utility functions."""
        from datetime import datetime

        from app.utils.timezone import convert_to_utc8, now_utc8_iso, utc8_timestamp_factory

        # Test now_utc8_iso
        iso_str = now_utc8_iso()
        assert isinstance(iso_str, str)
        assert "+" in iso_str  # Has timezone info

        # Test utc8_timestamp_factory
        ts = utc8_timestamp_factory()
        assert ts.tzinfo is not None

        # Test convert_to_utc8 with naive datetime
        naive_dt = datetime(2024, 1, 1, 0, 0, 0)
        converted = convert_to_utc8(naive_dt)
        assert converted.tzinfo is not None
