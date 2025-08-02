"""Tests for KV Store port interface."""

from abc import ABC

import pytest

from aegis_sdk.domain.models import KVEntry, KVOptions
from aegis_sdk.ports.kv_store import KVStorePort


class TestKVStorePort:
    """Test cases for KVStorePort interface."""

    def test_kv_store_port_is_abstract(self):
        """Test that KVStorePort is an abstract base class."""
        assert issubclass(KVStorePort, ABC)

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            KVStorePort()

    def test_kv_store_port_defines_interface(self):
        """Test that KVStorePort defines all required methods."""
        # Check all abstract methods are defined
        abstract_methods = {
            "connect",
            "disconnect",
            "is_connected",
            "get",
            "put",
            "delete",
            "exists",
            "keys",
            "get_many",
            "put_many",
            "delete_many",
            "watch",
            "history",
            "purge",
            "clear",
            "status",
        }

        # Get all abstract methods from the class
        actual_abstract_methods = {
            name
            for name, method in KVStorePort.__dict__.items()
            if getattr(method, "__isabstractmethod__", False)
        }

        assert abstract_methods == actual_abstract_methods

    def test_kv_store_port_method_signatures(self):
        """Test that port methods have correct signatures."""
        # Test connection methods
        connect_method = KVStorePort.connect
        assert connect_method.__name__ == "connect"
        assert hasattr(connect_method, "__isabstractmethod__")

        disconnect_method = KVStorePort.disconnect
        assert disconnect_method.__name__ == "disconnect"

        is_connected_method = KVStorePort.is_connected
        assert is_connected_method.__name__ == "is_connected"

        # Test basic operations
        get_method = KVStorePort.get
        assert get_method.__name__ == "get"

        put_method = KVStorePort.put
        assert put_method.__name__ == "put"

        delete_method = KVStorePort.delete
        assert delete_method.__name__ == "delete"

        exists_method = KVStorePort.exists
        assert exists_method.__name__ == "exists"

        # Test batch operations
        keys_method = KVStorePort.keys
        assert keys_method.__name__ == "keys"

        get_many_method = KVStorePort.get_many
        assert get_many_method.__name__ == "get_many"

        put_many_method = KVStorePort.put_many
        assert put_many_method.__name__ == "put_many"

        delete_many_method = KVStorePort.delete_many
        assert delete_many_method.__name__ == "delete_many"

        # Test advanced operations
        watch_method = KVStorePort.watch
        assert watch_method.__name__ == "watch"

        history_method = KVStorePort.history
        assert history_method.__name__ == "history"

        purge_method = KVStorePort.purge
        assert purge_method.__name__ == "purge"

        clear_method = KVStorePort.clear
        assert clear_method.__name__ == "clear"

        status_method = KVStorePort.status
        assert status_method.__name__ == "status"


class TestKVStorePortImplementation:
    """Test cases for KVStorePort implementation contract."""

    @pytest.fixture
    def mock_implementation(self):
        """Create a mock implementation of KVStorePort."""

        class MockKVStore(KVStorePort):
            def __init__(self):
                self.connected = False
                self.bucket = None
                self.store = {}
                self.revision_counter = 0

            async def connect(self, bucket: str) -> None:
                self.bucket = bucket
                self.connected = True

            async def disconnect(self) -> None:
                self.connected = False
                self.bucket = None

            async def is_connected(self) -> bool:
                return self.connected

            async def get(self, key: str) -> KVEntry | None:
                if key in self.store:
                    return self.store[key]
                return None

            async def put(self, key: str, value, options: KVOptions | None = None) -> int:
                self.revision_counter += 1
                from datetime import UTC, datetime

                now = datetime.now(UTC).isoformat()
                entry = KVEntry(
                    key=key,
                    value=value,
                    revision=self.revision_counter,
                    created_at=self.store[key].created_at if key in self.store else now,
                    updated_at=now,
                    ttl=options.ttl if options else None,
                )
                self.store[key] = entry
                return self.revision_counter

            async def delete(self, key: str, revision: int | None = None) -> bool:
                if key in self.store:
                    del self.store[key]
                    return True
                return False

            async def exists(self, key: str) -> bool:
                return key in self.store

            async def keys(self, prefix: str = "") -> list[str]:
                return [k for k in self.store if k.startswith(prefix)]

            async def get_many(self, keys: list[str]) -> dict[str, KVEntry]:
                return {k: self.store[k] for k in keys if k in self.store}

            async def put_many(
                self, entries: dict[str, any], options: KVOptions | None = None
            ) -> dict[str, int]:
                results = {}
                for key, value in entries.items():
                    results[key] = await self.put(key, value, options)
                return results

            async def delete_many(self, keys: list[str]) -> dict[str, bool]:
                return {k: await self.delete(k) for k in keys}

            async def watch(self, key: str | None = None, prefix: str | None = None):
                # Simple generator for testing
                if key and prefix:
                    raise ValueError("Cannot specify both key and prefix")
                yield  # pragma: no cover

            async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
                # Return single entry for testing
                if key in self.store:
                    return [self.store[key]]
                return []

            async def purge(self, key: str) -> None:
                if key in self.store:
                    del self.store[key]

            async def clear(self, prefix: str = "") -> int:
                keys_to_delete = [k for k in self.store if k.startswith(prefix)]
                for k in keys_to_delete:
                    del self.store[k]
                return len(keys_to_delete)

            async def status(self) -> dict[str, any]:
                return {
                    "bucket": self.bucket,
                    "connected": self.connected,
                    "size": len(self.store),
                }

        return MockKVStore()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, mock_implementation):
        """Test connection lifecycle methods."""
        # Initially not connected
        assert await mock_implementation.is_connected() is False

        # Connect
        await mock_implementation.connect("test-bucket")
        assert await mock_implementation.is_connected() is True
        assert mock_implementation.bucket == "test-bucket"

        # Disconnect
        await mock_implementation.disconnect()
        assert await mock_implementation.is_connected() is False
        assert mock_implementation.bucket is None

    @pytest.mark.asyncio
    async def test_basic_operations(self, mock_implementation):
        """Test basic CRUD operations."""
        await mock_implementation.connect("test-bucket")

        # Test put and get
        revision = await mock_implementation.put("test-key", {"value": "test"})
        assert revision > 0

        entry = await mock_implementation.get("test-key")
        assert isinstance(entry, KVEntry)
        assert entry.key == "test-key"
        assert entry.value == {"value": "test"}
        assert entry.revision == revision

        # Test exists
        assert await mock_implementation.exists("test-key") is True
        assert await mock_implementation.exists("non-existent") is False

        # Test delete
        assert await mock_implementation.delete("test-key") is True
        assert await mock_implementation.get("test-key") is None
        assert await mock_implementation.delete("non-existent") is False

    @pytest.mark.asyncio
    async def test_batch_operations(self, mock_implementation):
        """Test batch operations."""
        await mock_implementation.connect("test-bucket")

        # Test put_many
        entries = {"key1": "value1", "key2": "value2", "key3": "value3"}
        revisions = await mock_implementation.put_many(entries)
        assert len(revisions) == 3
        assert all(r > 0 for r in revisions.values())

        # Test keys
        keys = await mock_implementation.keys()
        assert set(keys) == {"key1", "key2", "key3"}

        # Test keys with prefix
        await mock_implementation.put("other-key", "value")
        keys_with_prefix = await mock_implementation.keys("key")
        assert set(keys_with_prefix) == {"key1", "key2", "key3"}

        # Test get_many
        results = await mock_implementation.get_many(["key1", "key2", "non-existent"])
        assert len(results) == 2
        assert "key1" in results
        assert "key2" in results
        assert "non-existent" not in results

        # Test delete_many
        delete_results = await mock_implementation.delete_many(["key1", "key2", "non-existent"])
        assert delete_results["key1"] is True
        assert delete_results["key2"] is True
        assert delete_results["non-existent"] is False

    @pytest.mark.asyncio
    async def test_advanced_operations(self, mock_implementation):
        """Test advanced operations."""
        await mock_implementation.connect("test-bucket")

        # Test history
        await mock_implementation.put("test-key", "value1")
        history = await mock_implementation.history("test-key")
        assert len(history) > 0
        assert history[0].key == "test-key"

        # Test purge
        await mock_implementation.purge("test-key")
        assert await mock_implementation.exists("test-key") is False

        # Test clear
        await mock_implementation.put("prefix:key1", "value1")
        await mock_implementation.put("prefix:key2", "value2")
        await mock_implementation.put("other:key", "value")

        cleared = await mock_implementation.clear("prefix:")
        assert cleared == 2
        assert await mock_implementation.exists("prefix:key1") is False
        assert await mock_implementation.exists("prefix:key2") is False
        assert await mock_implementation.exists("other:key") is True

        # Test status
        status = await mock_implementation.status()
        assert isinstance(status, dict)
        assert status["bucket"] == "test-bucket"
        assert status["connected"] is True

    @pytest.mark.asyncio
    async def test_put_with_options(self, mock_implementation):
        """Test put operation with options."""
        await mock_implementation.connect("test-bucket")

        # Test with TTL
        options = KVOptions(ttl=3600)
        await mock_implementation.put("ttl-key", "value", options)
        entry = await mock_implementation.get("ttl-key")
        assert entry.ttl == 3600

    @pytest.mark.asyncio
    async def test_watch_validation(self, mock_implementation):
        """Test watch parameter validation."""
        await mock_implementation.connect("test-bucket")

        # Should raise error if both key and prefix are provided
        with pytest.raises(ValueError):
            async for _ in mock_implementation.watch(key="key", prefix="prefix"):
                pass  # pragma: no cover


class TestKVStorePortContract:
    """Test that implementations must follow the port contract."""

    def test_implementation_must_override_all_methods(self):
        """Test that incomplete implementations raise TypeError."""

        # Create incomplete implementation
        class IncompleteKVStore(KVStorePort):
            async def connect(self, bucket: str) -> None:
                pass

            # Missing other methods

        # Should not be able to instantiate
        with pytest.raises(TypeError) as exc_info:
            IncompleteKVStore()

        error_msg = str(exc_info.value)
        assert "Can't instantiate abstract class" in error_msg

    def test_implementation_method_signatures_must_match(self):
        """Test that implementations must match method signatures."""
        # This is more of a documentation test - Python doesn't enforce
        # signature matching for abstract methods at runtime, but type
        # checkers like mypy will catch these issues

        class BadImplementation(KVStorePort):
            # Wrong signature - missing bucket parameter
            async def connect(self) -> None:  # type: ignore
                pass

            async def disconnect(self) -> None:
                pass

            async def is_connected(self) -> bool:
                return False

            # Wrong signature - missing key parameter
            async def get(self) -> KVEntry | None:  # type: ignore
                return None

            async def put(self, key: str, value, options: KVOptions | None = None) -> int:
                return 1

            async def delete(self, key: str, revision: int | None = None) -> bool:
                return False

            async def exists(self, key: str) -> bool:
                return False

            async def keys(self, prefix: str = "") -> list[str]:
                return []

            async def get_many(self, keys: list[str]) -> dict[str, KVEntry]:
                return {}

            async def put_many(
                self, entries: dict[str, any], options: KVOptions | None = None
            ) -> dict[str, int]:
                return {}

            async def delete_many(self, keys: list[str]) -> dict[str, bool]:
                return {}

            async def watch(self, key: str | None = None, prefix: str | None = None):
                yield  # pragma: no cover

            async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
                return []

            async def purge(self, key: str) -> None:
                pass

            async def clear(self, prefix: str = "") -> int:
                return 0

            async def status(self) -> dict[str, any]:
                return {}

        # Can instantiate (Python doesn't check signatures at runtime)
        # but type checkers would catch this
        bad_impl = BadImplementation()
        assert isinstance(bad_impl, KVStorePort)
