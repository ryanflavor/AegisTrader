"""Integration tests for NATS adapter with real NATS server."""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from testcontainers.nats import NatsContainer

from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter


@pytest.mark.integration
@pytest.mark.asyncio
class TestNATSIntegration:
    """Integration tests for NATS connection adapter."""

    @pytest.fixture(scope="class")
    async def nats_container(self) -> AsyncGenerator[str, None]:
        """Start NATS container for integration tests.

        Yields:
            NATS connection URL
        """
        # Check if we should use local NATS or container
        use_local = os.getenv("USE_LOCAL_NATS", "false").lower() == "true"

        if use_local:
            # Use local NATS instance
            yield "nats://localhost:4222"
        else:
            # Use testcontainers
            try:
                with NatsContainer() as nats:
                    yield nats.get_connection_url()
            except Exception:
                # Fallback to local if testcontainers fails
                pytest.skip("Testcontainers not available, skipping NATS integration tests")

    @pytest.fixture
    async def nats_adapter(self) -> NATSConnectionAdapter:
        """Create NATS connection adapter.

        Returns:
            NATSConnectionAdapter instance
        """
        return NATSConnectionAdapter()

    async def test_connect_to_nats(self, nats_adapter: NATSConnectionAdapter, nats_container: str):
        """Test connecting to real NATS server."""
        # Act
        connected = await nats_adapter.connect(nats_container)

        # Assert
        assert connected is True
        assert await nats_adapter.is_connected() is True

        # Cleanup
        await nats_adapter.disconnect()

    async def test_disconnect_from_nats(
        self, nats_adapter: NATSConnectionAdapter, nats_container: str
    ):
        """Test disconnecting from NATS server."""
        # Arrange
        await nats_adapter.connect(nats_container)
        assert await nats_adapter.is_connected() is True

        # Act
        await nats_adapter.disconnect()

        # Assert
        assert await nats_adapter.is_connected() is False

    async def test_create_kv_bucket(self, nats_adapter: NATSConnectionAdapter, nats_container: str):
        """Test creating KV bucket in NATS."""
        # Arrange
        await nats_adapter.connect(nats_container)
        bucket_name = "test_bucket"

        # Act
        await nats_adapter.create_kv_bucket(bucket_name)

        # Assert
        exists = await nats_adapter.bucket_exists(bucket_name)
        assert exists is True

        # Cleanup
        await nats_adapter.disconnect()

    async def test_bucket_exists_false(
        self, nats_adapter: NATSConnectionAdapter, nats_container: str
    ):
        """Test checking for non-existent bucket."""
        # Arrange
        await nats_adapter.connect(nats_container)

        # Act
        exists = await nats_adapter.bucket_exists("non_existent_bucket")

        # Assert
        assert exists is False

        # Cleanup
        await nats_adapter.disconnect()

    async def test_kv_operations(self, nats_adapter: NATSConnectionAdapter, nats_container: str):
        """Test KV store operations."""
        # Arrange
        await nats_adapter.connect(nats_container)
        bucket_name = "kv_test_bucket"
        await nats_adapter.create_kv_bucket(bucket_name)

        # Act - Put a value
        key = "test_key"
        value = {"data": "test_value", "count": 42}
        await nats_adapter.kv_put(bucket_name, key, value)

        # Assert - Get the value
        retrieved = await nats_adapter.kv_get(bucket_name, key)
        assert retrieved == value

        # Act - Delete the value
        await nats_adapter.kv_delete(bucket_name, key)

        # Assert - Value should be gone
        retrieved = await nats_adapter.kv_get(bucket_name, key)
        assert retrieved is None

        # Cleanup
        await nats_adapter.disconnect()

    async def test_publish_subscribe(
        self, nats_adapter: NATSConnectionAdapter, nats_container: str
    ):
        """Test publish/subscribe functionality."""
        # Arrange
        await nats_adapter.connect(nats_container)
        subject = "test.subject"
        received_messages = []

        async def message_handler(msg):
            received_messages.append(msg.data.decode())

        # Subscribe
        sub = await nats_adapter.subscribe(subject, cb=message_handler)

        # Act - Publish messages
        await nats_adapter.publish(subject, b"message1")
        await nats_adapter.publish(subject, b"message2")

        # Give some time for messages to be received
        await asyncio.sleep(0.1)

        # Assert
        assert len(received_messages) == 2
        assert "message1" in received_messages
        assert "message2" in received_messages

        # Cleanup
        await sub.unsubscribe()
        await nats_adapter.disconnect()

    async def test_request_reply(self, nats_adapter: NATSConnectionAdapter, nats_container: str):
        """Test request/reply pattern."""
        # Arrange
        await nats_adapter.connect(nats_container)
        subject = "test.request"

        # Set up responder
        async def responder(msg):
            await nats_adapter.publish(msg.reply, b"pong")

        await nats_adapter.subscribe(subject, cb=responder)

        # Act - Send request
        response = await nats_adapter.request(subject, b"ping", timeout=1.0)

        # Assert
        assert response.data == b"pong"

        # Cleanup
        await nats_adapter.disconnect()

    async def test_connection_retry(self, nats_adapter: NATSConnectionAdapter):
        """Test connection retry with invalid URL."""
        # Arrange
        invalid_url = "nats://invalid:4222"

        # Act
        connected = await nats_adapter.connect(invalid_url)

        # Assert
        assert connected is False
        assert await nats_adapter.is_connected() is False

    async def test_concurrent_operations(
        self, nats_adapter: NATSConnectionAdapter, nats_container: str
    ):
        """Test concurrent KV operations."""
        # Arrange
        await nats_adapter.connect(nats_container)
        bucket_name = "concurrent_bucket"
        await nats_adapter.create_kv_bucket(bucket_name)

        # Act - Perform concurrent operations
        async def put_value(key: str, value: str):
            await nats_adapter.kv_put(bucket_name, key, {"value": value})

        tasks = [put_value(f"key_{i}", f"value_{i}") for i in range(10)]
        await asyncio.gather(*tasks)

        # Assert - Verify all values were stored
        for i in range(10):
            value = await nats_adapter.kv_get(bucket_name, f"key_{i}")
            assert value == {"value": f"value_{i}"}

        # Cleanup
        await nats_adapter.disconnect()

    async def test_bucket_ttl(self, nats_adapter: NATSConnectionAdapter, nats_container: str):
        """Test KV bucket with TTL."""
        # Arrange
        await nats_adapter.connect(nats_container)
        bucket_name = "ttl_bucket"

        # Act - Create bucket with TTL
        await nats_adapter.create_kv_bucket(bucket_name, ttl_seconds=1)

        # Put a value
        await nats_adapter.kv_put(bucket_name, "ttl_key", {"data": "expires"})

        # Verify it exists
        value = await nats_adapter.kv_get(bucket_name, "ttl_key")
        assert value == {"data": "expires"}

        # Wait for TTL to expire
        await asyncio.sleep(2)

        # Assert - Value should be gone
        value = await nats_adapter.kv_get(bucket_name, "ttl_key")
        assert value is None

        # Cleanup
        await nats_adapter.disconnect()

    async def test_error_handling_no_connection(self, nats_adapter: NATSConnectionAdapter):
        """Test error handling when not connected."""
        # Assert operations fail gracefully when not connected
        assert await nats_adapter.is_connected() is False

        # These should not raise exceptions but return appropriate values
        exists = await nats_adapter.bucket_exists("any_bucket")
        assert exists is False

        value = await nats_adapter.kv_get("any_bucket", "any_key")
        assert value is None
