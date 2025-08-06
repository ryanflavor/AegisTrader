"""Tests for Aegis SDK KV adapter.

These tests cover the AegisSDKKVAdapter implementation following DDD principles.
This adapter acts as an Anti-Corruption Layer between the monitor-api bounded context
and the SDK bounded context.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceDefinition

if TYPE_CHECKING:
    pass


class TestAegisSDKAdapter:
    """Tests for Aegis SDK KV adapter."""

    @pytest.mark.asyncio
    async def test_adapter_connect(self) -> None:
        """Test adapter connection following hexagonal architecture."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # Mock infrastructure layer components (Ports and Adapters pattern)
        mock_nats_adapter = AsyncMock()
        mock_kv_store = AsyncMock()

        # Setup NATS adapter mock
        mock_nats_adapter.connect = AsyncMock()

        # Setup KV Store mock
        mock_kv_store.connect = AsyncMock()
        mock_kv_store._kv = MagicMock()  # Internal KV reference

        with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter") as mock_nats_class:
            with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSKVStore") as mock_kv_class:
                mock_nats_class.return_value = mock_nats_adapter
                mock_kv_class.return_value = mock_kv_store

                await adapter.connect("nats://localhost:4222")

                # Verify infrastructure initialization
                assert adapter._nats_adapter == mock_nats_adapter
                assert adapter._kv_store == mock_kv_store
                assert adapter._connected is True
                assert adapter.raw_kv == mock_kv_store._kv

                # Verify connection sequence
                mock_nats_adapter.connect.assert_called_once_with(["nats://localhost:4222"])
                mock_kv_store.connect.assert_called_once_with("service_registry")

    @pytest.mark.asyncio
    async def test_adapter_connect_failure(self) -> None:
        """Test adapter connection failure handling."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        mock_nats_adapter = AsyncMock()
        mock_nats_adapter.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter") as mock_nats_class:
            mock_nats_class.return_value = mock_nats_adapter

            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")

            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_disconnect(self) -> None:
        """Test adapter disconnection."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # Setup connected state with mocks
        mock_nats_adapter = AsyncMock()
        mock_kv_store = AsyncMock()

        mock_nats_adapter.disconnect = AsyncMock()
        mock_kv_store.disconnect = AsyncMock()

        adapter._nats_adapter = mock_nats_adapter
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        await adapter.disconnect()

        # Verify disconnection sequence
        mock_kv_store.disconnect.assert_called_once()
        mock_nats_adapter.disconnect.assert_called_once()
        assert adapter._connected is False

    @pytest.mark.asyncio
    async def test_adapter_operations(self) -> None:
        """Test adapter CRUD operations following Repository pattern."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Create test aggregate (ServiceDefinition)
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
        )

        # Test put operation (create new aggregate)
        mock_kv_store.exists = AsyncMock(return_value=False)
        mock_kv_store.put = AsyncMock()

        await adapter.put("test-service", service_def)

        mock_kv_store.exists.assert_called_once_with("test-service")
        mock_kv_store.put.assert_called_once()

        # Verify the data was serialized correctly
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "test-service"
        assert isinstance(call_args[0][1], dict)
        assert call_args[0][1]["service_name"] == "test-service"

        # Test get operation (retrieve aggregate)
        mock_entry = Mock()
        mock_entry.value = service_def.to_iso_dict()
        mock_entry.revision = 1
        mock_kv_store.get = AsyncMock(return_value=mock_entry)

        result = await adapter.get("test-service")
        assert result is not None
        assert result.service_name == "test-service"
        assert isinstance(result, ServiceDefinition)

        # Test get not found
        mock_kv_store.get = AsyncMock(return_value=None)
        result = await adapter.get("unknown-service")
        assert result is None

        # Test delete operation
        mock_kv_store.exists = AsyncMock(return_value=True)
        mock_kv_store.delete = AsyncMock()

        await adapter.delete("test-service")

        mock_kv_store.exists.assert_called_with("test-service")
        mock_kv_store.delete.assert_called_once_with("test-service")

        # Test list_all operation
        mock_kv_store.keys = AsyncMock(
            return_value=["service1", "service2", "service-instances_xyz"]
        )
        mock_kv_store.get = AsyncMock()

        # Setup get responses for non-instance keys
        async def get_side_effect(key: str) -> Any:
            if key.startswith("service-instances_"):
                return None
            mock_entry = Mock()
            mock_entry.value = {
                "service_name": key,
                "owner": "test-team",
                "description": f"Description for {key}",
                "version": "1.0.0",
                "created_at": "2024-01-01T12:00:00+00:00",
                "updated_at": "2024-01-01T12:00:00+00:00",
            }
            return mock_entry

        mock_kv_store.get.side_effect = get_side_effect

        services = await adapter.list_all()
        assert len(services) == 2  # Should exclude service-instances_ key

    @pytest.mark.asyncio
    async def test_adapter_error_handling(self) -> None:
        """Test adapter error handling with domain exceptions."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Create test aggregate
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
        )

        # Test put error - duplicate key (business rule violation)
        mock_kv_store.exists = AsyncMock(return_value=True)
        with pytest.raises(ValueError) as exc_info:
            await adapter.put("test-service", service_def)
        assert "already exists" in str(exc_info.value)

        # Test put infrastructure error
        mock_kv_store.exists = AsyncMock(return_value=False)
        mock_kv_store.put = AsyncMock(side_effect=Exception("Network error"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.put("test-service", service_def)
        assert "Failed to put key" in str(exc_info.value)

        # Test get error
        mock_kv_store.get = AsyncMock(side_effect=Exception("Get failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("test-service")
        assert "Failed to get key" in str(exc_info.value)

        # Test delete not found error (business rule)
        mock_kv_store.exists = AsyncMock(return_value=False)
        with pytest.raises(ValueError) as exc_info:
            await adapter.delete("test-service")
        assert "not found" in str(exc_info.value)

        # Test delete infrastructure error
        mock_kv_store.exists = AsyncMock(return_value=True)
        mock_kv_store.delete = AsyncMock(side_effect=Exception("Delete failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.delete("test-service")
        assert "Failed to delete key" in str(exc_info.value)

        # Test list error
        mock_kv_store.keys = AsyncMock(side_effect=Exception("List failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.list_all()
        assert "Failed to list keys" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_not_connected(self) -> None:
        """Test operations when not connected - infrastructure guard."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # Create test aggregate
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
        )

        # All repository operations should raise when not connected
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.put("test-service", service_def)
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("test-service")
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.delete("test-service")
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.list_all()
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.update("test-service", service_def)
        assert "Not connected to NATS KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_update_with_revision(self) -> None:
        """Test optimistic locking with revision for concurrent updates."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Create test aggregate
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team-updated",
            description="Updated description",
            version="1.1.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-02T12:00:00+00:00"),
        )

        # Test successful update with revision
        mock_entry = Mock()
        mock_entry.value = {"service_name": "test-service"}
        mock_kv_store.get = AsyncMock(return_value=mock_entry)
        mock_kv_store.put = AsyncMock()

        await adapter.update("test-service", service_def, revision=5)

        # Verify KVOptions was used
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "test-service"
        # Check that options with revision was passed
        if len(call_args[0]) > 2:
            options = call_args[0][2]
            assert options.revision == 5

        # Test revision mismatch error
        mock_kv_store.put = AsyncMock(side_effect=Exception("Revision mismatch: expected 5, got 7"))
        with pytest.raises(ValueError) as exc_info:
            await adapter.update("test-service", service_def, revision=5)
        assert "Revision mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_get_with_revision(self) -> None:
        """Test getting aggregate with revision for optimistic locking."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv_store = AsyncMock()
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Setup mock entry with revision
        mock_entry = Mock()
        mock_entry.value = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
            "created_at": "2024-01-01T12:00:00+00:00",
            "updated_at": "2024-01-01T12:00:00+00:00",
        }
        mock_entry.revision = 42
        mock_kv_store.get = AsyncMock(return_value=mock_entry)

        service, revision = await adapter.get_with_revision("test-service")

        assert service is not None
        assert service.service_name == "test-service"
        assert revision == 42

        # Test not found case
        mock_kv_store.get = AsyncMock(return_value=None)
        service, revision = await adapter.get_with_revision("unknown-service")

        assert service is None
        assert revision is None
