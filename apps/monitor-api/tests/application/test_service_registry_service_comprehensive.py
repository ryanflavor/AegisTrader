"""Comprehensive tests for ServiceRegistryService to achieve 90%+ coverage.

These tests cover all edge cases, error scenarios, and untested code paths
following TDD and hexagonal architecture principles.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.application.service_registry_service import ServiceRegistryService
from app.domain.exceptions import (
    ServiceRegistryException,
)
from app.domain.models import ServiceDefinition

if TYPE_CHECKING:
    pass


class TestServiceRegistryServiceComprehensive:
    """Comprehensive test cases for ServiceRegistryService achieving full coverage."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        mock = Mock()
        mock.get = AsyncMock()
        mock.put = AsyncMock()
        mock.delete = AsyncMock()
        mock.ls = AsyncMock()
        mock.keys = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_kv_store: Mock) -> ServiceRegistryService:
        """Create a service registry instance."""
        return ServiceRegistryService(mock_kv_store)

    @pytest.fixture
    def sample_definition(self) -> ServiceDefinition:
        """Create a sample service definition."""
        now = datetime.now()
        return ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now,
            updated_at=now,
            endpoints=["echo", "health"],
            metadata={"type": "rpc", "region": "us-east-1"},
        )

    # Test initialization
    def test_service_initialization(self, service: ServiceRegistryService) -> None:
        """Test service initialization."""
        assert service._kv_store is not None
        assert service._prefix == "service-definitions__"

    # Test create_or_update_service edge cases
    @pytest.mark.asyncio
    async def test_create_service_new(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test creating a new service definition."""
        # Arrange
        mock_kv_store.get.return_value = None  # Service doesn't exist
        mock_kv_store.put.return_value = None

        # Act
        result = await service.create_or_update_service(sample_definition)

        # Assert
        assert result == sample_definition
        mock_kv_store.get.assert_called_once()
        mock_kv_store.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_service_existing(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test updating an existing service definition."""
        # Arrange
        existing_data = sample_definition.model_dump()
        mock_entry = Mock()
        mock_entry.value = existing_data
        mock_kv_store.get.return_value = mock_entry
        mock_kv_store.put.return_value = None

        # Update the definition
        updated_definition = sample_definition.model_copy(
            update={"description": "Updated description", "version": "1.0.1"}
        )

        # Act
        result = await service.create_or_update_service(updated_definition)

        # Assert
        assert result == updated_definition
        mock_kv_store.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_service_kv_error(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test handling KV store error during create."""
        # Arrange
        mock_kv_store.get.return_value = None
        mock_kv_store.put.side_effect = Exception("KV store error")

        # Act & Assert
        with pytest.raises(ServiceRegistryException) as exc_info:
            await service.create_or_update_service(sample_definition)

        assert "Failed to create or update service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_service_optimistic_locking_conflict(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test optimistic locking conflict during update."""
        # Arrange - Simulate concurrent modification
        existing_data = sample_definition.model_dump()
        mock_entry = Mock()
        mock_entry.value = existing_data
        mock_entry.revision = 5
        mock_kv_store.get.return_value = mock_entry

        # Simulate version conflict
        mock_kv_store.put.side_effect = Exception("Wrong revision")

        # Act & Assert
        with pytest.raises(ServiceRegistryException) as exc_info:
            await service.create_or_update_service(sample_definition)

        assert "Wrong revision" in str(exc_info.value)

    # Test get_service_definition edge cases
    @pytest.mark.asyncio
    async def test_get_service_definition_success(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test successfully getting a service definition."""
        # Arrange
        mock_entry = Mock()
        mock_entry.value = sample_definition.model_dump()
        mock_kv_store.get.return_value = mock_entry

        # Act
        result = await service.get_service_definition("test-service")

        # Assert
        assert result is not None
        assert result.service_name == "test-service"
        mock_kv_store.get.assert_called_once_with("service-definitions__test-service")

    @pytest.mark.asyncio
    async def test_get_service_definition_not_found(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting non-existent service definition."""
        # Arrange
        mock_kv_store.get.return_value = None

        # Act
        result = await service.get_service_definition("non-existent")

        # Assert
        assert result is None
        mock_kv_store.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service_definition_invalid_data(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting service with invalid data."""
        # Arrange - Invalid data that can't be parsed
        mock_entry = Mock()
        mock_entry.value = {"invalid": "data", "missing": "required_fields"}
        mock_kv_store.get.return_value = mock_entry

        # Act & Assert
        with pytest.raises(ServiceRegistryException) as exc_info:
            await service.get_service_definition("invalid-service")

        assert "Failed to get service definition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_service_definition_kv_error(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test KV store error when getting service."""
        # Arrange
        mock_kv_store.get.side_effect = Exception("Connection lost")

        # Act & Assert
        with pytest.raises(ServiceRegistryException) as exc_info:
            await service.get_service_definition("error-service")

        assert "Failed to get service definition" in str(exc_info.value)

    # Test list_services edge cases
    @pytest.mark.asyncio
    async def test_list_services_success(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test listing all services successfully."""
        # Arrange
        mock_kv_store.keys.return_value = [
            "service-definitions__service-1",
            "service-definitions__service-2",
        ]

        mock_entry1 = Mock()
        mock_entry1.value = sample_definition.model_dump()

        mock_entry2 = Mock()
        definition2 = sample_definition.model_copy(update={"service_name": "service-2"})
        mock_entry2.value = definition2.model_dump()

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        result = await service.list_services()

        # Assert
        assert len(result) == 2
        assert result[0].service_name in ["test-service", "service-2"]
        mock_kv_store.keys.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_services_empty(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test listing services when none exist."""
        # Arrange
        mock_kv_store.keys.return_value = []

        # Act
        result = await service.list_services()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_list_services_with_invalid_entries(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test listing services with some invalid entries."""
        # Arrange
        mock_kv_store.keys.return_value = [
            "service-definitions__valid",
            "service-definitions__invalid",
        ]

        # First is valid
        mock_entry1 = Mock()
        mock_entry1.value = sample_definition.model_dump()

        # Second is invalid
        mock_entry2 = Mock()
        mock_entry2.value = {"invalid": "data"}

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act - Should skip invalid and return valid
        result = await service.list_services()

        # Assert
        assert len(result) == 1
        assert result[0].service_name == "test-service"

    @pytest.mark.asyncio
    async def test_list_services_kv_error(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test KV store error when listing services."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("KV unavailable")

        # Act & Assert
        with pytest.raises(ServiceRegistryException) as exc_info:
            await service.list_services()

        assert "Failed to list services" in str(exc_info.value)

    # Test delete_service edge cases
    @pytest.mark.asyncio
    async def test_delete_service_success(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test successfully deleting a service."""
        # Arrange
        mock_kv_store.delete.return_value = None

        # Act
        result = await service.delete_service("test-service")

        # Assert
        assert result is True
        mock_kv_store.delete.assert_called_once_with("service-definitions__test-service")

    @pytest.mark.asyncio
    async def test_delete_service_not_found(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test deleting non-existent service."""
        # Arrange
        mock_kv_store.delete.side_effect = Exception("Key not found")

        # Act
        result = await service.delete_service("non-existent")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_service_kv_error(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test KV error during delete."""
        # Arrange
        mock_kv_store.delete.side_effect = Exception("Permission denied")

        # Act
        result = await service.delete_service("protected-service")

        # Assert
        assert result is False

    # Test service_exists edge cases
    @pytest.mark.asyncio
    async def test_service_exists_true(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test checking if service exists - true case."""
        # Arrange
        mock_entry = Mock()
        mock_entry.value = sample_definition.model_dump()
        mock_kv_store.get.return_value = mock_entry

        # Act
        result = await service.service_exists("test-service")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_service_exists_false(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test checking if service exists - false case."""
        # Arrange
        mock_kv_store.get.return_value = None

        # Act
        result = await service.service_exists("non-existent")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_service_exists_kv_error(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test service_exists with KV error returns False."""
        # Arrange
        mock_kv_store.get.side_effect = Exception("Network error")

        # Act
        result = await service.service_exists("error-service")

        # Assert
        assert result is False

    # Test get_service_by_version edge cases
    @pytest.mark.asyncio
    async def test_get_service_by_version_found(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test getting service by specific version."""
        # Arrange
        mock_entry = Mock()
        mock_entry.value = sample_definition.model_dump()
        mock_kv_store.get.return_value = mock_entry

        # Act
        result = await service.get_service_by_version("test-service", "1.0.0")

        # Assert
        assert result is not None
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_service_by_version_wrong_version(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test getting service with non-matching version."""
        # Arrange
        mock_entry = Mock()
        mock_entry.value = sample_definition.model_dump()
        mock_kv_store.get.return_value = mock_entry

        # Act
        result = await service.get_service_by_version("test-service", "2.0.0")

        # Assert
        assert result is None  # Version doesn't match

    @pytest.mark.asyncio
    async def test_get_service_by_version_not_found(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
    ) -> None:
        """Test getting non-existent service by version."""
        # Arrange
        mock_kv_store.get.return_value = None

        # Act
        result = await service.get_service_by_version("non-existent", "1.0.0")

        # Assert
        assert result is None

    # Test search_services edge cases
    @pytest.mark.asyncio
    async def test_search_services_by_owner(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test searching services by owner."""
        # Arrange
        def1 = sample_definition
        def2 = sample_definition.model_copy(
            update={"service_name": "service-2", "owner": "other-team"}
        )
        def3 = sample_definition.model_copy(
            update={"service_name": "service-3", "owner": "test-team"}
        )

        mock_kv_store.keys.return_value = [
            "service-definitions__test-service",
            "service-definitions__service-2",
            "service-definitions__service-3",
        ]

        mock_entry1 = Mock()
        mock_entry1.value = def1.model_dump()
        mock_entry2 = Mock()
        mock_entry2.value = def2.model_dump()
        mock_entry3 = Mock()
        mock_entry3.value = def3.model_dump()

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2, mock_entry3]

        # Act
        result = await service.search_services(owner="test-team")

        # Assert
        assert len(result) == 2
        assert all(s.owner == "test-team" for s in result)

    @pytest.mark.asyncio
    async def test_search_services_by_metadata(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test searching services by metadata."""
        # Arrange
        def1 = sample_definition  # Has type: rpc
        def2 = sample_definition.model_copy(
            update={"service_name": "service-2", "metadata": {"type": "http"}}
        )

        mock_kv_store.keys.return_value = [
            "service-definitions__test-service",
            "service-definitions__service-2",
        ]

        mock_entry1 = Mock()
        mock_entry1.value = def1.model_dump()
        mock_entry2 = Mock()
        mock_entry2.value = def2.model_dump()

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        result = await service.search_services(metadata={"type": "rpc"})

        # Assert
        assert len(result) == 1
        assert result[0].metadata["type"] == "rpc"

    @pytest.mark.asyncio
    async def test_search_services_no_match(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test searching with no matches."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-definitions__test-service"]

        mock_entry = Mock()
        mock_entry.value = sample_definition.model_dump()
        mock_kv_store.get.return_value = mock_entry

        # Act
        result = await service.search_services(owner="non-existent-team")

        # Assert
        assert result == []

    # Test concurrent operations
    @pytest.mark.asyncio
    async def test_concurrent_updates(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test handling concurrent service updates."""
        import asyncio

        # Arrange
        mock_kv_store.get.return_value = None
        mock_kv_store.put.return_value = None

        # Act - Simulate concurrent updates
        tasks = [
            service.create_or_update_service(
                sample_definition.model_copy(update={"version": f"1.0.{i}"})
            )
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= 1  # At least one should succeed

    # Test error recovery
    @pytest.mark.asyncio
    async def test_transient_error_recovery(
        self,
        service: ServiceRegistryService,
        mock_kv_store: Mock,
        sample_definition: ServiceDefinition,
    ) -> None:
        """Test recovery from transient errors."""
        # Arrange - First call fails, second succeeds
        mock_kv_store.get.side_effect = [
            Exception("Temporary network issue"),
            None,
        ]
        mock_kv_store.put.return_value = None

        # Act
        # First attempt fails
        with pytest.raises(ServiceRegistryException):
            await service.create_or_update_service(sample_definition)

        # Reset side effect for second attempt
        mock_kv_store.get.side_effect = None
        mock_kv_store.get.return_value = None

        # Second attempt succeeds
        result = await service.create_or_update_service(sample_definition)

        # Assert
        assert result == sample_definition

    # Test hexagonal architecture compliance
    def test_service_follows_hexagonal_architecture(self, service: ServiceRegistryService) -> None:
        """Verify the service follows hexagonal architecture."""
        import inspect

        source = inspect.getsource(ServiceRegistryService)

        # Should not contain infrastructure-specific code
        assert "import nats" not in source
        assert "import redis" not in source
        assert "import psycopg" not in source

        # Should use domain models
        assert "ServiceDefinition" in source
        assert "ServiceRegistryException" in source

        # Should have proper abstraction
        assert "_kv_store" in source
