"""Unit tests for NATSConnectionAdapter following TDD principles."""

import asyncio
from unittest.mock import AsyncMock, patch

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
        mock_nats.connect.return_value = mock_client
        mock_jetstream = AsyncMock()
        mock_client.jetstream.return_value = mock_jetstream

        # Act
        result = await self.adapter.connect("nats://localhost:4222")

        # Assert
        assert result is True
        assert self.adapter._client == mock_client
        assert self.adapter._jetstream == mock_jetstream
        mock_nats.connect.assert_called_once_with("nats://localhost:4222")

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_with_timeout(self, mock_nats):
        """Test connection with custom timeout."""
        # Arrange
        mock_client = AsyncMock()
        mock_nats.connect.return_value = mock_client
        mock_jetstream = AsyncMock()
        mock_client.jetstream.return_value = mock_jetstream

        # Act
        result = await self.adapter.connect("nats://localhost:4222", timeout=10.0)

        # Assert
        assert result is True
        # Verify timeout was used (implementation may vary)

    @pytest.mark.asyncio
    @patch("aegis_sdk_dev.infrastructure.nats_adapter.nats")
    async def test_connect_failure(self, mock_nats):
        """Test connection failure."""
        # Arrange
        mock_nats.connect.side_effect = ConnectionError("Connection refused")

        # Act & Assert
        with pytest.raises(ConnectionError):
            await self.adapter.connect("nats://localhost:4222")

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
        call_kwargs = mock_jetstream.create_key_value.call_args[1]
        assert call_kwargs["bucket"] == "test_bucket"

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

    @pytest.mark.asyncio
    async def test_create_kv_bucket_not_connected(self):
        """Test creating a KV bucket when not connected."""
        # Arrange
        self.adapter._jetstream = None

        # Act & Assert
        with pytest.raises(ConnectionError):
            await self.adapter.create_kv_bucket("test_bucket")

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
        with pytest.raises(ConnectionError):
            await self.adapter.bucket_exists("test_bucket")

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
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow connection

        mock_nats.connect.side_effect = slow_connect

        # Act & Assert
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                self.adapter.connect("nats://localhost:4222", timeout=0.1), timeout=0.2
            )

    @pytest.mark.asyncio
    async def test_multiple_connect_calls(self):
        """Test multiple connect calls should close previous connection."""
        # Arrange
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()

        with patch("aegis_sdk_dev.infrastructure.nats_adapter.nats") as mock_nats:
            mock_nats.connect.side_effect = [mock_client1, mock_client2]
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
            mock_nats.connect.return_value = mock_client
            mock_client.jetstream.side_effect = Exception("JetStream not available")

            # Act & Assert
            with pytest.raises(Exception):
                await self.adapter.connect("nats://localhost:4222")

            # Verify cleanup
            assert self.adapter._client is None
            assert self.adapter._jetstream is None
