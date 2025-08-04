"""Unit tests for ServiceInstanceService.

These tests verify the application service behavior using mocks,
following TDD principles and hexagonal architecture patterns.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from app.application.service_instance_service import ServiceInstanceService
from app.domain.exceptions import KVStoreException, ServiceNotFoundException
from app.domain.models import ServiceInstance


@pytest.fixture
def mock_repository():
    """Create a mock repository for testing."""
    return AsyncMock()


@pytest.fixture
def service(mock_repository):
    """Create a service instance with mocked dependencies."""
    return ServiceInstanceService(mock_repository)


@pytest.fixture
def sample_instance():
    """Create a sample service instance for testing."""
    return ServiceInstance(
        service_name="test-service",
        instance_id="test-01",
        version="1.0.0",
        status="ACTIVE",
        last_heartbeat=datetime.now(UTC),
        metadata={"region": "us-east-1"},
    )


class TestServiceInstanceService:
    """Test cases for ServiceInstanceService."""

    @pytest.mark.asyncio
    async def test_list_all_instances_success(self, service, mock_repository, sample_instance):
        """Test successful retrieval of all service instances."""
        # Arrange
        expected_instances = [sample_instance]
        mock_repository.get_all_instances.return_value = expected_instances

        # Act
        result = await service.list_all_instances()

        # Assert
        assert result == expected_instances
        mock_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_instances_empty(self, service, mock_repository):
        """Test retrieval when no instances exist."""
        # Arrange
        mock_repository.get_all_instances.return_value = []

        # Act
        result = await service.list_all_instances()

        # Assert
        assert result == []
        mock_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_instances_by_service_success(
        self, service, mock_repository, sample_instance
    ):
        """Test successful retrieval of instances by service name."""
        # Arrange
        service_name = "test-service"
        expected_instances = [sample_instance]
        mock_repository.get_instances_by_service.return_value = expected_instances

        # Act
        result = await service.list_instances_by_service(service_name)

        # Assert
        assert result == expected_instances
        mock_repository.get_instances_by_service.assert_called_once_with(service_name)

    @pytest.mark.asyncio
    async def test_get_instance_success(self, service, mock_repository, sample_instance):
        """Test successful retrieval of a specific instance."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-01"
        mock_repository.get_instance.return_value = sample_instance

        # Act
        result = await service.get_instance(service_name, instance_id)

        # Assert
        assert result == sample_instance
        mock_repository.get_instance.assert_called_once_with(service_name, instance_id)

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, service, mock_repository):
        """Test retrieval of non-existent instance."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-01"
        mock_repository.get_instance.return_value = None

        # Act & Assert
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service.get_instance(service_name, instance_id)

        assert "Instance test-01 of service test-service not found" in str(exc_info.value)
        mock_repository.get_instance.assert_called_once_with(service_name, instance_id)

    @pytest.mark.asyncio
    async def test_get_health_summary(self, service, mock_repository):
        """Test health summary calculation."""
        # Arrange
        instances = [
            ServiceInstance(
                service_name="service-1",
                instance_id="inst-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-2",
                instance_id="inst-2",
                version="1.0.0",
                status="UNHEALTHY",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-3",
                instance_id="inst-3",
                version="1.0.0",
                status="STANDBY",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-4",
                instance_id="inst-4",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
        ]
        mock_repository.get_all_instances.return_value = instances

        # Act
        result = await service.get_health_summary()

        # Assert
        assert result == {
            "total": 4,
            "active": 2,
            "unhealthy": 1,
            "standby": 1,
        }
        mock_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stale_instances(self, service, mock_repository):
        """Test identification of stale instances."""
        # Arrange
        now = datetime.now(UTC)
        instances = [
            ServiceInstance(
                service_name="service-1",
                instance_id="fresh-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=now - timedelta(minutes=2),
            ),
            ServiceInstance(
                service_name="service-2",
                instance_id="stale-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=now - timedelta(minutes=10),
            ),
            ServiceInstance(
                service_name="service-3",
                instance_id="stale-2",
                version="1.0.0",
                status="UNHEALTHY",
                last_heartbeat=now - timedelta(minutes=6),
            ),
        ]
        mock_repository.get_all_instances.return_value = instances

        # Act
        result = await service.get_stale_instances(threshold_minutes=5)

        # Assert
        assert len(result) == 2
        assert result[0].instance_id == "stale-1"
        assert result[1].instance_id == "stale-2"
        mock_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_instances_count(self, service, mock_repository):
        """Test counting of active instances."""
        # Arrange
        expected_count = 5
        mock_repository.count_active_instances.return_value = expected_count

        # Act
        result = await service.get_active_instances_count()

        # Assert
        assert result == expected_count
        mock_repository.count_active_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instances_by_status_valid(self, service, mock_repository, sample_instance):
        """Test retrieval of instances by valid status."""
        # Arrange
        status = "ACTIVE"
        expected_instances = [sample_instance]
        mock_repository.get_instances_by_status.return_value = expected_instances

        # Act
        result = await service.get_instances_by_status(status)

        # Assert
        assert result == expected_instances
        mock_repository.get_instances_by_status.assert_called_once_with(status)

    @pytest.mark.asyncio
    async def test_get_instances_by_status_invalid(self, service, mock_repository):
        """Test retrieval with invalid status."""
        # Arrange
        invalid_status = "INVALID"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.get_instances_by_status(invalid_status)

        assert "Invalid status: INVALID" in str(exc_info.value)
        mock_repository.get_instances_by_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_service_distribution(self, service, mock_repository):
        """Test service distribution calculation."""
        # Arrange
        instances = [
            ServiceInstance(
                service_name="service-a",
                instance_id="a-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-a",
                instance_id="a-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-b",
                instance_id="b-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="service-a",
                instance_id="a-3",
                version="1.0.0",
                status="STANDBY",
                last_heartbeat=datetime.now(UTC),
            ),
        ]
        mock_repository.get_all_instances.return_value = instances

        # Act
        result = await service.get_service_distribution()

        # Assert
        assert result == {
            "service-a": 3,
            "service-b": 1,
        }
        mock_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_repository_error_propagation(self, service, mock_repository):
        """Test that repository errors are properly propagated."""
        # Arrange
        mock_repository.get_all_instances.side_effect = KVStoreException("Connection failed")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await service.list_all_instances()

        assert "Connection failed" in str(exc_info.value)
