"""Unit tests for ServiceInstanceRepositoryAdapter.

These tests verify the repository adapter behavior using mocks,
ensuring proper translation between domain models and infrastructure.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceInstance
from app.infrastructure.service_instance_repository_adapter import (
    ServiceInstanceRepositoryAdapter,
)


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store for testing."""
    return AsyncMock()


@pytest.fixture
def repository(mock_kv_store):
    """Create a repository adapter with mocked dependencies."""
    return ServiceInstanceRepositoryAdapter(mock_kv_store)


@pytest.fixture
def sample_instance_data():
    """Create sample instance data as it would be stored in KV."""
    return {
        "service_name": "test-service",
        "instance_id": "test-01",
        "version": "1.0.0",
        "status": "ACTIVE",
        "last_heartbeat": datetime.now(UTC).isoformat(),
        "metadata": {"region": "us-east-1"},
    }


def create_kv_entry(data):
    """Helper to create a mock KV entry."""
    entry = Mock()
    entry.value = json.dumps(data).encode()
    return entry


class TestServiceInstanceRepositoryAdapter:
    """Test cases for ServiceInstanceRepositoryAdapter."""

    @pytest.mark.asyncio
    async def test_get_all_instances_success(self, repository, mock_kv_store, sample_instance_data):
        """Test successful retrieval of all instances."""
        # Arrange
        mock_kv_store.keys.return_value = [
            "service-instances.service-a.inst-1",
            "service-instances.service-b.inst-1",
        ]

        instance_data_a = {
            **sample_instance_data,
            "service_name": "service-a",
            "instance_id": "inst-1",
        }
        instance_data_b = {
            **sample_instance_data,
            "service_name": "service-b",
            "instance_id": "inst-1",
        }

        mock_kv_store.get.side_effect = [
            create_kv_entry(instance_data_a),
            create_kv_entry(instance_data_b),
        ]

        # Act
        result = await repository.get_all_instances()

        # Assert
        assert len(result) == 2
        assert all(isinstance(inst, ServiceInstance) for inst in result)
        assert result[0].service_name == "service-a"
        assert result[1].service_name == "service-b"
        mock_kv_store.keys.assert_called_once_with("service-instances.*")

    @pytest.mark.asyncio
    async def test_get_all_instances_with_invalid_data(self, repository, mock_kv_store):
        """Test handling of invalid instance data."""
        # Arrange
        mock_kv_store.keys.return_value = [
            "service-instances.service-a.inst-1",
            "service-instances.service-b.inst-1",
        ]

        # First entry is valid, second is invalid
        valid_data = {
            "service_name": "service-a",
            "instance_id": "inst-1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now(UTC).isoformat(),
        }
        invalid_entry = Mock()
        invalid_entry.value = b"invalid json"

        mock_kv_store.get.side_effect = [
            create_kv_entry(valid_data),
            invalid_entry,
        ]

        # Act
        result = await repository.get_all_instances()

        # Assert
        assert len(result) == 1  # Only valid instance returned
        assert result[0].service_name == "service-a"

    @pytest.mark.asyncio
    async def test_get_instances_by_service(self, repository, mock_kv_store, sample_instance_data):
        """Test retrieval of instances for a specific service."""
        # Arrange
        service_name = "test-service"
        mock_kv_store.keys.return_value = [
            f"service-instances.{service_name}.inst-1",
            f"service-instances.{service_name}.inst-2",
        ]

        instance_data_1 = {**sample_instance_data, "instance_id": "inst-1"}
        instance_data_2 = {**sample_instance_data, "instance_id": "inst-2"}

        mock_kv_store.get.side_effect = [
            create_kv_entry(instance_data_1),
            create_kv_entry(instance_data_2),
        ]

        # Act
        result = await repository.get_instances_by_service(service_name)

        # Assert
        assert len(result) == 2
        assert result[0].instance_id == "inst-1"
        assert result[1].instance_id == "inst-2"
        mock_kv_store.keys.assert_called_once_with(f"service-instances.{service_name}.*")

    @pytest.mark.asyncio
    async def test_get_instance_found(self, repository, mock_kv_store, sample_instance_data):
        """Test retrieval of a specific instance that exists."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-01"
        mock_kv_store.get.return_value = create_kv_entry(sample_instance_data)

        # Act
        result = await repository.get_instance(service_name, instance_id)

        # Assert
        assert result is not None
        assert isinstance(result, ServiceInstance)
        assert result.service_name == service_name
        assert result.instance_id == instance_id
        mock_kv_store.get.assert_called_once_with(f"service-instances.{service_name}.{instance_id}")

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, repository, mock_kv_store):
        """Test retrieval of a non-existent instance."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-01"
        mock_kv_store.get.return_value = None

        # Act
        result = await repository.get_instance(service_name, instance_id)

        # Assert
        assert result is None
        mock_kv_store.get.assert_called_once_with(f"service-instances.{service_name}.{instance_id}")

    @pytest.mark.asyncio
    async def test_count_active_instances(self, repository, mock_kv_store, sample_instance_data):
        """Test counting of active instances."""
        # Arrange
        instances_data = [
            {**sample_instance_data, "status": "ACTIVE", "instance_id": "inst-1"},
            {**sample_instance_data, "status": "UNHEALTHY", "instance_id": "inst-2"},
            {**sample_instance_data, "status": "ACTIVE", "instance_id": "inst-3"},
            {**sample_instance_data, "status": "STANDBY", "instance_id": "inst-4"},
        ]

        mock_kv_store.keys.return_value = [
            f"service-instances.test-service.inst-{i + 1}" for i in range(4)
        ]
        mock_kv_store.get.side_effect = [create_kv_entry(data) for data in instances_data]

        # Act
        result = await repository.count_active_instances()

        # Assert
        assert result == 2  # Two ACTIVE instances

    @pytest.mark.asyncio
    async def test_get_instances_by_status_valid(
        self, repository, mock_kv_store, sample_instance_data
    ):
        """Test retrieval of instances by valid status."""
        # Arrange
        instances_data = [
            {**sample_instance_data, "status": "ACTIVE", "instance_id": "inst-1"},
            {**sample_instance_data, "status": "UNHEALTHY", "instance_id": "inst-2"},
            {**sample_instance_data, "status": "ACTIVE", "instance_id": "inst-3"},
        ]

        mock_kv_store.keys.return_value = [
            f"service-instances.test-service.inst-{i + 1}" for i in range(3)
        ]
        mock_kv_store.get.side_effect = [create_kv_entry(data) for data in instances_data]

        # Act
        result = await repository.get_instances_by_status("ACTIVE")

        # Assert
        assert len(result) == 2
        assert all(inst.status == "ACTIVE" for inst in result)

    @pytest.mark.asyncio
    async def test_get_instances_by_status_invalid(self, repository):
        """Test retrieval with invalid status."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await repository.get_instances_by_status("INVALID")

        assert "Invalid status: INVALID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_kv_store_error_handling(self, repository, mock_kv_store):
        """Test proper error handling for KV store failures."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("Connection failed")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await repository.get_all_instances()

        assert "Failed to retrieve all instances" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_key_value_handling(self, repository, mock_kv_store):
        """Test handling of empty values from KV store."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances.service-a.inst-1"]

        # Entry with None value
        empty_entry = Mock()
        empty_entry.value = None
        mock_kv_store.get.return_value = empty_entry

        # Act
        result = await repository.get_all_instances()

        # Assert
        assert len(result) == 0  # Empty value is skipped
