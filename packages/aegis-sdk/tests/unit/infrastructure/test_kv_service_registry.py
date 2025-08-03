"""Unit tests for KV-based service registry implementation."""

import asyncio
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

    @pytest.mark.asyncio
    async def test_register_invalid_ttl(self, mock_kv_store, sample_instance):
        """Test registration with invalid TTL value."""
        registry = KVServiceRegistry(mock_kv_store)

        # Zero TTL
        with pytest.raises(ValueError) as exc_info:
            await registry.register(sample_instance, ttl_seconds=0)
        assert "TTL must be positive" in str(exc_info.value)

        # Negative TTL
        with pytest.raises(ValueError) as exc_info:
            await registry.register(sample_instance, ttl_seconds=-10)
        assert "TTL must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_heartbeat_kv_store_error(
        self, mock_kv_store, mock_logger, sample_instance
    ):
        """Test heartbeat update with KVStoreError."""
        # Make get raise KVStoreError
        mock_kv_store.get.side_effect = KVStoreError(
            "KV connection lost", operation="get", key="test"
        )

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        with pytest.raises(KVStoreError):
            await registry.update_heartbeat(sample_instance, ttl_seconds=30)

    @pytest.mark.asyncio
    async def test_update_heartbeat_generic_error(
        self, mock_kv_store, mock_logger, sample_instance
    ):
        """Test heartbeat update with generic error."""
        # Make get raise generic exception
        mock_kv_store.get.side_effect = Exception("Network error")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        with pytest.raises(KVStoreError) as exc_info:
            await registry.update_heartbeat(sample_instance, ttl_seconds=30)

        assert "Failed to update heartbeat" in str(exc_info.value)
        mock_logger.warning.assert_called_once()
        assert "Failed to update heartbeat" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_heartbeat_re_register_with_logger(
        self, mock_kv_store, mock_logger, sample_instance
    ):
        """Test heartbeat update re-registration with logger."""
        # Entry doesn't exist
        mock_kv_store.get.return_value = None

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        await registry.update_heartbeat(sample_instance, ttl_seconds=30)

        # Should log re-registration
        await asyncio.sleep(0)  # Allow async logger call to complete
        assert mock_logger.info.called
        # Check if the log message was about re-registration
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Re-registering lost service instance" in call for call in info_calls)

    @pytest.mark.asyncio
    async def test_deregister_error_handling(self, mock_kv_store, mock_logger):
        """Test deregistration error handling."""
        mock_kv_store.delete.side_effect = Exception("Delete failed")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        with pytest.raises(KVStoreError) as exc_info:
            await registry.deregister("test-service", "test-123")

        assert "Failed to deregister instance" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance_error_handling(self, mock_kv_store, mock_logger):
        """Test get_instance error handling."""
        mock_kv_store.get.side_effect = Exception("Get failed")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        # Should return None on error
        instance = await registry.get_instance("test-service", "test-123")
        assert instance is None

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Failed to get service instance" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_instance_invalid_data_type(self, mock_kv_store):
        """Test get_instance with non-dict value."""
        # Mock entry with non-dict value
        entry = MagicMock()
        entry.value = "not a dict"
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")
        assert instance is None

    @pytest.mark.asyncio
    async def test_get_instance_mixed_case_fields(self, mock_kv_store):
        """Test get_instance with mixed camelCase and snake_case fields."""
        entry = MagicMock()
        entry.value = {
            "serviceName": "test-service",
            "instance_id": "test-123",  # Mixed: snake_case
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
            "sticky_active_group": "primary",  # Mixed: snake_case
        }
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")

        assert instance is not None
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        assert instance.sticky_active_group == "primary"

    @pytest.mark.asyncio
    async def test_list_instances_error_handling(self, mock_kv_store, mock_logger):
        """Test list_instances error handling."""
        mock_kv_store.keys.side_effect = Exception("Keys failed")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        # Should return empty list on error
        instances = await registry.list_instances("test-service")
        assert instances == []

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Failed to list service instances" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_instances_invalid_key_format(self, mock_kv_store):
        """Test list_instances with invalid key format."""
        # Mock keys with invalid format
        mock_kv_store.keys.return_value = [
            "service-instances.test-service",  # Missing instance ID
            "invalid-key",  # Completely invalid
            "service-instances.test-service.valid-instance",  # Valid
        ]

        # Only mock the valid instance
        entry = MagicMock()
        entry.value = {
            "serviceName": "test-service",
            "instanceId": "valid-instance",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instances = await registry.list_instances("test-service")

        # Should only return the valid instance
        assert len(instances) == 1
        assert instances[0].instance_id == "valid-instance"

    @pytest.mark.asyncio
    async def test_list_instances_get_failure(self, mock_kv_store):
        """Test list_instances when get_instance fails."""
        # Mock keys
        mock_kv_store.keys.return_value = [
            "service-instances.test-service.inst-1",
            "service-instances.test-service.inst-2",
        ]

        # First get succeeds, second fails
        entry1 = MagicMock()
        entry1.value = {
            "serviceName": "test-service",
            "instanceId": "inst-1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }
        mock_kv_store.get.side_effect = [entry1, Exception("Get failed")]

        registry = KVServiceRegistry(mock_kv_store)

        instances = await registry.list_instances("test-service")

        # Should only return successful instance
        assert len(instances) == 1
        assert instances[0].instance_id == "inst-1"

    @pytest.mark.asyncio
    async def test_list_all_services_error_handling(self, mock_kv_store, mock_logger):
        """Test list_all_services error handling."""
        mock_kv_store.keys.side_effect = Exception("Keys failed")

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        # Should return empty dict on error
        services = await registry.list_all_services()
        assert services == {}

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Failed to list all services" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_all_services_invalid_keys(self, mock_kv_store):
        """Test list_all_services with invalid key formats."""
        # Mix of valid and invalid keys
        mock_kv_store.keys.return_value = [
            "service-instances",  # Too short
            "service-instances.service-a",  # Missing instance
            "service-instances.service-a.inst-1",  # Valid
            "other-prefix.service-b.inst-1",  # Wrong prefix
        ]

        # Only mock the valid instance
        entry = MagicMock()
        entry.value = {
            "serviceName": "service-a",
            "instanceId": "inst-1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
        }

        # Mock get to return entry only for valid key
        async def get_side_effect(key):
            if key == "service-instances.service-a.inst-1":
                return entry
            return None

        mock_kv_store.get.side_effect = get_side_effect

        registry = KVServiceRegistry(mock_kv_store)

        services = await registry.list_all_services()

        # Should only have the valid service
        assert len(services) == 1
        assert "service-a" in services
        assert len(services["service-a"]) == 1

    @pytest.mark.asyncio
    async def test_update_heartbeat_with_debug_logger(
        self, mock_kv_store, mock_logger, sample_instance
    ):
        """Test successful heartbeat update with debug logging."""
        # Mock existing entry
        entry = MagicMock()
        entry.value = {"test": "data"}
        mock_kv_store.get.return_value = entry

        # Add debug logger method
        mock_logger.debug = AsyncMock()

        registry = KVServiceRegistry(mock_kv_store, mock_logger)

        await registry.update_heartbeat(sample_instance, ttl_seconds=30)

        # Should log debug message
        mock_logger.debug.assert_called_once()
        assert "Heartbeat updated" in mock_logger.debug.call_args[0][0]

    def test_make_key_format(self):
        """Test key generation format."""
        registry = KVServiceRegistry(MagicMock())

        key = registry._make_key("my-service", "instance-123")
        assert key == "service-instances.my-service.instance-123"

        # Test with special characters
        key = registry._make_key("service_name", "inst_id")
        assert key == "service-instances.service_name.inst_id"

    @pytest.mark.asyncio
    async def test_get_instance_sticky_active_group_camelcase(self, mock_kv_store):
        """Test get_instance with stickyActiveGroup in camelCase."""
        entry = MagicMock()
        entry.value = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "lastHeartbeat": "2025-01-01T00:00:00Z",
            "stickyActiveGroup": "group-primary",  # camelCase field
        }
        mock_kv_store.get.return_value = entry

        registry = KVServiceRegistry(mock_kv_store)

        instance = await registry.get_instance("test-service", "test-123")

        assert instance is not None
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        assert instance.sticky_active_group == "group-primary"
