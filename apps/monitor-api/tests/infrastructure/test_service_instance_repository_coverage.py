"""Additional tests for ServiceInstanceRepositoryAdapter to improve coverage.

These tests cover edge cases and error scenarios for the repository adapter.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.infrastructure.service_instance_repository_adapter import ServiceInstanceRepositoryAdapter

if TYPE_CHECKING:
    pass


class TestServiceInstanceRepositoryAdapterCoverage:
    """Additional test cases for complete coverage of ServiceInstanceRepositoryAdapter."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        kv = Mock()
        kv.keys = AsyncMock()
        kv.get = AsyncMock()
        return kv

    @pytest.fixture
    def adapter(self, mock_kv_store: Mock) -> ServiceInstanceRepositoryAdapter:
        """Create a repository adapter instance."""
        return ServiceInstanceRepositoryAdapter(mock_kv_store)

    @pytest.mark.asyncio
    async def test_get_all_instances_json_decode_error(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test handling of JSON decode errors in get_all_instances."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__test__123"]
        mock_entry = Mock()
        mock_entry.value = b"invalid json {"  # Invalid JSON
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await adapter.get_all_instances()

        # Assert - Should skip invalid entries
        assert instances == []

    @pytest.mark.asyncio
    async def test_get_all_instances_dict_value(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test handling dict values directly (not bytes or string)."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__test__123"]
        mock_entry = Mock()
        mock_entry.value = {
            "service_name": "test-service",  # Must match pattern
            "instance_id": "123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await adapter.get_all_instances()

        # Assert
        assert len(instances) == 1
        assert instances[0].service_name == "test-service"

    @pytest.mark.asyncio
    async def test_get_instances_by_service_json_error(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test get_instances_by_service handles JSON errors gracefully."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__test__123"]
        mock_entry = Mock()
        mock_entry.value = "not valid json"  # String but not JSON
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await adapter.get_instances_by_service("test")

        # Assert - Should skip invalid entries
        assert instances == []

    @pytest.mark.asyncio
    async def test_get_instances_by_service_dict_value(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test get_instances_by_service with dict values."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__test__123"]
        mock_entry = Mock()
        mock_entry.value = {
            "service_name": "test-service",  # Must match pattern
            "instance_id": "123",
            "version": "1.0.0",
            "status": "STANDBY",
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await adapter.get_instances_by_service("test")

        # Assert
        assert len(instances) == 1
        assert instances[0].status == "STANDBY"

    @pytest.mark.asyncio
    async def test_translate_to_domain_model_with_sticky_active(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test translation with sticky_active fields in data."""
        # Arrange
        data = {
            "service_name": "test",
            "instance_id": "123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now(UTC).isoformat(),
            "sticky_active_status": "LEADER",
            "lifecycle_state": "STARTED",
        }

        # Act
        instance = adapter._translate_to_domain_model(data)

        # Assert
        assert instance.service_name == "test"
        assert instance.metadata["sticky_active_status"] == "LEADER"
        assert instance.metadata["lifecycle_state"] == "STARTED"

    @pytest.mark.asyncio
    async def test_translate_with_camel_case_fields(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test translation handles camelCase field names."""
        # Arrange
        data = {
            "serviceName": "test-service",  # camelCase - must match pattern
            "instanceId": "123",  # camelCase
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": datetime.now(UTC).isoformat(),  # camelCase
            "stickyActiveGroup": "group-1",  # camelCase
        }

        # Act
        instance = adapter._translate_to_domain_model(data)

        # Assert
        assert instance.service_name == "test-service"
        assert instance.instance_id == "123"
        assert instance.sticky_active_group == "group-1"

    def test_parse_timestamp_with_datetime(self, adapter: ServiceInstanceRepositoryAdapter) -> None:
        """Test _parse_timestamp with datetime object."""
        # Arrange
        now = datetime.now(UTC)

        # Act
        result = adapter._parse_timestamp(now)

        # Assert
        assert result == now

    def test_parse_timestamp_with_unix_timestamp(
        self, adapter: ServiceInstanceRepositoryAdapter
    ) -> None:
        """Test _parse_timestamp with Unix timestamp."""
        # Arrange
        timestamp = 1609459200  # 2021-01-01 00:00:00 UTC

        # Act
        result = adapter._parse_timestamp(timestamp)

        # Assert
        assert result.year == 2021
        assert result.month == 1

    def test_parse_timestamp_with_float(self, adapter: ServiceInstanceRepositoryAdapter) -> None:
        """Test _parse_timestamp with float timestamp."""
        # Arrange
        timestamp = 1609459200.5

        # Act
        result = adapter._parse_timestamp(timestamp)

        # Assert
        assert isinstance(result, datetime)

    def test_parse_timestamp_invalid_string(
        self, adapter: ServiceInstanceRepositoryAdapter
    ) -> None:
        """Test _parse_timestamp with invalid string returns None."""
        # Arrange
        invalid = "not a timestamp"

        # Act
        result = adapter._parse_timestamp(invalid)

        # Assert
        assert result is None

    def test_parse_timestamp_none_value(self, adapter: ServiceInstanceRepositoryAdapter) -> None:
        """Test _parse_timestamp with None returns None."""
        # Act
        result = adapter._parse_timestamp(None)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_instance_string_value(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test get_instance with string JSON value."""
        # Arrange
        instance_data = {
            "service_name": "test",
            "instance_id": "123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        mock_entry = Mock()
        mock_entry.value = json.dumps(instance_data)
        mock_kv_store.get.return_value = mock_entry

        # Act
        instance = await adapter.get_instance("test", "123")

        # Assert
        assert instance is not None
        assert instance.instance_id == "123"

    @pytest.mark.asyncio
    async def test_get_instance_dict_value(
        self, adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test get_instance with dict value."""
        # Arrange
        mock_entry = Mock()
        mock_entry.value = {
            "service_name": "test",
            "instance_id": "123",
            "version": "1.0.0",
            "status": "UNHEALTHY",
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        mock_kv_store.get.return_value = mock_entry

        # Act
        instance = await adapter.get_instance("test", "123")

        # Assert
        assert instance is not None
        assert instance.status == "UNHEALTHY"
