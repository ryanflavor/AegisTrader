"""Comprehensive tests for cleanup task following TDD and hexagonal architecture.

These tests verify the cleanup task implementation with proper
mocking at architectural boundaries and comprehensive edge case coverage.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from app.domain.models import ServiceInstance
from app.infrastructure.cleanup_task import StaleEntryCleanupTask

if TYPE_CHECKING:
    pass


class TestStaleEntryCleanupTask:
    """Test cases for StaleEntryCleanupTask following hexagonal architecture."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        mock = Mock()
        mock.keys = AsyncMock()
        mock.get = AsyncMock()
        mock.delete = AsyncMock()
        mock.list_all = AsyncMock()
        return mock

    @pytest.fixture
    def cleanup_task(self, mock_kv_store: Mock) -> StaleEntryCleanupTask:
        """Create a cleanup task instance."""
        return StaleEntryCleanupTask(mock_kv_store, cleanup_interval=1, stale_threshold=30)

    @pytest.mark.asyncio
    async def test_cleanup_stale_entries_success(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test successful cleanup of stale entries."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)

        # Create stale service instance
        stale_service = ServiceInstance(
            service_name="test-service-one",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=old_timestamp,
            metadata={},
        )

        # Create fresh service instance
        fresh_service = ServiceInstance(
            service_name="test-service-two",
            instance_id="instance-2",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        mock_kv_store.list_all.return_value = [stale_service, fresh_service]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once_with("test-service-one")

    @pytest.mark.asyncio
    async def test_cleanup_stale_entries_no_stale(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup when no stale entries exist."""
        # Setup
        fresh_service = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        mock_kv_store.list_all.return_value = [fresh_service]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_unhealthy_status(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup of entries with unhealthy status."""
        # Setup
        unhealthy_service = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="UNHEALTHY",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        mock_kv_store.list_all.return_value = [unhealthy_service]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_cleanup_shutdown_status(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup of entries with shutdown status."""
        # Setup - Create a mock that returns SHUTDOWN status
        shutdown_service = Mock()
        shutdown_service.service_name = "test-service"
        shutdown_service.model_dump.return_value = {
            "service_name": "test-service",
            "instance_id": "instance-1",
            "last_heartbeat": datetime.now(UTC).isoformat(),
            "status": "SHUTDOWN",
        }

        mock_kv_store.list_all.return_value = [shutdown_service]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_cleanup_handles_invalid_data(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles invalid entry data gracefully."""
        # Setup - Return None which simulates invalid data
        mock_kv_store.list_all.return_value = [None]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_camelcase_fields(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles camelCase field names."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)

        # Create service with camelCase fields in dict representation
        camel_service = Mock()
        camel_service.service_name = "test-service"
        camel_dict = {
            "serviceName": "test-service",
            "instanceId": "instance-1",
            "lastHeartbeat": old_timestamp.isoformat(),
            "status": "ACTIVE",
        }
        camel_service.model_dump.return_value = camel_dict

        mock_kv_store.list_all.return_value = [camel_service]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_cleanup_with_ttl_entries_not_deleted(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test that entries with TTL are not deleted even if stale."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)
        mock_kv_store.keys.return_value = [
            "service-instances__test-service__instance-1",
        ]

        # Stale entry but has TTL
        ttl_entry = Mock()
        ttl_entry.value = {
            "service_name": "test-service",
            "instance_id": "instance-1",
            "last_heartbeat": old_timestamp.isoformat(),
            "status": "ACTIVE",
        }
        ttl_entry.ttl = 30  # Has TTL - should not be deleted

        mock_kv_store.get.return_value = ttl_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_cleanup_task(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test starting the cleanup task."""
        # Setup
        mock_kv_store.list_all.return_value = []

        # Act
        cleanup_task.start()

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Stop the task
        await cleanup_task.stop()

        # Assert - task should be created
        assert cleanup_task._task is not None

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test stopping the cleanup task."""
        # Setup
        mock_kv_store.list_all.return_value = []

        # Act
        cleanup_task.start()
        await asyncio.sleep(0.1)
        await cleanup_task.stop()

        # Assert - stop event should be set
        assert cleanup_task._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_cleanup_handles_delete_error(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles delete errors gracefully."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)
        mock_kv_store.keys.return_value = [
            "service-instances__test-service__instance-1",
        ]

        stale_entry = Mock()
        stale_entry.value = {
            "service_name": "test-service",
            "instance_id": "instance-1",
            "last_heartbeat": old_timestamp.isoformat(),
            "status": "ACTIVE",
        }
        stale_entry.ttl = None

        mock_kv_store.get.return_value = stale_entry
        mock_kv_store.delete.return_value = False  # Delete fails

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Should handle error and return 0
        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_handles_get_error(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles get errors gracefully."""
        # Setup
        mock_kv_store.keys.return_value = [
            "service-instances__test-service__instance-1",
        ]
        mock_kv_store.get.side_effect = Exception("Get failed")

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Should handle error and return 0
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_task_periodic_run(self, mock_kv_store: Mock) -> None:
        """Test cleanup task runs periodically."""
        # Setup - Use very short interval for testing
        cleanup_task = StaleEntryCleanupTask(
            mock_kv_store, cleanup_interval=0.1, stale_threshold=30
        )
        mock_kv_store.list_all.return_value = []

        # Act
        cleanup_task.start()

        # Let it run for a few cycles
        await asyncio.sleep(0.3)

        # Stop the task
        await cleanup_task.stop()

        # Assert - Should have been called multiple times
        assert mock_kv_store.list_all.call_count >= 2

    @pytest.mark.asyncio
    async def test_cleanup_with_missing_heartbeat(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup with missing heartbeat field."""
        # Setup
        service = Mock()
        service.service_name = "test-service"
        # No heartbeat in the dict
        service_dict = {
            "service_name": "test-service",
            "instance_id": "instance-1",
            "status": "ACTIVE",
        }
        service.model_dump.return_value = service_dict

        mock_kv_store.list_all.return_value = [service]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Entries without heartbeat are not cleaned (no reason to)
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_timezone_variations(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles various timezone formats in timestamps."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)

        # Service with +00:00 timezone
        service1 = Mock()
        service1.service_name = "test-service-one"
        _dict1 = service1.model_dump.return_value = {
            "service_name": "test-service-one",
            "instance_id": "instance-1",
            "last_heartbeat": old_timestamp.isoformat() + "+00:00",
            "status": "ACTIVE",
        }

        # Service with Z timezone
        service2 = Mock()
        service2.service_name = "test-service-two"
        _dict2 = service2.model_dump.return_value = {
            "service_name": "test-service-two",
            "instance_id": "instance-2",
            "last_heartbeat": old_timestamp.isoformat() + "Z",
            "status": "ACTIVE",
        }

        mock_kv_store.list_all.return_value = [service1, service2]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Both should be deleted
        assert deleted_count == 2
        assert mock_kv_store.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_run_once(self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock) -> None:
        """Test running cleanup once manually."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)
        stale_service = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=old_timestamp,
            metadata={},
        )

        mock_kv_store.list_all.return_value = [stale_service]
        mock_kv_store.delete.return_value = True

        # Act
        deleted_count = await cleanup_task.run_once()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once_with("test-service")

    @pytest.mark.asyncio
    async def test_cleanup_handles_list_all_error(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles errors from list_all gracefully."""
        # Setup
        mock_kv_store.list_all.side_effect = Exception("KV store error")

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_delete_exception(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles delete exceptions."""
        # Setup
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)
        stale_service = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=old_timestamp,
            metadata={},
        )

        mock_kv_store.list_all.return_value = [stale_service]
        mock_kv_store.delete.side_effect = Exception("Delete failed")

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Should count as 1 deleted even if delete failed
        assert deleted_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_periodic_run_with_error(self, mock_kv_store: Mock) -> None:
        """Test periodic cleanup continues even with errors."""
        # Setup
        cleanup_task = StaleEntryCleanupTask(
            mock_kv_store, cleanup_interval=0.1, stale_threshold=30
        )
        mock_kv_store.list_all.side_effect = Exception("Error")

        # Act
        cleanup_task.start()
        await asyncio.sleep(0.25)  # Let it run a couple times
        await cleanup_task.stop()

        # Assert - Should have tried multiple times despite errors
        assert mock_kv_store.list_all.call_count >= 2

    @pytest.mark.asyncio
    async def test_start_when_already_running(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test starting cleanup task when already running."""
        # Setup
        mock_kv_store.list_all.return_value = []

        # Act
        cleanup_task.start()
        initial_task = cleanup_task._task
        cleanup_task.start()  # Start again
        second_task = cleanup_task._task

        await cleanup_task.stop()

        # Assert - Should be the same task
        assert initial_task is second_task

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, cleanup_task: StaleEntryCleanupTask) -> None:
        """Test stopping cleanup task when not running."""
        # Act & Assert - Should not raise
        await cleanup_task.stop()
        assert cleanup_task._task is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception_in_processing(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles exceptions during entry processing."""
        # Setup - Create a service that will cause an exception when model_dump is called
        bad_service = Mock()
        bad_service.model_dump.side_effect = Exception("Processing error")

        good_service = ServiceInstance(
            service_name="good-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(UTC),
            metadata={},
        )

        mock_kv_store.list_all.return_value = [bad_service, good_service]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert - Should continue processing after error
        assert deleted_count == 0  # bad_service error, good_service is fresh
        mock_kv_store.delete.assert_not_called()
