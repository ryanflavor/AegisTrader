"""Repository interfaces for Echo Service following DDD principles.

Repository interfaces define the contract for persistence operations.
Implementations will be in the infrastructure layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .entities import ServiceMetrics, ServiceRegistration
from .value_objects import EchoMode, HealthStatus

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Base repository interface defining common persistence operations."""

    @abstractmethod
    async def save(self, entity: T) -> None:
        """Persist an entity.

        Args:
            entity: The entity to save
        """
        pass

    @abstractmethod
    async def find_by_id(self, entity_id: str) -> T | None:
        """Find an entity by its identifier.

        Args:
            entity_id: The entity identifier

        Returns:
            The entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by its identifier.

        Args:
            entity_id: The entity identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, entity_id: str) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The entity identifier

        Returns:
            True if exists, False otherwise
        """
        pass


class MetricsRepository(Repository[ServiceMetrics]):
    """Repository interface for service metrics persistence.

    Handles storage and retrieval of service metrics data.
    """

    @abstractmethod
    async def get_latest(self, instance_id: str) -> ServiceMetrics | None:
        """Get the latest metrics for a service instance.

        Args:
            instance_id: The service instance identifier

        Returns:
            Latest metrics if found, None otherwise
        """
        pass

    @abstractmethod
    async def save_snapshot(self, metrics: ServiceMetrics) -> None:
        """Save a metrics snapshot.

        Args:
            metrics: The metrics to save
        """
        pass

    @abstractmethod
    async def get_aggregated_metrics(
        self, start_time: float | None = None, end_time: float | None = None
    ) -> dict:
        """Get aggregated metrics across all instances.

        Args:
            start_time: Start time for aggregation (Unix timestamp)
            end_time: End time for aggregation (Unix timestamp)

        Returns:
            Aggregated metrics dictionary
        """
        pass

    @abstractmethod
    async def get_mode_statistics(self) -> dict[EchoMode, int]:
        """Get request statistics by echo mode.

        Returns:
            Dictionary mapping modes to request counts
        """
        pass


class ServiceRegistrationRepository(Repository[ServiceRegistration]):
    """Repository interface for service registration persistence.

    Manages service registration data in the system.
    """

    @abstractmethod
    async def register(self, registration: ServiceRegistration) -> None:
        """Register a service instance.

        Args:
            registration: The service registration data
        """
        pass

    @abstractmethod
    async def deregister(self, instance_id: str) -> bool:
        """Deregister a service instance.

        Args:
            instance_id: The instance identifier

        Returns:
            True if deregistered, False if not found
        """
        pass

    @abstractmethod
    async def update_heartbeat(self, instance_id: str) -> bool:
        """Update the heartbeat timestamp for an instance.

        Args:
            instance_id: The instance identifier

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    async def find_active_instances(self) -> list[ServiceRegistration]:
        """Find all active service instances.

        Returns:
            List of active service registrations
        """
        pass

    @abstractmethod
    async def find_by_service_name(self, service_name: str) -> list[ServiceRegistration]:
        """Find all instances of a specific service.

        Args:
            service_name: The service name to search for

        Returns:
            List of service registrations
        """
        pass

    @abstractmethod
    async def cleanup_expired(self, ttl_seconds: int = 300) -> int:
        """Remove expired service registrations.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            Number of registrations removed
        """
        pass


class HealthStatusRepository(ABC):
    """Repository interface for health status persistence.

    Tracks and stores service health information.
    """

    @abstractmethod
    async def save_health_check(
        self, instance_id: str, status: HealthStatus, details: dict
    ) -> None:
        """Save a health check result.

        Args:
            instance_id: The instance identifier
            status: The health status
            details: Additional health check details
        """
        pass

    @abstractmethod
    async def get_latest_health(self, instance_id: str) -> tuple[HealthStatus, dict] | None:
        """Get the latest health status for an instance.

        Args:
            instance_id: The instance identifier

        Returns:
            Tuple of (status, details) if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_health_history(
        self, instance_id: str, limit: int = 100
    ) -> list[tuple[float, HealthStatus, dict]]:
        """Get health check history for an instance.

        Args:
            instance_id: The instance identifier
            limit: Maximum number of records to return

        Returns:
            List of tuples (timestamp, status, details)
        """
        pass

    @abstractmethod
    async def get_unhealthy_instances(self) -> list[str]:
        """Get list of unhealthy instance IDs.

        Returns:
            List of instance IDs with unhealthy status
        """
        pass


class RequestLogRepository(ABC):
    """Repository interface for request logging.

    Stores and retrieves request/response logs for auditing.
    """

    @abstractmethod
    async def log_request(
        self, request_id: str, request_data: dict, response_data: dict | None, metadata: dict
    ) -> None:
        """Log a request and its response.

        Args:
            request_id: Unique request identifier
            request_data: The request data
            response_data: The response data (None if failed)
            metadata: Additional metadata (timing, instance, etc.)
        """
        pass

    @abstractmethod
    async def find_request(self, request_id: str) -> dict | None:
        """Find a request log by ID.

        Args:
            request_id: The request identifier

        Returns:
            Request log data if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_recent_requests(
        self, limit: int = 100, instance_id: str | None = None
    ) -> list[dict]:
        """Find recent request logs.

        Args:
            limit: Maximum number of logs to return
            instance_id: Filter by instance ID (optional)

        Returns:
            List of request log entries
        """
        pass

    @abstractmethod
    async def count_requests_by_mode(
        self, start_time: float | None = None, end_time: float | None = None
    ) -> dict[str, int]:
        """Count requests grouped by echo mode.

        Args:
            start_time: Start time filter (Unix timestamp)
            end_time: End time filter (Unix timestamp)

        Returns:
            Dictionary mapping mode to request count
        """
        pass
