"""Tests for Aegis SDK KV adapter.

These tests cover the AegisSDKKVAdapter implementation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException

if TYPE_CHECKING:
    pass


class TestAegisSDKAdapter:
    """Tests for Aegis SDK KV adapter."""

    @pytest.mark.asyncio
    async def test_adapter_connect(self) -> None:
        """Test adapter connection."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # Mock AegisSDK
        mock_sdk = Mock()
        mock_nats_client = Mock()
        mock_kv = Mock()

        mock_sdk.connect = AsyncMock(return_value=mock_nats_client)
        mock_sdk.get_kv = AsyncMock(return_value=mock_kv)

        with patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDK", return_value=mock_sdk):
            await adapter.connect("nats://localhost:4222")

            assert adapter._sdk == mock_sdk
            assert adapter._nats_client == mock_nats_client
            assert adapter._kv == mock_kv
            assert adapter.raw_kv == mock_kv

            mock_sdk.connect.assert_called_once_with("nats://localhost:4222")
            mock_sdk.get_kv.assert_called_once_with("aegis-kv")

    @pytest.mark.asyncio
    async def test_adapter_connect_failure(self) -> None:
        """Test adapter connection failure."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        mock_sdk = Mock()
        mock_sdk.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("app.infrastructure.aegis_sdk_kv_adapter.AegisSDK", return_value=mock_sdk):
            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")

            assert "Failed to connect to KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_disconnect(self) -> None:
        """Test adapter disconnection."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # Set up connected state
        mock_client = Mock()
        mock_client.close = AsyncMock()
        adapter._nats_client = mock_client

        await adapter.disconnect()
        mock_client.close.assert_called_once()
        assert adapter._nats_client is None

    @pytest.mark.asyncio
    async def test_adapter_operations(self) -> None:
        """Test adapter CRUD operations."""
        from app.domain.models import ServiceDefinition
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv = Mock()
        adapter._kv = mock_kv

        # Test put operation
        service_def = ServiceDefinition(
            service_name="test-service",
            description="Test service",
            version="1.0.0",
            endpoints=["test"],
            metadata={},
        )

        mock_kv.put = AsyncMock()
        await adapter.put("test-key", json.dumps(service_def.model_dump()))
        mock_kv.put.assert_called_once()

        # Test get operation
        mock_entry = Mock()
        mock_entry.value = json.dumps(service_def.model_dump()).encode()
        mock_kv.get = AsyncMock(return_value=mock_entry)

        result = await adapter.get("test-key")
        assert result == json.dumps(service_def.model_dump())

        # Test get not found
        mock_kv.get = AsyncMock(return_value=None)
        result = await adapter.get("unknown-key")
        assert result is None

        # Test delete operation
        mock_kv.delete = AsyncMock()
        await adapter.delete("test-key")
        mock_kv.delete.assert_called_once_with("test-key")

        # Test ls operation
        mock_kv.keys = AsyncMock(return_value=["key1", "key2"])
        keys = await adapter.ls("prefix")
        assert keys == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_adapter_error_handling(self) -> None:
        """Test adapter error handling."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()
        mock_kv = Mock()
        adapter._kv = mock_kv

        # Test put error
        mock_kv.put = AsyncMock(side_effect=Exception("Put failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.put("key", "value")
        assert "Failed to put value" in str(exc_info.value)

        # Test get error
        mock_kv.get = AsyncMock(side_effect=Exception("Get failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("key")
        assert "Failed to get value" in str(exc_info.value)

        # Test delete error
        mock_kv.delete = AsyncMock(side_effect=Exception("Delete failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.delete("key")
        assert "Failed to delete key" in str(exc_info.value)

        # Test ls error
        mock_kv.keys = AsyncMock(side_effect=Exception("List failed"))
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.ls("prefix")
        assert "Failed to list keys" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_adapter_not_connected(self) -> None:
        """Test operations when not connected."""
        from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter

        adapter = AegisSDKKVAdapter()

        # All operations should raise when not connected
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.put("key", "value")
        assert "Not connected to KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("key")
        assert "Not connected to KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.delete("key")
        assert "Not connected to KV Store" in str(exc_info.value)

        with pytest.raises(KVStoreException) as exc_info:
            await adapter.ls("prefix")
        assert "Not connected to KV Store" in str(exc_info.value)
