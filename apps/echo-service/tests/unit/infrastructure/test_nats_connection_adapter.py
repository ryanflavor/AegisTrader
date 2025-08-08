"""Comprehensive unit tests for NATS connection adapter.

Following TDD principles with complete coverage of all paths including
error handling, callbacks, and edge cases.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.infrastructure.nats_connection_adapter import (
    NATSConnectionAdapter,
    NATSConnectionConfig,
)
from nats.aio.client import Client as NATSClient
from pydantic import BaseModel


class TestNATSConnectionConfig:
    """Test NATS connection configuration validation."""

    def test_valid_config(self):
        """Test creation with valid configuration."""
        config = NATSConnectionConfig(
            url="nats://localhost:4222",
            name="test-service",
            connect_timeout=10.0,
            reconnect_time_wait=3.0,
            max_reconnect_attempts=10,
            ping_interval=60,
            max_outstanding_pings=3,
        )
        assert config.url == "nats://localhost:4222"
        assert config.name == "test-service"
        assert config.connect_timeout == 10.0

    def test_default_values(self):
        """Test default values are applied correctly."""
        config = NATSConnectionConfig(url="nats://localhost:4222")
        assert config.name == "echo-service"
        assert config.connect_timeout == 5.0
        assert config.reconnect_time_wait == 2.0
        assert config.max_reconnect_attempts == 60

    def test_validation_errors(self):
        """Test validation catches invalid values."""
        with pytest.raises(ValueError):
            NATSConnectionConfig(
                url="nats://localhost:4222",
                connect_timeout=-1,  # Must be > 0
            )

        with pytest.raises(ValueError):
            NATSConnectionConfig(
                url="nats://localhost:4222",
                max_reconnect_attempts=-1,  # Must be >= 0
            )


class TestModel(BaseModel):
    """Test model for Pydantic serialization tests."""

    message: str
    value: int


@pytest.fixture
def config():
    """Create test configuration."""
    return NATSConnectionConfig(
        url="nats://localhost:4222",
        name="test-client",
        connect_timeout=5.0,
    )


@pytest.fixture
def adapter(config):
    """Create NATS adapter instance."""
    return NATSConnectionAdapter(config)


@pytest.fixture
def mock_client():
    """Create mock NATS client."""
    client = AsyncMock(spec=NATSClient)
    client.is_connected = True
    client.jetstream = MagicMock()
    return client


class TestNATSConnectionAdapter:
    """Test NATS connection adapter functionality."""

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, config, mock_client):
        """Test successful connection to NATS."""
        with patch("app.infrastructure.nats_connection_adapter.nats.connect") as mock_connect:
            mock_connect.return_value = mock_client
            mock_jetstream = AsyncMock()
            mock_client.jetstream.return_value = mock_jetstream

            await adapter.connect()

            assert adapter._is_connected
            assert adapter._client == mock_client
            assert adapter._jetstream == mock_jetstream

            # Verify connection options
            mock_connect.assert_called_once()
            call_args = mock_connect.call_args[1]
            assert call_args["servers"] == [config.url]
            assert call_args["name"] == config.name
            assert call_args["connect_timeout"] == config.connect_timeout

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, adapter, mock_client):
        """Test connecting when already connected."""
        adapter._is_connected = True
        adapter._client = mock_client

        with patch("app.infrastructure.nats_connection_adapter.nats.connect") as mock_connect:
            await adapter.connect()
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_timeout(self, adapter):
        """Test connection timeout handling."""
        with patch("app.infrastructure.nats_connection_adapter.nats.connect") as mock_connect:
            mock_connect.side_effect = TimeoutError("Connection timeout")

            with pytest.raises(ConnectionError) as exc_info:
                await adapter.connect()

            assert "Connection timeout after" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_general_error(self, adapter):
        """Test general connection error handling."""
        with patch("app.infrastructure.nats_connection_adapter.nats.connect") as mock_connect:
            mock_connect.side_effect = Exception("Network error")

            with pytest.raises(ConnectionError) as exc_info:
                await adapter.connect()

            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_success(self, adapter, mock_client):
        """Test successful disconnection."""
        adapter._is_connected = True
        adapter._client = mock_client

        # Add mock subscriptions
        mock_sub1 = AsyncMock()
        mock_sub2 = AsyncMock()
        adapter._subscriptions = {"sub1": mock_sub1, "sub2": mock_sub2}

        await adapter.disconnect()

        # Verify all subscriptions were unsubscribed
        mock_sub1.unsubscribe.assert_called_once()
        mock_sub2.unsubscribe.assert_called_once()

        # Verify client was drained and closed
        mock_client.drain.assert_called_once()
        mock_client.close.assert_called_once()

        # Verify state was reset
        assert not adapter._is_connected
        assert adapter._client is None
        assert adapter._jetstream is None
        assert len(adapter._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, adapter):
        """Test disconnecting when not connected."""
        adapter._is_connected = False

        # Should not raise any errors
        await adapter.disconnect()
        assert not adapter._is_connected

    @pytest.mark.asyncio
    async def test_disconnect_error_handling(self, adapter, mock_client):
        """Test error handling during disconnect."""
        adapter._is_connected = True
        adapter._client = mock_client
        mock_client.drain.side_effect = Exception("Drain error")

        with pytest.raises(Exception) as exc_info:
            await adapter.disconnect()

        assert "Drain error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_with_dict(self, adapter, mock_client):
        """Test publishing dict data."""
        adapter._is_connected = True
        adapter._client = mock_client

        data = {"message": "test", "value": 42}
        await adapter.publish("test.subject", data)

        mock_client.publish.assert_called_once_with(
            "test.subject",
            json.dumps(data).encode(),
        )

    @pytest.mark.asyncio
    async def test_publish_with_pydantic_model(self, adapter, mock_client):
        """Test publishing Pydantic model."""
        adapter._is_connected = True
        adapter._client = mock_client

        model = TestModel(message="test", value=42)
        await adapter.publish("test.subject", model)

        mock_client.publish.assert_called_once_with(
            "test.subject",
            model.model_dump_json().encode(),
        )

    @pytest.mark.asyncio
    async def test_publish_with_bytes(self, adapter, mock_client):
        """Test publishing raw bytes."""
        adapter._is_connected = True
        adapter._client = mock_client

        data = b"raw bytes data"
        await adapter.publish("test.subject", data)

        mock_client.publish.assert_called_once_with("test.subject", data)

    @pytest.mark.asyncio
    async def test_publish_with_string(self, adapter, mock_client):
        """Test publishing string data."""
        adapter._is_connected = True
        adapter._client = mock_client

        data = "simple string"
        await adapter.publish("test.subject", data)

        mock_client.publish.assert_called_once_with("test.subject", data.encode())

    @pytest.mark.asyncio
    async def test_publish_not_connected(self, adapter):
        """Test publishing when not connected."""
        adapter._is_connected = False

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.publish("test.subject", {"data": "test"})

        assert "Not connected to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_error(self, adapter, mock_client):
        """Test error handling during publish."""
        adapter._is_connected = True
        adapter._client = mock_client
        mock_client.publish.side_effect = Exception("Publish failed")

        with pytest.raises(Exception) as exc_info:
            await adapter.publish("test.subject", {"data": "test"})

        assert "Publish failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_json_response(self, adapter, mock_client):
        """Test request with JSON response."""
        adapter._is_connected = True
        adapter._client = mock_client

        # Mock response message
        mock_msg = Mock()
        mock_msg.data = json.dumps({"result": "success"}).encode()
        mock_client.request.return_value = mock_msg

        result = await adapter.request("test.subject", {"query": "test"})

        assert result == {"result": "success"}
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_binary_response(self, adapter, mock_client):
        """Test request with binary response."""
        adapter._is_connected = True
        adapter._client = mock_client

        # Mock binary response
        mock_msg = Mock()
        mock_msg.data = b"\x00\x01\x02\x03"
        mock_client.request.return_value = mock_msg

        result = await adapter.request("test.subject", {"query": "test"})

        assert result == b"\x00\x01\x02\x03"

    @pytest.mark.asyncio
    async def test_request_timeout(self, adapter, mock_client):
        """Test request timeout handling."""
        adapter._is_connected = True
        adapter._client = mock_client
        mock_client.request.side_effect = TimeoutError("Request timeout")

        with pytest.raises(TimeoutError) as exc_info:
            await adapter.request("test.subject", {"data": "test"}, timeout=1.0)

        assert "Request timeout after 1.0s" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_not_connected(self, adapter):
        """Test request when not connected."""
        adapter._is_connected = False

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.request("test.subject", {"data": "test"})

        assert "Not connected to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subscribe_with_handler(self, adapter, mock_client):
        """Test subscribing to a subject with handler."""
        adapter._is_connected = True
        adapter._client = mock_client

        # Mock subscription
        mock_sub = Mock()
        mock_client.subscribe.return_value = mock_sub

        # Create test handler
        handler_called = False
        handler_data = None

        async def test_handler(data):
            nonlocal handler_called, handler_data
            handler_called = True
            handler_data = data
            return {"response": "ok"}

        sub_id = await adapter.subscribe("test.subject", test_handler)

        # Verify subscription was created
        assert sub_id in adapter._subscriptions
        assert adapter._subscriptions[sub_id] == mock_sub

        # Test the wrapped handler
        mock_client.subscribe.assert_called_once()
        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        # Create mock message
        mock_msg = Mock()
        mock_msg.data = json.dumps({"test": "data"}).encode()
        mock_msg.reply = "reply.subject"
        mock_msg.respond = AsyncMock()

        await wrapped_handler(mock_msg)

        assert handler_called
        assert handler_data == {"test": "data"}
        mock_msg.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_with_queue_group(self, adapter, mock_client):
        """Test subscribing with queue group."""
        adapter._is_connected = True
        adapter._client = mock_client

        mock_sub = Mock()
        mock_client.subscribe.return_value = mock_sub

        async def handler(data):
            return data

        await adapter.subscribe("test.subject", handler, queue="test-queue")

        mock_client.subscribe.assert_called_once_with(
            "test.subject",
            queue="test-queue",
            cb=mock_client.subscribe.call_args[1]["cb"],
        )

    @pytest.mark.asyncio
    async def test_subscribe_handler_no_reply(self, adapter, mock_client):
        """Test handler without reply subject."""
        adapter._is_connected = True
        adapter._client = mock_client

        mock_sub = Mock()
        mock_client.subscribe.return_value = mock_sub

        async def handler(data):
            return {"result": "no-reply"}

        await adapter.subscribe("test.subject", handler)

        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        # Message without reply subject
        mock_msg = Mock()
        mock_msg.data = json.dumps({"test": "data"}).encode()
        mock_msg.reply = None
        mock_msg.respond = AsyncMock()

        await wrapped_handler(mock_msg)

        # Should not respond when no reply subject
        mock_msg.respond.assert_not_called()

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, adapter):
        """Test subscribing when not connected."""
        adapter._is_connected = False

        async def handler(data):
            return data

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.subscribe("test.subject", handler)

        assert "Not connected to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter):
        """Test unsubscribing from a subscription."""
        mock_sub = AsyncMock()
        adapter._subscriptions = {"test_sub_123": mock_sub}

        await adapter.unsubscribe("test_sub_123")

        mock_sub.unsubscribe.assert_called_once()
        assert "test_sub_123" not in adapter._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self, adapter):
        """Test unsubscribing from non-existent subscription."""
        # Should not raise error
        await adapter.unsubscribe("nonexistent")
        assert len(adapter._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_create_kv_bucket_new(self, adapter):
        """Test creating a new KV bucket."""
        adapter._jetstream = AsyncMock()
        mock_kv = Mock()
        adapter._jetstream.create_key_value.return_value = mock_kv

        result = await adapter.create_kv_bucket("test-bucket", ttl=3600)

        assert result == mock_kv
        adapter._jetstream.create_key_value.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_kv_bucket_exists(self, adapter):
        """Test creating KV bucket when it already exists."""
        adapter._jetstream = AsyncMock()

        # First call fails with "already exists"
        adapter._jetstream.create_key_value.side_effect = Exception("Bucket already exists")

        # Get existing bucket returns mock
        mock_kv = Mock()
        adapter._jetstream.key_value.return_value = mock_kv

        result = await adapter.create_kv_bucket("test-bucket")

        assert result == mock_kv
        adapter._jetstream.key_value.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_create_kv_bucket_no_jetstream(self, adapter):
        """Test creating KV bucket without JetStream."""
        adapter._jetstream = None

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.create_kv_bucket("test-bucket")

        assert "JetStream not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_kv_bucket_success(self, adapter):
        """Test getting existing KV bucket."""
        adapter._jetstream = AsyncMock()
        mock_kv = Mock()
        adapter._jetstream.key_value.return_value = mock_kv

        result = await adapter.get_kv_bucket("test-bucket")

        assert result == mock_kv
        adapter._jetstream.key_value.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_get_kv_bucket_not_found(self, adapter):
        """Test getting non-existent KV bucket."""
        adapter._jetstream = AsyncMock()
        adapter._jetstream.key_value.side_effect = Exception("Bucket not found")

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.get_kv_bucket("test-bucket")

        assert "Failed to get KV bucket test-bucket" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_kv_bucket_no_jetstream(self, adapter):
        """Test getting KV bucket without JetStream."""
        adapter._jetstream = None

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.get_kv_bucket("test-bucket")

        assert "JetStream not available" in str(exc_info.value)

    def test_is_connected_property(self, adapter, mock_client):
        """Test is_connected property."""
        # Not connected initially
        assert not adapter.is_connected

        # Set as connected but no client
        adapter._is_connected = True
        assert not adapter.is_connected

        # Set client but client not connected
        adapter._client = mock_client
        mock_client.is_connected = False
        assert not adapter.is_connected

        # All conditions met
        mock_client.is_connected = True
        assert adapter.is_connected

    def test_client_property(self, adapter, mock_client):
        """Test client property accessor."""
        assert adapter.client is None

        adapter._client = mock_client
        assert adapter.client == mock_client

    def test_jetstream_property(self, adapter):
        """Test jetstream property accessor."""
        assert adapter.jetstream is None

        mock_js = Mock()
        adapter._jetstream = mock_js
        assert adapter.jetstream == mock_js

    @pytest.mark.asyncio
    async def test_error_callback(self, adapter):
        """Test error callback handler."""
        error = Exception("Test error")

        # Should not raise, just log
        await adapter._error_callback(error)

    @pytest.mark.asyncio
    async def test_disconnected_callback(self, adapter):
        """Test disconnected callback handler."""
        adapter._is_connected = True

        await adapter._disconnected_callback()

        assert not adapter._is_connected

    @pytest.mark.asyncio
    async def test_reconnected_callback(self, adapter):
        """Test reconnected callback handler."""
        adapter._is_connected = False

        await adapter._reconnected_callback()

        assert adapter._is_connected

    @pytest.mark.asyncio
    async def test_closed_callback(self, adapter):
        """Test closed callback handler."""
        adapter._is_connected = True

        await adapter._closed_callback()

        assert not adapter._is_connected

    @pytest.mark.asyncio
    async def test_request_with_pydantic_model(self, adapter, mock_client):
        """Test request with Pydantic model as data."""
        adapter._is_connected = True
        adapter._client = mock_client

        model = TestModel(message="test", value=42)
        mock_msg = Mock()
        mock_msg.data = json.dumps({"success": True}).encode()
        mock_client.request.return_value = mock_msg

        result = await adapter.request("test.subject", model)

        assert result == {"success": True}
        mock_client.request.assert_called_once_with(
            "test.subject",
            model.model_dump_json().encode(),
            timeout=1.0,
        )

    @pytest.mark.asyncio
    async def test_request_with_list(self, adapter, mock_client):
        """Test request with list as data."""
        adapter._is_connected = True
        adapter._client = mock_client

        data = ["item1", "item2", "item3"]
        mock_msg = Mock()
        mock_msg.data = json.dumps({"count": 3}).encode()
        mock_client.request.return_value = mock_msg

        result = await adapter.request("test.subject", data)

        assert result == {"count": 3}

    @pytest.mark.asyncio
    async def test_subscribe_handler_with_binary_data(self, adapter, mock_client):
        """Test subscribe handler with binary data."""
        adapter._is_connected = True
        adapter._client = mock_client

        mock_sub = Mock()
        mock_client.subscribe.return_value = mock_sub

        received_data = None

        async def handler(data):
            nonlocal received_data
            received_data = data
            return None

        await adapter.subscribe("test.subject", handler)

        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        # Send binary data that's not JSON
        mock_msg = Mock()
        mock_msg.data = b"\x00\x01\x02\x03"
        mock_msg.reply = None

        await wrapped_handler(mock_msg)

        assert received_data == b"\x00\x01\x02\x03"

    @pytest.mark.asyncio
    async def test_subscribe_handler_response_types(self, adapter, mock_client):
        """Test different response types from handler."""
        adapter._is_connected = True
        adapter._client = mock_client

        mock_sub = Mock()
        mock_client.subscribe.return_value = mock_sub

        # Test with Pydantic model response
        async def handler_pydantic(data):
            return TestModel(message="response", value=100)

        await adapter.subscribe("test.pydantic", handler_pydantic)
        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        mock_msg = Mock()
        mock_msg.data = json.dumps({"test": "data"}).encode()
        mock_msg.reply = "reply.subject"
        mock_msg.respond = AsyncMock()

        await wrapped_handler(mock_msg)

        # Verify Pydantic model was serialized
        expected = TestModel(message="response", value=100).model_dump_json().encode()
        mock_msg.respond.assert_called_once_with(expected)

        # Test with dict response
        mock_msg.respond.reset_mock()

        async def handler_dict(data):
            return {"type": "dict", "data": data}

        await adapter.subscribe("test.dict", handler_dict)
        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        await wrapped_handler(mock_msg)
        mock_msg.respond.assert_called_once()

        # Test with string response
        mock_msg.respond.reset_mock()

        async def handler_string(data):
            return "simple string response"

        await adapter.subscribe("test.string", handler_string)
        wrapped_handler = mock_client.subscribe.call_args[1]["cb"]

        await wrapped_handler(mock_msg)
        mock_msg.respond.assert_called_once_with(b"simple string response")
