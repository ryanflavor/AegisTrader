"""Unit tests for sticky active use cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.application.sticky_active_use_cases import (
    StickyActiveHeartbeatRequest,
    StickyActiveHeartbeatUseCase,
    StickyActiveRegistrationRequest,
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
    return repo


@pytest.fixture
def mock_service_registry():
    """Create mock service registry."""
    registry = AsyncMock()
    registry.register = AsyncMock()
    registry.get_instances = AsyncMock(return_value=[])
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


class TestStickyActiveRegistrationUseCase:
    """Test sticky active registration use case."""

    @pytest.mark.asyncio
    async def test_register_and_win_election(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test successful registration with election win."""
        # Arrange
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
            group_id="default",
            ttl_seconds=30,
            leader_ttl_seconds=5,
            metadata={"zone": "us-east-1"},
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.service_name == "test-service"
        assert response.instance_id == "instance-1"
        assert response.is_leader is True
        assert response.sticky_active_status == "ACTIVE"
        assert response.group_id == "default"

        # Verify election attempt
        mock_election_repository.attempt_leadership.assert_called_once()
        call_args = mock_election_repository.attempt_leadership.call_args
        assert str(call_args.kwargs["service_name"]) == "test-service"
        assert str(call_args.kwargs["instance_id"]) == "instance-1"
        assert call_args.kwargs["group_id"] == "default"
        assert call_args.kwargs["ttl_seconds"] == 5

        # Verify service registration
        mock_service_registry.register.assert_called_once()
        service_instance = mock_service_registry.register.call_args.args[0]
        assert isinstance(service_instance, ServiceInstance)
        assert service_instance.service_name == "test-service"
        assert service_instance.sticky_active_status == "ACTIVE"
        assert service_instance.sticky_active_group == "default"

        # Verify metrics
        mock_metrics.increment.assert_called_with("sticky_active.election.won")

    @pytest.mark.asyncio
    async def test_register_and_lose_election(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test registration when losing election."""
        # Arrange
        mock_election_repository.attempt_leadership.return_value = False
        mock_election_repository.get_current_leader.return_value = (
            InstanceId(value="instance-2"),
            {},
        )

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

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.is_leader is False
        assert response.sticky_active_status == "STANDBY"

        # Verify service registration with STANDBY status
        service_instance = mock_service_registry.register.call_args.args[0]
        assert service_instance.sticky_active_status == "STANDBY"

        # Verify metrics
        mock_metrics.increment.assert_called_with("sticky_active.election.lost")

    @pytest.mark.asyncio
    async def test_restore_existing_election_state(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_message_bus,
        mock_metrics,
        mock_logger,
    ):
        """Test restoring existing election state."""
        # Arrange
        existing_election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="production",
        )
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
            group_id="production",
        )

        # Act
        await use_case.execute(request)

        # Assert
        mock_election_repository.get_election_state.assert_called_once()
        # Should use existing election, not create new one
        assert mock_election_repository.save_election_state.call_args.args[0] == existing_election


class TestStickyActiveHeartbeatUseCase:
    """Test sticky active heartbeat use case."""

    @pytest.mark.asyncio
    async def test_heartbeat_as_leader(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat update as leader."""
        # Arrange
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        election.start_election()
        election.win_election()

        mock_election_repository.get_election_state.return_value = election
        mock_election_repository.get_current_leader.return_value = (
            InstanceId(value="instance-1"),
            {},
        )

        service_instance = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_status="ACTIVE",
        )
        mock_service_registry.get_instances.return_value = [service_instance]

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

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is True
        mock_election_repository.update_leadership.assert_called_once()
        mock_service_registry.update_heartbeat.assert_called_once()
        mock_metrics.increment.assert_any_call("sticky_active.leader.heartbeat")
        mock_metrics.increment.assert_any_call("sticky_active.heartbeat.success")

    @pytest.mark.asyncio
    async def test_heartbeat_as_standby(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat update as standby."""
        # Arrange
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        # Not a leader
        mock_election_repository.get_election_state.return_value = election
        mock_election_repository.get_current_leader.return_value = (
            InstanceId(value="instance-2"),
            {},
        )

        service_instance = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_status="STANDBY",
        )
        mock_service_registry.get_instances.return_value = [service_instance]

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

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is True
        mock_election_repository.update_leadership.assert_not_called()
        mock_service_registry.update_heartbeat.assert_called_once()
        assert service_instance.sticky_active_status == "STANDBY"

    @pytest.mark.asyncio
    async def test_heartbeat_leader_fails_update(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat when leader fails to update."""
        # Arrange
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        election.start_election()
        election.win_election()

        mock_election_repository.get_election_state.return_value = election
        mock_election_repository.update_leadership.return_value = False  # Failed

        service_instance = ServiceInstance(
            service_name="test-service",
            instance_id="instance-1",
            version="1.0.0",
            status="ACTIVE",
        )
        mock_service_registry.get_instances.return_value = [service_instance]

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

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is True
        mock_metrics.increment.assert_any_call("sticky_active.leader.lost")
        # Should step down from leadership
        assert election.status.value == "STANDBY"

    @pytest.mark.asyncio
    async def test_heartbeat_no_election_state(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat when no election state exists."""
        # Arrange
        mock_election_repository.get_election_state.return_value = None

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

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is False
        mock_logger.warning.assert_called_once()
        mock_service_registry.update_heartbeat.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_instance_not_found(
        self,
        mock_election_repository,
        mock_service_registry,
        mock_metrics,
        mock_logger,
    ):
        """Test heartbeat when instance not found in registry."""
        # Arrange
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            group_id="default",
        )
        mock_election_repository.get_election_state.return_value = election
        mock_service_registry.get_instances.return_value = []  # No instances

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

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is False
        mock_logger.error.assert_called_once()
        mock_service_registry.update_heartbeat.assert_not_called()
