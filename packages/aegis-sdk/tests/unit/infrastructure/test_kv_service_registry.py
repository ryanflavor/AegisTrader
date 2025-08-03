"""Unit tests for KV-based service registry implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.domain.exceptions import KVStoreError
from aegis_sdk.domain.models import KVOptions, ServiceInstance
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store."""
    mock = AsyncMock()
    mock.get = AsyncMock()
    mock.put = AsyncMock()
    mock.delete = AsyncMock()
    mock.keys = AsyncMock()
    return mock


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    mock = AsyncMock()
    mock.info = AsyncMock()
    mock.warning = AsyncMock()
    mock.error = AsyncMock()
    return mock


@pytest.fixture
def sample_instance():
    """Create a sample service instance."""
    return ServiceInstance(
        service_name="test-service",
        instance_id="test-123",
        version="1.0.0",
        status="ACTIVE",
    )


class TestKVServiceRegistry:
    """Test cases for KV-based service registry."""

    @pytest.mark.asyncio
    async def test_register_success(self, mock_kv_store, mock_logger, sample_instance):
        """Test successful service registration."""
        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        await registry.register(sample_instance, ttl_seconds=30)

        # Verify KV store was called
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args

        # Check key format
        assert call_args[0][0] == "service-instances.test-service.test-123"

        # Check data includes camelCase fields
        data = call_args[0][1]
        assert data["serviceName"] == "test-service"
        assert data["instanceId"] == "test-123"
        assert data["version"] == "1.0.0"
        assert data["status"] == "ACTIVE"

        # Check TTL option
        options = call_args.kwargs["options"]
        assert isinstance(options, KVOptions)
        assert options.ttl == 30

        # Check logging
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_failure(self, mock_kv_store, mock_logger, sample_instance):
        """Test registration failure handling."""
        mock_kv_store.put.side_effect = Exception("KV error")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        with pytest.raises(KVStoreError) as exc_info:
            await registry.register(sample_instance, ttl_seconds=30)

        assert "Failed to register instance" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_heartbeat_success(self, mock_kv_store, sample_instance):
        """Test successful heartbeat update."""
        # Mock existing entry
        entry = MagicMock()
        entry.value = {"test": "data"}
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        await registry.update_heartbeat(sample_instance, ttl_seconds=30)

        # Verify get and put were called
        mock_kv_store.get.assert_called_once_with("service-instances.test-service.test-123")
        mock_kv_store.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_heartbeat_missing_entry(self, mock_kv_store, sample_instance):
        """Test heartbeat update when entry is missing."""
        mock_kv_store.get.return_value = None

        registry = KVServiceRegistry(mock_kv_store)

        await registry.update_heartbeat(sample_instance, ttl_seconds=30)

        # Should re-register
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "service-instances.test-service.test-123"

    @pytest.mark.asyncio
    async def test_deregister_success(self, mock_kv_store, mock_logger):
        """Test successful deregistration."""
        mock_kv_store.delete.return_value = True

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        await registry.deregister("test-service", "test-123")

        mock_kv_store.delete.assert_called_once_with("service-instances.test-service.test-123")
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_deregister_not_found(self, mock_kv_store, mock_logger):
        """Test deregistration when instance not found."""
        mock_kv_store.delete.return_value = False

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        await registry.deregister("test-service", "test-123")

        mock_kv_store.delete.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance_found(self, mock_kv_store):
        """Test getting an existing instance."""
        # Mock KV entry with camelCase data
        entry = MagicMock()
        entry.value = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
            "metadata": {"key": "value"},
        }
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")

        assert instance is not None
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        assert instance.version == "1.0.0"
        assert instance.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_get_instance_snake_case(self, mock_kv_store):
        """Test getting instance with snake_case data."""
        # Mock KV entry with snake_case data
        entry = MagicMock()
        entry.value = {
            "service_name": "test-service",
            "instance_id": "test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": "2025-01-01T00:00:00Z",
        }
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")

        assert instance is not None
        assert instance.service_name == "test-service"

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, mock_kv_store):
        """Test getting non-existent instance."""
        mock_kv_store.get.return_value = None

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")

        assert instance is None

    @pytest.mark.asyncio
    async def test_list_instances(self, mock_kv_store):
        """Test listing service instances."""
        # Mock keys
        mock_kv_store.keys.return_value = [
            "service-instances.test-service.inst-1",
            "service-instances.test-service.inst-2",
        ]

        # Mock get calls for each instance
        entry1 = MagicMock()
        entry1.value = {
            "serviceName": "test-service",
            "instanceId": "inst-1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        entry2 = MagicMock()
        entry2.value = {
            "serviceName": "test-service",
            "instanceId": "inst-2",
            "version": "1.0.0",
            "status": "STANDBY",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        mock_kv_store.get.side_effect = [entry1, entry2]

        registry = KVServiceRegistry(mock_kv_store)

        instances = await registry.list_instances("test-service")

        assert len(instances) == 2
        assert instances[0].instance_id == "inst-1"
        assert instances[0].status == "ACTIVE"
        assert instances[1].instance_id == "inst-2"
        assert instances[1].status == "STANDBY"

    @pytest.mark.asyncio
    async def test_list_all_services(self, mock_kv_store):
        """Test listing all services."""
        # Mock keys for different services
        mock_kv_store.keys.return_value = [
            "service-instances.service-a.inst-1",
            "service-instances.service-a.inst-2",
            "service-instances.service-b.inst-1",
        ]

        # Mock get calls
        entry_a1 = MagicMock()
        entry_a1.value = {
            "serviceName": "service-a",
            "instanceId": "inst-1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        entry_a2 = MagicMock()
        entry_a2.value = {
            "serviceName": "service-a",
            "instanceId": "inst-2",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        entry_b1 = MagicMock()
        entry_b1.value = {
            "serviceName": "service-b",
            "instanceId": "inst-1",
            "version": "2.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        mock_kv_store.get.side_effect = [entry_a1, entry_a2, entry_b1]

        registry = KVServiceRegistry(mock_kv_store)

        all_services = await registry.list_all_services()

        assert len(all_services) == 2
        assert "service-a" in all_services
        assert "service-b" in all_services
        assert len(all_services["service-a"]) == 2
        assert len(all_services["service-b"]) == 1

    @pytest.mark.asyncio
    async def test_error_handling_without_logger(self, mock_kv_store):
        """Test error handling when logger is not provided."""
        mock_kv_store.put.side_effect = Exception("KV error")

        registry = KVServiceRegistry(mock_kv_store)  # No logger

        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
        )

        # Should still raise error
        with pytest.raises(KVStoreError):
            await registry.register(instance, ttl_seconds=30)
