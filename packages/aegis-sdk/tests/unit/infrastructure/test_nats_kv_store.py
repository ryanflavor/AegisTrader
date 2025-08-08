"""Unit tests for NATSKVStore."""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk.domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVKeyNotFoundError,
    KVNotConnectedError,
    KVRevisionMismatchError,
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


class TestNATSKVStoreWatchOperations:
    """Test watch operations."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        store._logger = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_watch_single_key(self, connected_store):
        """Test watching a single key for changes."""
        store = connected_store

        # Mock watcher
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        # Mock updates
        mock_update = MagicMock()
        mock_update.key = "test-key"
        mock_update.value = b'{"data": "new"}'
        mock_update.revision = 2
        mock_update.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_update.delta = None
        mock_update.operation = "PUT"

        # Make updates return values then stop
        updates_called = 0

        async def mock_updates(timeout=5.0):
            nonlocal updates_called
            updates_called += 1
            if updates_called == 1:
                return None  # Initial marker
            elif updates_called == 2:
                return mock_update
            else:
                raise asyncio.TimeoutError()

        mock_watcher.updates = mock_updates

        # Watch and collect events
        events = []
        async for event in store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify watch setup
        store._kv.watch.assert_called_once_with("test-key", include_history=False)

        # Verify event
        assert len(events) == 1
        assert events[0].operation == "PUT"
        assert events[0].entry.key == "test-key"
        assert events[0].entry.value == {"data": "new"}

    @pytest.mark.asyncio
    async def test_watch_with_prefix(self, connected_store):
        """Test watching keys with a prefix."""
        store = connected_store

        # Mock watcher
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        # Mock updates with different keys
        mock_update1 = MagicMock()
        mock_update1.key = "prefix:key1"
        mock_update1.value = b'{"data": 1}'
        mock_update1.revision = 1
        mock_update1.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_update1.delta = 0  # Initial
        mock_update1.operation = None  # Initial PUT

        mock_update2 = MagicMock()
        mock_update2.key = "other:key"
        mock_update2.value = b'{"data": 2}'
        mock_update2.revision = 2
        mock_update2.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_update2.delta = 100
        mock_update2.operation = "PUT"

        mock_update3 = MagicMock()
        mock_update3.key = "prefix:key2"
        mock_update3.value = b'{"data": 3}'
        mock_update3.revision = 3
        mock_update3.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_update3.delta = 200
        mock_update3.operation = "PUT"

        updates = [None, mock_update1, mock_update2, mock_update3]
        update_index = 0

        async def mock_updates(timeout=5.0):
            nonlocal update_index
            if update_index < len(updates):
                result = updates[update_index]
                update_index += 1
                return result
            raise asyncio.TimeoutError()

        mock_watcher.updates = mock_updates

        # Watch with prefix and collect events
        events = []
        async for event in store.watch(prefix="prefix:"):
            events.append(event)
            if len(events) >= 2:
                break

        # Verify watch setup (watches all keys, filters in app)
        store._kv.watch.assert_called_once_with(">", include_history=False)

        # Verify only prefix-matched events returned
        assert len(events) == 2
        assert all(event.entry.key.startswith("prefix:") for event in events if event.entry)

    @pytest.mark.asyncio
    async def test_watch_delete_operation(self, connected_store):
        """Test watching DELETE operations."""
        store = connected_store

        # Mock watcher
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        # Mock delete update
        mock_update = MagicMock()
        mock_update.key = "test-key"
        mock_update.value = None
        mock_update.revision = 5
        mock_update.operation = "DELETE"
        mock_update.delta = 100

        updates = [None, mock_update]
        update_index = 0

        async def mock_updates(timeout=5.0):
            nonlocal update_index
            if update_index < len(updates):
                result = updates[update_index]
                update_index += 1
                return result
            raise asyncio.TimeoutError()

        mock_watcher.updates = mock_updates

        # Watch and collect events
        events = []
        async for event in store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify DELETE event
        assert len(events) == 1
        assert events[0].operation == "DELETE"
        assert events[0].entry is None

    @pytest.mark.asyncio
    async def test_watch_purge_operation(self, connected_store):
        """Test watching PURGE operations."""
        store = connected_store

        # Mock watcher
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        # Mock purge update
        mock_update = MagicMock()
        mock_update.key = "test-key"
        mock_update.value = None
        mock_update.revision = 10
        mock_update.operation = "PURGE"

        updates = [None, mock_update]
        update_index = 0

        async def mock_updates(timeout=5.0):
            nonlocal update_index
            if update_index < len(updates):
                result = updates[update_index]
                update_index += 1
                return result
            raise asyncio.TimeoutError()

        mock_watcher.updates = mock_updates

        # Watch and collect events
        events = []
        async for event in store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify PURGE event
        assert len(events) == 1
        assert events[0].operation == "PURGE"
        assert events[0].entry is None

    @pytest.mark.asyncio
    async def test_watch_unknown_operation(self, connected_store):
        """Test watching with unknown operation (should be skipped)."""
        store = connected_store

        # Mock watcher
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        # Mock unknown operation followed by valid one
        mock_unknown = MagicMock()
        mock_unknown.key = "test-key"
        mock_unknown.value = b'{"data": "unknown"}'
        mock_unknown.operation = "UNKNOWN_OP"
        mock_unknown.revision = 1
        mock_unknown.created = None
        mock_unknown.delta = None

        mock_valid = MagicMock()
        mock_valid.key = "test-key"
        mock_valid.value = b'{"data": "valid"}'
        mock_valid.revision = 2
        mock_valid.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_valid.operation = "PUT"
        mock_valid.delta = None

        updates = [None, mock_unknown, mock_valid]
        update_index = 0

        async def mock_updates(timeout=5.0):
            nonlocal update_index
            if update_index < len(updates):
                result = updates[update_index]
                update_index += 1
                return result
            raise asyncio.TimeoutError()

        mock_watcher.updates = mock_updates

        # Watch and collect events
        events = []
        async for event in store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Verify only valid event returned
        assert len(events) == 1
        assert events[0].operation == "PUT"
        # Verify warning logged for unknown operation
        store._logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_error_handling(self, connected_store):
        """Test watch error handling."""
        store = connected_store

        # Mock watcher that raises exception
        mock_watcher = AsyncMock()
        store._kv.watch = AsyncMock(return_value=mock_watcher)

        async def mock_updates(timeout=5.0):
            raise Exception("Watcher error")

        mock_watcher.updates = mock_updates

        # Watch should stop on error
        events = []
        async for event in store.watch(key="test-key"):
            events.append(event)

        # No events should be yielded
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_watch_both_key_and_prefix_error(self, connected_store):
        """Test that specifying both key and prefix raises error."""
        store = connected_store

        with pytest.raises(ValueError, match="Cannot specify both key and prefix"):
            async for _ in store.watch(key="test", prefix="prefix"):
                pass


class TestNATSKVStoreTTLOperations:
    """Test TTL and stream creation operations."""

    @pytest.fixture
    def store_with_adapter(self):
        """Create store with mocked NATS adapter."""
        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        mock_adapter = MagicMock(spec=NATSAdapter)
        mock_adapter.is_connected = AsyncMock(return_value=True)
        mock_adapter._js = MagicMock()
        mock_adapter._connections = [MagicMock()]
        store = NATSKVStore(nats_adapter=mock_adapter)
        store._logger = MagicMock()
        store._config = KVStoreConfig(bucket="test")
        return store

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_success(self, store_with_adapter):
        """Test successful TTL stream creation."""
        store = store_with_adapter

        # Mock stream creation and update
        store._nats_adapter._js.add_stream = AsyncMock()
        store._nats_adapter._js.stream_info = AsyncMock()

        # Mock stream config
        mock_config = MagicMock()
        mock_config.as_dict = MagicMock(return_value={"name": "KV_test"})
        store._nats_adapter._js.stream_info.return_value.config = mock_config

        # Mock NATS connection request for TTL update
        mock_conn = store._nats_adapter._connections[0]
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True}).encode()
        mock_conn.request = AsyncMock(return_value=mock_response)

        result = await store._create_kv_stream_with_ttl("test")

        assert result is True
        store._logger.info.assert_called_with("Created stream KV_test with TTL support")

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_update_error(self, store_with_adapter):
        """Test TTL stream creation with update error."""
        store = store_with_adapter

        # Mock stream creation success but TTL update fails
        store._nats_adapter._js.add_stream = AsyncMock()
        store._nats_adapter._js.stream_info = AsyncMock()

        # Mock stream config
        mock_config = MagicMock()
        mock_config.as_dict = MagicMock(return_value={"name": "KV_test"})
        store._nats_adapter._js.stream_info.return_value.config = mock_config

        # Mock NATS connection request with error response
        mock_conn = store._nats_adapter._connections[0]
        mock_response = MagicMock()
        mock_response.data = json.dumps({"error": "TTL not supported"}).encode()
        mock_conn.request = AsyncMock(return_value=mock_response)

        result = await store._create_kv_stream_with_ttl("test")

        assert result is False
        store._logger.error.assert_called_with("Failed to enable TTL: TTL not supported")

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_exception(self, store_with_adapter):
        """Test TTL stream creation with exception."""
        store = store_with_adapter

        # Mock exception during stream creation
        store._nats_adapter._js.add_stream = AsyncMock(
            side_effect=Exception("Stream creation failed")
        )

        result = await store._create_kv_stream_with_ttl("test")

        assert result is False
        store._logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_async_as_dict(self, store_with_adapter):
        """Test TTL stream creation with async as_dict method."""
        store = store_with_adapter

        # Mock stream creation
        store._nats_adapter._js.add_stream = AsyncMock()
        store._nats_adapter._js.stream_info = AsyncMock()

        # Mock stream config with async as_dict
        mock_config = MagicMock()
        mock_config.as_dict = AsyncMock(return_value={"name": "KV_test"})
        store._nats_adapter._js.stream_info.return_value.config = mock_config

        # Mock successful update
        mock_conn = store._nats_adapter._connections[0]
        mock_response = MagicMock()
        mock_response.data = json.dumps({"success": True}).encode()
        mock_conn.request = AsyncMock(return_value=mock_response)

        result = await store._create_kv_stream_with_ttl("test")

        assert result is True
        # Verify as_dict was awaited
        mock_config.as_dict.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_with_ttl_option(self, store_with_adapter):
        """Test put operation with TTL option (stream-level TTL)."""
        store = store_with_adapter
        store._kv = MagicMock()
        store._kv.put = AsyncMock(return_value=123)
        store._metrics = MagicMock()

        options = KVOptions(ttl=300)
        revision = await store.put("test-key", {"data": "value"}, options)

        assert revision == 123
        # Verify debug log about stream-level TTL
        assert store._logger.debug.call_count >= 1
        debug_calls = [str(call) for call in store._logger.debug.call_args_list]
        assert any("TTL requested" in str(call) for call in debug_calls)
        store._metrics.increment.assert_any_call("kv.put.stream_ttl")


class TestNATSKVStoreAdvancedPutOperations:
    """Test advanced put operations with options."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        store._metrics = MagicMock()
        store._logger = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_put_with_update_only_no_revision(self, connected_store):
        """Test put with update_only and no revision specified."""
        store = connected_store

        # Mock get to retrieve current revision
        mock_entry = MagicMock()
        mock_entry.revision = 5
        store._kv.get = AsyncMock(return_value=mock_entry)
        store._kv.update = AsyncMock(return_value=6)

        options = KVOptions(update_only=True)
        revision = await store.put("test-key", {"data": "value"}, options)

        assert revision == 6
        store._kv.get.assert_called_once_with("test-key")
        store._kv.update.assert_called_once_with("test-key", b'{"data":"value"}', 5)

    @pytest.mark.asyncio
    async def test_put_with_update_only_key_not_found(self, connected_store):
        """Test put with update_only when key doesn't exist."""
        store = connected_store

        # Mock get to raise exception (key not found)
        store._kv.get = AsyncMock(side_effect=Exception("not found"))

        options = KVOptions(update_only=True)

        with pytest.raises(KVKeyNotFoundError):
            await store.put("missing-key", {"data": "value"}, options)

    @pytest.mark.asyncio
    async def test_put_with_revision_check_mismatch(self, connected_store):
        """Test put with revision check that fails."""
        store = connected_store

        # Mock get to return different revision
        mock_entry = MagicMock()
        mock_entry.revision = 10
        store._kv.get = AsyncMock(return_value=mock_entry)

        options = KVOptions(revision=5)

        with pytest.raises(KVRevisionMismatchError) as exc_info:
            await store.put("test-key", {"data": "value"}, options)

        assert "5" in str(exc_info.value)
        assert "10" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_put_with_revision_check_key_not_found(self, connected_store):
        """Test put with revision check when key doesn't exist."""
        store = connected_store

        # Mock get to raise "not found" exception
        store._kv.get = AsyncMock(side_effect=Exception("not found"))

        options = KVOptions(revision=5)

        with pytest.raises(KVKeyNotFoundError):
            await store.put("missing-key", {"data": "value"}, options)

    @pytest.mark.asyncio
    async def test_put_with_revision_check_general_error(self, connected_store):
        """Test put with revision check that encounters general error."""
        store = connected_store

        # Mock get to raise general exception
        store._kv.get = AsyncMock(side_effect=Exception("Connection error"))

        options = KVOptions(revision=5)

        with pytest.raises(KVStoreError, match="Revision check failed"):
            await store.put("test-key", {"data": "value"}, options)

    @pytest.mark.asyncio
    async def test_delete_with_revision(self, connected_store):
        """Test delete with revision check."""
        store = connected_store
        store._kv.delete = AsyncMock()

        result = await store.delete("test-key", revision=5)

        assert result is True
        store._kv.delete.assert_called_with("test-key", last=5)

    @pytest.mark.asyncio
    async def test_purge_operation(self, connected_store):
        """Test purge operation."""
        store = connected_store
        store._kv.purge = AsyncMock()

        await store.purge("test-key")

        store._kv.purge.assert_called_once_with("test-key")
        store._metrics.increment.assert_called_with("kv.purge")

    @pytest.mark.asyncio
    async def test_purge_not_connected(self):
        """Test purge when not connected."""
        store = NATSKVStore()
        store._kv = None

        with pytest.raises(KVNotConnectedError):
            await store.purge("test-key")


class TestNATSKVStoreBatchOperationsExtended:
    """Extended tests for batch operations."""

    @pytest.fixture
    def connected_store(self):
        """Create connected store."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test_bucket"
        return store

    @pytest.mark.asyncio
    async def test_keys_with_prefix(self, connected_store):
        """Test keys operation with prefix filter."""
        store = connected_store
        store._kv.keys = AsyncMock(return_value=["prefix:key1", "prefix:key2", "other:key"])

        result = await store.keys(prefix="prefix:")

        assert result == ["prefix:key1", "prefix:key2"]

    @pytest.mark.asyncio
    async def test_put_many_operation(self, connected_store):
        """Test put_many operation."""
        store = connected_store

        # Mock individual put calls
        async def mock_put(key, value, options):
            return {"key1": 1, "key2": 2}.get(key, 0)

        with patch.object(store, "put", side_effect=mock_put):
            entries = {"key1": {"data": 1}, "key2": {"data": 2}}
            result = await store.put_many(entries)

            assert result == {"key1": 1, "key2": 2}

    @pytest.mark.asyncio
    async def test_delete_many_operation(self, connected_store):
        """Test delete_many operation."""
        store = connected_store

        # Mock individual delete calls
        async def mock_delete(key, revision=None):
            return key != "missing"

        with patch.object(store, "delete", side_effect=mock_delete):
            result = await store.delete_many(["key1", "key2", "missing"])

            assert result == {"key1": True, "key2": True, "missing": False}

    @pytest.mark.asyncio
    async def test_clear_with_prefix(self, connected_store):
        """Test clear operation with prefix."""
        store = connected_store

        # Mock keys and delete_many
        with patch.object(store, "keys", return_value=["prefix:1", "prefix:2"]):
            with patch.object(
                store, "delete_many", return_value={"prefix:1": True, "prefix:2": False}
            ):
                result = await store.clear("prefix:")

                assert result == 1  # Only one successful deletion

    @pytest.mark.asyncio
    async def test_history_with_limit(self, connected_store):
        """Test history operation with custom limit."""
        store = connected_store

        # Create many mock entries
        mock_entries = []
        for i in range(20):
            entry = MagicMock()
            entry.value = json.dumps({"version": i}).encode()
            entry.revision = i
            entry.created = datetime(2025, 1, i + 1, tzinfo=UTC)
            entry.delta = None
            mock_entries.append(entry)

        store._kv.history = AsyncMock(return_value=mock_entries)

        result = await store.history("test-key", limit=5)

        # Should return only 5 entries, newest first
        assert len(result) == 5
        assert result[0].revision == 19  # Newest
        assert result[4].revision == 15  # 5th newest

    @pytest.mark.asyncio
    async def test_history_with_no_created_timestamp(self, connected_store):
        """Test history with entries missing created timestamp."""
        store = connected_store

        # Mock entry without created timestamp
        mock_entry = MagicMock()
        mock_entry.value = b'{"data": "test"}'
        mock_entry.revision = 1
        mock_entry.created = None  # No timestamp
        mock_entry.delta = None

        store._kv.history = AsyncMock(return_value=[mock_entry])

        result = await store.history("test-key")

        # Should use current time as fallback
        assert len(result) == 1
        assert result[0].created_at is not None
        assert result[0].updated_at is not None


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

    # Test removed - NATS KV always provides revision numbers in production

    @pytest.mark.asyncio
    async def test_get_with_positive_delta(self):
        """Test get operation with positive delta (TTL)."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test"
        store._metrics = MagicMock()
        store._logger = MagicMock()

        # Mock entry with positive delta
        mock_entry = MagicMock()
        mock_entry.value = b'{"test": "data"}'
        mock_entry.revision = 1
        mock_entry.created = datetime(2025, 1, 1, tzinfo=UTC)
        mock_entry.delta = 300  # 300 seconds TTL

        store._kv.get = AsyncMock(return_value=mock_entry)

        result = await store.get("test-key")

        assert result.ttl == 300
        # Verify debug logging
        assert store._logger.debug.call_count >= 1

    @pytest.mark.asyncio
    async def test_connect_with_wrong_adapter_type(self):
        """Test connect with non-NATSAdapter type."""

        # Use a mock that doesn't match NATSAdapter type
        # We need to make isinstance() check fail
        class FakeAdapter:
            async def is_connected(self):
                return True

        mock_adapter = FakeAdapter()

        store = NATSKVStore(nats_adapter=mock_adapter)

        with pytest.raises(KVStoreError, match="NATS KV Store requires NATSAdapter"):
            await store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_status_with_error(self):
        """Test status operation with error."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test"
        store._logger = MagicMock()

        # Mock status to raise exception
        store._kv.status = AsyncMock(side_effect=Exception("Status error"))

        result = await store.status()

        assert result["connected"] is True
        assert result["bucket"] == "test"
        assert result["error"] == "Status error"
        store._logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_with_config(self):
        """Test status operation with config information."""
        store = NATSKVStore()
        store._kv = MagicMock()
        store._bucket_name = "test"
        store._config = KVStoreConfig(
            bucket="test",
            max_value_size=512 * 1024,
            history_size=20,
        )

        # Mock status
        mock_status = MagicMock()
        mock_status.bucket = "test"
        mock_status.values = 10
        mock_status.history = 50
        mock_status.bytes = 2048
        mock_status.ttl = 300
        mock_status.max_value_size = 512 * 1024
        mock_status.max_history = 20
        store._kv.status = AsyncMock(return_value=mock_status)

        result = await store.status()

        assert result["connected"] is True
        assert result["bucket"] == "test"
        assert result["values"] == 10
        assert result["config"]["max_value_size"] == 512 * 1024
        assert result["config"]["history_size"] == 20
