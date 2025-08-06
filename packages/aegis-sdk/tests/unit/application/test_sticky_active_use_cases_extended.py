"""Extended unit tests for sticky active use cases to achieve 100% coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.application.sticky_active_use_cases import (
    StickyActiveHeartbeatRequest,
    StickyActiveHeartbeatUseCase,
    StickyActiveMonitoringUseCase,
    StickyActiveRegistrationRequest,
    StickyActiveRegistrationResponse,
    StickyActiveRegistrationUseCase,
)
from aegis_sdk.domain.aggregates import StickyActiveElection
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.domain.value_objects import InstanceId, ServiceName


@pytest.fixture
def mock_election_repository():
    """Create mock election repository."""
    repo = AsyncMock()
    repo.get_election_state = AsyncMock(return_value=None)
    repo.attempt_leadership = AsyncMock(return_value=True)
    repo.get_current_leader = AsyncMock(return_value=(None, {}))
    repo.save_election_state = AsyncMock()
    repo.update_leadership = AsyncMock(return_value=True)
    repo.release_leadership = AsyncMock(return_value=True)

    # Mock watch_leadership to return an empty async iterator by default
    async def default_watch():
        return
        yield  # Make it an async generator

    repo.watch_leadership = MagicMock(return_value=default_watch())
    return repo


@pytest.fixture
def mock_service_registry():
    """Create mock service registry."""
    registry = AsyncMock()
    registry.register = AsyncMock()
    registry.get_instance = AsyncMock(return_value=None)
    registry.update_heartbeat = AsyncMock()
    return registry


@pytest.fixture
def mock_message_bus():
    """Create mock message bus."""
    bus = AsyncMock()
    bus.publish_event = AsyncMock()
    return bus


@pytest.fixture
def mock_metrics():
    """Create mock metrics."""
    metrics = MagicMock()
    metrics.increment = MagicMock()
    return metrics


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.exception = MagicMock()
    return logger


class TestStickyActiveRegistrationUseCaseExtended:
    """Extended tests for sticky active registration use case."""

    @pytest.mark.asyncio
    async def test_registration_with_invalid_request(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test registration with invalid request parameters."""
        # Test with invalid service name
        with pytest.raises(ValueError, match="Invalid format"):
            StickyActiveRegistrationRequest(
                service_name="-invalid",  # Invalid format
                instance_id="instance-1",
                version="1.0.0",
            )

    @pytest.mark.asyncio
    async def test_registration_when_already_leader(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test registration when instance is already leader."""
        # Create existing election where instance is already leader
        existing_election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        existing_election.start_election()
        existing_election.win_election()

        mock_election_repository.get_election_state.return_value = existing_election

        use_case = StickyActiveRegistrationUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveRegistrationRequest(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
        )

        response = await use_case.execute(request)

        # Should maintain leadership without new election
        assert response.is_leader is True
        assert response.sticky_active_status == "ACTIVE"
        mock_election_repository.attempt_leadership.assert_not_called()

    @pytest.mark.asyncio
    async def test_registration_with_save_failure(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test registration when saving election state fails."""
        mock_election_repository.save_election_state.side_effect = Exception("Save failed")

        use_case = StickyActiveRegistrationUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveRegistrationRequest(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
        )

        # Should continue despite save failure
        response = await use_case.execute(request)

        assert response.is_leader is True
        mock_logger.exception.assert_called_with("Failed to save election state: Save failed")

    @pytest.mark.asyncio
    async def test_registration_with_registry_failure(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test registration when service registry fails."""
        mock_service_registry.register.side_effect = RuntimeError("Registry unavailable")

        use_case = StickyActiveRegistrationUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveRegistrationRequest(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
        )

        with pytest.raises(RuntimeError, match="Service registration failed"):
            await use_case.execute(request)

        mock_metrics.increment.assert_any_call("sticky_active.registration.error")


class TestStickyActiveHeartbeatUseCaseExtended:
    """Extended tests for sticky active heartbeat use case."""

    @pytest.mark.asyncio
    async def test_heartbeat_with_invalid_request(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat with invalid request parameters."""
        # Mock to raise ValueError on value object creation
        mock_election_repository.get_election_state.side_effect = ValueError("Invalid name")

        use_case = StickyActiveHeartbeatUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveHeartbeatRequest(
            service_name="test",  # Too short but will be caught in execution
            instance_id="i",
        )

        # The request validation in execute should handle this
        result = await use_case.execute(request)

        assert result is False
        mock_metrics.increment.assert_called_with("sticky_active.heartbeat.validation_error")

    @pytest.mark.asyncio
    async def test_heartbeat_registry_exception(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat when registry operations fail."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        mock_election_repository.get_election_state.return_value = election

        # Make registry fail
        mock_service_registry.get_instance.side_effect = Exception("Registry error")

        use_case = StickyActiveHeartbeatUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveHeartbeatRequest(
            service_name="test-service",
            instance_id="instance-1",
        )

        result = await use_case.execute(request)

        assert result is False
        mock_metrics.increment.assert_called_with("sticky_active.heartbeat.error")
        mock_logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_heartbeat_save_state_failure(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat when saving election state fails."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        mock_election_repository.get_election_state.return_value = election
        mock_election_repository.save_election_state.side_effect = Exception("Save failed")

        # Create service instance
        service_instance = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_status="STANDBY",
        )
        mock_service_registry.get_instance.return_value = service_instance

        use_case = StickyActiveHeartbeatUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_metrics,
            mock_logger,
        )

        request = StickyActiveHeartbeatRequest(
            service_name="test-service",
            instance_id="instance-1",
        )

        result = await use_case.execute(request)

        # Should succeed despite save failure
        assert result is True
        mock_logger.error.assert_called_with("Failed to save election state: Save failed")


class TestStickyActiveMonitoringUseCaseExtended:
    """Extended tests for sticky active monitoring use case."""

    @pytest.mark.asyncio
    async def test_monitoring_with_consecutive_errors(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test monitoring stops after too many consecutive errors."""

        # Make watch_leadership raise exceptions
        async def failing_watch():
            raise Exception("Watch failed")
            yield  # Never reached

        mock_election_repository.watch_leadership.return_value = failing_watch()

        use_case = StickyActiveMonitoringUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        with pytest.raises(RuntimeError, match="Monitoring failed after"):
            await use_case._monitor_leadership(
                ServiceName(value="test-service"),
                InstanceId(value="instance-1"),
                "default",
            )

        # Should log errors and increment metrics
        assert mock_logger.exception.call_count >= 1
        mock_metrics.increment.assert_any_call("sticky_active.monitoring.error")
        mock_metrics.increment.assert_any_call("sticky_active.monitoring.stopped")

    @pytest.mark.asyncio
    async def test_monitoring_leader_expired_but_takeover_fails(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test handling leader expiration when takeover fails."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )

        # Takeover fails
        mock_election_repository.attempt_leadership.return_value = False
        mock_election_repository.get_current_leader.return_value = (
            InstanceId(value="instance-2"),
            {},
        )

        use_case = StickyActiveMonitoringUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        await use_case._handle_leader_expired(
            ServiceName(value="test-service"),
            InstanceId(value="instance-1"),
            "default",
            election,
        )

        # Should lose election
        assert not election.is_leader
        mock_metrics.increment.assert_called_with("sticky_active.failover.lost")

    @pytest.mark.asyncio
    async def test_monitoring_status_update_failure(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test when updating instance status fails."""
        mock_service_registry.get_instance.side_effect = Exception("Registry error")

        use_case = StickyActiveMonitoringUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        # Should not raise exception
        await use_case._update_instance_status(
            ServiceName(value="test-service"),
            InstanceId(value="instance-1"),
            "ACTIVE",
        )

        mock_logger.exception.assert_called()
        mock_metrics.increment.assert_called_with("sticky_active.status_update.error")

    @pytest.mark.asyncio
    async def test_monitoring_with_status_callback(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test monitoring with status callback function."""
        status_changes = []

        def status_callback(is_active: bool):
            status_changes.append(is_active)

        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )

        mock_election_repository.attempt_leadership.return_value = True

        use_case = StickyActiveMonitoringUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
            status_callback=status_callback,
        )

        await use_case._handle_leader_expired(
            ServiceName(value="test-service"),
            InstanceId(value="instance-1"),
            "default",
            election,
        )

        # Callback should be called with True when becoming leader
        assert status_changes == [True]
        assert election.is_leader

    @pytest.mark.asyncio
    async def test_monitoring_restart_existing_task(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test that starting monitoring cancels existing task."""
        use_case = StickyActiveMonitoringUseCase(
            mock_election_repository,
            mock_service_registry,
            mock_message_bus,
            mock_metrics,
            mock_logger,
        )

        # Start monitoring
        await use_case.start_monitoring("test-service", "instance-1", "default")
        key = "test-service/instance-1/default"
        first_task = use_case._monitoring_tasks[key]

        # Start monitoring again (should cancel first task)
        await use_case.start_monitoring("test-service", "instance-1", "default")
        second_task = use_case._monitoring_tasks[key]

        assert first_task != second_task
        assert first_task.cancelled() or first_task.done()

        # Clean up
        second_task.cancel()


class TestRequestValidation:
    """Test request model validation."""

    def test_registration_request_validation(self):
        """Test StickyActiveRegistrationRequest validation."""
        # Valid request
        request = StickyActiveRegistrationRequest(
            service_name="valid-service",
            instance_id="instance-123",
            version="1.2.3",
            group_id="production",
            ttl_seconds=30,
            leader_ttl_seconds=5,
        )
        assert request.service_name == "valid-service"

        # Invalid service name format
        with pytest.raises(ValueError, match="Invalid format"):
            StickyActiveRegistrationRequest(
                service_name="-invalid",
                instance_id="instance-1",
                version="1.0.0",
            )

        # Invalid version format
        with pytest.raises(ValueError):
            StickyActiveRegistrationRequest(
                service_name="test",
                instance_id="instance-1",
                version="invalid",
            )

        # Invalid TTL values
        with pytest.raises(ValueError):
            StickyActiveRegistrationRequest(
                service_name="test",
                instance_id="instance-1",
                version="1.0.0",
                ttl_seconds=0,  # Must be >= 1
            )

    def test_heartbeat_request_validation(self):
        """Test StickyActiveHeartbeatRequest validation."""
        # Valid request
        request = StickyActiveHeartbeatRequest(
            service_name="valid-service",
            instance_id="instance-123",
            group_id="production",
            ttl_seconds=30,
            leader_ttl_seconds=5,
        )
        assert request.service_name == "valid-service"

        # Invalid values
        with pytest.raises(ValueError):
            StickyActiveHeartbeatRequest(
                service_name="",  # Empty name
                instance_id="instance-1",
            )

        with pytest.raises(ValueError):
            StickyActiveHeartbeatRequest(
                service_name="test",
                instance_id="",  # Empty instance ID
            )

    def test_registration_response_validation(self):
        """Test StickyActiveRegistrationResponse validation."""
        # Valid response
        response = StickyActiveRegistrationResponse(
            service_name="test-service",
            instance_id="instance-1",
            is_leader=True,
            sticky_active_status="ACTIVE",
            group_id="default",
        )
        assert response.sticky_active_status == "ACTIVE"

        # Invalid status
        with pytest.raises(ValueError, match="ACTIVE|STANDBY"):
            StickyActiveRegistrationResponse(
                service_name="test-service",
                instance_id="instance-1",
                is_leader=True,
                sticky_active_status="INVALID",
                group_id="default",
            )
