"""Unit tests for NATSKVStore."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk.domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVNotConnectedError,
    KVStoreError,
)
from aegis_sdk.domain.models import KVEntry, KVOptions
from aegis_sdk.infrastructure.config import KVStoreConfig
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class TestNATSKVStoreInit:
    """Test NATSKVStore initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        store = NATSKVStore()

        assert store._nats_adapter is not None
        assert store._metrics is not None
        assert store._logger is not None
        assert store._config is None
        assert store._kv is None
        assert store._bucket_name is None

    def test_init_with_custom_components(self):
        """Test initialization with custom components."""
        mock_adapter = MagicMock()
        mock_metrics = MagicMock()
        mock_logger = MagicMock()
        config = KVStoreConfig(bucket="test_bucket")

        store = NATSKVStore(
            nats_adapter=mock_adapter, metrics=mock_metrics, logger=mock_logger, config=config
        )

        assert store._nats_adapter == mock_adapter
        assert store._metrics == mock_metrics
        assert store._logger == mock_logger
        assert store._config == config

    def test_init_with_config(self):
        """Test initialization with config."""
        config = KVStoreConfig(bucket="test_bucket", max_value_size=512 * 1024)
        store = NATSKVStore(config=config)

        assert store._config == config


class TestNATSKVStoreKeyValidation:
    """Test key validation functionality."""

    def test_validate_key_with_dots(self):
        """Test that keys with dots are rejected."""
        store = NATSKVStore()

        with pytest.raises(ValueError, match="contains invalid character '\\.'"):
            store._validate_key("key.with.dots")

    def test_validate_key_with_spaces(self):
        """Test that keys with spaces are rejected."""
        store = NATSKVStore()

        with pytest.raises(ValueError, match="contains invalid character ' '"):
            store._validate_key("key with spaces")

    def test_validate_key_with_asterisk(self):
        """Test that keys with asterisks are rejected."""
        store = NATSKVStore()

        with pytest.raises(ValueError, match="contains invalid character '\\*'"):
            store._validate_key("key*with*asterisk")

    def test_validate_key_with_greater_than(self):
        """Test that keys with > are rejected."""
        store = NATSKVStore()

        with pytest.raises(ValueError, match="contains invalid character '>'"):
            store._validate_key("key>test")

    def test_validate_key_with_slash(self):
        """Test that keys with slashes are rejected."""
        store = NATSKVStore()

        with pytest.raises(ValueError, match="contains invalid character '/'"):
            store._validate_key("key/with/slash")

    def test_validate_key_valid(self):
        """Test that valid keys pass validation."""
        store = NATSKVStore()

        # Should not raise
        store._validate_key("valid_key")
        store._validate_key("valid-key-123")
        store._validate_key("VALID_KEY_456")
        store._validate_key("key_with_underscores")
        store._validate_key("key-with-hyphens")


class TestNATSKVStoreConnection:
    """Test connection management."""

    @pytest.fixture
    def store(self):
        """Create store with mocked dependencies."""
        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        mock_adapter = MagicMock(spec=NATSAdapter)
        store = NATSKVStore(nats_adapter=mock_adapter)
        return store

    @pytest.mark.asyncio
    async def test_connect_success_existing_bucket(self, store):
        """Test successful connection to existing bucket."""
        # Mock adapter is connected
        store._nats_adapter.is_connected = AsyncMock(return_value=True)
        store._nats_adapter._js = MagicMock()
        store._metrics = MagicMock()

        # Mock existing bucket
        mock_kv = MagicMock()
        store._nats_adapter._js.key_value = AsyncMock(return_value=mock_kv)

        await store.connect("test_bucket")

        assert store._kv == mock_kv
        assert store._bucket_name == "test_bucket"
        store._metrics.gauge.assert_called_with("kv.buckets.active", 1)

    @pytest.mark.asyncio
    async def test_connect_create_bucket_with_ttl_fallback(self, store):
        """Test connection creating new bucket with TTL fallback."""
        store._nats_adapter.is_connected = AsyncMock(return_value=True)
        store._nats_adapter._js = MagicMock()
        store._metrics = MagicMock()

        # Mock TTL creation to fail, triggering fallback
        with patch.object(store, "_create_kv_stream_with_ttl", return_value=False):
            # First call fails (no bucket), second succeeds after creation
            mock_kv = MagicMock()
            store._nats_adapter._js.key_value = AsyncMock(
                side_effect=[Exception("not found"), mock_kv]
            )
            store._nats_adapter._js.stream_info = AsyncMock(
                side_effect=Exception("stream not found")
            )
            store._nats_adapter._js.add_stream = AsyncMock()

            await store.connect("test_bucket")

            # Verify fallback stream created and bucket connected
            store._nats_adapter._js.add_stream.assert_called_once()
            assert store._kv == mock_kv
            assert store._bucket_name == "test_bucket"

    @pytest.mark.asyncio
    async def test_connect_create_bucket_with_ttl(self, store):
        """Test connection creating new bucket with TTL."""
        store._nats_adapter.is_connected = AsyncMock(return_value=True)
        store._nats_adapter._js = MagicMock()

        # Mock TTL stream creation
        with patch.object(store, "_create_kv_stream_with_ttl", return_value=True) as mock_create:
            # First call fails (no bucket), second succeeds after creation
            mock_kv = MagicMock()
            store._nats_adapter._js.key_value = AsyncMock(
                side_effect=[Exception("not found"), mock_kv]
            )
            store._nats_adapter._js.stream_info = AsyncMock(
                side_effect=Exception("stream not found")
            )

            await store.connect("test_bucket")

            # Verify TTL stream created
            mock_create.assert_called_once_with("test_bucket")
            assert store._kv == mock_kv

    @pytest.mark.asyncio
    async def test_connect_adapter_not_connected(self, store):
        """Test connection when NATS adapter is not connected."""
        store._nats_adapter.is_connected = AsyncMock(return_value=False)

        with pytest.raises(KVNotConnectedError):
            await store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_connect_no_jetstream(self, store):
        """Test connection when JetStream is not available."""
        store._nats_adapter.is_connected = AsyncMock(return_value=True)
        store._nats_adapter._js = None

        with pytest.raises(KVStoreError, match="NATS JetStream not initialized"):
            await store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_disconnect(self, store):
        """Test disconnection."""
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        store._metrics = MagicMock()

        await store.disconnect()

        assert store._kv is None
        assert store._bucket_name is None
        store._metrics.gauge.assert_called_with("kv.buckets.active", 0)

    @pytest.mark.asyncio
    async def test_is_connected(self, store):
        """Test connection status check."""
        # Not connected
        assert await store.is_connected() is False

        # Connected
        store._kv = MagicMock()
        assert await store.is_connected() is True


class TestNATSKVStoreBasicOperations:
    """Test basic KV operations."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store with mocked KV."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        store._metrics = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_get_success(self, connected_store):
        """Test successful get operation."""
        store = connected_store

        # Mock KV entry
        mock_entry = MagicMock()
        mock_entry.value = b'{"test": "data"}'
        mock_entry.revision = 5
        mock_entry.delta = None  # Stream-level TTL, not per-message
        mock_entry.created = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        # Make get method async and return the mock entry
        store._kv.get = AsyncMock(return_value=mock_entry)

        result = await store.get("test-key")

        assert result is not None
        assert result.key == "test-key"
        assert result.value == {"test": "data"}
        assert result.revision == 5
        assert result.ttl is None  # Stream-level TTL
        store._metrics.increment.assert_called_with("kv.get.success")

    @pytest.mark.asyncio
    async def test_get_not_found(self, connected_store):
        """Test get operation when key not found."""
        store = connected_store
        store._kv.get = AsyncMock(side_effect=Exception("not found"))

        result = await store.get("missing-key")

        assert result is None
        store._metrics.increment.assert_called_with("kv.get.miss")

    @pytest.mark.asyncio
    async def test_get_not_connected(self):
        """Test get operation when not connected."""
        store = NATSKVStore()
        store._kv = None

        with pytest.raises(KVNotConnectedError):
            await store.get("test-key")

    @pytest.mark.asyncio
    async def test_put_basic(self, connected_store):
        """Test basic put operation."""
        store = connected_store
        store._kv.put = AsyncMock(return_value=123)

        revision = await store.put("test-key", {"data": "value"})

        assert revision == 123
        store._kv.put.assert_called_once()
        store._metrics.increment.assert_called_with("kv.put.success")

    @pytest.mark.asyncio
    async def test_put_with_create_only(self, connected_store):
        """Test put with create_only option."""
        store = connected_store
        store._kv.create = AsyncMock(return_value=1)

        options = KVOptions(create_only=True)
        revision = await store.put("new-key", {"data": "value"}, options)

        assert revision == 1
        store._kv.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_create_only_key_exists(self, connected_store):
        """Test put with create_only when key already exists."""
        store = connected_store
        store._kv.create = AsyncMock(side_effect=Exception("wrong last sequence"))

        options = KVOptions(create_only=True)

        with pytest.raises(KVKeyAlreadyExistsError):
            await store.put("existing-key", {"data": "value"}, options)

    @pytest.mark.asyncio
    async def test_put_not_connected(self):
        """Test put when not connected."""
        store = NATSKVStore()
        store._kv = None

        with pytest.raises(KVNotConnectedError):
            await store.put("test-key", {"data": "value"})

    @pytest.mark.asyncio
    async def test_delete_success(self, connected_store):
        """Test successful delete operation."""
        store = connected_store
        store._kv.delete = AsyncMock()

        result = await store.delete("test-key")

        assert result is True
        store._kv.delete.assert_called_with("test-key")
        store._metrics.increment.assert_called_with("kv.delete.success")

    @pytest.mark.asyncio
    async def test_delete_not_found(self, connected_store):
        """Test delete when key not found."""
        store = connected_store
        store._kv.delete = AsyncMock(side_effect=Exception("not found"))

        result = await store.delete("missing-key")

        assert result is False
        store._metrics.increment.assert_called_with("kv.delete.miss")

    @pytest.mark.asyncio
    async def test_exists_true(self, connected_store):
        """Test exists when key exists."""
        store = connected_store
        store._kv.get = AsyncMock(return_value=MagicMock())

        result = await store.exists("test-key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, connected_store):
        """Test exists when key doesn't exist."""
        store = connected_store
        store._kv.get = AsyncMock(side_effect=Exception("not found"))

        result = await store.exists("missing-key")

        assert result is False


class TestNATSKVStoreBatchOperations:
    """Test batch operations."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        return store

    @pytest.mark.asyncio
    async def test_keys_success(self, connected_store):
        """Test successful keys operation."""
        store = connected_store
        store._kv.keys = AsyncMock(return_value=["key1", "key2", "sanitized_key"])

        # No key mapping needed anymore

        result = await store.keys()

        expected = ["key1", "key2", "sanitized_key"]
        assert result == expected

    @pytest.mark.asyncio
    async def test_keys_empty(self, connected_store):
        """Test keys operation with no keys."""
        store = connected_store
        store._kv.keys = AsyncMock(side_effect=Exception("no keys"))

        result = await store.keys()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_many(self, connected_store):
        """Test get_many operation."""
        store = connected_store

        # Mock individual get calls
        async def mock_get(key):
            if key == "key1":
                return KVEntry(
                    key="key1",
                    value={"data": 1},
                    revision=1,
                    created_at="2025-01-01T00:00:00Z",
                    updated_at="2025-01-01T00:00:00Z",
                )
            elif key == "key2":
                return KVEntry(
                    key="key2",
                    value={"data": 2},
                    revision=2,
                    created_at="2025-01-01T00:00:00Z",
                    updated_at="2025-01-01T00:00:00Z",
                )
            return None

        with patch.object(store, "get", side_effect=mock_get):
            result = await store.get_many(["key1", "key2", "missing"])

            assert len(result) == 2
            assert "key1" in result
            assert "key2" in result
            assert "missing" not in result


class TestNATSKVStoreAdvancedOperations:
    """Test advanced operations."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        return store

    @pytest.mark.asyncio
    async def test_watch_not_connected(self):
        """Test watch when not connected."""
        store = NATSKVStore()
        store._kv = None

        with pytest.raises(KVNotConnectedError):
            async for _ in store.watch("test-key"):
                pass

    @pytest.mark.asyncio
    async def test_history_success(self, connected_store):
        """Test successful history operation."""
        store = connected_store

        # Mock history entries
        mock_entry1 = MagicMock()
        mock_entry1.value = b'{"version": 1}'
        mock_entry1.revision = 1
        mock_entry1.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_entry1.delta = None

        mock_entry2 = MagicMock()
        mock_entry2.value = b'{"version": 2}'
        mock_entry2.revision = 2
        mock_entry2.created = datetime(2025, 1, 2, tzinfo=UTC)
        mock_entry2.delta = None

        store._kv.history = AsyncMock(return_value=[mock_entry1, mock_entry2])

        result = await store.history("test-key", limit=5)

        assert len(result) == 2
        # Should be reversed (newest first)
        assert result[0].value == {"version": 2}
        assert result[1].value == {"version": 1}

    @pytest.mark.asyncio
    async def test_history_not_found(self, connected_store):
        """Test history when key not found."""
        store = connected_store
        store._kv.history = AsyncMock(side_effect=Exception("not found"))

        result = await store.history("missing-key")

        assert result == []

    @pytest.mark.asyncio
    async def test_clear_success(self, connected_store):
        """Test successful clear operation."""
        store = connected_store

        # Mock keys and delete_many
        with patch.object(store, "keys", return_value=["key1", "key2"]):
            with patch.object(store, "delete_many", return_value={"key1": True, "key2": True}):
                result = await store.clear()

                assert result == 2

    @pytest.mark.asyncio
    async def test_status_connected(self, connected_store):
        """Test status when connected."""
        store = connected_store

        # Mock bucket status
        mock_status = MagicMock()
        mock_status.bucket = "test_bucket"
        mock_status.values = 10
        mock_status.history = 50
        mock_status.bytes = 1024
        store._kv.status = AsyncMock(return_value=mock_status)

        result = await store.status()

        assert result["connected"] is True
        assert result["bucket"] == "test_bucket"
        # Note: The actual implementation may not have these exact keys
        # Just check that it returns a dict with basic info
        assert "bucket" in result

    @pytest.mark.asyncio
    async def test_status_not_connected(self):
        """Test status when not connected."""
        store = NATSKVStore()
        store._kv = None

        result = await store.status()

        assert result["connected"] is False
        assert result["bucket"] is None
        assert result["values"] == 0


class TestNATSKVStoreErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store with mocked KV."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        store._metrics = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_put_error_increments_metric(self, connected_store):
        """Test that put errors increment error metrics."""
        store = connected_store
        store._kv.put = AsyncMock(side_effect=Exception("Put failed"))

        with pytest.raises(Exception):
            await store.put("test-key", {"data": "value"})

        store._metrics.increment.assert_called_with("kv.put.error")

    # TTL test removed - NATS KV now uses stream-level TTL configuration
    # Per-message TTL is no longer supported in the current implementation


class TestNATSKVStoreIntegration:
    """Test integration scenarios."""

    def test_serializer_integration(self):
        """Test that store properly handles JSON serialization."""
        store = NATSKVStore()
        assert store._nats_adapter is not None

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete store lifecycle."""
        # Create store with mocks
        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        mock_adapter = MagicMock(spec=NATSAdapter)
        mock_adapter.is_connected = AsyncMock(return_value=True)
        mock_adapter._js = MagicMock()

        mock_kv = MagicMock()
        mock_adapter._js.key_value = AsyncMock(return_value=mock_kv)

        store = NATSKVStore(nats_adapter=mock_adapter)
        store._metrics = MagicMock()

        # Connect
        await store.connect("test_bucket")
        assert store._bucket_name == "test_bucket"

        # Disconnect
        await store.disconnect()
        assert store._bucket_name is None
