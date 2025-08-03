"""Unit tests for ServiceRegistryService focusing on edge cases and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.application.service_registry_service import ServiceRegistryService
from app.domain.exceptions import (
    ServiceNotFoundException,
)
from app.domain.models import ServiceDefinition


class TestServiceRegistryServiceEdgeCases:
    """Test edge cases and error handling in ServiceRegistryService."""

    @pytest.fixture
    def mock_kv_store(self):
        """Create a mock KV store."""
        return AsyncMock()

    @pytest.fixture
    def service_registry(self, mock_kv_store):
        """Create a service registry with mocked KV store."""
        return ServiceRegistryService(mock_kv_store)

    @pytest.fixture
    def test_service_data(self):
        """Test service data."""
        return {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }

    @pytest.mark.asyncio
    async def test_create_service_general_exception(
        self, service_registry, mock_kv_store, test_service_data
    ):
        """Test create_service handles general exceptions from KV store."""
        # Mock KV store to raise a non-ValueError exception
        mock_kv_store.put.side_effect = RuntimeError("Unexpected error")

        # Should re-raise the exception
        with pytest.raises(RuntimeError, match="Unexpected error"):
            await service_registry.create_service(test_service_data)

    @pytest.mark.asyncio
    async def test_create_service_value_error_without_already_exists(
        self, service_registry, mock_kv_store, test_service_data
    ):
        """Test create_service re-raises ValueError that's not 'already exists'."""
        # Mock KV store to raise a ValueError without "already exists" in message
        mock_kv_store.put.side_effect = ValueError("Some other KV store error")

        # Should re-raise the exception
        with pytest.raises(ValueError, match="Some other KV store error"):
            await service_registry.create_service(test_service_data)

    @pytest.mark.asyncio
    async def test_update_service_not_found_in_get(
        self, service_registry, mock_kv_store, test_service_data
    ):
        """Test update_service when service is not found during initial get."""
        # Mock KV store to return None
        mock_kv_store.get.return_value = None

        # Should raise ServiceNotFoundException
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service_registry.update_service("test-service", {"version": "2.0.0"})

        assert "test-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_service_not_found_during_update(
        self, service_registry, mock_kv_store, test_service_data
    ):
        """Test update_service when service is not found during update operation."""
        # Mock KV store to return existing service
        from app.utils.timezone import now_utc8

        test_time = now_utc8()
        existing_service = ServiceDefinition(
            **test_service_data, created_at=test_time, updated_at=test_time
        )
        mock_kv_store.get.return_value = existing_service

        # Mock update to raise ValueError with "not found"
        mock_kv_store.update.side_effect = ValueError("Service not found")

        # Should raise ServiceNotFoundException
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service_registry.update_service("test-service", {"version": "2.0.0"})

        assert "test-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_service_general_exception(
        self, service_registry, mock_kv_store, test_service_data
    ):
        """Test update_service handles general exceptions from KV store."""
        # Mock KV store to return existing service
        from app.utils.timezone import now_utc8

        test_time = now_utc8()
        existing_service = ServiceDefinition(
            **test_service_data, created_at=test_time, updated_at=test_time
        )
        mock_kv_store.get.return_value = existing_service

        # Mock update to raise a general ValueError
        mock_kv_store.update.side_effect = ValueError("Some other error")

        # Should re-raise the exception
        with pytest.raises(ValueError, match="Some other error"):
            await service_registry.update_service("test-service", {"version": "2.0.0"})

    @pytest.mark.asyncio
    async def test_delete_service_general_exception(self, service_registry, mock_kv_store):
        """Test delete_service handles general exceptions from KV store."""
        # Mock KV store to raise a general ValueError
        mock_kv_store.delete.side_effect = ValueError("Some delete error")

        # Should re-raise the exception
        with pytest.raises(ValueError, match="Some delete error"):
            await service_registry.delete_service("test-service")
