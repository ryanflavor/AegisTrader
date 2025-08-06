"""Unit tests for refactored NATS KV Store implementation."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aegis_sdk.domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVNotConnectedError,
    KVStoreError,
)
from aegis_sdk.domain.models import KVEntry
from aegis_sdk.infrastructure.config import KVStoreConfig
from aegis_sdk.infrastructure.factories import KVOptionsFactory
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class TestNATSKVStoreInitialization:
    """Tests for NATS KV Store initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        store = NATSKVStore()
        assert store._nats_adapter is not None
        assert store._metrics is not None
        assert store._logger is not None
        assert store._kv is None
        assert store._bucket_name is None
        assert store._config is None
        assert store._key_mapping == {}

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = KVStoreConfig(bucket="test_bucket", sanitize_keys=False)
        store = NATSKVStore(config=config)
        assert store._config == config
        assert store._config.sanitize_keys is False

    @patch("aegis_sdk.infrastructure.nats_kv_store.NATSAdapter")
    def test_init_with_custom_adapter(self, mock_adapter_class):
        """Test initialization with custom NATS adapter."""
        mock_adapter = Mock()
        store = NATSKVStore(nats_adapter=mock_adapter)
        assert store._nats_adapter == mock_adapter
        mock_adapter_class.assert_not_called()

    @patch("aegis_sdk.infrastructure.nats_kv_store.InMemoryMetrics")
    @patch("aegis_sdk.infrastructure.nats_kv_store.SimpleLogger")
    def test_init_creates_defaults(self, mock_logger_class, mock_metrics_class):
        """Test that initialization creates default instances."""
        mock_metrics = Mock()
        mock_logger = Mock()
        mock_metrics_class.return_value = mock_metrics
        mock_logger_class.return_value = mock_logger

        store = NATSKVStore()

        mock_metrics_class.assert_called_once()
        mock_logger_class.assert_called_once_with("aegis_sdk.nats_kv_store")
        assert store._metrics == mock_metrics
        assert store._logger == mock_logger


class TestNATSKVStoreKeySanitization:
    """Tests for key sanitization functionality."""

    def test_sanitize_key_when_enabled(self):
        """Test key sanitization when enabled."""
        config = KVStoreConfig(bucket="test", sanitize_keys=True)
        store = NATSKVStore(config=config)

        # Test key that needs sanitization
        original, sanitized = store._sanitize_key("user:123:profile")
        assert original == "user:123:profile"
        assert sanitized == "user_123_profile"
        assert store._key_mapping[sanitized] == original

        # Test key that doesn't need sanitization
        original, sanitized = store._sanitize_key("simple_key")
        assert original == "simple_key"
        assert sanitized == "simple_key"

    def test_sanitize_key_when_disabled(self):
        """Test key sanitization when disabled."""
        config = KVStoreConfig(bucket="test", sanitize_keys=False)
        store = NATSKVStore(config=config)

        # Key should not be changed
        original, sanitized = store._sanitize_key("user:123:profile")
        assert original == "user:123:profile"
        assert sanitized == "user:123:profile"

    def test_sanitize_key_without_config(self):
        """Test key sanitization when config is not set."""
        store = NATSKVStore()

        # Should not sanitize without config
        original, sanitized = store._sanitize_key("user:123:profile")
        assert original == "user:123:profile"
        assert sanitized == "user:123:profile"

    def test_get_original_key(self):
        """Test reverse key lookup."""
        config = KVStoreConfig(bucket="test", sanitize_keys=True)
        store = NATSKVStore(config=config)

        # Create a mapping
        store._sanitize_key("user:123:profile")

        # Test reverse lookup
        original = store._get_original_key("user_123_profile")
        assert original == "user:123:profile"

        # Test unknown key
        original = store._get_original_key("unknown_key")
        assert original == "unknown_key"


class TestNATSKVStoreConnection:
    """Tests for connection management."""

    @pytest.fixture
    def mock_nats_adapter(self):
        """Create mock NATS adapter."""
        from unittest.mock import create_autospec

        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        # Create a mock that satisfies isinstance check
        adapter = create_autospec(NATSAdapter, instance=True)
        adapter.is_connected = AsyncMock(return_value=True)
        adapter._connections = [AsyncMock()]
        adapter._js = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_connect_creates_config(self, mock_nats_adapter):
        """Test connect creates config when not provided."""
        store = NATSKVStore(nats_adapter=mock_nats_adapter)
        mock_kv = AsyncMock()
        mock_nats_adapter._js.key_value = AsyncMock(return_value=mock_kv)

        await store.connect("test_bucket", enable_ttl=False)

        assert store._config is not None
        assert store._config.bucket == "test_bucket"
        assert store._config.enable_ttl is False
        assert store._bucket_name == "test_bucket"
        assert store._kv == mock_kv

    @pytest.mark.asyncio
    async def test_connect_updates_existing_config(self, mock_nats_adapter):
        """Test connect updates existing config."""
        config = KVStoreConfig(bucket="old_bucket", enable_ttl=True)
        store = NATSKVStore(nats_adapter=mock_nats_adapter, config=config)
        mock_kv = AsyncMock()
        mock_nats_adapter._js.key_value = AsyncMock(return_value=mock_kv)

        await store.connect("new_bucket", enable_ttl=False)

        assert store._config.bucket == "new_bucket"
        assert store._config.enable_ttl is False

    @pytest.mark.asyncio
    async def test_connect_not_connected(self):
        """Test connect fails when NATS is not connected."""
        mock_adapter = AsyncMock()
        mock_adapter.is_connected = AsyncMock(return_value=False)
        store = NATSKVStore(nats_adapter=mock_adapter)

        with pytest.raises(KVNotConnectedError):
            await store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_connect_no_jetstream(self, mock_nats_adapter):
        """Test connect fails when JetStream is not initialized."""
        mock_nats_adapter._js = None
        store = NATSKVStore(nats_adapter=mock_nats_adapter)

        with pytest.raises(KVStoreError) as exc_info:
            await store.connect("test_bucket")
        assert "JetStream not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_nats_adapter):
        """Test disconnect clears state."""
        store = NATSKVStore(nats_adapter=mock_nats_adapter)
        store._kv = AsyncMock()
        store._bucket_name = "test_bucket"
        store._config = KVStoreConfig(bucket="test_bucket")
        store._key_mapping = {"sanitized": "original"}

        await store.disconnect()

        assert store._kv is None
        assert store._bucket_name is None
        assert store._key_mapping == {}


class TestNATSKVStoreOperations:
    """Tests for KV operations."""

    @pytest.fixture
    def mock_kv_store(self):
        """Create mock KV store with all dependencies."""
        from unittest.mock import create_autospec

        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        # Create a mock that satisfies isinstance check
        mock_adapter = create_autospec(NATSAdapter, instance=True)
        mock_adapter.is_connected = AsyncMock(return_value=True)
        mock_adapter._connections = [AsyncMock()]  # Add connections for TTL
        mock_adapter._js = None  # Will be set in tests that need it

        mock_metrics = Mock()
        mock_metrics.timer = MagicMock()
        mock_metrics.increment = Mock()

        store = NATSKVStore(
            nats_adapter=mock_adapter,
            metrics=mock_metrics,
            config=KVStoreConfig(bucket="test_bucket"),
        )
        store._kv = AsyncMock()
        store._bucket_name = "test_bucket"

        return store, mock_metrics

    @pytest.mark.asyncio
    async def test_get_success(self, mock_kv_store):
        """Test successful get operation."""
        store, metrics = mock_kv_store

        # Mock KV entry
        mock_entry = Mock()
        mock_entry.value = json.dumps({"test": "data"}).encode()
        mock_entry.revision = 42
        mock_entry.created = datetime.now(UTC)
        mock_entry.delta = None

        store._kv.get = AsyncMock(return_value=mock_entry)

        result = await store.get("test_key")

        assert isinstance(result, KVEntry)
        assert result.key == "test_key"
        assert result.value == {"test": "data"}
        assert result.revision == 42
        assert result.ttl is None

        store._kv.get.assert_called_once_with("test_key")
        metrics.increment.assert_called_with("kv.get.success")

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_kv_store):
        """Test get when key not found."""
        store, metrics = mock_kv_store

        store._kv.get = AsyncMock(side_effect=Exception("not found"))

        result = await store.get("missing_key")

        assert result is None
        metrics.increment.assert_called_with("kv.get.miss")

    @pytest.mark.asyncio
    async def test_put_success(self, mock_kv_store):
        """Test successful put operation."""
        store, metrics = mock_kv_store

        store._kv.put = AsyncMock(return_value=123)

        revision = await store.put("test_key", {"data": "value"})

        assert revision == 123
        store._kv.put.assert_called_once()
        call_args = store._kv.put.call_args
        assert call_args[0][0] == "test_key"
        assert json.loads(call_args[0][1]) == {"data": "value"}
        metrics.increment.assert_called_with("kv.put.success")

    @pytest.mark.asyncio
    async def test_put_with_ttl(self, mock_kv_store):
        """Test put with TTL using factory."""
        store, metrics = mock_kv_store
        mock_adapter = store._nats_adapter
        mock_adapter._js = AsyncMock()
        mock_adapter._js.publish = AsyncMock()
        mock_adapter._js.publish.return_value = Mock(seq=456)

        options = KVOptionsFactory.create_with_ttl(300)
        revision = await store.put("test_key", {"data": "value"}, options)

        assert revision == 456
        mock_adapter._js.publish.assert_called_once()
        call_args = mock_adapter._js.publish.call_args
        assert call_args[0][0] == "$KV.test_bucket.test_key"
        assert call_args[1]["headers"]["Nats-TTL"] == "300"

    @pytest.mark.asyncio
    async def test_put_create_only(self, mock_kv_store):
        """Test put with create_only using factory."""
        store, metrics = mock_kv_store

        # Test successful create
        store._kv.create = AsyncMock(return_value=789)
        options = KVOptionsFactory.create_exclusive()
        revision = await store.put("new_key", {"data": "value"}, options)

        assert revision == 789
        store._kv.create.assert_called_once()

        # Test key already exists
        store._kv.create = AsyncMock(side_effect=Exception("wrong last sequence"))
        with pytest.raises(KVKeyAlreadyExistsError):
            await store.put("existing_key", {"data": "value"}, options)

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_kv_store):
        """Test successful delete operation."""
        store, metrics = mock_kv_store

        store._kv.delete = AsyncMock()

        result = await store.delete("test_key")

        assert result is True
        store._kv.delete.assert_called_once_with("test_key")
        metrics.increment.assert_called_with("kv.delete.success")

    @pytest.mark.asyncio
    async def test_delete_with_revision(self, mock_kv_store):
        """Test delete with revision check."""
        store, metrics = mock_kv_store

        store._kv.delete = AsyncMock()

        result = await store.delete("test_key", revision=42)

        assert result is True
        store._kv.delete.assert_called_once_with("test_key", last=42)

    @pytest.mark.asyncio
    async def test_status_connected(self, mock_kv_store):
        """Test status when connected."""
        store, _ = mock_kv_store

        mock_status = Mock()
        mock_status.bucket = "test_bucket"
        mock_status.values = 10
        mock_status.history = 100
        mock_status.bytes = 1024

        store._kv.status = AsyncMock(return_value=mock_status)

        result = await store.status()

        assert result["connected"] is True
        assert result["bucket"] == "test_bucket"
        assert result["values"] == 10
        assert result["history"] == 100
        assert result["bytes"] == 1024
        assert "config" in result
        assert result["config"]["enable_ttl"] is True
        assert result["config"]["sanitize_keys"] is True

    @pytest.mark.asyncio
    async def test_status_not_connected(self):
        """Test status when not connected."""
        store = NATSKVStore()

        result = await store.status()

        assert result["connected"] is False
        assert result["bucket"] is None
        assert result["values"] == 0
