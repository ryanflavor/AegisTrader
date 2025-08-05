"""Integration tests for NATS KV Store with TTL support using SDK built-in functionality."""

import asyncio
import os
import time

import pytest
import pytest_asyncio

from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


@pytest.mark.integration
class TestNATSKVStoreTTL:
    """Test NATS KV Store TTL functionality with SDK built-in support."""

    @pytest_asyncio.fixture
    async def nats_adapter(self):
        """Create NATS adapter connected to test server."""
        adapter = NATSAdapter()
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        await adapter.connect([nats_url])
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_per_message_ttl_with_sdk(self, nats_adapter):
        """Test per-message TTL using SDK's built-in TTL support."""
        # Create unique bucket name
        bucket_name = f"ttl_sdk_test_{int(time.time())}"

        # Connect KV store with TTL support enabled
        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect(bucket_name, enable_ttl=True)

        try:
            # Test 1: Put with 2 second TTL
            options = KVOptions(ttl=2)
            revision = await kv_store.put("ttl-key-2s", {"data": "expires in 2s"}, options)
            assert revision > 0

            # Test 2: Put with 5 second TTL
            options = KVOptions(ttl=5)
            revision = await kv_store.put("ttl-key-5s", {"data": "expires in 5s"}, options)
            assert revision > 0

            # Test 3: Put without TTL
            revision = await kv_store.put("ttl-key-permanent", {"data": "never expires"})
            assert revision > 0

            # Verify all exist immediately
            assert await kv_store.exists("ttl-key-2s") is True
            assert await kv_store.exists("ttl-key-5s") is True
            assert await kv_store.exists("ttl-key-permanent") is True

            # Wait 3 seconds
            await asyncio.sleep(3)

            # 2s key should be expired, others should exist
            assert await kv_store.exists("ttl-key-2s") is False
            assert await kv_store.exists("ttl-key-5s") is True
            assert await kv_store.exists("ttl-key-permanent") is True

            # Wait another 3 seconds (total 6)
            await asyncio.sleep(3)

            # Both TTL keys should be expired
            assert await kv_store.exists("ttl-key-2s") is False
            assert await kv_store.exists("ttl-key-5s") is False
            assert await kv_store.exists("ttl-key-permanent") is True

        finally:
            await kv_store.disconnect()

    @pytest.mark.asyncio
    async def test_ttl_disabled_by_default(self, nats_adapter):
        """Test that TTL is properly disabled when not requested."""
        # Create a bucket without TTL support
        bucket_name = f"no_ttl_sdk_test_{int(time.time())}"
        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect(bucket_name, enable_ttl=False)

        try:
            # Attempting to use TTL should raise an error
            options = KVOptions(ttl=5)
            # When TTL is disabled but attempted to use, it raises KVTTLNotSupportedError
            from aegis_sdk.domain.exceptions import KVTTLNotSupportedError

            with pytest.raises(KVTTLNotSupportedError):
                await kv_store.put("ttl-test", "value", options)

        finally:
            await kv_store.disconnect()

    @pytest.mark.asyncio
    async def test_mixed_ttl_operations(self, nats_adapter):
        """Test mixing TTL and non-TTL operations."""
        bucket_name = f"mixed_ttl_test_{int(time.time())}"
        kv_store = NATSKVStore(nats_adapter=nats_adapter)
        await kv_store.connect(bucket_name, enable_ttl=True)

        try:
            # Put multiple keys with different TTLs
            await kv_store.put("key1", "no ttl")
            await kv_store.put("key2", "ttl 1s", KVOptions(ttl=1))
            await kv_store.put("key3", "ttl 3s", KVOptions(ttl=3))
            await kv_store.put("key4", "no ttl again")

            # All should exist immediately
            assert await kv_store.exists("key1") is True
            assert await kv_store.exists("key2") is True
            assert await kv_store.exists("key3") is True
            assert await kv_store.exists("key4") is True

            # Wait 2 seconds
            await asyncio.sleep(2)

            # key2 should be expired
            assert await kv_store.exists("key1") is True
            assert await kv_store.exists("key2") is False
            assert await kv_store.exists("key3") is True
            assert await kv_store.exists("key4") is True

            # Wait another 2 seconds (total 4)
            await asyncio.sleep(2)

            # key3 should also be expired
            assert await kv_store.exists("key1") is True
            assert await kv_store.exists("key2") is False
            assert await kv_store.exists("key3") is False
            assert await kv_store.exists("key4") is True

        finally:
            await kv_store.disconnect()
