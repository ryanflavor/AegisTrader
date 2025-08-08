"""Unit tests for stale entry filtering in ServiceInstanceRepositoryAdapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.models import ServiceInstance
from app.infrastructure.service_instance_repository_adapter import (
    ServiceInstanceRepositoryAdapter,
)


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store."""
    kv_store = AsyncMock()
    kv_store.keys = AsyncMock()
    kv_store.get = AsyncMock()
    return kv_store


@pytest.fixture
def repository(mock_kv_store):
    """Create a repository with mock KV store."""
    return ServiceInstanceRepositoryAdapter(mock_kv_store, stale_threshold_seconds=35)


class TestStaleFiltering:
    """Test stale entry filtering functionality."""

    def test_is_stale_no_heartbeat(self, repository):
        """Test that instances with very old heartbeat are considered stale."""
        # Use a very old timestamp instead of None (which is invalid)
        very_old_heartbeat = datetime(2020, 1, 1, tzinfo=UTC)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=very_old_heartbeat,  # Very old heartbeat
        )
        assert repository._is_stale(instance) is True

    def test_is_stale_old_heartbeat(self, repository):
        """Test that instances with old heartbeats are considered stale."""
        # Create an instance with a heartbeat 60 seconds ago
        old_heartbeat = datetime.now(UTC) - timedelta(seconds=60)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=old_heartbeat,
        )
        assert repository._is_stale(instance) is True

    def test_is_not_stale_recent_heartbeat(self, repository):
        """Test that instances with recent heartbeats are not considered stale."""
        # Create an instance with a heartbeat 10 seconds ago
        recent_heartbeat = datetime.now(UTC) - timedelta(seconds=10)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=recent_heartbeat,
        )
        assert repository._is_stale(instance) is False

    def test_is_stale_boundary_condition(self, repository):
        """Test stale detection at the exact threshold boundary."""
        # Exactly at threshold (35 seconds)
        boundary_heartbeat = datetime.now(UTC) - timedelta(seconds=35)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=boundary_heartbeat,
        )
        # Should be stale at exactly 35 seconds (using > not >=)
        assert repository._is_stale(instance) is True

        # Just over threshold (36 seconds)
        over_threshold = datetime.now(UTC) - timedelta(seconds=36)
        instance_stale = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=over_threshold,
        )
        assert repository._is_stale(instance_stale) is True

    def test_is_stale_timezone_handling(self, repository):
        """Test that timezone-aware timestamps are handled correctly."""
        # Create a timezone-aware timestamp (60 seconds old)
        aware_heartbeat = datetime.now(UTC) - timedelta(seconds=60)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=aware_heartbeat,
        )
        # Should be detected as stale (60s > 35s threshold)
        assert repository._is_stale(instance) is True

    def test_configurable_threshold(self, mock_kv_store):
        """Test that the stale threshold is configurable."""
        # Create repository with custom 60-second threshold
        custom_repo = ServiceInstanceRepositoryAdapter(mock_kv_store, stale_threshold_seconds=60)

        # Instance with 45-second old heartbeat
        heartbeat_45s = datetime.now(UTC) - timedelta(seconds=45)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=heartbeat_45s,
        )

        # Should NOT be stale with 60-second threshold
        assert custom_repo._is_stale(instance) is False

        # But WOULD be stale with default 35-second threshold
        default_repo = ServiceInstanceRepositoryAdapter(mock_kv_store, stale_threshold_seconds=35)
        assert default_repo._is_stale(instance) is True

    @pytest.mark.asyncio
    async def test_get_all_instances_filters_stale(self, repository, mock_kv_store):
        """Test that get_all_instances filters out stale entries."""
        # Setup mock data
        now = datetime.now(UTC)
        fresh_heartbeat = now - timedelta(seconds=10)
        stale_heartbeat = now - timedelta(seconds=60)

        # Mock KV store responses
        mock_kv_store.keys.return_value = [
            "service-instances__service1__fresh",
            "service-instances__service1__stale",
        ]

        # Create mock entries
        fresh_entry = MagicMock()
        fresh_entry.value = {
            "service_name": "service1",
            "instance_id": "fresh",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": fresh_heartbeat.isoformat(),
            "metadata": {},
        }

        stale_entry = MagicMock()
        stale_entry.value = {
            "service_name": "service1",
            "instance_id": "stale",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": stale_heartbeat.isoformat(),
            "metadata": {},
        }

        mock_kv_store.get.side_effect = [fresh_entry, stale_entry]

        # Get all instances
        instances = await repository.get_all_instances()

        # Should only return the fresh instance
        assert len(instances) == 1
        assert instances[0].instance_id == "fresh"

    @pytest.mark.asyncio
    async def test_get_instance_returns_none_if_stale(self, repository, mock_kv_store):
        """Test that get_instance returns None for stale entries."""
        # Setup stale instance data
        stale_heartbeat = datetime.now(UTC) - timedelta(seconds=60)
        stale_entry = MagicMock()
        stale_entry.value = {
            "service_name": "test-service",
            "instance_id": "test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": stale_heartbeat.isoformat(),
            "metadata": {},
        }

        mock_kv_store.get.return_value = stale_entry

        # Get specific instance
        instance = await repository.get_instance("test-service", "test-123")

        # Should return None because it's stale
        assert instance is None

    @pytest.mark.asyncio
    async def test_get_instance_returns_fresh(self, repository, mock_kv_store):
        """Test that get_instance returns fresh entries."""
        # Setup fresh instance data
        fresh_heartbeat = datetime.now(UTC) - timedelta(seconds=10)
        fresh_entry = MagicMock()
        fresh_entry.value = {
            "service_name": "test-service",
            "instance_id": "test-123",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": fresh_heartbeat.isoformat(),
            "metadata": {},
        }

        mock_kv_store.get.return_value = fresh_entry

        # Get specific instance
        instance = await repository.get_instance("test-service", "test-123")

        # Should return the instance because it's fresh
        assert instance is not None
        assert instance.instance_id == "test-123"
        assert instance.service_name == "test-service"

    @pytest.mark.asyncio
    async def test_get_instances_by_service_filters_stale(self, repository, mock_kv_store):
        """Test that get_instances_by_service filters out stale entries."""
        # Setup mock data
        now = datetime.now(UTC)
        fresh_heartbeat = now - timedelta(seconds=10)
        stale_heartbeat = now - timedelta(seconds=60)

        # Mock KV store responses
        mock_kv_store.keys.return_value = [
            "service-instances__my-service.fresh1",
            "service-instances__my-service.fresh2",
            "service-instances__my-service.stale1",
        ]

        # Create mock entries
        fresh_entry1 = MagicMock()
        fresh_entry1.value = {
            "service_name": "my-service",
            "instance_id": "fresh1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": fresh_heartbeat.isoformat(),
            "metadata": {},
        }

        fresh_entry2 = MagicMock()
        fresh_entry2.value = {
            "service_name": "my-service",
            "instance_id": "fresh2",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": (now - timedelta(seconds=5)).isoformat(),
            "metadata": {},
        }

        stale_entry = MagicMock()
        stale_entry.value = {
            "service_name": "my-service",
            "instance_id": "stale1",
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": stale_heartbeat.isoformat(),
            "metadata": {},
        }

        mock_kv_store.get.side_effect = [fresh_entry1, fresh_entry2, stale_entry]

        # Get instances for service
        instances = await repository.get_instances_by_service("my-service")

        # Should only return the fresh instances
        assert len(instances) == 2
        instance_ids = {inst.instance_id for inst in instances}
        assert instance_ids == {"fresh1", "fresh2"}

    def test_parse_timestamp_formats(self, repository):
        """Test that various timestamp formats are handled correctly."""
        # ISO format with Z
        data = {"last_heartbeat": "2024-01-01T12:00:00Z"}
        instance = repository._translate_to_domain_model(
            {
                "service_name": "test",
                "instance_id": "123",
                "version": "1.0.0",
                "status": "ACTIVE",
                **data,
            }
        )
        assert instance.last_heartbeat is not None

        # ISO format with timezone
        data = {"last_heartbeat": "2024-01-01T12:00:00+00:00"}
        instance = repository._translate_to_domain_model(
            {
                "service_name": "test",
                "instance_id": "123",
                "version": "1.0.0",
                "status": "ACTIVE",
                **data,
            }
        )
        assert instance.last_heartbeat is not None

        # Unix timestamp
        data = {"last_heartbeat": 1704110400}  # 2024-01-01 12:00:00 UTC
        instance = repository._translate_to_domain_model(
            {
                "service_name": "test",
                "instance_id": "123",
                "version": "1.0.0",
                "status": "ACTIVE",
                **data,
            }
        )
        assert instance.last_heartbeat is not None
