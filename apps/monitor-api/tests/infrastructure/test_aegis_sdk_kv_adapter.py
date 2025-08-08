"""Comprehensive tests for AegisSDKKVAdapter following TDD and hexagonal architecture.

These tests verify the infrastructure adapter implementation with proper
mocking at architectural boundaries and comprehensive edge case coverage.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceDefinition
from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter
from app.utils.timezone import utc8_timestamp_factory

if TYPE_CHECKING:
    pass


class TestAegisSDKKVAdapter:
    """Test cases for AegisSDKKVAdapter following hexagonal architecture."""

    @pytest.fixture
    def adapter(self) -> AegisSDKKVAdapter:
        """Create an adapter instance."""
        return AegisSDKKVAdapter()

    @pytest.fixture
    def sample_service_definition(self) -> ServiceDefinition:
        """Create a sample service definition."""
        now = utc8_timestamp_factory()
        return ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service description",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )

    # Test connect method
    @pytest.mark.asyncio
    async def test_connect_success(self, adapter: AegisSDKKVAdapter) -> None:
        """Test successful connection to NATS."""
        with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter") as mock_nats_class:
            with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSKVStore") as mock_kv_class:
                # Setup mocks
                mock_nats = AsyncMock()
                mock_nats_class.return_value = mock_nats
                mock_kv = AsyncMock()
                mock_kv_class.return_value = mock_kv

                # Act
                await adapter.connect("nats://localhost:4222")

                # Assert - NATSAdapter initialization doesn't use pool_size, use_msgpack
                mock_nats_class.assert_called_once()
                mock_nats.connect.assert_called_once_with(["nats://localhost:4222"])
                mock_kv_class.assert_called_once_with(mock_nats)
                mock_kv.connect.assert_called_once_with("service_registry")
                assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter: AegisSDKKVAdapter) -> None:
        """Test connection failure handling."""
        with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter") as mock_nats_class:
            # Setup mock to fail
            mock_nats = AsyncMock()
            mock_nats.connect.side_effect = Exception("Connection failed")
            mock_nats_class.return_value = mock_nats

            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")

            assert "Failed to connect to NATS" in str(exc_info.value)

    # Test disconnect method
    @pytest.mark.asyncio
    async def test_disconnect(self, adapter: AegisSDKKVAdapter) -> None:
        """Test disconnection from NATS."""
        # Setup adapter with mocked connections
        adapter._nats_adapter = AsyncMock()
        adapter._kv_store = AsyncMock()
        adapter._connected = True

        # Act
        await adapter.disconnect()

        # Assert
        adapter._kv_store.disconnect.assert_called_once()
        adapter._nats_adapter.disconnect.assert_called_once()
        assert adapter._connected is False

    # Test get method
    @pytest.mark.asyncio
    async def test_get_success_with_dict_value(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test getting a service definition when value is a dict."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = sample_service_definition.to_iso_dict()
        adapter._kv_store.get.return_value = mock_entry

        # Act
        result = await adapter.get("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"
        assert result.owner == "test-team"
        adapter._kv_store.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_success_with_string_value(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test getting a service definition when value is a JSON string."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = json.dumps(sample_service_definition.to_iso_dict())
        adapter._kv_store.get.return_value = mock_entry

        # Act
        result = await adapter.get("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"

    @pytest.mark.asyncio
    async def test_get_not_found(self, adapter: AegisSDKKVAdapter) -> None:
        """Test getting a non-existent service definition."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.get.return_value = None

        # Act
        result = await adapter.get("non-existent")

        # Assert
        assert result is None
        adapter._kv_store.get.assert_called_once_with("non-existent")

    @pytest.mark.asyncio
    async def test_get_not_connected(self, adapter: AegisSDKKVAdapter) -> None:
        """Test get when not connected raises exception."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("test-service")

        assert "Not connected to NATS KV Store" in str(exc_info.value)

    # Test put method
    @pytest.mark.asyncio
    async def test_put_success(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test putting a new service definition."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.exists.return_value = False

        # Act
        await adapter.put("test-service", sample_service_definition)

        # Assert
        adapter._kv_store.exists.assert_called_once_with("test-service")
        adapter._kv_store.put.assert_called_once()
        put_call_args = adapter._kv_store.put.call_args
        assert put_call_args[0][0] == "test-service"
        assert put_call_args[0][1]["service_name"] == "test-service"

    @pytest.mark.asyncio
    async def test_put_already_exists(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test putting when service already exists."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.exists.return_value = True

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await adapter.put("test-service", sample_service_definition)

        assert "Key 'test-service' already exists" in str(exc_info.value)
        adapter._kv_store.exists.assert_called_once_with("test-service")
        adapter._kv_store.put.assert_not_called()

    # Test update method
    @pytest.mark.asyncio
    async def test_update_success_without_revision(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test updating an existing service without revision."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = sample_service_definition.to_iso_dict()
        adapter._kv_store.get.return_value = mock_entry

        # Act
        updated_service = ServiceDefinition(
            **{**sample_service_definition.model_dump(), "description": "Updated description"}
        )
        await adapter.update("test-service", updated_service)

        # Assert
        adapter._kv_store.get.assert_called_once_with("test-service")
        adapter._kv_store.put.assert_called_once()
        put_call_args = adapter._kv_store.put.call_args
        assert put_call_args[0][0] == "test-service"
        assert put_call_args[0][1]["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_success_with_revision(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test updating with revision for optimistic locking."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = sample_service_definition.to_iso_dict()
        mock_entry.revision = 42
        adapter._kv_store.get.return_value = mock_entry

        # Act
        updated_service = ServiceDefinition(
            **{**sample_service_definition.model_dump(), "description": "Updated description"}
        )
        await adapter.update("test-service", updated_service, revision=42)

        # Assert
        adapter._kv_store.get.assert_called_once_with("test-service")
        adapter._kv_store.put.assert_called_once()
        put_call_args = adapter._kv_store.put.call_args
        assert put_call_args[0][0] == "test-service"
        # Check that KVOptions was created with revision
        assert hasattr(put_call_args[0][2], "revision")
        assert put_call_args[0][2].revision == 42

    @pytest.mark.asyncio
    async def test_update_not_found(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test updating non-existent service."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await adapter.update("non-existent", sample_service_definition)

        assert "Key 'non-existent' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_revision_mismatch(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test update with revision mismatch."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = sample_service_definition.to_iso_dict()
        adapter._kv_store.get.return_value = mock_entry
        adapter._kv_store.put.side_effect = Exception("Revision mismatch: expected 42 got 43")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await adapter.update("test-service", sample_service_definition, revision=42)

        assert "Revision mismatch for key 'test-service'" in str(exc_info.value)

    # Test delete method
    @pytest.mark.asyncio
    async def test_delete_success(self, adapter: AegisSDKKVAdapter) -> None:
        """Test deleting an existing service."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.exists.return_value = True

        # Act
        await adapter.delete("test-service")

        # Assert
        adapter._kv_store.exists.assert_called_once_with("test-service")
        adapter._kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_delete_not_found(self, adapter: AegisSDKKVAdapter) -> None:
        """Test deleting non-existent service."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.exists.return_value = False

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await adapter.delete("non-existent")

        assert "Key 'non-existent' not found" in str(exc_info.value)
        adapter._kv_store.delete.assert_not_called()

    # Test list_all method
    @pytest.mark.asyncio
    async def test_list_all_success(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test listing all service definitions."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.keys.return_value = ["service1", "service2", "service-instances__test"]

        mock_entry1 = Mock()
        mock_entry1.value = sample_service_definition.to_iso_dict()

        service2_data = {**sample_service_definition.to_iso_dict(), "service_name": "service2"}
        mock_entry2 = Mock()
        mock_entry2.value = service2_data

        adapter._kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        services = await adapter.list_all()

        # Assert
        assert len(services) == 2
        assert services[0].service_name == "test-service"
        assert services[1].service_name == "service2"
        # Verify service-instances_ key was skipped
        assert adapter._kv_store.get.call_count == 2

    @pytest.mark.asyncio
    async def test_list_all_with_parse_error(self, adapter: AegisSDKKVAdapter) -> None:
        """Test list_all handles parsing errors gracefully."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.keys.return_value = ["service1", "service2"]

        mock_entry1 = Mock()
        mock_entry1.value = {"invalid": "data"}  # Missing required fields

        mock_entry2 = Mock()
        mock_entry2.value = {
            "service_name": "service2",
            "owner": "team2",
            "description": "Valid service",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        adapter._kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        services = await adapter.list_all()

        # Assert
        assert len(services) == 1
        assert services[0].service_name == "service2"

    # Test get_with_revision method
    @pytest.mark.asyncio
    async def test_get_with_revision_success(
        self, adapter: AegisSDKKVAdapter, sample_service_definition: ServiceDefinition
    ) -> None:
        """Test getting a service with its revision."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()

        mock_entry = Mock()
        mock_entry.value = sample_service_definition.to_iso_dict()
        mock_entry.revision = 123
        adapter._kv_store.get.return_value = mock_entry

        # Act
        service, revision = await adapter.get_with_revision("test-service")

        # Assert
        assert service is not None
        assert service.service_name == "test-service"
        assert revision == 123
        adapter._kv_store.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_with_revision_not_found(self, adapter: AegisSDKKVAdapter) -> None:
        """Test get_with_revision when service not found."""
        # Setup
        adapter._connected = True
        adapter._kv_store = AsyncMock()
        adapter._kv_store.get.return_value = None

        # Act
        service, revision = await adapter.get_with_revision("non-existent")

        # Assert
        assert service is None
        assert revision is None

    # Test raw_kv property
    def test_raw_kv_property(self, adapter: AegisSDKKVAdapter) -> None:
        """Test raw_kv property access."""
        # Setup
        mock_kv = Mock()
        mock_kv._kv = "raw_kv_instance"
        adapter._kv_store = mock_kv

        # Act
        raw_kv = adapter.raw_kv

        # Assert
        assert raw_kv == "raw_kv_instance"

    def test_raw_kv_property_when_none(self, adapter: AegisSDKKVAdapter) -> None:
        """Test raw_kv property when kv_store is None."""
        # Setup
        adapter._kv_store = None

        # Act
        raw_kv = adapter.raw_kv

        # Assert
        assert raw_kv is None
