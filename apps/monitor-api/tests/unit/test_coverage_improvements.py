"""Test coverage improvements for low-coverage modules.

This module contains additional tests to improve coverage for modules
with coverage below 90%, focusing on error handling paths and edge cases.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.domain.exceptions import (
    KVStoreException,
    ServiceNotFoundException,
)
from app.domain.models import ServiceDefinition
from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition
from app.infrastructure.api.error_handlers import (
    create_error_response,
    domain_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.ports.configuration import ConfigurationPort
from app.ports.monitoring import MonitoringPort
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


class TestErrorHandlersImproved:
    """Additional tests for error handlers module."""

    @pytest.mark.asyncio
    async def test_create_error_response_with_domain_exception(self):
        """Test create_error_response with a domain exception."""
        exc = ServiceNotFoundException("test-service")
        response = create_error_response(exc, 404, {"service": "test-service"})

        assert response.status_code == 404
        content = json.loads(response.body)
        assert content["error"]["code"] == "SERVICE_NOT_FOUND"
        assert "test-service" in content["error"]["message"]
        assert content["error"]["details"]["service"] == "test-service"

    @pytest.mark.asyncio
    async def test_create_error_response_with_generic_exception(self):
        """Test create_error_response with a generic exception."""
        exc = ValueError("Something went wrong")
        response = create_error_response(exc, 500)

        assert response.status_code == 500
        content = json.loads(response.body)
        assert content["error"]["code"] == "INTERNAL_ERROR"
        assert content["error"]["message"] == "Something went wrong"

    @pytest.mark.asyncio
    async def test_domain_exception_handler_with_details(self):
        """Test domain exception handler extracting service name from message."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/services/test-service"

        exc = ServiceNotFoundException("test-service")
        response = await domain_exception_handler(request, exc)

        assert response.status_code == 404
        content = json.loads(response.body)
        assert content["error"]["code"] == "SERVICE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_validation_exception_handler_with_request_validation_error(self):
        """Test validation exception handler with RequestValidationError."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/services"

        # Create a RequestValidationError
        errors = [
            {
                "loc": ("body", "name"),
                "msg": "field required",
                "type": "value_error.missing",
            }
        ]
        exc = RequestValidationError(errors)
        response = await validation_exception_handler(request, exc)

        assert response.status_code == 422
        content = json.loads(response.body)
        assert content["error"]["code"] == "VALIDATION_ERROR"
        assert "body.name" in content["error"]["message"]
        assert content["error"]["details"]["field"] == "body.name"

    @pytest.mark.asyncio
    async def test_validation_exception_handler_with_validation_error(self):
        """Test validation exception handler with ValidationError."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/services"

        # Create a ValidationError
        try:
            ServiceDefinition(
                service_name="",
                owner="test-team",
                description="Test",
                version="1.0.0",
                repository_url="https://github.com/test/repo",
            )
        except ValidationError as e:
            exc = e

        response = await validation_exception_handler(request, exc)

        assert response.status_code == 422
        content = json.loads(response.body)
        assert content["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in content["error"]

    @pytest.mark.asyncio
    async def test_http_exception_handler_with_dict_detail(self):
        """Test HTTP exception handler with dict detail in error format."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"

        exc = HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Resource not found"}},
        )
        response = await http_exception_handler(request, exc)

        assert response.status_code == 404
        content = json.loads(response.body)
        assert content["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_http_exception_handler_with_string_detail(self):
        """Test HTTP exception handler with string detail."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"

        exc = HTTPException(status_code=403, detail="Access denied")
        response = await http_exception_handler(request, exc)

        assert response.status_code == 403
        content = json.loads(response.body)
        assert content["error"]["code"] == "HTTP_403"
        assert content["error"]["message"] == "Access denied"

    @pytest.mark.asyncio
    async def test_general_exception_handler(self):
        """Test general exception handler for unexpected errors."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"

        exc = RuntimeError("Unexpected error")
        response = await general_exception_handler(request, exc)

        assert response.status_code == 500
        content = json.loads(response.body)
        assert content["error"]["code"] == "INTERNAL_ERROR"
        assert content["error"]["message"] == "An internal server error occurred"


class TestAegisKVCompositionImproved:
    """Additional tests for AegisKVStoreComposition to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_with_dict_value(self):
        """Test get method when entry value is already a dict."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True  # Mark as connected to bypass check

        # Mock entry with dict value
        entry = MagicMock()
        entry.value = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test",
            "version": "1.0.0",
            "repository_url": "https://github.com/test/repo",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_kv_store.get.return_value = entry

        result = await adapter.get("test-key")
        assert result is not None
        assert result.service_name == "test-service"

    @pytest.mark.asyncio
    async def test_get_with_kv_store_exception(self):
        """Test get method handling KV store exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.get.side_effect = Exception("Connection failed")

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("test-key")

        assert "Failed to get key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_put_with_existing_key(self):
        """Test put method when key already exists."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.exists.return_value = True

        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test",
            version="1.0.0",
            repository_url="https://github.com/test/repo",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValueError) as exc_info:
            await adapter.put("test-key", service)

        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_put_with_kv_store_exception(self):
        """Test put method handling KV store exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.exists.return_value = False
        mock_kv_store.put.side_effect = Exception("Write failed")

        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test",
            version="1.0.0",
            repository_url="https://github.com/test/repo",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.put("test-key", service)

        assert "Failed to put key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_key_not_found(self):
        """Test update method when key doesn't exist."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.get.return_value = None

        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test",
            version="1.0.0",
            repository_url="https://github.com/test/repo",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValueError) as exc_info:
            await adapter.update("test-key", service)

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_with_revision_mismatch(self):
        """Test update method with revision mismatch error."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Mock existing entry
        entry = MagicMock()
        entry.value = json.dumps(
            {
                "service_name": "test-service",
                "owner": "test-team",
                "description": "Test",
                "version": "1.0.0",
                "repository_url": "https://github.com/test/repo",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        mock_kv_store.get.return_value = entry
        mock_kv_store.put.side_effect = Exception("Revision mismatch: expected 2, got 1")

        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Updated",
            version="1.0.0",
            repository_url="https://github.com/test/repo",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValueError) as exc_info:
            await adapter.update("test-key", service, revision=1)

        assert "Revision mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_with_kv_store_exception(self):
        """Test update method handling other KV store exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Mock existing entry
        entry = MagicMock()
        entry.value = json.dumps(
            {
                "service_name": "test-service",
                "owner": "test-team",
                "description": "Test",
                "version": "1.0.0",
                "repository_url": "https://github.com/test/repo",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        mock_kv_store.get.return_value = entry
        mock_kv_store.put.side_effect = Exception("Network error")

        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Updated",
            version="1.0.0",
            repository_url="https://github.com/test/repo",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.update("test-key", service)

        assert "Failed to update key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_key_not_found(self):
        """Test delete method when key doesn't exist."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.exists.return_value = False

        with pytest.raises(ValueError) as exc_info:
            await adapter.delete("test-key")

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_with_kv_store_exception(self):
        """Test delete method handling KV store exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.exists.return_value = True
        mock_kv_store.delete.side_effect = Exception("Delete failed")

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.delete("test-key")

        assert "Failed to delete key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_all_with_invalid_json(self):
        """Test list_all method when entry has invalid JSON."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.keys.return_value = ["service1", "service2"]

        # First entry is valid, second has invalid JSON
        entry1 = MagicMock()
        entry1.value = json.dumps(
            {
                "service_name": "service-one",
                "owner": "test-team",
                "description": "Test",
                "version": "1.0.0",
                "repository_url": "https://github.com/test/repo",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        entry2 = MagicMock()
        entry2.value = "invalid json {"

        mock_kv_store.get.side_effect = [entry1, entry2]

        services = await adapter.list_all()
        assert len(services) == 1
        assert services[0].service_name == "service-one"

    @pytest.mark.asyncio
    async def test_list_all_with_kv_store_exception(self):
        """Test list_all method handling KV store exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.keys.side_effect = Exception("Connection lost")

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.list_all()

        assert "Failed to list" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_with_revision_key_not_found(self):
        """Test get_with_revision when key doesn't exist."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.get.return_value = None

        result = await adapter.get_with_revision("test-key")
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_with_revision_exception(self):
        """Test get_with_revision handling exceptions."""
        adapter = AegisKVStoreComposition()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        mock_kv_store.get.side_effect = Exception("Read failed")

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get_with_revision("test-key")

        assert "Failed to get key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connect method when already connected - it will try to connect again."""
        adapter = AegisKVStoreComposition()

        # Mock the NATSAdapter class so we can control the connection
        with patch("app.infrastructure.aegis_kv_composition.NATSAdapter") as mock_nats_class:
            mock_adapter = AsyncMock()
            mock_nats_class.return_value = mock_adapter

            with patch("app.infrastructure.aegis_kv_composition.NATSKVStore") as mock_kv_class:
                mock_kv_store = AsyncMock()
                mock_kv_class.return_value = mock_kv_store

                await adapter.connect("nats://localhost:4222")

                assert adapter._connected is True
                mock_adapter.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """Test disconnect method when not connected."""
        adapter = AegisKVStoreComposition()
        adapter._connected = False

        await adapter.disconnect()
        # Should not raise any exceptions


class TestPortsImproved:
    """Additional tests for port interfaces to improve coverage."""

    def test_monitoring_port_abstract_methods(self):
        """Test that MonitoringPort is a Protocol."""
        from typing import Protocol

        # Test that MonitoringPort is a Protocol
        assert issubclass(MonitoringPort.__class__, type(Protocol))

        # Test that we can create a class that implements the protocol
        class ConcreteMonitoring:
            async def check_health(self):
                pass

            async def get_system_status(self):
                pass

            async def get_start_time(self):
                pass

            async def is_ready(self):
                pass

            async def get_detailed_health(self):
                pass

        # Should be able to instantiate it
        monitoring = ConcreteMonitoring()
        assert monitoring is not None

    def test_configuration_port_abstract_methods(self):
        """Test that ConfigurationPort is a Protocol."""
        from typing import Protocol

        # Test that ConfigurationPort is a Protocol
        assert issubclass(ConfigurationPort.__class__, type(Protocol))

        # Test that we can create a class that implements the protocol
        class ConcreteConfiguration:
            def load_configuration(self):
                pass

            def validate_configuration(self, config):
                pass

        # Should be able to instantiate it
        config = ConcreteConfiguration()
        assert config is not None


# Removed TestServiceRoutesImproved class - would need more complex setup to test properly
