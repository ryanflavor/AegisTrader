"""Unit tests for AegisSDKKVAdapter infrastructure adapter.

These tests ensure the adapter properly implements the ServiceRegistryKVStorePort
interface while using AegisSDK's NATSAdapter.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceDefinition
from app.infrastructure.aegis_sdk_kv_adapter import AegisSDKKVAdapter


@pytest.fixture
def service_definition() -> ServiceDefinition:
    """Create a test service definition."""
    now = datetime.now(UTC)
    return ServiceDefinition(
        service_name="test-service",
        owner="test-team",
        description="Test service",
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_aegis_adapter() -> Mock:
    """Create a mock AegisSDK NATSAdapter."""
    mock = Mock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    return mock


@pytest.fixture
def adapter() -> AegisSDKKVAdapter:
    """Create an Aegis KV adapter instance."""
    return AegisSDKKVAdapter()


class TestAegisSDKKVAdapter:
    """Test cases for AegisSDKKVAdapter."""

    @pytest.mark.asyncio
    async def test_connect_success(
        self,
        adapter: AegisSDKKVAdapter,
        mock_aegis_adapter: Mock,
    ) -> None:
        """Test connecting to NATS and initializing KV Store."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.connect = AsyncMock()

        with (
            patch(
                "app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter",
                return_value=mock_aegis_adapter,
            ),
            patch(
                "app.infrastructure.aegis_sdk_kv_adapter.NATSKVStore",
                return_value=mock_kv_store,
            ),
        ):
            # Act
            await adapter.connect("nats://localhost:4222")

            # Assert
            assert adapter._nats_adapter == mock_aegis_adapter
            assert adapter._kv_store == mock_kv_store
            assert adapter._connected is True
            mock_aegis_adapter.connect.assert_called_once_with(["nats://localhost:4222"])
            mock_kv_store.connect.assert_called_once_with("service-registry")

    @pytest.mark.asyncio
    async def test_connect_failure(
        self,
        adapter: AegisSDKKVAdapter,
        mock_aegis_adapter: Mock,
    ) -> None:
        """Test connection failure."""
        # Arrange
        mock_aegis_adapter.connect.side_effect = Exception("Connection failed")

        with patch(
            "app.infrastructure.aegis_sdk_kv_adapter.NATSAdapter",
            return_value=mock_aegis_adapter,
        ):
            # Act & Assert
            with pytest.raises(KVStoreException) as exc_info:
                await adapter.connect("nats://localhost:4222")
            assert "Failed to connect to NATS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter: AegisSDKKVAdapter) -> None:
        """Test disconnecting from NATS."""
        # Arrange
        mock_nats_adapter = Mock()
        mock_nats_adapter.disconnect = AsyncMock()
        mock_kv_store = Mock()
        mock_kv_store.disconnect = AsyncMock()

        adapter._nats_adapter = mock_nats_adapter
        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act
        await adapter.disconnect()

        # Assert
        mock_kv_store.disconnect.assert_called_once()
        mock_nats_adapter.disconnect.assert_called_once()
        assert adapter._connected is False

    def test_ensure_connected_raises_when_not_connected(self, adapter: AegisSDKKVAdapter) -> None:
        """Test that operations fail when not connected."""
        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            adapter._ensure_connected()
        assert "Not connected to NATS KV Store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_existing_key(
        self,
        adapter: AegisSDKKVAdapter,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test getting an existing key."""
        # Arrange
        mock_kv_store = Mock()
        mock_entry = Mock()
        mock_entry.value = service_definition.model_dump()
        mock_kv_store.get = AsyncMock(return_value=mock_entry)

        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act
        result = await adapter.get("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"
        assert result.owner == "test-team"
        mock_kv_store.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_put_new_key(
        self,
        adapter: AegisSDKKVAdapter,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test putting a new key."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.exists = AsyncMock(return_value=False)
        mock_kv_store.put = AsyncMock()

        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act
        await adapter.put("test-service", service_definition)

        # Assert
        mock_kv_store.exists.assert_called_once_with("test-service")
        mock_kv_store.put.assert_called_once_with("test-service", service_definition.to_iso_dict())

    @pytest.mark.asyncio
    async def test_update_with_revision_conflict_handling(
        self,
        adapter: AegisSDKKVAdapter,
        service_definition: ServiceDefinition,
    ) -> None:
        """Test concurrent update conflict detection."""
        # Arrange
        mock_kv_store = Mock()
        mock_entry = Mock()
        mock_entry.value = service_definition.model_dump()
        mock_kv_store.get = AsyncMock(return_value=mock_entry)
        mock_kv_store.put = AsyncMock(side_effect=ValueError("revision check failed"))

        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await adapter.update("test-service", service_definition, revision=41)
        assert "Revision mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, adapter: AegisSDKKVAdapter) -> None:
        """Test deleting an existing key."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.exists = AsyncMock(return_value=True)
        mock_kv_store.delete = AsyncMock()

        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act
        await adapter.delete("test-service")

        # Assert
        mock_kv_store.exists.assert_called_once_with("test-service")
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_list_all_with_services(
        self, adapter: AegisSDKKVAdapter, service_definition: ServiceDefinition
    ) -> None:
        """Test listing all services."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.keys = AsyncMock(return_value=["service1", "service2"])
        mock_entry = Mock()
        mock_entry.value = service_definition.model_dump()
        mock_kv_store.get = AsyncMock(return_value=mock_entry)

        adapter._kv_store = mock_kv_store
        adapter._connected = True

        # Act
        result = await adapter.list_all()

        # Assert
        assert len(result) == 2
        assert all(s.service_name == "test-service" for s in result)
        mock_kv_store.keys.assert_called_once()
        assert mock_kv_store.get.call_count == 2
