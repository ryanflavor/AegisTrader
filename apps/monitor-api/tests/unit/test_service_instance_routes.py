"""Unit tests for service instance API routes.

These tests verify the behavior of API endpoints for service instance monitoring,
including proper error handling, dependency injection, and response formatting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.exceptions import ServiceNotFoundException
from app.domain.models import ServiceInstance
from app.infrastructure.api.service_instance_routes import (
    get_health_summary,
    get_instances_by_status,
    get_service_instance,
    get_service_instance_service,
    list_service_instances,
    list_service_instances_by_name,
)
from fastapi import HTTPException

if TYPE_CHECKING:
    pass


class TestServiceInstanceRoutes:
    """Test cases for service instance API routes."""

    @pytest.fixture
    def mock_instance(self) -> ServiceInstance:
        """Create a mock service instance."""
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

    @pytest.fixture
    def mock_connection_manager(self) -> Mock:
        """Create a mock connection manager."""
        manager = Mock()
        manager.instance_repository = Mock()
        return manager

    @pytest.fixture
    def mock_service_instance_service(self) -> Mock:
        """Create a mock service instance service."""
        service = Mock()
        # Set up async methods
        service.list_all_instances = AsyncMock()
        service.list_instances_by_service = AsyncMock()
        service.get_instance = AsyncMock()
        service.get_health_summary = AsyncMock()
        service.get_instances_by_status = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_service_instance_service(self, mock_connection_manager: Mock) -> None:
        """Test dependency injection for service instance service."""
        # Arrange & Act
        service = await get_service_instance_service(mock_connection_manager)

        # Assert
        assert service is not None
        assert service._repository == mock_connection_manager.instance_repository

    @pytest.mark.asyncio
    async def test_list_service_instances_success(
        self, mock_service_instance_service: Mock, mock_instance: ServiceInstance
    ) -> None:
        """Test successfully listing all service instances."""
        # Arrange
        expected_instances = [mock_instance]
        mock_service_instance_service.list_all_instances.return_value = expected_instances

        # Act
        result = await list_service_instances(service=mock_service_instance_service)

        # Assert
        assert result == expected_instances
        mock_service_instance_service.list_all_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_service_instances_error(self, mock_service_instance_service: Mock) -> None:
        """Test error handling when listing service instances fails."""
        # Arrange
        mock_service_instance_service.list_all_instances.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await list_service_instances(service=mock_service_instance_service)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to list service instances"

    @pytest.mark.asyncio
    async def test_list_service_instances_by_name_success(
        self, mock_service_instance_service: Mock, mock_instance: ServiceInstance
    ) -> None:
        """Test successfully listing instances by service name."""
        # Arrange
        service_name = "test-service"
        expected_instances = [mock_instance]
        mock_service_instance_service.list_instances_by_service.return_value = expected_instances

        # Act
        result = await list_service_instances_by_name(
            service_name=service_name, service=mock_service_instance_service
        )

        # Assert
        assert result == expected_instances
        mock_service_instance_service.list_instances_by_service.assert_called_once_with(
            service_name
        )

    @pytest.mark.asyncio
    async def test_list_service_instances_by_name_error(
        self, mock_service_instance_service: Mock
    ) -> None:
        """Test error handling when listing instances by name fails."""
        # Arrange
        service_name = "test-service"
        mock_service_instance_service.list_instances_by_service.side_effect = Exception(
            "Connection error"
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await list_service_instances_by_name(
                service_name=service_name, service=mock_service_instance_service
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == f"Failed to list instances for service {service_name}"

    @pytest.mark.asyncio
    async def test_get_health_summary_success(self, mock_service_instance_service: Mock) -> None:
        """Test successfully getting health summary."""
        # Arrange
        expected_summary = {
            "total": 10,
            "active": 7,
            "unhealthy": 2,
            "standby": 1,
        }
        mock_service_instance_service.get_health_summary.return_value = expected_summary

        # Act
        result = await get_health_summary(service=mock_service_instance_service)

        # Assert
        assert result == expected_summary
        mock_service_instance_service.get_health_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_health_summary_error(self, mock_service_instance_service: Mock) -> None:
        """Test error handling when getting health summary fails."""
        # Arrange
        mock_service_instance_service.get_health_summary.side_effect = Exception(
            "Aggregation error"
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_health_summary(service=mock_service_instance_service)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to get health summary"

    @pytest.mark.asyncio
    async def test_get_instances_by_status_success(
        self, mock_service_instance_service: Mock, mock_instance: ServiceInstance
    ) -> None:
        """Test successfully getting instances by status."""
        # Arrange
        status = "ACTIVE"
        expected_instances = [mock_instance]
        mock_service_instance_service.get_instances_by_status.return_value = expected_instances

        # Act
        result = await get_instances_by_status(status=status, service=mock_service_instance_service)

        # Assert
        assert result == expected_instances
        mock_service_instance_service.get_instances_by_status.assert_called_once_with(status)

    @pytest.mark.asyncio
    async def test_get_instances_by_status_invalid_status(
        self, mock_service_instance_service: Mock
    ) -> None:
        """Test error handling for invalid status value."""
        # Arrange
        status = "INVALID"
        mock_service_instance_service.get_instances_by_status.side_effect = ValueError(
            f"Invalid status: {status}. Must be one of {{'ACTIVE', 'UNHEALTHY', 'STANDBY'}}"
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_instances_by_status(status=status, service=mock_service_instance_service)

        assert exc_info.value.status_code == 400
        assert "Invalid status" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_instances_by_status_error(self, mock_service_instance_service: Mock) -> None:
        """Test error handling when getting instances by status fails."""
        # Arrange
        status = "ACTIVE"
        mock_service_instance_service.get_instances_by_status.side_effect = Exception("Query error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_instances_by_status(status=status, service=mock_service_instance_service)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to get instances by status"

    @pytest.mark.asyncio
    async def test_get_service_instance_success(
        self, mock_service_instance_service: Mock, mock_instance: ServiceInstance
    ) -> None:
        """Test successfully getting a specific service instance."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-123"
        mock_service_instance_service.get_instance.return_value = mock_instance

        # Act
        result = await get_service_instance(
            service_name=service_name,
            instance_id=instance_id,
            service=mock_service_instance_service,
        )

        # Assert
        assert result == mock_instance
        mock_service_instance_service.get_instance.assert_called_once_with(
            service_name, instance_id
        )

    @pytest.mark.asyncio
    async def test_get_service_instance_not_found(
        self, mock_service_instance_service: Mock
    ) -> None:
        """Test error handling when service instance is not found."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-123"
        mock_service_instance_service.get_instance.side_effect = ServiceNotFoundException(
            f"Instance {instance_id} of service {service_name} not found"
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_service_instance(
                service_name=service_name,
                instance_id=instance_id,
                service=mock_service_instance_service,
            )

        assert exc_info.value.status_code == 404
        assert (
            f"Instance {instance_id} of service {service_name} not found" in exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_get_service_instance_error(self, mock_service_instance_service: Mock) -> None:
        """Test error handling when getting service instance fails."""
        # Arrange
        service_name = "test-service"
        instance_id = "test-123"
        mock_service_instance_service.get_instance.side_effect = Exception("Lookup error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_service_instance(
                service_name=service_name,
                instance_id=instance_id,
                service=mock_service_instance_service,
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to get instance details"

    @pytest.mark.asyncio
    @patch("app.infrastructure.api.service_instance_routes.logger")
    async def test_logging_on_list_error(
        self, mock_logger: Mock, mock_service_instance_service: Mock
    ) -> None:
        """Test that errors are properly logged when listing instances fails."""
        # Arrange
        error_message = "Database connection failed"
        mock_service_instance_service.list_all_instances.side_effect = Exception(error_message)

        # Act
        with pytest.raises(HTTPException):
            await list_service_instances(service=mock_service_instance_service)

        # Assert
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed to list service instances" in error_call
        assert error_message in error_call

    @pytest.mark.asyncio
    @patch("app.infrastructure.api.service_instance_routes.logger")
    async def test_logging_on_health_summary_error(
        self, mock_logger: Mock, mock_service_instance_service: Mock
    ) -> None:
        """Test that errors are properly logged when health summary fails."""
        # Arrange
        error_message = "Aggregation failed"
        mock_service_instance_service.get_health_summary.side_effect = Exception(error_message)

        # Act
        with pytest.raises(HTTPException):
            await get_health_summary(service=mock_service_instance_service)

        # Assert
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed to get health summary" in error_call
        assert error_message in error_call

    @pytest.mark.asyncio
    async def test_multiple_instances_returned(self, mock_service_instance_service: Mock) -> None:
        """Test handling multiple service instances."""
        # Arrange
        instances = [
            ServiceInstance(
                service_name=f"service-{i}",
                instance_id=f"instance-{i}",
                host=f"host-{i}",
                port=8080 + i,
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
                metadata={"index": i},
            )
            for i in range(5)
        ]
        mock_service_instance_service.list_all_instances.return_value = instances

        # Act
        result = await list_service_instances(service=mock_service_instance_service)

        # Assert
        assert len(result) == 5
        assert all(isinstance(inst, ServiceInstance) for inst in result)
        assert result == instances

    @pytest.mark.asyncio
    async def test_empty_instances_list(self, mock_service_instance_service: Mock) -> None:
        """Test handling empty list of instances."""
        # Arrange
        mock_service_instance_service.list_all_instances.return_value = []

        # Act
        result = await list_service_instances(service=mock_service_instance_service)

        # Assert
        assert result == []
        mock_service_instance_service.list_all_instances.assert_called_once()
