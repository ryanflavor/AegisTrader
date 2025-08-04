"""Unit tests for ServiceInstanceRepositoryAdapter.

These tests verify the repository adapter implementation
for service instance persistence and retrieval.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceInstance
from app.infrastructure.service_instance_repository_adapter import ServiceInstanceRepositoryAdapter

if TYPE_CHECKING:
    pass


class TestServiceInstanceRepositoryAdapter:
    """Test cases for ServiceInstanceRepositoryAdapter."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        kv = Mock()
        kv.keys = AsyncMock()
        kv.get = AsyncMock()
        return kv

    @pytest.fixture
    def repository_adapter(self, mock_kv_store: Mock) -> ServiceInstanceRepositoryAdapter:
        """Create a repository adapter instance."""
        return ServiceInstanceRepositoryAdapter(mock_kv_store)

    @pytest.fixture
    def sample_instance(self) -> ServiceInstance:
        """Create a sample service instance."""
        return ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            host="localhost",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={"region": "us-east-1"},
        )

    def test_init(
        self, repository_adapter: ServiceInstanceRepositoryAdapter, mock_kv_store: Mock
    ) -> None:
        """Test repository adapter initialization."""
        assert repository_adapter._kv == mock_kv_store

    @pytest.mark.asyncio
    async def test_get_all_instances_success(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
        sample_instance: ServiceInstance,
    ) -> None:
        """Test successfully getting all instances."""
        # Arrange
        instance_data = sample_instance.model_dump(mode="json")
        instance_data["last_heartbeat"] = sample_instance.last_heartbeat.isoformat()

        mock_kv_store.keys.return_value = ["service-instances.test-service.test-123"]
        # Mock the entry object returned by get
        mock_entry = Mock()
        mock_entry.value = json.dumps(instance_data).encode()
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await repository_adapter.get_all_instances()

        # Assert
        assert len(instances) == 1
        assert instances[0].service_name == sample_instance.service_name
        assert instances[0].instance_id == sample_instance.instance_id
        mock_kv_store.keys.assert_called_once_with("service-instances.*")
        mock_kv_store.get.assert_called_once_with("service-instances.test-service.test-123")

    @pytest.mark.asyncio
    async def test_get_all_instances_empty(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting all instances when none exist."""
        # Arrange
        mock_kv_store.keys.return_value = []

        # Act
        instances = await repository_adapter.get_all_instances()

        # Assert
        assert instances == []
        mock_kv_store.keys.assert_called_once_with("service-instances.*")

    @pytest.mark.asyncio
    async def test_get_all_instances_kv_error(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test error handling when KV store fails."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("KV store error")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await repository_adapter.get_all_instances()

        assert "Failed to retrieve all instances" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_instances_by_service_success(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
        sample_instance: ServiceInstance,
    ) -> None:
        """Test getting instances by service name."""
        # Arrange
        instance_data = sample_instance.model_dump(mode="json")
        instance_data["last_heartbeat"] = sample_instance.last_heartbeat.isoformat()

        mock_kv_store.keys.return_value = ["service-instances.test-service.test-123"]
        # Mock the entry object returned by get
        mock_entry = Mock()
        mock_entry.value = json.dumps(instance_data).encode()
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await repository_adapter.get_instances_by_service("test-service")

        # Assert
        assert len(instances) == 1
        assert instances[0].service_name == "test-service"
        mock_kv_store.keys.assert_called_once_with("service-instances.test-service.*")

    @pytest.mark.asyncio
    async def test_get_instances_by_service_not_found(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting instances for non-existent service."""
        # Arrange
        mock_kv_store.keys.return_value = []

        # Act
        instances = await repository_adapter.get_instances_by_service("unknown-service")

        # Assert
        assert instances == []
        mock_kv_store.keys.assert_called_once_with("service-instances.unknown-service.*")

    @pytest.mark.asyncio
    async def test_get_instance_success(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
        sample_instance: ServiceInstance,
    ) -> None:
        """Test getting a specific instance."""
        # Arrange
        instance_data = sample_instance.model_dump(mode="json")
        instance_data["last_heartbeat"] = sample_instance.last_heartbeat.isoformat()

        # Mock the entry object returned by get
        mock_entry = Mock()
        mock_entry.value = json.dumps(instance_data).encode()
        mock_kv_store.get.return_value = mock_entry

        # Act
        instance = await repository_adapter.get_instance("test-service", "test-123")

        # Assert
        assert instance is not None
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        mock_kv_store.get.assert_called_once_with("service-instances.test-service.test-123")

    @pytest.mark.asyncio
    async def test_get_instance_not_found(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting non-existent instance."""
        # Arrange
        # Mock None return for not found
        mock_kv_store.get.return_value = None

        # Act
        instance = await repository_adapter.get_instance("test-service", "unknown-id")

        # Assert
        assert instance is None
        mock_kv_store.get.assert_called_once_with("service-instances.test-service.unknown-id")

    @pytest.mark.asyncio
    async def test_get_instance_invalid_json(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test handling invalid JSON data."""
        # Arrange
        mock_kv_store.get.return_value = b"invalid json"

        # Act
        instance = await repository_adapter.get_instance("test-service", "test-123")

        # Assert
        assert instance is None

    @pytest.mark.asyncio
    async def test_count_active_instances(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test counting active instances."""
        # Arrange
        active_instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            host="localhost",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )
        inactive_instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-456",
            host="localhost",
            port=8081,
            version="1.0.0",
            status="STANDBY",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        active_data = active_instance.model_dump(mode="json")
        active_data["last_heartbeat"] = active_instance.last_heartbeat.isoformat()
        inactive_data = inactive_instance.model_dump(mode="json")
        inactive_data["last_heartbeat"] = inactive_instance.last_heartbeat.isoformat()

        mock_kv_store.keys.return_value = [
            "service-instances.test-service.test-123",
            "service-instances.test-service.test-456",
        ]
        mock_kv_store.get.side_effect = [
            Mock(value=json.dumps(active_data).encode()),
            Mock(value=json.dumps(inactive_data).encode()),
        ]

        # Act
        count = await repository_adapter.count_active_instances()

        # Assert
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_active_instances_error(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test error handling when counting active instances."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("Count error")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await repository_adapter.count_active_instances()

        assert "Failed to count active instances" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_instances_by_status_active(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting instances by ACTIVE status."""
        # Arrange
        active_instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            host="localhost",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        instance_data = active_instance.model_dump(mode="json")
        instance_data["last_heartbeat"] = active_instance.last_heartbeat.isoformat()

        mock_kv_store.keys.return_value = ["service-instances.test-service.test-123"]
        # Mock the entry object returned by get
        mock_entry = Mock()
        mock_entry.value = json.dumps(instance_data).encode()
        mock_kv_store.get.return_value = mock_entry

        # Act
        instances = await repository_adapter.get_instances_by_status("ACTIVE")

        # Assert
        assert len(instances) == 1
        assert instances[0].status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_get_instances_by_status_filters_correctly(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test that status filtering works correctly."""
        # Arrange
        active_instance = ServiceInstance(
            service_name="service1",
            instance_id="id1",
            host="host1",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )
        unhealthy_instance = ServiceInstance(
            service_name="service2",
            instance_id="id2",
            host="host2",
            port=8081,
            version="1.0.0",
            status="UNHEALTHY",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        active_data = active_instance.model_dump(mode="json")
        active_data["last_heartbeat"] = active_instance.last_heartbeat.isoformat()
        unhealthy_data = unhealthy_instance.model_dump(mode="json")
        unhealthy_data["last_heartbeat"] = unhealthy_instance.last_heartbeat.isoformat()

        mock_kv_store.keys.return_value = [
            "service-instances.service1.id1",
            "service-instances.service2.id2",
        ]
        mock_kv_store.get.side_effect = [
            Mock(value=json.dumps(active_data).encode()),
            Mock(value=json.dumps(unhealthy_data).encode()),
        ]

        # Act
        instances = await repository_adapter.get_instances_by_status("UNHEALTHY")

        # Assert
        assert len(instances) == 1
        assert instances[0].status == "UNHEALTHY"
        assert instances[0].service_name == "service2"

    @pytest.mark.asyncio
    async def test_get_instances_by_status_error(
        self,
        repository_adapter: ServiceInstanceRepositoryAdapter,
        mock_kv_store: Mock,
    ) -> None:
        """Test error handling when getting instances by status."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("Status query error")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await repository_adapter.get_instances_by_status("ACTIVE")

        assert "Failed to get instances by status" in str(exc_info.value)
