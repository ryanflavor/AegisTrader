"""Unit tests for KV service registry adapter.

Tests the infrastructure adapter for service registration
using mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import KVOptions
from app.domain.models import ServiceDefinitionInfo, ServiceRegistrationData
from app.infrastructure.kv_service_registry_adapter import KVServiceRegistryAdapter
from app.ports.service_registry import RegistrationError


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.put = AsyncMock()
    mock.delete = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def registry_adapter(mock_kv_store):
    """Create a registry adapter with mocked dependencies."""
    return KVServiceRegistryAdapter(mock_kv_store)


@pytest.fixture
def sample_registration():
    """Create a sample service registration."""
    definition = ServiceDefinitionInfo(
        service_name="test-service",
        owner="Test Team",
        description="Test service description",
        version="1.0.0",
    )
    return ServiceRegistrationData(
        definition=definition,
        instance_id="test-service-abc123",
        nats_url="nats://localhost:4222",
    )


class TestServiceDefinitionRegistration:
    """Test service definition registration."""

    async def test_register_new_service_definition(
        self, registry_adapter, mock_kv_store, sample_registration
    ):
        """Test registering a new service definition."""
        # Setup: Service doesn't exist
        mock_kv_store.get.return_value = None

        # Act
        await registry_adapter.register_service_definition(sample_registration)

        # Assert
        mock_kv_store.get.assert_called_once_with("test-service")
        mock_kv_store.put.assert_called_once()

        call_args = mock_kv_store.put.call_args
        assert call_args[1]["key"] == "test-service"

        service_def = call_args[1]["value"]
        assert service_def["service_name"] == "test-service"
        assert service_def["owner"] == "Test Team"
        assert service_def["description"] == "Test service description"
        assert service_def["version"] == "1.0.0"
        assert "created_at" in service_def
        assert "updated_at" in service_def

        assert call_args[1]["options"] is None  # No TTL for definitions

    async def test_update_existing_service_definition(
        self, registry_adapter, mock_kv_store, sample_registration
    ):
        """Test updating an existing service definition."""
        # Setup: Service already exists
        mock_kv_store.get.return_value = {"service_name": "test-service"}

        # Act
        await registry_adapter.register_service_definition(sample_registration)

        # Assert: Should call update method
        assert mock_kv_store.put.call_count == 1  # Only one put call for update

        # Check the update call
        update_call = mock_kv_store.put.call_args
        assert update_call[1]["key"] == "test-service"

        service_def = update_call[1]["value"]
        assert "updated_at" in service_def

    async def test_register_service_definition_error_handling(
        self, registry_adapter, mock_kv_store, sample_registration
    ):
        """Test error handling during service definition registration."""
        # Setup: KV store raises exception
        mock_kv_store.get.side_effect = Exception("Connection error")

        # Act & Assert
        with pytest.raises(RegistrationError) as exc_info:
            await registry_adapter.register_service_definition(sample_registration)

        assert "Failed to register service definition" in str(exc_info.value)
        assert exc_info.value.service_name == "test-service"

    async def test_check_service_exists(self, registry_adapter, mock_kv_store):
        """Test checking if service definition exists."""
        # Test when service exists
        mock_kv_store.get.return_value = {"service_name": "test-service"}
        exists = await registry_adapter.check_service_exists("test-service")
        assert exists is True

        # Test when service doesn't exist
        mock_kv_store.get.return_value = None
        exists = await registry_adapter.check_service_exists("nonexistent")
        assert exists is False

        # Test error handling
        mock_kv_store.get.side_effect = Exception("Connection error")
        exists = await registry_adapter.check_service_exists("test-service")
        assert exists is False  # Returns False on error


class TestInstanceRegistration:
    """Test service instance registration."""

    async def test_register_instance(self, registry_adapter, mock_kv_store):
        """Test registering a service instance."""
        # Arrange
        instance_data = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
        }

        # Act
        await registry_adapter.register_instance(
            service_name="test-service",
            instance_id="test-123",
            instance_data=instance_data,
            ttl_seconds=30,
        )

        # Assert
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args

        assert call_args[1]["key"] == "service-instances__test-service__test-123"

        stored_data = call_args[1]["value"]
        assert "lastHeartbeat" in stored_data
        assert stored_data["status"] == ServiceStatus.ACTIVE.value

        options = call_args[1]["options"]
        assert isinstance(options, KVOptions)
        assert options.ttl == 30

    async def test_register_instance_with_existing_fields(self, registry_adapter, mock_kv_store):
        """Test registering instance with pre-existing status and heartbeat."""
        # Arrange
        instance_data = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
            "status": ServiceStatus.STANDBY.value,
            "lastHeartbeat": "2024-01-01T12:00:00Z",
        }

        # Act
        await registry_adapter.register_instance(
            service_name="test-service",
            instance_id="test-123",
            instance_data=instance_data,
            ttl_seconds=60,
        )

        # Assert
        stored_data = mock_kv_store.put.call_args[1]["value"]
        assert stored_data["status"] == ServiceStatus.STANDBY.value
        assert stored_data["lastHeartbeat"] == "2024-01-01T12:00:00Z"

    async def test_update_instance_heartbeat(self, registry_adapter, mock_kv_store):
        """Test updating instance heartbeat."""
        # Setup: Instance exists
        mock_kv_store.get.return_value = {"instanceId": "test-123"}

        instance_data = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
        }

        # Act
        await registry_adapter.update_instance_heartbeat(
            service_name="test-service",
            instance_id="test-123",
            instance_data=instance_data,
            ttl_seconds=30,
        )

        # Assert
        mock_kv_store.get.assert_called_once_with("service-instances__test-service__test-123")
        mock_kv_store.put.assert_called_once()

        stored_data = mock_kv_store.put.call_args[1]["value"]
        assert "lastHeartbeat" in stored_data

    async def test_update_heartbeat_re_registers_if_lost(self, registry_adapter, mock_kv_store):
        """Test that heartbeat update re-registers instance if lost."""
        # Setup: Instance doesn't exist
        mock_kv_store.get.return_value = None

        instance_data = {
            "serviceName": "test-service",
            "instanceId": "test-123",
            "version": "1.0.0",
        }

        # Act
        await registry_adapter.update_instance_heartbeat(
            service_name="test-service",
            instance_id="test-123",
            instance_data=instance_data,
            ttl_seconds=30,
        )

        # Assert: Should re-register
        mock_kv_store.put.assert_called_once()
        assert mock_kv_store.put.call_args[1]["key"] == "service-instances__test-service__test-123"

    async def test_update_heartbeat_error_handling(self, registry_adapter, mock_kv_store):
        """Test that heartbeat errors don't raise exceptions."""
        # Setup: KV store raises exception
        mock_kv_store.get.side_effect = Exception("Connection error")

        instance_data = {"instanceId": "test-123"}

        # Act: Should not raise
        await registry_adapter.update_instance_heartbeat(
            service_name="test-service",
            instance_id="test-123",
            instance_data=instance_data,
            ttl_seconds=30,
        )

        # Assert: Method completed without raising

    async def test_deregister_instance(self, registry_adapter, mock_kv_store):
        """Test deregistering a service instance."""
        # Setup
        mock_kv_store.delete.return_value = True

        # Act
        await registry_adapter.deregister_instance("test-service", "test-123")

        # Assert
        mock_kv_store.delete.assert_called_once_with("service-instances__test-service__test-123")

    async def test_deregister_nonexistent_instance(self, registry_adapter, mock_kv_store):
        """Test deregistering instance that doesn't exist."""
        # Setup
        mock_kv_store.delete.return_value = False

        # Act: Should not raise
        await registry_adapter.deregister_instance("test-service", "test-123")

        # Assert
        mock_kv_store.delete.assert_called_once()

    async def test_deregister_instance_error_handling(self, registry_adapter, mock_kv_store):
        """Test error handling during instance deregistration."""
        # Setup
        mock_kv_store.delete.side_effect = Exception("Connection error")

        # Act & Assert
        with pytest.raises(RegistrationError) as exc_info:
            await registry_adapter.deregister_instance("test-service", "test-123")

        assert "Failed to deregister instance" in str(exc_info.value)
        assert exc_info.value.service_name == "test-service"
