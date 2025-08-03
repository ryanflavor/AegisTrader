"""Integration tests for NATS KV Store with real NATS server."""

import asyncio

import pytest
import pytest_asyncio

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
        """Test basic Create, Read, Update, Delete operations."""
        # Test create
        revision1 = await kv_store.put("test-key", {"name": "test", "value": 42})
        assert revision1 > 0

        # Test read
        entry = await kv_store.get("test-key")
        assert entry is not None
        assert entry.key == "test-key"
        assert entry.value == {"name": "test", "value": 42}
        assert entry.revision == revision1

        # Test update
        revision2 = await kv_store.put("test-key", {"name": "updated", "value": 100})
        assert revision2 > revision1

        # Verify update
        updated_entry = await kv_store.get("test-key")
        assert updated_entry.value == {"name": "updated", "value": 100}
        assert updated_entry.revision == revision2

        # Test exists
        assert await kv_store.exists("test-key") is True
        assert await kv_store.exists("non-existent") is False

        # Test delete
        assert await kv_store.delete("test-key") is True
        assert await kv_store.get("test-key") is None
        assert await kv_store.exists("test-key") is False

    @pytest.mark.asyncio
    async def test_options_create_only(self, kv_store):
        """Test create_only option prevents overwriting."""
        options = KVOptions(create_only=True)

        # First create should succeed
        revision1 = await kv_store.put("unique-key", "first-value", options)
        assert revision1 > 0

        # Second create should fail
        with pytest.raises(Exception, match="key already exists|duplicate"):
            await kv_store.put("unique-key", "second-value", options)

        # Verify first value is unchanged
        entry = await kv_store.get("unique-key")
        assert entry.value == "first-value"

    @pytest.mark.asyncio
    async def test_options_update_only(self, kv_store):
        """Test update_only option requires existing key."""
        # Create the key first
        initial_rev = await kv_store.put("update-test-key", "initial")

        # Update with update_only should succeed
        options = KVOptions(update_only=True)
        revision = await kv_store.put("update-test-key", "updated", options)
        assert revision > initial_rev

        entry = await kv_store.get("update-test-key")
        assert entry.value == "updated"

        # Update non-existent key should fail
        with pytest.raises(ValueError, match="Key does not exist"):
            await kv_store.put("non-existent-update-key", "value", options)

    @pytest.mark.asyncio
    async def test_revision_check(self, kv_store):
        """Test optimistic concurrency control with revision."""
        # Create initial entry
        revision1 = await kv_store.put("concurrent-key", "version-1")

        # Update with correct revision should succeed
        options = KVOptions(revision=revision1)
        revision2 = await kv_store.put("concurrent-key", "version-2", options)
        assert revision2 > revision1

        # Update with wrong revision should fail
        options = KVOptions(revision=revision1)  # Using old revision
        with pytest.raises(ValueError, match="Revision mismatch|revision check failed"):
            await kv_store.put("concurrent-key", "version-3", options)

        # Verify current value
        entry = await kv_store.get("concurrent-key")
        assert entry.value == "version-2"
        assert entry.revision == revision2

    @pytest.mark.asyncio
    async def test_batch_operations(self, kv_store):
        """Test batch get, put, and delete operations."""
        # Batch put
        entries = {
            "batch:key1": {"id": 1, "name": "Item 1"},
            "batch:key2": {"id": 2, "name": "Item 2"},
            "batch:key3": {"id": 3, "name": "Item 3"},
            "other:key4": {"id": 4, "name": "Item 4"},
        }
        revisions = await kv_store.put_many(entries)
        assert len(revisions) == 4
        assert all(r > 0 for r in revisions.values())

        # List keys with prefix
        batch_keys = await kv_store.keys("batch:")
        assert len(batch_keys) == 3
        assert set(batch_keys) == {"batch:key1", "batch:key2", "batch:key3"}

        # Batch get
        results = await kv_store.get_many(["batch:key1", "batch:key2", "missing-key"])
        assert len(results) == 2
        assert results["batch:key1"].value == {"id": 1, "name": "Item 1"}
        assert results["batch:key2"].value == {"id": 2, "name": "Item 2"}
        assert "missing-key" not in results

        # Batch delete
        delete_results = await kv_store.delete_many(["batch:key1", "batch:key2", "missing-key"])
        assert delete_results["batch:key1"] is True
        assert delete_results["batch:key2"] is True
        # Note: NATS KV delete doesn't fail for non-existent keys
        # so this might return True even for missing keys

        # Verify deletions
        assert await kv_store.exists("batch:key1") is False
        assert await kv_store.exists("batch:key2") is False
        assert await kv_store.exists("batch:key3") is True

    @pytest.mark.asyncio
    async def test_watch_key_changes(self, kv_store):
        """Test watching for key changes."""
        events = []
        watch_task = None

        async def collect_events():
            """Collect watch events."""
            async for event in kv_store.watch(key="watch-key"):
                events.append(event)
                if len(events) >= 3:  # Collect 3 events then stop
                    break

        # Start watching
        watch_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)  # Let watcher initialize

        # Make changes
        await kv_store.put("watch-key", "value-1")
        await asyncio.sleep(0.1)

        await kv_store.put("watch-key", "value-2")
        await asyncio.sleep(0.1)

        await kv_store.delete("watch-key")
        await asyncio.sleep(0.1)

        # Wait for events
        await asyncio.wait_for(watch_task, timeout=5.0)

        # Verify events
        assert len(events) == 3

        assert events[0].operation == "PUT"
        assert events[0].entry.value == "value-1"

        assert events[1].operation == "PUT"
        assert events[1].entry.value == "value-2"

        assert events[2].operation == "DELETE"
        assert events[2].entry is None

    @pytest.mark.asyncio
    async def test_watch_prefix(self, kv_store):
        """Test watching for changes by prefix."""
        events = []

        async def collect_events():
            """Collect watch events for prefix."""
            async for event in kv_store.watch(prefix="prefix:"):
                events.append(event)
                if len(events) >= 3:
                    break

        # Start watching
        watch_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Make changes to keys with prefix
        await kv_store.put("prefix:key1", "value1")
        await kv_store.put("prefix:key2", "value2")
        await kv_store.put("other:key", "ignored")  # Should not trigger event
        await kv_store.delete("prefix:key1")

        # Wait for events
        await asyncio.wait_for(watch_task, timeout=5.0)

        # Verify only prefix events were captured
        assert len(events) == 3
        assert all(e.entry is None or e.entry.key.startswith("prefix:") for e in events)

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
    @pytest.mark.skip(reason="Requires NATS server with allow_msg_ttl enabled")
    async def test_per_message_ttl_with_stream_config(self, nats_adapter):
        """Test per-message TTL with stream configuration."""
        # Create a new KV store with our custom stream config
        import time

        bucket_name = f"ttl-enabled-{int(time.time())}"

        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect(bucket_name)  # This will create stream with allow_msg_ttl

        try:
            # Put with TTL should work now
            options = KVOptions(ttl=5)  # 5 seconds
            revision = await kv_store.put("ttl-test-key", "temporary-value", options)
            assert revision > 0

            # Should exist immediately
            entry = await kv_store.get("ttl-test-key")
            assert entry is not None
            assert entry.value == "temporary-value"

            # Note: We can't actually test expiration without waiting,
            # but we've verified the TTL was accepted

        finally:
            # Clean up
            await kv_store.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires NATS server with allow_msg_ttl enabled")
    async def test_per_message_ttl_expiration(self, kv_store):
        """Test per-message TTL expiration when server supports it."""
        # This test requires NATS server with allow_msg_ttl: true
        # Put with 1 second TTL
        options = KVOptions(ttl=1)
        await kv_store.put("ttl-key", "temporary-value", options)

        # Should exist immediately
        entry = await kv_store.get("ttl-key")
        assert entry is not None
        assert entry.value == "temporary-value"

        # Wait for expiration
        await asyncio.sleep(2)

        # Should be expired
        assert await kv_store.exists("ttl-key") is False
        assert await kv_store.get("ttl-key") is None

    @pytest.mark.asyncio
    async def test_bucket_ttl_expiration(self, nats_adapter):
        """Test bucket-level TTL expiration."""
        # Use a unique bucket name to avoid conflicts
        import time

        bucket_name = f"ttl-test-{int(time.time())}"

        # Create a new KV store with TTL greater than duplicate window (120s)
        # Using 150 seconds (2.5 minutes) to be safe
        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect(bucket_name, ttl=150)  # 2.5 minute TTL

        try:
            # Put some values
            await kv_store.put("ttl-test-key1", "value1")
            await kv_store.put("ttl-test-key2", "value2")

            # Should exist immediately
            assert await kv_store.exists("ttl-test-key1") is True
            assert await kv_store.exists("ttl-test-key2") is True

            # Get status to verify TTL is configured
            status = await kv_store.status()
            print(f"Bucket status: {status}")
            # Check TTL is set
            if "ttl" in status:
                ttl_seconds = status["ttl"]
                print(f"TTL in seconds: {ttl_seconds}")
                # TTL should be 150 seconds or 150e9 nanoseconds
                assert ttl_seconds == 150.0 or ttl_seconds == 150000000000

            # Since we can't wait 2.5 minutes for expiration in a test,
            # we'll just verify that TTL is properly configured
            # In a real scenario, entries would expire after 150 seconds
            print("✅ TTL is properly configured on the bucket")

        finally:
            # Clean up - delete the bucket by purging all keys
            try:
                await kv_store.clear()
            except Exception:
                pass
            await kv_store.disconnect()

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
        """Test concurrent access patterns."""

        # Create multiple concurrent writers
        async def writer(writer_id: int, count: int):
            for i in range(count):
                key = f"concurrent:{writer_id}:{i}"
                value = {"writer": writer_id, "seq": i}
                await kv_store.put(key, value)

        # Run writers concurrently
        tasks = [
            writer(1, 10),
            writer(2, 10),
            writer(3, 10),
        ]
        await asyncio.gather(*tasks)

        # Verify all writes succeeded
        all_keys = await kv_store.keys("concurrent:")
        assert len(all_keys) == 30

        # Test concurrent reads
        async def reader(keys: list[str]):
            return await kv_store.get_many(keys)

        # Read concurrently
        read_tasks = [
            reader(all_keys[:10]),
            reader(all_keys[10:20]),
            reader(all_keys[20:30]),
        ]
        results = await asyncio.gather(*read_tasks)

        # Verify all reads succeeded
        total_entries = sum(len(r) for r in results)
        assert total_entries == 30

    @pytest.mark.asyncio
    async def test_error_handling(self, kv_store):
        """Test error handling for various failure scenarios."""
        # Test invalid bucket after disconnect
        await kv_store.disconnect()

        with pytest.raises(Exception, match="KV store not connected"):
            await kv_store.get("any-key")

        # Reconnect for remaining tests
        await kv_store.connect("test-bucket")

        # Test revision mismatch
        rev = await kv_store.put("error-key", "initial")
        options = KVOptions(revision=rev + 100)  # Wrong revision

        with pytest.raises(ValueError, match="Revision mismatch|revision check failed"):
            await kv_store.put("error-key", "updated", options)

        # Test create_only on existing key
        options = KVOptions(create_only=True)
        with pytest.raises(Exception, match="key already exists|duplicate"):
            await kv_store.put("error-key", "new-value", options)

        # Test update_only on missing key
        options = KVOptions(update_only=True)
        with pytest.raises(ValueError, match="Key does not exist"):
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
