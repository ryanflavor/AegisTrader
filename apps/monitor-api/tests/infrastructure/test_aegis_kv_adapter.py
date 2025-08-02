"""Unit tests for AegisKVStoreAdapter infrastructure adapter.

These tests ensure the adapter properly implements the KVStorePort
interface while using AegisSDK's NATSAdapter.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import (
    ConcurrentUpdateException,
    KVStoreException,
)
from app.domain.models import ServiceDefinition
from app.infrastructure.aegis_kv_adapter import AegisKVStoreAdapter
from nats.js.errors import BucketNotFoundError, KeyNotFoundError
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
def mock_aegis_adapter() -> Mock:
    """Create a mock AegisSDK NATSAdapter."""
    mock = Mock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock._js = None  # Will be set in tests
    mock._connections = []  # Will be set in tests
    mock._metrics = Mock()
    mock._metrics.get_all = Mock(return_value={"test": "metrics"})
    return mock


@pytest.fixture
def adapter() -> AegisKVStoreAdapter:
    """Create an Aegis KV adapter instance."""
    return AegisKVStoreAdapter(bucket_name="test-bucket")


class TestAegisKVStoreAdapter:
    """Test cases for AegisKVStoreAdapter."""

    @pytest.mark.asyncio
    async def test_connect_creates_new_bucket_using_aegis_js(
        self,
        adapter: AegisKVStoreAdapter,
        mock_aegis_adapter: Mock,
        mock_jetstream: Mock,
        mock_kv: Mock,
    ) -> None:
        """Test connecting and creating a new bucket using AegisSDK's JetStream."""
        # Arrange
        mock_aegis_adapter._js = mock_jetstream
        mock_jetstream.key_value.side_effect = BucketNotFoundError()
        mock_jetstream.create_key_value.return_value = mock_kv

        with patch(
            "app.infrastructure.aegis_kv_adapter.NATSAdapter",
            return_value=mock_aegis_adapter,
        ):
            # Act
            await adapter.connect("nats://localhost:4222")

            # Assert
            assert adapter._adapter == mock_aegis_adapter
            assert adapter._js == mock_jetstream
            assert adapter._kv == mock_kv
            mock_aegis_adapter.connect.assert_called_once_with(["nats://localhost:4222"])
            mock_jetstream.create_key_value.assert_called_once()
            config = mock_jetstream.create_key_value.call_args[0][0]
            assert config.bucket == "test-bucket"
            assert config.description == "Service registry definitions"
            assert config.max_value_size == 1024 * 1024
            assert config.history == 10

    @pytest.mark.asyncio
    async def test_connect_fallback_to_connections(
        self,
        adapter: AegisKVStoreAdapter,
        mock_aegis_adapter: Mock,
        mock_nats_client: Mock,
        mock_jetstream: Mock,
        mock_kv: Mock,
    ) -> None:
        """Test connecting when AegisSDK doesn't expose _js but has _connections."""
        # Arrange
        mock_aegis_adapter._js = None  # No _js attribute
        mock_aegis_adapter._connections = [mock_nats_client]
        mock_nats_client.jetstream.return_value = mock_jetstream
        mock_jetstream.key_value.return_value = mock_kv

        with patch(
            "app.infrastructure.aegis_kv_adapter.NATSAdapter",
            return_value=mock_aegis_adapter,
        ):
            # Act
            await adapter.connect("nats://localhost:4222")

            # Assert
            assert adapter._js == mock_jetstream
            assert adapter._kv == mock_kv
            mock_nats_client.jetstream.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure_no_jetstream_access(
        self,
        adapter: AegisKVStoreAdapter,
        mock_aegis_adapter: Mock,
    ) -> None:
        """Test connection failure when AegisSDK doesn't provide JetStream access."""
        # Arrange
        mock_aegis_adapter._js = None
        mock_aegis_adapter._connections = []

        with patch(
            "app.infrastructure.aegis_kv_adapter.NATSAdapter",
            return_value=mock_aegis_adapter,
        ):
            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")
            assert "Unable to access NATS JetStream from AegisSDK" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter: AegisKVStoreAdapter, mock_aegis_adapter: Mock) -> None:
        """Test disconnecting using AegisSDK."""
        # Arrange
        adapter._adapter = mock_aegis_adapter

        # Act
        await adapter.disconnect()

        # Assert
        mock_aegis_adapter.disconnect.assert_called_once()

    def test_ensure_connected_raises_when_not_connected(self, adapter: AegisKVStoreAdapter) -> None:
        """Test that operations fail when not connected."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            adapter._ensure_connected()
        assert "Not connected to NATS KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_existing_key(
        self,
        adapter: AegisKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test getting an existing key."""
        # Arrange
        adapter._kv = mock_kv
        mock_kv.get.return_value = mock_kv_entry

        # Act
        result = await adapter.get("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"
        assert result.owner == "test-team"
        mock_kv.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_put_new_key(
        self,
        adapter: AegisKVStoreAdapter,
        mock_kv: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test putting a new key."""
        # Arrange
        adapter._kv = mock_kv
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
    async def test_update_with_revision_conflict_handling(
        self,
        adapter: AegisKVStoreAdapter,
        mock_kv: Mock,
        mock_kv_entry: Mock,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test concurrent update conflict detection."""
        # Arrange
        adapter._kv = mock_kv
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.update.side_effect = Exception("wrong last sequence")

        # Act & Assert
        with pytest.raises(ConcurrentUpdateException) as exc_info:
            await adapter.update("test-service", service_definition, revision=41)
        assert "test-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_existing_key(
        self, adapter: AegisKVStoreAdapter, mock_kv: Mock, mock_kv_entry: Mock
    ) -> None:
        """Test deleting an existing key."""
        # Arrange
        adapter._kv = mock_kv
        mock_kv.get.return_value = mock_kv_entry
        mock_kv.delete.return_value = None

        # Act
        await adapter.delete("test-service")

        # Assert
        mock_kv.get.assert_called_once_with("test-service")
        mock_kv.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_list_all_with_services(
        self, adapter: AegisKVStoreAdapter, mock_kv: Mock, mock_kv_entry: Mock
    ) -> None:
        """Test listing all services."""
        # Arrange
        adapter._kv = mock_kv
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
    async def test_get_metrics(
        self, adapter: AegisKVStoreAdapter, mock_aegis_adapter: Mock
    ) -> None:
        """Test getting metrics from AegisSDK adapter."""
        # Arrange
        adapter._adapter = mock_aegis_adapter
        expected_metrics = {"connections": 1, "messages": 100}
        mock_aegis_adapter._metrics.get_all.return_value = expected_metrics

        # Act
        result = adapter.get_metrics()

        # Assert
        assert result == expected_metrics
        mock_aegis_adapter._metrics.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_no_metrics_available(
        self, adapter: AegisKVStoreAdapter, mock_aegis_adapter: Mock
    ) -> None:
        """Test getting metrics when AegisSDK doesn't have metrics."""
        # Arrange
        adapter._adapter = mock_aegis_adapter
        delattr(mock_aegis_adapter, "_metrics")  # Remove _metrics attribute

        # Act
        result = adapter.get_metrics()

        # Assert
        assert result == {}
