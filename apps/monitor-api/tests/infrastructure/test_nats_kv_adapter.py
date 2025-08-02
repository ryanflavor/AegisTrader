"""Unit tests for NATSKVStoreAdapter infrastructure adapter.

These tests ensure the adapter properly implements the KVStorePort
interface and handles NATS-specific concerns.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import (
    ConcurrentUpdateException,
    KVStoreException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
)
from app.domain.models import ServiceDefinition
from app.infrastructure.nats_kv_adapter import NATSKVStoreAdapter
from nats.js.errors import BucketNotFoundError, KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue


@pytest.fixture
def service_definition() -> ServiceDefinition:
    """Create a test service definition."""
    now = datetime.now(UTC).isoformat()
    return ServiceDefinition(
        service_name="test-service",
        owner="test-team",
        description="Test service",
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_kv_entry() -> Mock:
    """Create a mock KV entry."""
    entry = Mock()
    entry.value = (
        b'{"service_name": "test-service", "owner": "test-team", '
        b'"description": "Test service", "version": "1.0.0", '
        b'"created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}'
    )
    entry.revision = 42
    return entry


@pytest.fixture
def mock_kv() -> Mock:
    """Create a mock KeyValue instance."""
    mock = Mock(spec=KeyValue)
    mock.get = AsyncMock()
    mock.put = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.keys = AsyncMock()
    return mock


@pytest.fixture
def mock_jetstream() -> Mock:
    """Create a mock JetStream context."""
    mock = Mock()
    mock.key_value = AsyncMock()
    mock.create_key_value = AsyncMock()
    return mock


@pytest.fixture
def mock_nats_client() -> Mock:
    """Create a mock NATS client."""
    mock = Mock()
    mock.jetstream = Mock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def adapter() -> NATSKVStoreAdapter:
    """Create a NATS KV adapter instance."""
    return NATSKVStoreAdapter(bucket_name="test-bucket")


class TestNATSKVStoreAdapter:
    """Test cases for NATSKVStoreAdapter."""

    @pytest.mark.asyncio
    async def test_connect_creates_new_bucket(
        self,
        adapter: NATSKVStoreAdapter,
        mock_nats_client: Mock,
        mock_jetstream: Mock,
        mock_kv: Mock,
    ) -> None:
        """Test connecting and creating a new bucket when it doesn't exist."""
        # Arrange
        mock_nats_client.jetstream.return_value = mock_jetstream
        mock_jetstream.key_value.side_effect = BucketNotFoundError()
        mock_jetstream.create_key_value.return_value = mock_kv

        with patch(
            "app.infrastructure.nats_kv_adapter.nats.connect",
            AsyncMock(return_value=mock_nats_client),
        ):
            # Act
            await adapter.connect("nats://localhost:4222")

            # Assert
            assert adapter._nc == mock_nats_client
            assert adapter._js == mock_jetstream
            assert adapter._kv == mock_kv
            mock_jetstream.create_key_value.assert_called_once()
            config = mock_jetstream.create_key_value.call_args[0][0]
            assert config.bucket == "test-bucket"
            assert config.description == "Service registry definitions"
            assert config.max_value_size == 1024 * 1024
            assert config.history == 10

    @pytest.mark.asyncio
    async def test_connect_uses_existing_bucket(
        self,
        adapter: NATSKVStoreAdapter,
        mock_nats_client: Mock,
        mock_jetstream: Mock,
        mock_kv: Mock,
    ) -> None:
        """Test connecting and using an existing bucket."""
        # Arrange
        mock_nats_client.jetstream.return_value = mock_jetstream
        mock_jetstream.key_value.return_value = mock_kv

        with patch(
            "app.infrastructure.nats_kv_adapter.nats.connect",
            AsyncMock(return_value=mock_nats_client),
        ):
            # Act
            await adapter.connect("nats://localhost:4222")

            # Assert
            assert adapter._kv == mock_kv
            mock_jetstream.key_value.assert_called_once_with("test-bucket")
            mock_jetstream.create_key_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter: NATSKVStoreAdapter) -> None:
        """Test connection failure handling."""
        # Arrange
        with patch(
            "app.infrastructure.nats_kv_adapter.nats.connect",
            AsyncMock(side_effect=Exception("Connection failed")),
        ):
            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")
            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter: NATSKVStoreAdapter, mock_nats_client: Mock) -> None:
        """Test disconnecting from NATS."""
        # Arrange
        adapter._nc = mock_nats_client

        # Act
        await adapter.disconnect()

        # Assert
        mock_nats_client.close.assert_called_once()

    def test_ensure_connected_raises_when_not_connected(self, adapter: NATSKVStoreAdapter) -> None:
        """Test that operations fail when not connected."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            adapter._ensure_connected()
        assert "Not connected to NATS KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_existing_key(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test getting an existing key."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()  # Mark as connected
        mock_kv.get.return_value = mock_kv_entry

        # Act
        result = await adapter.get("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"
        assert result.owner == "test-team"
        mock_kv.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_non_existent_key(self, adapter: NATSKVStoreAdapter, mock_kv: Mock) -> None:
        """Test getting a non-existent key returns None."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = KeyNotFoundError()

        # Act
        result = await adapter.get("non-existent")

        # Assert
        assert result is None
        mock_kv.get.assert_called_once_with("non-existent")

    @pytest.mark.asyncio
    async def test_get_error_handling(self, adapter: NATSKVStoreAdapter, mock_kv: Mock) -> None:
        """Test error handling in get operation."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await adapter.get("test-service")
        assert "Failed to get key 'test-service'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_put_new_key(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test putting a new key."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = KeyNotFoundError()  # Key doesn't exist
        mock_kv.put.return_value = None

        # Act
        await adapter.put("test-service", service_definition)

        # Assert
        mock_kv.get.assert_called_once_with("test-service")
        mock_kv.put.assert_called_once()
        put_data = mock_kv.put.call_args[0][1]
        assert service_definition.model_dump_json().encode() == put_data

    @pytest.mark.asyncio
    async def test_put_existing_key_raises_error(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test putting an existing key raises ServiceAlreadyExistsException."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry  # Key exists

        # Act & Assert
        with pytest.raises(ServiceAlreadyExistsException) as exc_info:
            await adapter.put("test-service", service_definition)
        assert "test-service" in str(exc_info.value)
        mock_kv.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_existing_key(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test updating an existing key."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.put.return_value = None

        # Act
        await adapter.update("test-service", service_definition)

        # Assert
        mock_kv.get.assert_called_once_with("test-service")
        mock_kv.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_revision(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test updating with optimistic locking using revision."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.update.return_value = None

        # Act
        await adapter.update("test-service", service_definition, revision=42)

        # Assert
        mock_kv.get.assert_called_once_with("test-service")
        mock_kv.update.assert_called_once()
        update_args = mock_kv.update.call_args[0]
        assert update_args[0] == "test-service"
        assert update_args[2] == 42

    @pytest.mark.asyncio
    async def test_update_non_existent_key(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test updating a non-existent key raises ServiceNotFoundException."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = KeyNotFoundError()

        # Act & Assert
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await adapter.update("non-existent", service_definition)
        assert "non-existent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_concurrent_conflict(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test concurrent update conflict detection."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.update.side_effect = Exception("wrong last sequence")

        # Act & Assert
        with pytest.raises(ConcurrentUpdateException) as exc_info:
            await adapter.update("test-service", service_definition, revision=41)
        assert "test-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_existing_key(
        self, adapter: NATSKVStoreAdapter, mock_kv: Mock, mock_kv_entry: Mock
    ) -> None:
        """Test deleting an existing key."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.delete.return_value = None

        # Act
        await adapter.delete("test-service")

        # Assert
        mock_kv.get.assert_called_once_with("test-service")
        mock_kv.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_delete_non_existent_key(
        self, adapter: NATSKVStoreAdapter, mock_kv: Mock
    ) -> None:
        """Test deleting a non-existent key raises ServiceNotFoundException."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = KeyNotFoundError()

        # Act & Assert
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await adapter.delete("non-existent")
        assert "non-existent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_all_with_services(
        self, adapter: NATSKVStoreAdapter, mock_kv: Mock, mock_kv_entry: Mock
    ) -> None:
        """Test listing all services."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.keys.return_value = ["service1", "service2"]
        mock_kv.get.return_value = mock_kv_entry

        # Act
        result = await adapter.list_all()

        # Assert
        assert len(result) == 2
        assert all(s.service_name == "test-service" for s in result)
        mock_kv.keys.assert_called_once()
        assert mock_kv.get.call_count == 2

    @pytest.mark.asyncio
    async def test_list_all_empty(self, adapter: NATSKVStoreAdapter, mock_kv: Mock) -> None:
        """Test listing all when no services exist."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.keys.side_effect = NoKeysError()

        # Act
        result = await adapter.list_all()

        # Assert
        assert result == []
        mock_kv.keys.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_revision(
        self,
        adapter: NATSKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
    ) -> None:
        """Test getting a key with its revision."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.return_value = mock_kv_entry

        # Act
        service, revision = await adapter.get_with_revision("test-service")

        # Assert
        assert service is not None
        assert service.service_name == "test-service"
        assert revision == 42
        mock_kv.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_with_revision_not_found(
        self, adapter: NATSKVStoreAdapter, mock_kv: Mock
    ) -> None:
        """Test getting a non-existent key with revision returns None."""
        # Arrange
        adapter._kv = mock_kv
        adapter._nc = Mock()
        mock_kv.get.side_effect = KeyNotFoundError()

        # Act
        service, revision = await adapter.get_with_revision("non-existent")

        # Assert
        assert service is None
        assert revision is None
