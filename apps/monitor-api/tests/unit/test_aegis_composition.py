"""Tests for Aegis KV composition to boost coverage.

These tests cover the aegis_kv_composition module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

if TYPE_CHECKING:
    pass


class TestAegisComposition:
    """Tests for Aegis KV composition."""

    @pytest.mark.asyncio
    async def test_aegis_kv_composition_basic(self) -> None:
        """Test basic Aegis KV composition functionality."""
        from app.infrastructure.aegis_kv_composition import AegisKVComposition

        # Create instance
        composition = AegisKVComposition("test-bucket")
        assert composition.bucket == "test-bucket"
        assert composition._kv is None

        # Test connect
        mock_client = Mock()
        mock_js = Mock()
        mock_kv = Mock()
        mock_client.jetstream.return_value = mock_js
        mock_js.key_value = AsyncMock(return_value=mock_kv)

        with pytest.fixture_scope.patch("nats.connect", AsyncMock(return_value=mock_client)):
            await composition.connect("nats://localhost:4222")
            assert composition._kv == mock_kv

        # Test disconnect
        mock_client.close = AsyncMock()
        composition._client = mock_client
        await composition.disconnect()
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_aegis_kv_operations(self) -> None:
        """Test KV operations."""
        from app.infrastructure.aegis_kv_composition import AegisKVComposition

        composition = AegisKVComposition("test-bucket")
        mock_kv = Mock()
        composition._kv = mock_kv

        # Test put
        mock_kv.put = AsyncMock()
        await composition.put("key", b"value")
        mock_kv.put.assert_called_once_with("key", b"value")

        # Test get
        mock_entry = Mock(value=b"test-value")
        mock_kv.get = AsyncMock(return_value=mock_entry)
        result = await composition.get("key")
        assert result.value == b"test-value"

        # Test delete
        mock_kv.delete = AsyncMock()
        await composition.delete("key")
        mock_kv.delete.assert_called_once_with("key")

        # Test ls
        mock_kv.keys = AsyncMock(return_value=["key1", "key2"])
        keys = await composition.ls("prefix")
        assert keys == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_aegis_kv_not_connected(self) -> None:
        """Test operations when not connected."""
        from app.infrastructure.aegis_kv_composition import AegisKVComposition

        composition = AegisKVComposition("test-bucket")

        # All operations should raise when not connected
        with pytest.raises(RuntimeError):
            await composition.put("key", b"value")

        with pytest.raises(RuntimeError):
            await composition.get("key")

        with pytest.raises(RuntimeError):
            await composition.delete("key")

        with pytest.raises(RuntimeError):
            await composition.ls("prefix")
