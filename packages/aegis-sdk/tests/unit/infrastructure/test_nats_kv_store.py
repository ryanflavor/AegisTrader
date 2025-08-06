"""Unit tests for NATS KV Store adapter - concise and comprehensive."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aegis_sdk.domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVKeyNotFoundError,
    KVNotConnectedError,
    KVRevisionMismatchError,
    KVStoreError,
    KVTTLNotSupportedError,
)
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
        js.create_key_value = AsyncMock(return_value=kv)

        return client, js, kv

    @pytest.fixture
    def kv_store(self, mock_metrics):
        """Create NATS KV Store instance."""
        from unittest.mock import create_autospec

        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

        # Create a mock NATS adapter that satisfies isinstance check
        mock_adapter = create_autospec(NATSAdapter, instance=True)
        mock_adapter.is_connected = AsyncMock(return_value=True)
        mock_adapter._js = None  # Will be set in tests
        mock_adapter._connections = []  # Will be set in tests
        return NATSKVStore(nats_adapter=mock_adapter, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_connect_creates_kv_bucket(self, kv_store, mock_nats_client):
        """Test that connect creates or gets KV bucket."""
        client, js, kv = mock_nats_client

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        await kv_store.connect("test_bucket")

        js.key_value.assert_called_once_with("test_bucket")
        assert kv_store._kv == kv
        assert kv_store._bucket_name == "test_bucket"

    @pytest.mark.asyncio
    async def test_connect_with_enable_ttl(self, kv_store, mock_nats_client):
        """Test connect with enable_ttl creates bucket with TTL support."""
        client, js, kv = mock_nats_client

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        await kv_store.connect("ttl_bucket", enable_ttl=True)

        # Should try key_value first
        assert js.key_value.call_count >= 1
        assert kv_store._bucket_name == "ttl_bucket"

    @pytest.mark.asyncio
    async def test_connect_not_connected(self, kv_store):
        """Test connect fails when not connected to NATS."""
        # Configure the mock adapter that was injected
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=False)

        with pytest.raises(KVNotConnectedError):
            await kv_store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_disconnect_clears_kv_reference(self, kv_store):
        """Test that disconnect clears KV references."""
        kv_store._kv = AsyncMock()
        kv_store._bucket_name = "test_bucket"

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
        kv_store._bucket_name = "test_bucket"

        # Mock get for revision check
        mock_entry = Mock()
        mock_entry.revision = 123
        mock_kv.get = AsyncMock(return_value=mock_entry)
        mock_kv.put = AsyncMock(return_value=124)

        # Mock the NATS adapter and JetStream
        mock_js = AsyncMock()
        mock_pa = Mock()
        mock_pa.seq = 125
        mock_js.publish = AsyncMock(return_value=mock_pa)
        kv_store._nats_adapter._js = mock_js

        # Test TTL option with per-message TTL
        options = KVOptions(ttl=3600)
        revision = await kv_store.put("test-key", "value", options)

        # Should use JetStream publish with TTL header
        mock_js.publish.assert_called_once()
        call_args = mock_js.publish.call_args
        assert call_args[0][0] == "$KV.test_bucket.test-key"
        assert call_args[0][1] == b'"value"'
        assert call_args[1]["headers"]["Nats-TTL"] == "3600"
        assert revision == 125

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
        kv_store._key_mapping = {}  # Initialize key mapping

        # Mock watcher with updates method
        mock_watcher = AsyncMock()

        # Mock updates sequence
        updates_sequence = [
            None,  # Initial marker
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

        # Configure updates method to return values in sequence
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)

        # Configure watch to return the watcher
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

        # Verify watch was called correctly
        mock_kv.watch.assert_called_once_with("test-key", include_history=False)

    @pytest.mark.asyncio
    async def test_watch_prefix(self, kv_store):
        """Test watch with prefix filter."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}  # Initialize key mapping

        # Mock watcher with updates method
        mock_watcher = AsyncMock()

        # Mock updates including keys with and without prefix
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="PUT",
                key="prefix:key1",
                value=b'"value1"',
                revision=1,
                created=datetime.now(UTC),
                delta=None,
            ),
            Mock(
                operation="PUT",
                key="other:key",
                value=b'"ignored"',
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]

        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(prefix="prefix:"):
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) == 1
        assert events[0].entry.key == "prefix:key1"
        # For prefix watching, NATS watches all keys (">") and filters in app
        mock_kv.watch.assert_called_once_with(">", include_history=False)

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

        # Mock history entries (oldest first, as returned by NATS)
        mock_entries = [
            Mock(
                key="test-key",
                value=b'"value-v1"',
                revision=1,
                created=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
                delta=None,
            ),
            Mock(
                key="test-key",
                value=b'"value-v2"',
                revision=2,
                created=datetime(2025, 1, 1, 0, 1, 0, tzinfo=UTC),
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
        kv_store._bucket_name = "test_bucket"

        # Mock status
        mock_status = Mock()
        mock_status.bucket = "test_bucket"
        mock_status.values = 42
        mock_status.history = 10
        mock_status.bytes = 1024

        mock_kv.status = AsyncMock(return_value=mock_status)

        status = await kv_store.status()

        assert status["bucket"] == "test_bucket"
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

    def test_sanitize_key(self):
        """Test key sanitization for NATS compatibility."""
        from aegis_sdk.infrastructure.config import KVStoreConfig

        config = KVStoreConfig(bucket="test", sanitize_keys=True)
        kv_store = NATSKVStore(config=config)

        # Test various invalid characters
        original, sanitized = kv_store._sanitize_key("key with spaces")
        assert sanitized == "key_with_spaces"
        assert original == "key with spaces"

        original, sanitized = kv_store._sanitize_key("key.with.dots")
        assert sanitized == "key_with_dots"

        original, sanitized = kv_store._sanitize_key("key*with*stars")
        assert sanitized == "key_with_stars"

        original, sanitized = kv_store._sanitize_key("key>with>gt")
        assert sanitized == "key_with_gt"

        original, sanitized = kv_store._sanitize_key("key/with/slash")
        assert sanitized == "key_with_slash"

        original, sanitized = kv_store._sanitize_key("key\\with\\backslash")
        assert sanitized == "key_with_backslash"

        original, sanitized = kv_store._sanitize_key("key:with:colon")
        assert sanitized == "key_with_colon"

        # Test key mapping is stored
        assert kv_store._key_mapping["key_with_spaces"] == "key with spaces"

        # Test with sanitization disabled
        config_no_sanitize = KVStoreConfig(bucket="test", sanitize_keys=False)
        kv_store_no_sanitize = NATSKVStore(config=config_no_sanitize)
        original, sanitized = kv_store_no_sanitize._sanitize_key("key with spaces")
        assert sanitized == "key with spaces"
        assert original == "key with spaces"

    @pytest.mark.asyncio
    async def test_put_with_ttl_and_revision(self, kv_store):
        """Test put with both TTL and revision check."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._bucket_name = "test_bucket"

        # Mock get for revision check
        mock_entry = Mock()
        mock_entry.revision = 123
        mock_kv.get = AsyncMock(return_value=mock_entry)

        # Mock JetStream publish
        mock_js = AsyncMock()
        mock_pa = Mock()
        mock_pa.seq = 125
        mock_js.publish = AsyncMock(return_value=mock_pa)
        kv_store._nats_adapter._js = mock_js

        # Test with both TTL and revision
        options = KVOptions(ttl=3600, revision=123)
        revision = await kv_store.put("test-key", "value", options)

        # Verify revision check was performed
        mock_kv.get.assert_called_once_with("test-key")

        # Verify publish was called with TTL header
        mock_js.publish.assert_called_once()
        call_args = mock_js.publish.call_args
        assert call_args[1]["headers"]["Nats-TTL"] == "3600"
        # Note: revision check is done separately, not in the publish call
        assert revision == 125

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl(self, kv_store, mock_nats_client):
        """Test creating KV stream with TTL enabled."""
        client, js, kv = mock_nats_client

        # Mock stream info response
        mock_stream_info = Mock()
        mock_config = Mock()
        mock_config.as_dict = Mock(
            return_value={
                "name": "KV_test-bucket",
                "subjects": ["$KV.test-bucket.>"],
                "max_msgs_per_subject": 1,
                "allow_msg_ttl": False,  # Will be set to True
            }
        )
        mock_stream_info.config = mock_config
        js.stream_info = AsyncMock(return_value=mock_stream_info)

        # Mock stream API response
        mock_response = Mock()
        mock_response.data = b'{"stream_info": {"created": true}}'  # Valid JSON response

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        # Mock the request method
        client.request = AsyncMock(return_value=mock_response)

        result = await kv_store._create_kv_stream_with_ttl("test-bucket")
        assert result is True

        # Verify stream update request (updates existing stream with TTL)
        client.request.assert_called_once()
        call_args = client.request.call_args
        assert call_args[0][0] == "$JS.API.STREAM.UPDATE.KV_test-bucket"

        # Verify stream config has allow_msg_ttl
        import json

        config = json.loads(call_args[0][1])
        assert config["allow_msg_ttl"] is True

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_error(self, kv_store, mock_nats_client):
        """Test creating KV stream with TTL error handling."""
        client, js, kv = mock_nats_client

        # Mock error response
        mock_response = Mock()
        mock_response.data = b'{"error": {"code": 400, "description": "Stream already exists"}}'

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        client.request = AsyncMock(return_value=mock_response)

        result = await kv_store._create_kv_stream_with_ttl("test-bucket")
        assert result is False

    @pytest.mark.asyncio
    async def test_put_with_ttl_not_supported(self, kv_store):
        """Test put with TTL when server doesn't support it."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._bucket_name = "test_bucket"

        # Mock JetStream publish that fails with TTL error
        mock_js = AsyncMock()
        mock_js.publish = AsyncMock(side_effect=Exception("per-message TTL is disabled"))
        kv_store._nats_adapter._js = mock_js

        # Test TTL option
        options = KVOptions(ttl=3600)

        with pytest.raises(KVTTLNotSupportedError):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_connect_js_not_initialized(self, kv_store, mock_nats_client):
        """Test connect fails when JetStream not initialized."""
        client, js, kv = mock_nats_client

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = None  # No JetStream
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        with pytest.raises(KVStoreError, match="NATS JetStream not initialized"):
            await kv_store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_connect_create_bucket_no_ttl(self, kv_store, mock_nats_client):
        """Test connect creates bucket without TTL support."""
        client, js, kv = mock_nats_client

        # First call to key_value fails (bucket doesn't exist)
        js.key_value.side_effect = [Exception("bucket not found"), kv]
        # Stream doesn't exist
        js.stream_info = AsyncMock(side_effect=Exception("stream not found"))
        # Add stream succeeds
        js.add_stream = AsyncMock()

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        await kv_store.connect("test_bucket", enable_ttl=False)

        # Should have tried to add stream
        js.add_stream.assert_called_once()
        assert kv_store._bucket_name == "test_bucket"

    @pytest.mark.asyncio
    async def test_connect_stream_exists(self, kv_store, mock_nats_client):
        """Test connect when stream already exists."""
        client, js, kv = mock_nats_client

        # First call to key_value fails (bucket interface issue)
        # Second call succeeds
        js.key_value.side_effect = [Exception("some error"), kv]
        # Stream already exists
        js.stream_info = AsyncMock()  # No exception means it exists

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        await kv_store.connect("test_bucket")

        # Should get KV bucket after checking stream exists
        assert js.key_value.call_count == 2
        assert kv_store._bucket_name == "test_bucket"

    @pytest.mark.asyncio
    async def test_get_no_created_timestamp(self, kv_store, mock_metrics):
        """Test get handles missing created timestamp."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock KV entry without created timestamp
        mock_entry = Mock()
        mock_entry.key = "test-key"
        mock_entry.value = b'{"data": "test"}'
        mock_entry.revision = 42
        mock_entry.created = None  # No timestamp
        mock_entry.delta = 0

        mock_kv.get = AsyncMock(return_value=mock_entry)

        # Test get
        with mock_metrics.timer.return_value:
            result = await kv_store.get("test-key")

        assert isinstance(result, KVEntry)
        assert result.key == "test-key"
        assert result.value == {"data": "test"}
        # Should have current timestamp
        assert result.created_at is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_with_ttl(self, kv_store, mock_metrics):
        """Test get retrieves entry with TTL."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock KV entry with TTL
        mock_entry = Mock()
        mock_entry.key = "test-key"
        mock_entry.value = b'{"data": "test"}'
        mock_entry.revision = 42
        mock_entry.created = datetime.now(UTC)
        mock_entry.delta = 3600  # 1 hour TTL

        mock_kv.get = AsyncMock(return_value=mock_entry)

        # Test get
        with mock_metrics.timer.return_value:
            result = await kv_store.get("test-key")

        assert isinstance(result, KVEntry)
        assert result.ttl == 3600

    @pytest.mark.asyncio
    async def test_put_revision_mismatch(self, kv_store):
        """Test put with revision mismatch."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get returns different revision successfully (no exception)
        mock_entry = Mock()
        mock_entry.revision = 456  # Different from expected
        mock_kv.get = AsyncMock(return_value=mock_entry)

        options = KVOptions(revision=123)  # Expected revision

        # Should raise KVRevisionMismatchError
        with pytest.raises(KVRevisionMismatchError) as exc_info:
            await kv_store.put("test-key", "value", options)

        assert exc_info.value.expected_revision == 123
        assert exc_info.value.actual_revision == 456

    @pytest.mark.asyncio
    async def test_put_revision_check_key_not_found(self, kv_store):
        """Test put with revision check when key doesn't exist."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get throws exception (key not found)
        mock_kv.get = AsyncMock(side_effect=Exception("key not found"))

        options = KVOptions(revision=123)

        with pytest.raises(KVKeyNotFoundError) as exc_info:
            await kv_store.put("test-key", "value", options)

        assert exc_info.value.key == "test-key"

    @pytest.mark.asyncio
    async def test_watch_no_kv_store(self, kv_store):
        """Test watch fails when not connected."""
        kv_store._kv = None

        with pytest.raises(KVNotConnectedError):
            async for _ in kv_store.watch(key="test-key"):
                pass

    @pytest.mark.asyncio
    async def test_watch_timeout(self, kv_store):
        """Test watch handles timeout gracefully."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher that times out
        mock_watcher = AsyncMock()
        mock_watcher.updates = AsyncMock(side_effect=[None, asyncio.TimeoutError()])
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            # Should exit after timeout
            break

        # No events due to timeout
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_watch_unknown_operation(self, kv_store):
        """Test watch handles unknown operations."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher with unknown operation
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="UNKNOWN_OP",
                key="test-key",
                value=b'"value"',
                revision=1,
                created=datetime.now(UTC),
                delta=None,
            ),
            Mock(
                operation="PUT",
                key="test-key",
                value=b'"value"',
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        # No need to patch print, the logger will output warnings
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Should skip unknown operation and get PUT
        assert len(events) == 1
        assert events[0].operation == "PUT"
        # Logger warning will be in captured logs

    @pytest.mark.asyncio
    async def test_watch_initial_delete(self, kv_store):
        """Test watch skips initial DELETE events."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher with initial DELETE (key doesn't exist initially)
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="DELETE",
                key="test-key",
                value=None,
                revision=1,
                created=None,
                delta=0,  # Initial update
            ),
            Mock(
                operation="PUT",
                key="test-key",
                value=b'"value"',
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Should skip initial DELETE and only get PUT
        assert len(events) == 1
        assert events[0].operation == "PUT"

    @pytest.mark.asyncio
    async def test_watch_exception_handling(self, kv_store):
        """Test watch handles exceptions gracefully."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher that throws exception
        mock_watcher = AsyncMock()
        mock_watcher.updates = AsyncMock(side_effect=[None, Exception("watch error")])
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            # Should exit on exception

        # No events due to exception
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_get_no_kv_store(self, kv_store):
        """Test get fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.get("test-key")

    @pytest.mark.asyncio
    async def test_put_no_kv_store(self, kv_store):
        """Test put fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.put("test-key", "value")

    @pytest.mark.asyncio
    async def test_delete_no_kv_store(self, kv_store):
        """Test delete fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.delete("test-key")

    @pytest.mark.asyncio
    async def test_exists_no_kv_store(self, kv_store):
        """Test exists fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.exists("test-key")

    @pytest.mark.asyncio
    async def test_keys_no_kv_store(self, kv_store):
        """Test keys fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.keys()

    @pytest.mark.asyncio
    async def test_history_no_kv_store(self, kv_store):
        """Test history fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.history("test-key")

    @pytest.mark.asyncio
    async def test_purge_no_kv_store(self, kv_store):
        """Test purge fails when not connected."""
        kv_store._kv = None

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.purge("test-key")

    @pytest.mark.asyncio
    async def test_status_not_connected(self, kv_store):
        """Test status when not connected."""
        kv_store._kv = None

        status = await kv_store.status()

        assert status["connected"] is False
        assert status["bucket"] is None
        assert status["values"] == 0

    @pytest.mark.asyncio
    async def test_status_error(self, kv_store):
        """Test status with error."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._bucket_name = "test_bucket"

        # Mock status throws exception
        mock_kv.status = AsyncMock(side_effect=Exception("status error"))

        status = await kv_store.status()

        assert status["connected"] is True
        assert status["bucket"] == "test_bucket"
        assert "error" in status

    @pytest.mark.asyncio
    async def test_keys_with_prefix_filtering(self, kv_store):
        """Test keys with prefix filtering."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {
            "prefix_key1": "prefix:key1",
            "prefix_key2": "prefix:key2",
            "other_key": "other:key",
        }

        mock_kv.keys = AsyncMock(return_value=["prefix_key1", "prefix_key2", "other_key"])

        keys = await kv_store.keys("prefix:")

        assert len(keys) == 2
        assert "prefix:key1" in keys
        assert "prefix:key2" in keys
        assert "other:key" not in keys

    @pytest.mark.asyncio
    async def test_keys_exception_returns_empty(self, kv_store):
        """Test keys returns empty list on exception."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        mock_kv.keys = AsyncMock(side_effect=Exception("keys error"))

        keys = await kv_store.keys()

        assert keys == []

    @pytest.mark.asyncio
    async def test_history_exception_returns_empty(self, kv_store):
        """Test history returns empty list on exception."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        mock_kv.history = AsyncMock(side_effect=Exception("history error"))

        history = await kv_store.history("test-key")

        assert history == []

    @pytest.mark.asyncio
    async def test_put_create_only_duplicate_error(self, kv_store):
        """Test put with create_only handles duplicate error."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock create throws duplicate error
        mock_kv.create = AsyncMock(side_effect=Exception("duplicate key"))

        options = KVOptions(create_only=True)

        with pytest.raises(KVKeyAlreadyExistsError) as exc_info:
            await kv_store.put("test-key", "value", options)

        assert exc_info.value.key == "test-key"

    @pytest.mark.asyncio
    async def test_put_update_only_no_revision(self, kv_store):
        """Test put with update_only and no revision gets current revision."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get returns current entry
        mock_entry = Mock()
        mock_entry.revision = 123
        mock_kv.get = AsyncMock(return_value=mock_entry)
        mock_kv.update = AsyncMock(return_value=124)

        options = KVOptions(update_only=True)
        revision = await kv_store.put("test-key", "value", options)

        assert revision == 124
        mock_kv.update.assert_called_once_with("test-key", b'"value"', 123)

    @pytest.mark.asyncio
    async def test_create_kv_stream_with_ttl_no_connection(self, kv_store):
        """Test create KV stream fails without connection."""
        kv_store._nats_adapter._connections = []

        result = await kv_store._create_kv_stream_with_ttl("test-bucket")

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_create_stream_with_ttl_failure(self, kv_store, mock_nats_client):
        """Test connect handles TTL stream creation failure."""
        client, js, kv = mock_nats_client

        # First call to key_value fails
        js.key_value.side_effect = [Exception("bucket not found")]
        # Stream doesn't exist
        js.stream_info = AsyncMock(side_effect=Exception("stream not found"))

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        # Mock create_kv_stream_with_ttl to fail
        with (
            patch.object(kv_store, "_create_kv_stream_with_ttl", return_value=False),
            pytest.raises(Exception, match="Failed to create stream with TTL support"),
        ):
            await kv_store.connect("test_bucket", enable_ttl=True)

    @pytest.mark.asyncio
    async def test_connect_failure(self, kv_store, mock_nats_client):
        """Test connect handles general failure."""
        client, js, kv = mock_nats_client

        # key_value always fails
        js.key_value.side_effect = Exception("connection error")

        # Configure the mock adapter that was injected
        kv_store._nats_adapter._connections = [client]
        kv_store._nats_adapter._js = js
        kv_store._nats_adapter.is_connected = AsyncMock(return_value=True)

        with pytest.raises(Exception, match="Failed to connect to KV bucket"):
            await kv_store.connect("test_bucket")

    @pytest.mark.asyncio
    async def test_put_create_only_generic_error(self, kv_store):
        """Test put with create_only re-raises generic errors."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock create throws generic error (not duplicate)
        mock_kv.create = AsyncMock(side_effect=Exception("network error"))

        options = KVOptions(create_only=True)

        with pytest.raises(Exception, match="network error"):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_put_update_only_with_revision(self, kv_store):
        """Test put with update_only and provided revision."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.update = AsyncMock(return_value=124)

        options = KVOptions(update_only=True, revision=123)
        revision = await kv_store.put("test-key", "value", options)

        assert revision == 124
        # Should use provided revision directly, not fetch current
        mock_kv.update.assert_called_once_with("test-key", b'"value"', 123)
        mock_kv.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_put_update_only_key_not_found(self, kv_store):
        """Test put with update_only when key doesn't exist."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get throws exception (key not found)
        mock_kv.get = AsyncMock(side_effect=Exception("key not found"))

        options = KVOptions(update_only=True)

        # Import the specific exception type
        from aegis_sdk.domain.exceptions import KVKeyNotFoundError

        with pytest.raises(KVKeyNotFoundError):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_put_revision_check_key_not_found_specific(self, kv_store):
        """Test put with revision check when key not found."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get throws "not found" error
        mock_kv.get = AsyncMock(side_effect=Exception("key not found"))

        options = KVOptions(revision=123)

        from aegis_sdk.domain.exceptions import KVKeyNotFoundError

        with pytest.raises(KVKeyNotFoundError):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_put_revision_check_generic_error(self, kv_store):
        """Test put with revision check generic error."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock get throws generic error (not "not found")
        mock_kv.get = AsyncMock(side_effect=Exception("connection error"))

        options = KVOptions(revision=123)

        from aegis_sdk.domain.exceptions import KVStoreError

        with pytest.raises(KVStoreError, match="Revision check failed"):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_put_with_ttl_generic_error(self, kv_store):
        """Test put with TTL re-raises generic errors."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._bucket_name = "test_bucket"

        # Mock JetStream publish that fails with generic error
        mock_js = AsyncMock()
        mock_js.publish = AsyncMock(side_effect=Exception("network error"))
        kv_store._nats_adapter._js = mock_js

        options = KVOptions(ttl=3600)

        with pytest.raises(Exception, match="network error"):
            await kv_store.put("test-key", "value", options)

    @pytest.mark.asyncio
    async def test_put_normal_without_options(self, kv_store):
        """Test normal put when options is None but revision check path is taken."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        mock_kv.put = AsyncMock(return_value=123)

        # Test with options that has revision=None, not create_only or update_only
        options = KVOptions()  # All fields None by default
        revision = await kv_store.put("test-key", "value", options)

        assert revision == 123
        mock_kv.put.assert_called_once_with("test-key", b'"value"')

    @pytest.mark.asyncio
    async def test_watch_all_keys(self, kv_store):
        """Test watch without key or prefix (watch all)."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="PUT",
                key="any-key",
                value=b'"value"',
                revision=1,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch():  # No key or prefix
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) == 1
        # Should watch all keys
        mock_kv.watch.assert_called_once_with(">", include_history=False)

    @pytest.mark.asyncio
    async def test_watch_prefix_filter_non_matching(self, kv_store):
        """Test watch filters out non-matching prefix in event loop."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher that returns events with different prefixes
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="PUT",
                key="other:key",  # Non-matching prefix
                value=b'"ignored"',
                revision=1,
                created=datetime.now(UTC),
                delta=None,
            ),
            Mock(
                operation="PUT",
                key="prefix:key1",  # Matching prefix
                value=b'"value1"',
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]

        # Add a counter to prevent infinite loop
        call_count = 0

        async def mock_updates(*args, **kwargs):
            nonlocal call_count
            if call_count < len(updates_sequence):
                result = updates_sequence[call_count]
                call_count += 1
                return result
            # After all updates, raise timeout to exit
            raise asyncio.TimeoutError()

        mock_watcher.updates = AsyncMock(side_effect=mock_updates)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(prefix="prefix:"):
            events.append(event)
            # Should get only one matching event
            if len(events) >= 1:
                break

        assert len(events) == 1
        assert events[0].entry.key == "prefix:key1"

    @pytest.mark.asyncio
    async def test_watch_put_with_no_value(self, kv_store):
        """Test watch skips PUT operations with no value."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher with PUT that has no value
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,  # Initial marker
            Mock(
                operation="PUT",
                key="test-key",
                value=None,  # No value
                revision=1,
                created=datetime.now(UTC),
                delta=None,
            ),
            Mock(
                operation="PUT",
                key="test-key",
                value=b'"real-value"',  # Has value
                revision=2,
                created=datetime.now(UTC),
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        # Should skip first PUT and only get second
        assert len(events) == 1
        assert events[0].entry.value == "real-value"

    @pytest.mark.asyncio
    async def test_watch_put_no_created_timestamp(self, kv_store):
        """Test watch handles PUT without created timestamp."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher with PUT that has no created timestamp
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,
            Mock(
                operation="PUT",
                key="test-key",
                value=b'"value"',
                revision=1,
                created=None,  # No timestamp
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) == 1
        # Should have current timestamp
        assert events[0].entry.created_at is not None
        assert events[0].entry.updated_at is not None

    @pytest.mark.asyncio
    async def test_watch_purge_operation(self, kv_store):
        """Test watch handles PURGE operations."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv
        kv_store._key_mapping = {}

        # Mock watcher with PURGE operation
        mock_watcher = AsyncMock()
        updates_sequence = [
            None,
            Mock(
                operation="PURGE",
                key="test-key",
                value=None,
                revision=1,
                created=None,
                delta=None,
            ),
        ]
        mock_watcher.updates = AsyncMock(side_effect=updates_sequence)
        mock_kv.watch = AsyncMock(return_value=mock_watcher)

        events = []
        async for event in kv_store.watch(key="test-key"):
            events.append(event)
            if len(events) >= 1:
                break

        assert len(events) == 1
        assert events[0].operation == "PURGE"
        assert events[0].entry is None

    @pytest.mark.asyncio
    async def test_history_no_created_timestamp(self, kv_store):
        """Test history handles entries without created timestamp."""
        mock_kv = AsyncMock()
        kv_store._kv = mock_kv

        # Mock history entries without created timestamp
        mock_entries = [
            Mock(
                key="test-key",
                value=b'{"data": "v1"}',
                revision=1,
                created=None,  # No timestamp
                delta=None,
            ),
        ]

        mock_kv.history = AsyncMock(return_value=mock_entries)

        history = await kv_store.history("test-key")

        assert len(history) == 1
        # Should have current timestamp
        assert history[0].created_at is not None
        assert history[0].updated_at is not None
