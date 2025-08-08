"""Tests for Aegis KV composition following DDD principles.

These tests cover the aegis_kv_composition module which acts as
an Anti-Corruption Layer using composition pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceDefinition

if TYPE_CHECKING:
    pass


class TestAegisComposition:
    """Tests for Aegis KV composition."""

    @pytest.mark.asyncio
    async def test_aegis_kv_composition_basic(self) -> None:
        """Test basic Aegis KV composition functionality using hexagonal architecture."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        # Create instance with composition pattern
        composition = AegisKVStoreComposition("test-bucket")
        assert composition.bucket_name == "test-bucket"
        assert composition._kv_store is None
        assert composition._nats_adapter is None
        assert composition._connected is False

        # Test connect with mocked SDK components
        mock_nats_adapter = AsyncMock()
        mock_kv_store = AsyncMock()

        mock_nats_adapter.connect = AsyncMock()
        mock_kv_store.connect = AsyncMock()
        mock_kv_store._kv = MagicMock()  # Internal KV reference

        with patch("app.infrastructure.aegis_kv_composition.NATSAdapter") as mock_nats_class:
            with patch("app.infrastructure.aegis_kv_composition.NATSKVStore") as mock_kv_class:
                mock_nats_class.return_value = mock_nats_adapter
                mock_kv_class.return_value = mock_kv_store

                await composition.connect("nats://localhost:4222")

                # Verify composition setup
                assert composition._nats_adapter == mock_nats_adapter
                assert composition._kv_store == mock_kv_store
                assert composition._connected is True
                assert composition.raw_kv == mock_kv_store._kv

                mock_nats_adapter.connect.assert_called_once_with(["nats://localhost:4222"])
                mock_kv_store.connect.assert_called_once_with("test-bucket")

        # Test disconnect
        mock_nats_adapter.disconnect = AsyncMock()
        mock_kv_store.disconnect = AsyncMock()

        await composition.disconnect()

        mock_kv_store.disconnect.assert_called_once()
        mock_nats_adapter.disconnect.assert_called_once()
        assert composition._connected is False

    @pytest.mark.asyncio
    async def test_aegis_kv_operations(self) -> None:
        """Test KV operations following Repository pattern."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        composition = AegisKVStoreComposition("test-bucket")
        mock_kv_store = AsyncMock()
        composition._kv_store = mock_kv_store
        composition._connected = True

        # Create test aggregate (ServiceDefinition)
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
        )

        # Test put operation
        mock_kv_store.exists = AsyncMock(return_value=False)
        mock_kv_store.put = AsyncMock()

        await composition.put("test-service", service_def)

        mock_kv_store.exists.assert_called_once_with("test-service")
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "test-service"
        assert isinstance(call_args[0][1], dict)

        # Test get operation
        mock_entry = Mock()
        mock_entry.value = service_def.to_iso_dict()
        mock_entry.revision = 1
        mock_kv_store.get = AsyncMock(return_value=mock_entry)

        result = await composition.get("test-service")
        assert result is not None
        assert result.service_name == "test-service"
        assert isinstance(result, ServiceDefinition)

        # Test delete operation
        mock_kv_store.exists = AsyncMock(return_value=True)
        mock_kv_store.delete = AsyncMock()

        await composition.delete("test-service")

        mock_kv_store.exists.assert_called_with("test-service")
        mock_kv_store.delete.assert_called_once_with("test-service")

        # Test list_all operation
        mock_kv_store.keys = AsyncMock(return_value=["service1", "service2"])

        async def get_side_effect(key: str):
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

        services = await composition.list_all()
        assert len(services) == 2

    @pytest.mark.asyncio
    async def test_aegis_kv_not_connected(self) -> None:
        """Test operations when not connected - infrastructure guard."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        composition = AegisKVStoreComposition("test-bucket")

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
            await composition.put("test-service", service_def)
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await composition.get("test-service")
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await composition.delete("test-service")
        assert "Not connected to NATS KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await composition.list_all()
        assert "Not connected to NATS KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_composition_error_handling(self) -> None:
        """Test error handling in composition pattern."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        composition = AegisKVStoreComposition("test-bucket")

        # Test connection failure
        mock_nats_adapter = AsyncMock()
        mock_nats_adapter.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("app.infrastructure.aegis_kv_composition.NATSAdapter") as mock_nats_class:
            mock_nats_class.return_value = mock_nats_adapter

            with pytest.raises(KVStoreException) as exc_info:
                await composition.connect("nats://localhost:4222")
            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_composition_with_revision(self) -> None:
        """Test operations with revision for optimistic locking."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        composition = AegisKVStoreComposition("test-bucket")
        mock_kv_store = AsyncMock()
        composition._kv_store = mock_kv_store
        composition._connected = True

        # Test get_with_revision
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

        service, revision = await composition.get_with_revision("test-service")

        assert service is not None
        assert service.service_name == "test-service"
        assert revision == 42

        # Test update with revision
        service_def = ServiceDefinition(
            service_name="test-service",
            owner="test-team-updated",
            description="Updated description",
            version="1.1.0",
            created_at=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-01-02T12:00:00+00:00"),
        )

        mock_kv_store.get = AsyncMock(return_value=mock_entry)
        mock_kv_store.put = AsyncMock()

        await composition.update("test-service", service_def, revision=42)

        # Verify the update was called with options
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "test-service"

    @pytest.mark.asyncio
    async def test_get_messaging_adapter(self) -> None:
        """Test getting the messaging adapter for other operations."""
        from app.infrastructure.aegis_kv_composition import AegisKVStoreComposition

        composition = AegisKVStoreComposition("test-bucket")

        # Before connection
        assert composition.get_messaging_adapter() is None

        # After connection
        mock_nats_adapter = AsyncMock()
        composition._nats_adapter = mock_nats_adapter

        assert composition.get_messaging_adapter() == mock_nats_adapter
