"""Comprehensive unit tests for ServiceInstanceService.

These tests verify the business logic for service instance management,
following TDD principles and hexagonal architecture patterns.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.service_instance_service import ServiceInstanceService
from app.domain.exceptions import KVStoreException
from app.domain.models import ServiceInstance

if TYPE_CHECKING:
    pass


class TestServiceInstanceService:
    """Test cases for ServiceInstanceService following TDD principles."""

    @pytest.fixture
    def mock_instance_repository(self) -> Mock:
        """Create a mock instance repository following hexagonal architecture."""
        repository = Mock()
        repository.get_all_instances = AsyncMock()
        repository.get_instances_by_service = AsyncMock()
        repository.get_instance = AsyncMock()
        repository.count_active_instances = AsyncMock()
        repository.get_instances_by_status = AsyncMock()
        return repository

    @pytest.fixture
    def service_instance_service(self, mock_instance_repository: Mock) -> ServiceInstanceService:
        """Create a service instance service with mocked dependencies."""
        return ServiceInstanceService(repository=mock_instance_repository)

    @pytest.fixture
    def sample_instance(self) -> ServiceInstance:
        """Create a sample service instance for testing."""
        return ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            sticky_active_group="group-1",
            metadata={
                "host": "localhost",
                "port": 8080,
                "region": "us-east-1",
                "lifecycle_state": "STARTED",
            },
        )

    @pytest.fixture
    def sample_instances(self, sample_instance: ServiceInstance) -> list[ServiceInstance]:
        """Create multiple sample instances for testing."""
        instance2 = ServiceInstance(
            service_name="test-service",
            instance_id="test-456",
            version="1.0.0",
            status="STANDBY",
            last_heartbeat=datetime.now(UTC),
            sticky_active_group="group-1",
            metadata={"host": "localhost", "port": 8081},
        )
        instance3 = ServiceInstance(
            service_name="other-service",
            instance_id="other-789",
            version="2.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={"host": "remote", "port": 9090},
        )
        return [sample_instance, instance2, instance3]

    # Test list_all_instances
    @pytest.mark.asyncio
    async def test_list_all_instances_success(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test successfully getting all instances."""
        # Arrange
        mock_instance_repository.get_all_instances.return_value = sample_instances

        # Act
        instances = await service_instance_service.list_all_instances()

        # Assert
        assert len(instances) == 3
        assert instances == sample_instances
        mock_instance_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_instances_empty(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test getting all instances when none exist."""
        # Arrange
        mock_instance_repository.get_all_instances.return_value = []

        # Act
        instances = await service_instance_service.list_all_instances()

        # Assert
        assert instances == []
        mock_instance_repository.get_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_instances_repository_error(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test error handling when repository fails."""
        # Arrange
        mock_instance_repository.get_all_instances.side_effect = KVStoreException(
            "Repository error"
        )

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await service_instance_service.list_all_instances()

        assert "Repository error" in str(exc_info.value)
        mock_instance_repository.get_all_instances.assert_called_once()

    # Test list_instances_by_service
    @pytest.mark.asyncio
    async def test_list_instances_by_service_success(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test getting instances by service name."""
        # Arrange
        service_instances = [i for i in sample_instances if i.service_name == "test-service"]
        mock_instance_repository.get_instances_by_service.return_value = service_instances

        # Act
        instances = await service_instance_service.list_instances_by_service("test-service")

        # Assert
        assert len(instances) == 2
        assert all(i.service_name == "test-service" for i in instances)
        mock_instance_repository.get_instances_by_service.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_list_instances_by_service_not_found(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test getting instances for non-existent service."""
        # Arrange
        mock_instance_repository.get_instances_by_service.return_value = []

        # Act
        instances = await service_instance_service.list_instances_by_service("unknown-service")

        # Assert
        assert instances == []
        mock_instance_repository.get_instances_by_service.assert_called_once_with("unknown-service")

    # Test get_instance
    @pytest.mark.asyncio
    async def test_get_instance_success(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instance: ServiceInstance,
    ) -> None:
        """Test getting a specific instance."""
        # Arrange
        mock_instance_repository.get_instance.return_value = sample_instance

        # Act
        instance = await service_instance_service.get_instance("test-service", "test-123")

        # Assert
        assert instance == sample_instance
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        mock_instance_repository.get_instance.assert_called_once_with("test-service", "test-123")

    @pytest.mark.asyncio
    async def test_get_instance_success_when_found(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instance: ServiceInstance,
    ) -> None:
        """Test getting instance when it exists."""
        # Arrange
        mock_instance_repository.get_instance.return_value = sample_instance

        # Act
        instance = await service_instance_service.get_instance("test-service", "test-123")

        # Assert
        assert instance == sample_instance
        mock_instance_repository.get_instance.assert_called_once_with("test-service", "test-123")

    # Test get_active_instances_count
    @pytest.mark.asyncio
    async def test_get_active_instances_count_success(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test counting active instances."""
        # Arrange
        mock_instance_repository.count_active_instances.return_value = 5

        # Act
        count = await service_instance_service.get_active_instances_count()

        # Assert
        assert count == 5
        mock_instance_repository.count_active_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_instances_count_zero(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test counting when no active instances exist."""
        # Arrange
        mock_instance_repository.count_active_instances.return_value = 0

        # Act
        count = await service_instance_service.get_active_instances_count()

        # Assert
        assert count == 0
        mock_instance_repository.count_active_instances.assert_called_once()

    # Test get_instances_by_status
    @pytest.mark.asyncio
    async def test_get_instances_by_status_active(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test getting instances by ACTIVE status."""
        # Arrange
        active_instances = [i for i in sample_instances if i.status == "ACTIVE"]
        mock_instance_repository.get_instances_by_status.return_value = active_instances

        # Act
        instances = await service_instance_service.get_instances_by_status("ACTIVE")

        # Assert
        assert len(instances) == 2
        assert all(i.status == "ACTIVE" for i in instances)
        mock_instance_repository.get_instances_by_status.assert_called_once_with("ACTIVE")

    @pytest.mark.asyncio
    async def test_get_instances_by_status_standby(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test getting instances by STANDBY status."""
        # Arrange
        standby_instances = [i for i in sample_instances if i.status == "STANDBY"]
        mock_instance_repository.get_instances_by_status.return_value = standby_instances

        # Act
        instances = await service_instance_service.get_instances_by_status("STANDBY")

        # Assert
        assert len(instances) == 1
        assert all(i.status == "STANDBY" for i in instances)
        mock_instance_repository.get_instances_by_status.assert_called_once_with("STANDBY")

    @pytest.mark.asyncio
    async def test_get_instances_by_status_unhealthy(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test getting instances by UNHEALTHY status."""
        # Arrange
        mock_instance_repository.get_instances_by_status.return_value = []

        # Act
        instances = await service_instance_service.get_instances_by_status("UNHEALTHY")

        # Assert
        assert instances == []
        mock_instance_repository.get_instances_by_status.assert_called_once_with("UNHEALTHY")

    # Test get_health_summary
    @pytest.mark.asyncio
    async def test_get_health_summary(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test getting health summary across all services."""
        # Arrange
        mock_instance_repository.get_all_instances.return_value = sample_instances

        # Act
        summary = await service_instance_service.get_health_summary()

        # Assert
        assert summary["total"] == 3
        assert summary["active"] == 2  # Two ACTIVE instances in sample_instances
        assert summary["standby"] == 1  # One STANDBY instance
        assert summary["unhealthy"] == 0  # No UNHEALTHY instances

    # Test get_stale_instances
    @pytest.mark.asyncio
    async def test_get_stale_instances(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test getting stale instances."""
        # Arrange
        now = datetime.now(UTC)
        stale_instance = ServiceInstance(
            service_name="test-service",
            instance_id="stale-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=now - timedelta(minutes=10),  # 10 minutes old
            metadata={},
        )
        fresh_instance = ServiceInstance(
            service_name="test-service",
            instance_id="fresh-456",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=now - timedelta(minutes=1),  # 1 minute old
            metadata={},
        )
        mock_instance_repository.get_all_instances.return_value = [stale_instance, fresh_instance]

        # Act
        stale_instances = await service_instance_service.get_stale_instances(threshold_minutes=5)

        # Assert
        assert len(stale_instances) == 1
        assert stale_instances[0].instance_id == "stale-123"
        mock_instance_repository.get_all_instances.assert_called_once()

    # Test get_service_distribution
    @pytest.mark.asyncio
    async def test_get_service_distribution(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
        sample_instances: list[ServiceInstance],
    ) -> None:
        """Test getting distribution of instances across services."""
        # Arrange
        mock_instance_repository.get_all_instances.return_value = sample_instances

        # Act
        distribution = await service_instance_service.get_service_distribution()

        # Assert
        assert distribution["test-service"] == 2  # Two instances for test-service
        assert distribution["other-service"] == 1  # One instance for other-service
        mock_instance_repository.get_all_instances.assert_called_once()

    # Test get_instance with ServiceNotFoundException
    @pytest.mark.asyncio
    async def test_get_instance_raises_not_found(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test get_instance raises ServiceNotFoundException when instance not found."""
        # Arrange
        mock_instance_repository.get_instance.return_value = None

        # Act & Assert
        from app.domain.exceptions import ServiceNotFoundException

        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service_instance_service.get_instance("test-service", "unknown-id")

        assert "Instance unknown-id of service test-service not found" in str(exc_info.value)
        mock_instance_repository.get_instance.assert_called_once_with("test-service", "unknown-id")

    # Test get_instances_by_status with invalid status
    @pytest.mark.asyncio
    async def test_get_instances_by_status_invalid(
        self,
        service_instance_service: ServiceInstanceService,
        mock_instance_repository: Mock,
    ) -> None:
        """Test get_instances_by_status raises ValueError for invalid status."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service_instance_service.get_instances_by_status("INVALID")

        assert "Invalid status: INVALID" in str(exc_info.value)
        mock_instance_repository.get_instances_by_status.assert_not_called()

    # Test dependency injection and hexagonal architecture
    def test_service_follows_hexagonal_architecture(
        self, service_instance_service: ServiceInstanceService, mock_instance_repository: Mock
    ) -> None:
        """Test that service follows hexagonal architecture with proper dependency injection."""
        # Assert - Service depends on abstract port, not concrete implementation
        assert hasattr(service_instance_service, "_repository")
        assert service_instance_service._repository == mock_instance_repository
        # Service should not have any infrastructure dependencies
        assert not hasattr(service_instance_service, "_kv_store")
        assert not hasattr(service_instance_service, "_nats_adapter")
