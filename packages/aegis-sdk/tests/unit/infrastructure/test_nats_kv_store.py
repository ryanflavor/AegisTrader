"""Unit tests for NATS KV Store adapter."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aegis_sdk.domain.models import KVEntry, KVOptions
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.ports.metrics import MetricsPort


class TestNATSKVStore:
    """Test cases for NATS KV Store adapter."""

    @pytest.fixture
    def mock_metrics(self):
        """Create mock metrics port."""
        metrics = Mock(spec=MetricsPort)
        metrics.increment = Mock()
        metrics.gauge = Mock()
        metrics.timer = MagicMock()
        return metrics

    @pytest.fixture
    def mock_nats_client(self):
        """Create mock NATS client."""
        client = AsyncMock()
        client.is_connected = True

        # Mock JetStream
        js = AsyncMock()
        client.jetstream = Mock(return_value=js)

        # Mock KV
        kv = AsyncMock()
        js.key_value = AsyncMock(return_value=kv)

        return client, js, kv

    @pytest.fixture
    def kv_store(self, mock_metrics):
        """Create NATS KV Store instance."""
        return NATSKVStore(metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_connect_creates_kv_bucket(self, kv_store, mock_nats_client):
        """Test that connect creates or gets KV bucket."""
        client, js, kv = mock_nats_client

        with patch.object(kv_store, "_nats_adapter") as mock_adapter:
            mock_adapter._connections = [client]
            mock_adapter._js = js
            mock_adapter.is_connected = AsyncMock(return_value=True)

            await kv_store.connect("test-bucket")

            js.key_value.assert_called_once_with("test-bucket")
            assert kv_store._kv == kv
            assert kv_store._bucket_name == "test-bucket"

    @pytest.mark.asyncio
    async def test_disconnect_clears_kv_reference(self, kv_store):
        """Test that disconnect clears KV references."""
        kv_store._kv = AsyncMock()
        kv_store._bucket_name = "test-bucket"

        await kv_store.disconnect()

        assert kv_store._kv is None
        assert kv_store._bucket_name is None

    @pytest.mark.asyncio
    async def test_is_connected_checks_kv_status(self, kv_store):
        """Test is_connected checks KV availability."""
        # Not connected
        assert await kv_store.is_connected() is False

        # Connected
        kv_store._kv = AsyncMock()
        assert await kv_store.is_connected() is True

    @pytest.mark.asyncio
    async def test_get_retrieves_entry(self, kv_store, mock_metrics):
        """Test get retrieves and deserializes entry."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock KV entry
        mock_entry = Mock()
        mock_entry.key = "test-key"
        mock_entry.value = b'{"data": "test"}'
        mock_entry.revision = 42
        mock_entry.created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        mock_entry.delta = 0  # No TTL

        mock_kv.get = AsyncMock(return_value=mock_entry)

        # Test get
        with mock_metrics.timer.return_value:
            result = await kv_store.get("test-key")

        assert isinstance(result, KVEntry)
        assert result.key == "test-key"
        assert result.value == {"data": "test"}
        assert result.revision == 42
        assert result.ttl is None

        mock_kv.get.assert_called_once_with("test-key")
        mock_metrics.increment.assert_called_with("kv.get.success")

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self, kv_store, mock_metrics):
        """Test get returns None for missing key."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.get = AsyncMock(side_effect=Exception("key not found"))

        with mock_metrics.timer.return_value:
            result = await kv_store.get("missing-key")

        assert result is None
        mock_metrics.increment.assert_called_with("kv.get.miss")

    @pytest.mark.asyncio
    async def test_put_stores_value(self, kv_store, mock_metrics):
        """Test put stores and serializes value."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.put = AsyncMock(return_value=123)

        # Test put
        with mock_metrics.timer.return_value:
            revision = await kv_store.put("test-key", {"data": "test"})

        assert revision == 123
        mock_kv.put.assert_called_once()
        call_args = mock_kv.put.call_args
        assert call_args[0][0] == "test-key"
        assert call_args[0][1] == b'{"data":"test"}'
        mock_metrics.increment.assert_called_with("kv.put.success")

    @pytest.mark.asyncio
    async def test_put_with_options(self, kv_store):
        """Test put with TTL and revision check."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get for revision check
        mock_entry = Mock()
        mock_entry.revision = 123
        mock_kv.get = AsyncMock(return_value=mock_entry)
        mock_kv.put = AsyncMock(return_value=124)

        # Test TTL option (Note: NATS KV doesn't support per-key TTL)
        options = KVOptions(ttl=3600)
        await kv_store.put("test-key", "value", options)

        mock_kv.put.assert_called_once()
        call_args = mock_kv.put.call_args
        # TTL is not passed to put method in NATS KV
        assert call_args[0][0] == "test-key"  # no sanitization needed for this key
        assert call_args[0][1] == b'"value"'

    @pytest.mark.asyncio
    async def test_put_create_only(self, kv_store):
        """Test put with create_only option."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.create = AsyncMock(return_value=1)

        options = KVOptions(create_only=True)

        await kv_store.put("new-key", "value", options)

        mock_kv.create.assert_called_once_with("new-key", b'"value"')

    @pytest.mark.asyncio
    async def test_put_update_only(self, kv_store):
        """Test put with update_only option."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.update = AsyncMock(return_value=2)

        options = KVOptions(update_only=True)

        await kv_store.put("existing-key", "value", options)

        mock_kv.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_removes_key(self, kv_store, mock_metrics):
        """Test delete removes key."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.delete = AsyncMock()

        with mock_metrics.timer.return_value:
            result = await kv_store.delete("test-key")

        assert result is True
        mock_kv.delete.assert_called_once_with("test-key")
        mock_metrics.increment.assert_called_with("kv.delete.success")

    @pytest.mark.asyncio
    async def test_delete_with_revision(self, kv_store):
        """Test delete with revision check."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.delete = AsyncMock()

        await kv_store.delete("test-key", revision=42)

        mock_kv.delete.assert_called_once_with("test-key", last=42)

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_missing_key(self, kv_store, mock_metrics):
        """Test delete returns False for missing key."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.delete = AsyncMock(side_effect=Exception("key not found"))

        with mock_metrics.timer.return_value:
            result = await kv_store.delete("missing-key")

        assert result is False
        mock_metrics.increment.assert_called_with("kv.delete.miss")

    @pytest.mark.asyncio
    async def test_exists_checks_key(self, kv_store):
        """Test exists checks if key exists."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Key exists
        mock_kv.get = AsyncMock(return_value=Mock())
        assert await kv_store.exists("existing-key") is True

        # Key doesn't exist
        mock_kv.get = AsyncMock(side_effect=Exception("key not found"))
        assert await kv_store.exists("missing-key") is False

    @pytest.mark.asyncio
    async def test_keys_lists_all_keys(self, kv_store):
        """Test keys lists all keys with optional prefix."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.keys = AsyncMock(return_value=["key1", "key2", "prefix:key3"])

        # All keys
        keys = await kv_store.keys()
        assert keys == ["key1", "key2", "prefix:key3"]

        # With prefix filter (done in adapter)
        keys = await kv_store.keys("prefix:")
        mock_kv.keys.assert_called()

    @pytest.mark.asyncio
    async def test_get_many_retrieves_multiple_entries(self, kv_store):
        """Test get_many retrieves multiple entries."""

        async def mock_get(key):
            if key == "key1":
                return KVEntry(
                    key="key1",
                    value="value1",
                    revision=1,
                    created_at=datetime.now(UTC).isoformat(),
                    updated_at=datetime.now(UTC).isoformat(),
                )
            elif key == "key2":
                return KVEntry(
                    key="key2",
                    value="value2",
                    revision=2,
                    created_at=datetime.now(UTC).isoformat(),
                    updated_at=datetime.now(UTC).isoformat(),
                )
            return None

        kv_store.get = mock_get

        result = await kv_store.get_many(["key1", "key2", "missing"])

        assert len(result) == 2
        assert "key1" in result
        assert "key2" in result
        assert "missing" not in result

    @pytest.mark.asyncio
    async def test_put_many_stores_multiple_entries(self, kv_store):
        """Test put_many stores multiple entries."""
        revisions = {"key1": 1, "key2": 2}
        call_count = 0

        async def mock_put(key, value, options):
            nonlocal call_count
            call_count += 1
            return revisions.get(key, 0)

        kv_store.put = mock_put

        entries = {"key1": "value1", "key2": "value2"}
        result = await kv_store.put_many(entries)

        assert result == revisions
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_delete_many_deletes_multiple_keys(self, kv_store):
        """Test delete_many deletes multiple keys."""
        delete_results = {"key1": True, "key2": True, "missing": False}

        async def mock_delete(key, revision=None):
            return delete_results.get(key, False)

        kv_store.delete = mock_delete

        result = await kv_store.delete_many(["key1", "key2", "missing"])

        assert result == delete_results

    @pytest.mark.asyncio
    async def test_watch_key_changes(self, kv_store):
        """Test watch yields events for key changes."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock watcher
        mock_watcher = AsyncMock()
        mock_updates = [
            Mock(
                operation="PUT",
                key="test-key",
                value=b'"new-value"',
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
            Mock(
                operation="DELETE",
                key="test-key",
                value=None,
                revision=3,
                created=None,
                delta=None,
            ),
        ]

        async def mock_updates_gen():
            for update in mock_updates:
                yield update

        mock_watcher.updates = mock_updates_gen
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 2:
                break

        assert len(events) == 2
        assert events[0].operation == "PUT"
        assert events[0].entry.key == "test-key"
        assert events[0].entry.value == "new-value"
        assert events[1].operation == "DELETE"
        assert events[1].entry is None

    @pytest.mark.asyncio
    async def test_watch_validates_parameters(self, kv_store):
        """Test watch validates mutually exclusive parameters."""
        with pytest.raises(ValueError, match="Cannot specify both key and prefix"):
            async for _ in kv_store.watch(key="key", prefix="prefix"):
                pass

    @pytest.mark.asyncio
    async def test_history_retrieves_revisions(self, kv_store):
        """Test history retrieves revision history."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock history entries
        mock_entries = [
            Mock(
                key="test-key",
                value=b'"value-v2"',
                revision=2,
                created=datetime(2025, 1, 1, 0, 1, 0, tzinfo=UTC),
                delta=None,
            ),
            Mock(
                key="test-key",
                value=b'"value-v1"',
                revision=1,
                created=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
                delta=None,
            ),
        ]

        mock_kv.history = AsyncMock(return_value=mock_entries)

        history = await kv_store.history("test-key", limit=10)

        assert len(history) == 2
        assert history[0].revision == 2
        assert history[0].value == "value-v2"
        assert history[1].revision == 1
        assert history[1].value == "value-v1"

        mock_kv.history.assert_called_once_with("test-key")

    @pytest.mark.asyncio
    async def test_purge_removes_all_revisions(self, kv_store):
        """Test purge removes all revisions of a key."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        await kv_store.purge("test-key")

        mock_kv.purge.assert_called_once_with("test-key")

    @pytest.mark.asyncio
    async def test_clear_removes_keys_with_prefix(self, kv_store):
        """Test clear removes all keys with prefix."""
        kv_store.keys = AsyncMock(return_value=["prefix:key1", "prefix:key2"])
        kv_store.delete_many = AsyncMock(return_value={"prefix:key1": True, "prefix:key2": True})

        count = await kv_store.clear("prefix:")

        assert count == 2
        kv_store.keys.assert_called_once_with("prefix:")
        kv_store.delete_many.assert_called_once_with(["prefix:key1", "prefix:key2"])

    @pytest.mark.asyncio
    async def test_status_returns_bucket_info(self, kv_store):
        """Test status returns KV bucket information."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._bucket_name = "test-bucket"

        # Mock status
        mock_status = Mock()
        mock_status.bucket = "test-bucket"
        mock_status.values = 42
        mock_status.history = 10
        mock_status.bytes = 1024

        mock_kv.status = AsyncMock(return_value=mock_status)

        status = await kv_store.status()

        assert status["bucket"] == "test-bucket"
        assert status["values"] == 42
        assert status["history"] == 10
        assert status["bytes"] == 1024
        assert status["connected"] is True

    @pytest.mark.asyncio
    async def test_error_handling(self, kv_store, mock_metrics):
        """Test proper error handling and metrics."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Test put error
        mock_kv.put = AsyncMock(side_effect=Exception("put failed"))

        with pytest.raises(Exception, match="put failed"), mock_metrics.timer.return_value:
            await kv_store.put("key", "value")

        mock_metrics.increment.assert_called_with("kv.put.error")

    def test_requires_nats_adapter(self):
        """Test that NATS KV Store requires NATS adapter."""
        # Should create with default NATS adapter
        kv_store = NATSKVStore()
        assert kv_store._nats_adapter is not None

        # Should use provided NATS adapter
        mock_adapter = Mock()
        kv_store = NATSKVStore(nats_adapter=mock_adapter)
        assert kv_store._nats_adapter == mock_adapter
