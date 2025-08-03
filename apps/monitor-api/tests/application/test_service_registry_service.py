"""Unit tests for ServiceRegistryService application service.

These tests ensure the service layer properly orchestrates
domain logic and infrastructure calls.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.service_registry_service import ServiceRegistryService
from app.domain.exceptions import (
    ConcurrentUpdateException,
    KVStoreException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
)
from app.domain.models import ServiceDefinition


@pytest.fixture
def mock_kv_store() -> Mock:
    """Create a mock KV store port."""
    from app.ports.service_registry_kv_store import ServiceRegistryKVStorePort

    mock = Mock(spec=ServiceRegistryKVStorePort)
    mock.get = AsyncMock()
    mock.put = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.list_all = AsyncMock()
    mock.get_with_revision = AsyncMock()
    return mock


@pytest.fixture
def service_registry(mock_kv_store: Mock) -> ServiceRegistryService:
    """Create a service registry instance with mocked dependencies."""
    return ServiceRegistryService(mock_kv_store)


class TestServiceRegistryService:
    """Test cases for ServiceRegistryService."""

    @pytest.mark.asyncio
    async def test_create_service_success(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test successful service creation."""
        # Arrange
        service_data = {
            "service_name": "payment-service",
            "owner": "payments-team",
            "description": "Handles payment processing",
            "version": "1.0.0",
        }
        mock_kv_store.put.return_value = None

        # Act
        result = await service_registry.create_service(service_data)

        # Assert
        assert result.service_name == "payment-service"
        assert result.owner == "payments-team"
        assert result.description == "Handles payment processing"
        assert result.version == "1.0.0"
        assert result.created_at == result.updated_at
        assert result.created_at is not None

        # Verify KV store was called
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args
        assert call_args[0][0] == "payment-service"
        assert isinstance(call_args[0][1], ServiceDefinition)

    @pytest.mark.asyncio
    async def test_create_service_already_exists(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test creating a service that already exists."""
        # Arrange
        service_data = {
            "service_name": "existing-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }
        mock_kv_store.put.side_effect = ValueError("Key 'existing-service' already exists")

        # Act & Assert
        with pytest.raises(ServiceAlreadyExistsException) as exc_info:
            await service_registry.create_service(service_data)
        assert "existing-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_service_kv_store_error(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test handling KV store errors during creation."""
        # Arrange
        service_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }
        mock_kv_store.put.side_effect = KVStoreException("Connection failed")

        # Act & Assert
        with pytest.raises(KVStoreException) as exc_info:
            await service_registry.create_service(service_data)
        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_service_found(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test getting an existing service."""
        # Arrange
        now = datetime.now(UTC)
        expected_service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock_kv_store.get.return_value = expected_service

        # Act
        result = await service_registry.get_service("test-service")

        # Assert
        assert result == expected_service
        mock_kv_store.get.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_get_service_not_found(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test getting a non-existent service."""
        # Arrange
        mock_kv_store.get.return_value = None

        # Act
        result = await service_registry.get_service("non-existent")

        # Assert
        assert result is None
        mock_kv_store.get.assert_called_once_with("non-existent")

    @pytest.mark.asyncio
    async def test_update_service_success(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test successful service update."""
        # Arrange
        now = datetime.now(UTC)
        existing_service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Old description",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock_kv_store.get.return_value = existing_service
        mock_kv_store.update.return_value = None

        updates = {
            "description": "New description",
            "version": "1.1.0",
        }

        # Act
        result = await service_registry.update_service("test-service", updates)

        # Assert
        assert result.service_name == "test-service"
        assert result.owner == "test-team"  # Unchanged
        assert result.description == "New description"
        assert result.version == "1.1.0"
        assert result.created_at == existing_service.created_at  # Unchanged
        assert result.updated_at > existing_service.updated_at  # Updated

        # Verify calls
        mock_kv_store.get.assert_called_once_with("test-service")
        mock_kv_store.update.assert_called_once()
        update_args = mock_kv_store.update.call_args
        assert update_args[0][0] == "test-service"
        assert isinstance(update_args[0][1], ServiceDefinition)
        assert update_args[0][2] is None  # No revision

    @pytest.mark.asyncio
    async def test_update_service_with_revision(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test service update with optimistic locking."""
        # Arrange
        now = datetime.now(UTC)
        existing_service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock_kv_store.get.return_value = existing_service
        mock_kv_store.update.return_value = None

        updates = {"version": "1.1.0"}
        revision = 42

        # Act
        result = await service_registry.update_service("test-service", updates, revision)

        # Assert
        assert result.version == "1.1.0"
        mock_kv_store.update.assert_called_once()
        update_args = mock_kv_store.update.call_args
        assert update_args[0][2] == revision

    @pytest.mark.asyncio
    async def test_update_service_not_found(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test updating a non-existent service."""
        # Arrange
        mock_kv_store.get.return_value = None
        updates = {"version": "1.1.0"}

        # Act & Assert
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service_registry.update_service("non-existent", updates)
        assert "non-existent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_service_concurrent_update(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test handling concurrent update conflicts."""
        # Arrange
        now = datetime.now(UTC)
        existing_service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock_kv_store.get.return_value = existing_service
        mock_kv_store.update.side_effect = ValueError("Revision mismatch for key 'test-service'")

        updates = {"version": "1.1.0"}

        # Act & Assert
        with pytest.raises(ConcurrentUpdateException) as exc_info:
            await service_registry.update_service("test-service", updates, revision=1)
        assert "test-service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_service_success(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test successful service deletion."""
        # Arrange
        mock_kv_store.delete.return_value = None

        # Act
        await service_registry.delete_service("test-service")

        # Assert
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_delete_service_not_found(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test deleting a non-existent service."""
        # Arrange
        mock_kv_store.delete.side_effect = ValueError("Key 'non-existent' not found")

        # Act & Assert
        with pytest.raises(ServiceNotFoundException) as exc_info:
            await service_registry.delete_service("non-existent")
        assert "non-existent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_services_success(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test listing all services."""
        # Arrange
        now = datetime.now(UTC)
        services = [
            ServiceDefinition(
                service_name="service1",
                owner="team1",
                description="Service 1",
                version="1.0.0",
                created_at=now,
                updated_at=now,
            ),
            ServiceDefinition(
                service_name="service2",
                owner="team2",
                description="Service 2",
                version="2.0.0",
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_kv_store.list_all.return_value = services

        # Act
        result = await service_registry.list_services()

        # Assert
        assert result == services
        assert len(result) == 2
        mock_kv_store.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_services_empty(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test listing services when registry is empty."""
        # Arrange
        mock_kv_store.list_all.return_value = []

        # Act
        result = await service_registry.list_services()

        # Assert
        assert result == []
        mock_kv_store.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service_with_revision_supported(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test getting service with revision when adapter supports it."""
        # Arrange
        now = datetime.now(UTC)
        expected_service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        mock_kv_store.get_with_revision = AsyncMock(return_value=(expected_service, 42))

        # Act
        service, revision = await service_registry.get_service_with_revision("test-service")

        # Assert
        assert service == expected_service
        assert revision == 42
        mock_kv_store.get_with_revision.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_timestamps_are_iso_format(
        self, service_registry: ServiceRegistryService, mock_kv_store: Mock
    ) -> None:
        """Test that timestamps are properly formatted as ISO 8601."""
        # Arrange
        service_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }
        mock_kv_store.put.return_value = None

        # Act
        result = await service_registry.create_service(service_data)

        # Assert
        # Verify timestamps are datetime objects with timezone
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)
        assert result.created_at.tzinfo is not None
        assert result.updated_at.tzinfo is not None
