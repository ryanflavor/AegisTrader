"""Integration tests for NATS KV Store - concise and comprehensive."""

import asyncio

import pytest
import pytest_asyncio

from aegis_sdk.domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVKeyNotFoundError,
    KVRevisionMismatchError,
)
from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


@pytest.mark.integration
class TestNATSKVStoreIntegration:
    """Integration tests for NATS KV Store."""

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create NATS adapter connected to test server."""
        adapter = NATSAdapter()
        await adapter.connect(["nats://localhost:4222"])
        yield adapter
        await adapter.disconnect()

    @pytest_asyncio.fixture
    async def kv_store(self, nats_adapter):
        """Create KV Store connected to test bucket."""
        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect("test-bucket")

        # Clear any existing data
        await kv_store.clear()

        yield kv_store

        # Cleanup
        await kv_store.clear()
        await kv_store.disconnect()

    @pytest.mark.asyncio
    async def test_basic_crud_operations(self, kv_store):
        """Test basic CRUD operations."""
        # Create
        rev1 = await kv_store.put("key1", {"value": 1})
        assert rev1 > 0

        # Read
        entry = await kv_store.get("key1")
        assert entry.value == {"value": 1}
        assert entry.revision == rev1

        # Update
        rev2 = await kv_store.put("key1", {"value": 2})
        assert rev2 > rev1

        # Delete
        assert await kv_store.delete("key1") is True
        assert await kv_store.get("key1") is None

    @pytest.mark.asyncio
    async def test_create_update_options(self, kv_store):
        """Test create_only and update_only options."""
        # Create only
        options = KVOptions(create_only=True)
        await kv_store.put("key1", "value1", options)

        with pytest.raises(KVKeyAlreadyExistsError):
            await kv_store.put("key1", "value2", options)

        # Update only
        options = KVOptions(update_only=True)
        await kv_store.put("key1", "updated", options)

        with pytest.raises(KVKeyNotFoundError):
            await kv_store.put("key2", "new", options)

    @pytest.mark.asyncio
    async def test_revision_check(self, kv_store):
        """Test optimistic concurrency control."""
        rev1 = await kv_store.put("key1", "v1")

        # Correct revision succeeds
        options = KVOptions(revision=rev1)
        await kv_store.put("key1", "v2", options)

        # Wrong revision fails
        options = KVOptions(revision=rev1)
        with pytest.raises(KVRevisionMismatchError):
            await kv_store.put("key1", "v3", options)

    @pytest.mark.asyncio
    async def test_batch_operations(self, kv_store):
        """Test batch operations."""
        # Put many
        entries = {f"key{i}": {"value": i} for i in range(1, 4)}
        revisions = await kv_store.put_many(entries)
        assert len(revisions) == 3

        # Get many
        results = await kv_store.get_many(["key1", "key2", "missing"])
        assert len(results) == 2
        assert results["key1"].value == {"value": 1}

        # Delete many
        deletes = await kv_store.delete_many(["key1", "key2"])
        assert all(deletes.values())

    @pytest.mark.asyncio
    async def test_watch_operations(self, kv_store):
        """Test watch functionality."""
        events = []

        async def collect_events():
            async for event in kv_store.watch(key="key1"):
                events.append(event)
                if len(events) >= 2:
                    break

        # Start watching
        task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Make changes
        await kv_store.put("key1", "value1")
        await kv_store.delete("key1")

        # Wait for events
        await asyncio.wait_for(task, timeout=2.0)

        assert len(events) == 2
        assert events[0].operation == "PUT"
        assert events[1].operation == "DELETE"

    @pytest.mark.asyncio
    async def test_history_tracking(self, kv_store):
        """Test revision history tracking."""
        # Create multiple revisions
        await kv_store.put("history-key", "version-1")
        await asyncio.sleep(0.1)
        await kv_store.put("history-key", "version-2")
        await asyncio.sleep(0.1)
        await kv_store.put("history-key", "version-3")

        # Get history
        history = await kv_store.history("history-key", limit=10)

        # Should have 3 revisions, newest first
        assert len(history) >= 3
        assert history[0].value == "version-3"
        assert history[0].revision > history[1].revision

        # Verify chronological order
        for i in range(len(history) - 1):
            assert history[i].revision > history[i + 1].revision

    @pytest.mark.asyncio
    async def test_purge_operation(self, kv_store):
        """Test purging all revisions of a key."""
        # Create key with history
        await kv_store.put("purge-key", "version-1")
        await kv_store.put("purge-key", "version-2")
        await kv_store.put("purge-key", "version-3")

        # Verify history exists
        history = await kv_store.history("purge-key")
        assert len(history) >= 3

        # Purge the key
        await kv_store.purge("purge-key")

        # Key should not exist
        assert await kv_store.exists("purge-key") is False

        # History should be empty or contain only tombstone
        history = await kv_store.history("purge-key")
        # NATS KV might keep a tombstone record after purge
        assert len(history) <= 1
        if len(history) == 1:
            # If there's a record, it should be a deletion marker
            assert history[0].value is None

    @pytest.mark.asyncio
    async def test_clear_with_prefix(self, kv_store):
        """Test clearing keys by prefix."""
        # Create multiple keys
        await kv_store.put("clear:key1", "value1")
        await kv_store.put("clear:key2", "value2")
        await kv_store.put("clear:key3", "value3")
        await kv_store.put("keep:key4", "value4")

        # Clear with prefix
        cleared = await kv_store.clear("clear:")
        assert cleared == 3

        # Verify cleared keys
        assert await kv_store.exists("clear:key1") is False
        assert await kv_store.exists("clear:key2") is False
        assert await kv_store.exists("clear:key3") is False

        # Other keys should remain
        assert await kv_store.exists("keep:key4") is True

    @pytest.mark.asyncio
    async def test_status_information(self, kv_store):
        """Test status reporting."""
        # Add some data
        await kv_store.put("status:key1", {"data": "value1"})
        await kv_store.put("status:key2", {"data": "value2"})
        await kv_store.put("status:key3", {"data": "value3"})

        # Get status
        status = await kv_store.status()

        assert status["connected"] is True
        assert status["bucket"] == "test-bucket"
        # Check for either 'values' or 'bytes' - different NATS versions might have different fields
        assert "bytes" in status or "values" in status
        if "values" in status:
            assert status["values"] >= 3
        if "bytes" in status:
            assert status["bytes"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, kv_store):
        """Test concurrent access."""

        async def writer(id: int):
            for i in range(5):
                await kv_store.put(f"c:{id}:{i}", {"id": id, "i": i})

        # Concurrent writes
        await asyncio.gather(*[writer(i) for i in range(3)])

        # Verify
        keys = await kv_store.keys("c:")
        assert len(keys) == 15

    @pytest.mark.asyncio
    async def test_error_handling(self, kv_store):
        """Test error handling for various failure scenarios."""
        # Test invalid bucket after disconnect
        await kv_store.disconnect()

        from aegis_sdk.domain.exceptions import KVNotConnectedError

        with pytest.raises(KVNotConnectedError):
            await kv_store.get("any-key")

        # Reconnect for remaining tests
        await kv_store.connect("test-bucket")

        # Test revision mismatch
        rev = await kv_store.put("error-key", "initial")
        options = KVOptions(revision=rev + 100)  # Wrong revision

        with pytest.raises(KVRevisionMismatchError):
            await kv_store.put("error-key", "updated", options)

        # Test create_only on existing key
        options = KVOptions(create_only=True)
        with pytest.raises(KVKeyAlreadyExistsError):
            await kv_store.put("error-key", "new-value", options)

        # Test update_only on missing key
        options = KVOptions(update_only=True)
        with pytest.raises(KVKeyNotFoundError):
            await kv_store.put("missing-key", "value", options)

    @pytest.mark.asyncio
    async def test_large_values(self, kv_store):
        """Test handling of large values."""
        # Create a large value (100KB)
        large_data = {
            "data": "x" * 100000,
            "metadata": {
                "size": 100000,
                "type": "test",
            },
        }

        # Store large value
        revision = await kv_store.put("large-key", large_data)
        assert revision > 0

        # Retrieve and verify
        entry = await kv_store.get("large-key")
        assert entry is not None
        assert entry.value == large_data
        assert len(entry.value["data"]) == 100000

    @pytest.mark.asyncio
    async def test_special_characters_in_keys(self, kv_store):
        """Test keys with special characters."""
        special_keys = [
            "user:123:profile",
            "path/to/resource",
            "key-with-dashes",
            "key_with_underscores",
            "key.with.dots",
        ]

        # Store with special keys
        for key in special_keys:
            await kv_store.put(key, {"key": key})

        # Verify all can be retrieved
        for key in special_keys:
            entry = await kv_store.get(key)
            assert entry is not None
            assert entry.value == {"key": key}
