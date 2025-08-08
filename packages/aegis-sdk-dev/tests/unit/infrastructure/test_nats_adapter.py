"""Unit tests for NATSConnectionAdapter following TDD principles."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter
from aegis_sdk_dev.ports.nats import NATSConnectionPort


class TestNATSConnectionAdapter:
    """Test NATSConnectionAdapter implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = NATSConnectionAdapter()

    def test_implements_nats_connection_port(self):
        """Test that NATSConnectionAdapter implements NATSConnectionPort interface."""
        # Assert
        assert isinstance(self.adapter, NATSConnectionPort)

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_success(self, mock_nats):
        """Test successful connection to NATS server."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True

        # Make connect return a coroutine that returns the mock_client
        async def async_connect(*args, **kwargs):
            return mock_client

        mock_nats.connect = async_connect

        mock_jetstream = AsyncMock()
        mock_client.jetstream = Mock(return_value=mock_jetstream)

        # Act
        result = await self.adapter.connect("nats://localhost:4222")

        # Assert
        assert result is True
        assert self.adapter._client == mock_client
        assert self.adapter._jetstream == mock_jetstream

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_with_timeout(self, mock_nats):
        """Test connection with custom timeout."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True

        async def async_connect(*args, **kwargs):
            return mock_client

        mock_nats.connect = async_connect

        mock_jetstream = AsyncMock()
        mock_client.jetstream = Mock(return_value=mock_jetstream)

        # Act
        result = await self.adapter.connect("nats://localhost:4222", timeout=10.0)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_failure(self, mock_nats):
        """Test connection failure."""

        # Arrange
        async def async_fail(*args, **kwargs):
            raise Exception("Connection refused")

        mock_nats.connect = async_fail

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await self.adapter.connect("nats://localhost:4222")
        assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self):
        """Test disconnecting when connected."""
        # Arrange
        mock_client = AsyncMock()
        self.adapter._client = mock_client

        # Act
        await self.adapter.disconnect()

        # Assert
        mock_client.close.assert_called_once()
        assert self.adapter._client is None
        assert self.adapter._jetstream is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test disconnecting when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        await self.adapter.disconnect()  # Should not raise

        # Assert
        assert self.adapter._client is None

    @pytest.mark.asyncio
    async def test_is_connected_true(self):
        """Test checking connection status when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True
        self.adapter._client = mock_client

        # Act
        result = await self.adapter.is_connected()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_connected_false_no_client(self):
        """Test checking connection status when no client."""
        # Arrange
        self.adapter._client = None

        # Act
        result = await self.adapter.is_connected()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_connected_false_disconnected(self):
        """Test checking connection status when client is disconnected."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = False
        self.adapter._client = mock_client

        # Act
        result = await self.adapter.is_connected()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_get_server_info_connected(self):
        """Test getting server info when connected."""
        # Arrange
        mock_client = AsyncMock()
        server_info = {
            "server_id": "test_server",
            "version": "2.10.0",
            "proto": 1,
            "go": "go1.20",
        }
        mock_client.server_info = server_info
        mock_client.is_connected = True
        self.adapter._client = mock_client

        # Act
        result = await self.adapter.get_server_info()

        # Assert
        assert result == server_info

    @pytest.mark.asyncio
    async def test_get_server_info_not_connected(self):
        """Test getting server info when not connected."""
        # Arrange
        self.adapter._client = None

        # Act & Assert
        with pytest.raises(ConnectionError):
            await self.adapter.get_server_info()

    @pytest.mark.asyncio
    async def test_create_kv_bucket_success(self):
        """Test creating a KV bucket successfully."""
        # Arrange
        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_jetstream.create_key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.create_kv_bucket("test_bucket")

        # Assert
        assert result is True
        mock_jetstream.create_key_value.assert_called_once()
        # Check that a config object was passed
        call_args = mock_jetstream.create_key_value.call_args[0]
        assert len(call_args) == 1
        config = call_args[0]
        assert hasattr(config, "bucket")
        assert config.bucket == "test_bucket"

    @pytest.mark.asyncio
    async def test_create_kv_bucket_already_exists(self):
        """Test creating a KV bucket that already exists."""
        # Arrange
        mock_jetstream = AsyncMock()
        # Simulate bucket already exists error
        mock_jetstream.create_key_value.side_effect = Exception("bucket already exists")
        mock_jetstream.key_value.return_value = AsyncMock()  # Fallback to get existing
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.create_kv_bucket("test_bucket")

        # Assert
        assert result is True  # Should still return True for existing bucket
        mock_jetstream.key_value.assert_called_once_with("test_bucket")

    @pytest.mark.asyncio
    async def test_create_kv_bucket_not_connected(self):
        """Test creating a KV bucket when not connected."""
        # Arrange
        self.adapter._jetstream = None

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await self.adapter.create_kv_bucket("test_bucket")
        assert "Not connected to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_bucket_exists_true(self):
        """Test checking if bucket exists (true case)."""
        # Arrange
        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_jetstream.key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.bucket_exists("test_bucket")

        # Assert
        assert result is True
        mock_jetstream.key_value.assert_called_once_with("test_bucket")

    @pytest.mark.asyncio
    async def test_bucket_exists_false(self):
        """Test checking if bucket exists (false case)."""
        # Arrange
        mock_jetstream = AsyncMock()
        mock_jetstream.key_value.side_effect = Exception("bucket not found")
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.bucket_exists("test_bucket")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_bucket_exists_not_connected(self):
        """Test checking if bucket exists when not connected."""
        # Arrange
        self.adapter._jetstream = None

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await self.adapter.bucket_exists("test_bucket")
        assert "Not connected to NATS" in str(exc_info.value)

    def test_nats_adapter_initial_state(self):
        """Test that NATSConnectionAdapter starts with no connection."""
        # Arrange
        adapter = NATSConnectionAdapter()

        # Assert
        assert adapter._client is None
        assert adapter._jetstream is None

    @pytest.mark.asyncio
    async def test_connect_invalid_url_format(self):
        """Test connection with invalid URL format."""
        # Arrange
        invalid_url = "invalid://url"

        # Act & Assert
        with pytest.raises(ConnectionError):
            await self.adapter.connect(invalid_url)

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_timeout_exceeded(self, mock_nats):
        """Test connection timeout."""

        # Arrange
        async def timeout_connect(*args, **kwargs):
            raise asyncio.TimeoutError("Connection timeout")

        mock_nats.connect = timeout_connect

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            await self.adapter.connect("nats://localhost:4222", timeout=0.1)
        assert "Connection timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_connect_calls(self):
        """Test multiple connect calls should close previous connection."""
        # Arrange
        mock_client1 = AsyncMock()
        mock_client1.is_connected = True
        mock_client2 = AsyncMock()
        mock_client2.is_connected = True

        with patch("aegis_sdk_dev.infrastructure.nats_adapter.nats") as mock_nats:
            clients = [mock_client1, mock_client2]

            async def connect_sequence(*args, **kwargs):
                return clients.pop(0)

            mock_nats.connect = connect_sequence

            mock_client1.jetstream.return_value = AsyncMock()
            mock_client2.jetstream.return_value = AsyncMock()

            # Act
            await self.adapter.connect("nats://localhost:4222")
            first_client = self.adapter._client

            await self.adapter.connect("nats://localhost:4223")
            second_client = self.adapter._client

            # Assert
            assert first_client != second_client
            mock_client1.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_adapter_cleanup_on_error(self):
        """Test that adapter cleans up properly on connection error."""
        # Arrange
        with patch("aegis_sdk_dev.infrastructure.nats_adapter.nats") as mock_nats:
            mock_client = AsyncMock()

            async def async_connect(*args, **kwargs):
                return mock_client

            mock_nats.connect = async_connect

            # Make jetstream() raise an exception
            def raise_error():
                raise Exception("JetStream not available")

            mock_client.jetstream = raise_error

            # Act & Assert
            with pytest.raises(ConnectionError) as exc_info:
                await self.adapter.connect("nats://localhost:4222")

            # Verify cleanup
            assert self.adapter._client is None
            assert self.adapter._jetstream is None
            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_kv_put_connected(self):
        """Test putting a value in KV store when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True
        self.adapter._client = mock_client

        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_jetstream.key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        test_value = {"key": "value"}

        # Act
        await self.adapter.kv_put("test_bucket", "test_key", test_value)

        # Assert
        mock_jetstream.key_value.assert_called_once_with("test_bucket")
        mock_kv.put.assert_called_once()
        call_args = mock_kv.put.call_args[0]
        assert call_args[0] == "test_key"
        assert json.loads(call_args[1].decode()) == test_value

    @pytest.mark.asyncio
    async def test_kv_put_not_connected(self):
        """Test putting a value in KV store when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        await self.adapter.kv_put("test_bucket", "test_key", {"key": "value"})

        # Assert - should return without error
        assert True  # No exception raised

    @pytest.mark.asyncio
    async def test_kv_get_connected(self):
        """Test getting a value from KV store when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True
        self.adapter._client = mock_client

        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_entry = Mock()
        test_value = {"key": "value"}
        mock_entry.value = json.dumps(test_value).encode()
        mock_kv.get.return_value = mock_entry
        mock_jetstream.key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.kv_get("test_bucket", "test_key")

        # Assert
        assert result == test_value
        mock_jetstream.key_value.assert_called_once_with("test_bucket")
        mock_kv.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_kv_get_not_connected(self):
        """Test getting a value from KV store when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        result = await self.adapter.kv_get("test_bucket", "test_key")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_kv_get_key_not_found(self):
        """Test getting a non-existent key from KV store."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True
        self.adapter._client = mock_client

        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_kv.get.side_effect = Exception("key not found")
        mock_jetstream.key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        # Act
        result = await self.adapter.kv_get("test_bucket", "test_key")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_kv_delete_connected(self):
        """Test deleting a value from KV store when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.is_connected = True
        self.adapter._client = mock_client

        mock_jetstream = AsyncMock()
        mock_kv = AsyncMock()
        mock_jetstream.key_value.return_value = mock_kv
        self.adapter._jetstream = mock_jetstream

        # Act
        await self.adapter.kv_delete("test_bucket", "test_key")

        # Assert
        mock_jetstream.key_value.assert_called_once_with("test_bucket")
        mock_kv.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_kv_delete_not_connected(self):
        """Test deleting a value from KV store when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        await self.adapter.kv_delete("test_bucket", "test_key")

        # Assert - should return without error
        assert True  # No exception raised

    @pytest.mark.asyncio
    async def test_publish_connected(self):
        """Test publishing a message when connected."""
        # Arrange
        mock_client = AsyncMock()
        self.adapter._client = mock_client
        test_data = b"test message"

        # Act
        await self.adapter.publish("test.subject", test_data)

        # Assert
        mock_client.publish.assert_called_once_with("test.subject", test_data)

    @pytest.mark.asyncio
    async def test_publish_not_connected(self):
        """Test publishing a message when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        await self.adapter.publish("test.subject", b"test message")

        # Assert - should not raise exception
        assert True

    @pytest.mark.asyncio
    async def test_subscribe_connected(self):
        """Test subscribing to a subject when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_subscription = AsyncMock()
        mock_client.subscribe.return_value = mock_subscription
        self.adapter._client = mock_client

        mock_callback = Mock()

        # Act
        result = await self.adapter.subscribe("test.subject", cb=mock_callback)

        # Assert
        assert result == mock_subscription
        mock_client.subscribe.assert_called_once_with("test.subject", cb=mock_callback)

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self):
        """Test subscribing when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        result = await self.adapter.subscribe("test.subject")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_request_connected(self):
        """Test sending a request when connected."""
        # Arrange
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.request.return_value = mock_response
        self.adapter._client = mock_client

        test_data = b"test request"

        # Act
        result = await self.adapter.request("test.subject", test_data, timeout=2.0)

        # Assert
        assert result == mock_response
        mock_client.request.assert_called_once_with("test.subject", test_data, timeout=2.0)

    @pytest.mark.asyncio
    async def test_request_not_connected(self):
        """Test sending a request when not connected."""
        # Arrange
        self.adapter._client = None

        # Act
        result = await self.adapter.request("test.subject", b"test request")

        # Assert
        assert result is None
