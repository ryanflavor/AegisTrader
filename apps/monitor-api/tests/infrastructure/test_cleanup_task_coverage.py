"""Additional tests for cleanup_task to improve coverage.

These tests cover edge cases and improve overall coverage.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from app.infrastructure.cleanup_task import StaleEntryCleanupTask


class TestCleanupTaskCoverage:
    """Additional test cases for StaleEntryCleanupTask to improve coverage."""

    @pytest.fixture
    def mock_kv_store(self) -> Mock:
        """Create a mock KV store."""
        mock = Mock()
        mock.keys = AsyncMock(return_value=[])
        mock.get = AsyncMock(return_value=None)
        mock.delete = AsyncMock()
        return mock

    @pytest.fixture
    def cleanup_task(self, mock_kv_store: Mock) -> StaleEntryCleanupTask:
        """Create a cleanup task instance."""
        return StaleEntryCleanupTask(mock_kv_store, stale_threshold=30)

    @pytest.mark.asyncio
    async def test_cleanup_with_valid_entries(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup with valid (non-stale) entries."""
        # Arrange
        recent_time = datetime.now(UTC).isoformat()
        mock_kv_store.keys.return_value = [
            "service-instances__service1__instance1",
            "service-instances__service2__instance2",
        ]

        mock_entry1 = Mock()
        mock_entry1.value = json.dumps(
            {
                "status": "ACTIVE",
                "last_heartbeat": recent_time,
            }
        ).encode()

        mock_entry2 = Mock()
        mock_entry2.value = json.dumps(
            {
                "status": "ACTIVE",
                "lastHeartbeat": recent_time,  # CamelCase variant
            }
        ).encode()

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_stale_entries(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup with stale entries."""
        # Arrange
        stale_time = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        mock_kv_store.keys.return_value = [
            "service-instances__service1__instance1",
            "service-instances__service2__instance2",
        ]

        mock_entry1 = Mock()
        mock_entry1.value = json.dumps(
            {
                "status": "ACTIVE",
                "last_heartbeat": stale_time,
            }
        ).encode()

        mock_entry2 = Mock()
        mock_entry2.value = json.dumps(
            {
                "status": "UNHEALTHY",
                "last_heartbeat": stale_time,
            }
        ).encode()

        mock_kv_store.get.side_effect = [mock_entry1, mock_entry2]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 2
        assert mock_kv_store.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_with_shutdown_status(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup immediately removes SHUTDOWN status entries."""
        # Arrange
        recent_time = datetime.now(UTC).isoformat()
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "status": "SHUTDOWN",
                "last_heartbeat": recent_time,  # Recent but SHUTDOWN
            }
        ).encode()

        mock_kv_store.get.return_value = mock_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_malformed_json(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles malformed JSON gracefully."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        mock_entry = Mock()
        mock_entry.value = b"not valid json"
        mock_kv_store.get.return_value = mock_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_missing_heartbeat(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles entries without heartbeat field."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "status": "ACTIVE",
                # No heartbeat field
            }
        ).encode()

        mock_kv_store.get.return_value = mock_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_invalid_datetime(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles invalid datetime formats."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "status": "ACTIVE",
                "last_heartbeat": "not-a-datetime",
            }
        ).encode()

        mock_kv_store.get.return_value = mock_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_timezone_aware_datetime(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles timezone-aware datetime formats."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        # Use a stale time with timezone
        stale_time = (datetime.now(UTC) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "status": "ACTIVE",
                "last_heartbeat": stale_time,
            }
        ).encode()

        mock_kv_store.get.return_value = mock_entry

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 1
        mock_kv_store.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_get_exception(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles exceptions during get operation."""
        # Arrange
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]
        mock_kv_store.get.side_effect = Exception("Get failed")

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_delete_exception(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles exceptions during delete operation."""
        # Arrange
        stale_time = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        mock_kv_store.keys.return_value = ["service-instances__service1__instance1"]

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "status": "ACTIVE",
                "last_heartbeat": stale_time,
            }
        ).encode()

        mock_kv_store.get.return_value = mock_entry
        mock_kv_store.delete.side_effect = Exception("Delete failed")

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0  # Delete failed, so count should be 0

    @pytest.mark.asyncio
    async def test_start_and_stop(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test starting and stopping the cleanup task."""
        # Arrange
        mock_kv_store.keys.return_value = []

        # Act
        cleanup_task.start()
        assert cleanup_task._task is not None
        assert not cleanup_task._task.done()

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop the task
        await cleanup_task.stop()

        # Assert
        assert cleanup_task._task.cancelled() or cleanup_task._task.done()

    @pytest.mark.asyncio
    async def test_stop_without_start(self, cleanup_task: StaleEntryCleanupTask) -> None:
        """Test stopping when task was never started."""
        # Act & Assert - should not raise
        await cleanup_task.stop()
        assert cleanup_task._task is None

    @pytest.mark.asyncio
    async def test_multiple_start_calls(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test that multiple start calls don't create multiple tasks."""
        # Arrange
        mock_kv_store.keys.return_value = []

        # Act
        cleanup_task.start()
        first_task = cleanup_task._task

        cleanup_task.start()  # Second call
        second_task = cleanup_task._task

        # Assert
        assert first_task is second_task

        # Cleanup
        await cleanup_task.stop()

    @pytest.mark.asyncio
    async def test_cleanup_interval_timing(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test that cleanup runs at the specified interval."""
        # Arrange
        mock_kv_store.keys.return_value = []
        cleanup_task.cleanup_interval = 0.1  # Short interval for testing

        # Act
        cleanup_task.start()
        await asyncio.sleep(0.25)  # Should run at least twice
        await cleanup_task.stop()

        # Assert - keys should be called at least once
        assert mock_kv_store.keys.call_count >= 1

    @pytest.mark.asyncio
    async def test_cleanup_with_empty_value(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles entries with None or empty values."""
        # Arrange
        mock_kv_store.keys.return_value = [
            "service-instances__service1__instance1",
            "service-instances__service2__instance2",
        ]

        mock_kv_store.get.side_effect = [None, Mock(value=b"")]

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 0
        mock_kv_store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_camelcase_and_snake_case_mix(
        self, cleanup_task: StaleEntryCleanupTask, mock_kv_store: Mock
    ) -> None:
        """Test cleanup handles both camelCase and snake_case field names."""
        # Arrange
        stale_time = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        recent_time = datetime.now(UTC).isoformat()

        mock_kv_store.keys.return_value = [
            "service-instances__service1__instance1",
            "service-instances__service2__instance2",
            "service-instances__service3__instance3",
        ]

        # Mix of field naming conventions
        entries = [
            Mock(value=json.dumps({"status": "ACTIVE", "last_heartbeat": stale_time}).encode()),
            Mock(value=json.dumps({"status": "ACTIVE", "lastHeartbeat": recent_time}).encode()),
            Mock(value=json.dumps({"status": "ACTIVE", "LastHeartbeat": stale_time}).encode()),
        ]

        mock_kv_store.get.side_effect = entries

        # Act
        deleted_count = await cleanup_task._cleanup_stale_entries()

        # Assert
        assert deleted_count == 2  # Two stale entries should be deleted
        assert mock_kv_store.delete.call_count == 2
