"""Unit tests for ElectionCoordinator class."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aegis_sdk.domain.enums import StickyActiveStatus
from aegis_sdk.domain.models import KVEntry
from aegis_sdk.domain.value_objects import (
    ElectionState,
    FailoverPolicy,
    InstanceId,
    ServiceName,
)
from aegis_sdk.infrastructure.election_coordinator import ElectionCoordinator
from aegis_sdk.ports.kv_store import KVStorePort
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store."""
    store = Mock(spec=KVStorePort)
    store.get = AsyncMock()
    store.put = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def mock_service_registry():
    """Create a mock service registry."""
    registry = Mock(spec=ServiceRegistryPort)
    registry.get_instance = AsyncMock()
    registry.update_instance = AsyncMock()
    registry.register_instance = AsyncMock()
    return registry


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock(spec=LoggerPort)
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    logger.debug = AsyncMock()
    return logger


@pytest.fixture
def election_coordinator(mock_kv_store, mock_service_registry, mock_logger):
    """Create an ElectionCoordinator instance with mocked dependencies."""
    return ElectionCoordinator(
        kv_store=mock_kv_store,
        service_registry=mock_service_registry,
        service_name=ServiceName(value="test-service"),
        instance_id=InstanceId(value="instance-1"),
        group_id="test-group",
        failover_policy=FailoverPolicy.aggressive(),
        logger=mock_logger,
    )


@pytest.mark.asyncio
async def test_election_coordinator_initialization():
    """Test ElectionCoordinator initialization."""
    mock_store = Mock(spec=KVStorePort)
    mock_registry = Mock(spec=ServiceRegistryPort)

    coordinator = ElectionCoordinator(
        kv_store=mock_store,
        service_registry=mock_registry,
        service_name=ServiceName(value="service"),
        instance_id=InstanceId(value="instance"),
        group_id="group",
    )

    assert coordinator._service_name.value == "service"
    assert coordinator._instance_id.value == "instance"
    assert coordinator._group_id == "group"
    assert coordinator._failover_policy.is_balanced()
    assert coordinator._election_state.is_idle()


@pytest.mark.asyncio
async def test_set_callbacks(election_coordinator):
    """Test setting election callbacks."""
    on_elected = Mock()
    on_lost = Mock()

    election_coordinator.set_on_elected_callback(on_elected)
    election_coordinator.set_on_lost_callback(on_lost)

    assert election_coordinator._on_elected_callback == on_elected
    assert election_coordinator._on_lost_callback == on_lost


@pytest.mark.asyncio
async def test_trigger_election_matching(election_coordinator):
    """Test triggering election for matching service/group."""
    with patch.object(election_coordinator, "start_election", new_callable=AsyncMock) as mock_start:
        await election_coordinator.trigger_election("test-service", "test-group")
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_election_non_matching(election_coordinator, mock_logger):
    """Test triggering election for non-matching service/group."""
    with patch.object(election_coordinator, "start_election", new_callable=AsyncMock) as mock_start:
        await election_coordinator.trigger_election("other-service", "other-group")
        mock_start.assert_not_called()
        mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_start_election_success(election_coordinator, mock_kv_store, mock_service_registry):
    """Test successful election."""
    # No existing leader
    mock_kv_store.get.return_value = None
    # Put succeeds (we win)
    mock_kv_store.put.return_value = 1

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    result = await election_coordinator.start_election()

    assert result is True
    assert election_coordinator._election_state.is_elected()

    # Verify leader key was created with create_only option
    mock_kv_store.put.assert_called()
    call_args = mock_kv_store.put.call_args
    assert call_args[0][0] == "sticky-active.test-service.test-group.leader"
    # options is passed as the third positional argument
    assert call_args[0][2].create_only is True


@pytest.mark.asyncio
async def test_start_election_already_leader(election_coordinator, mock_kv_store):
    """Test election when already the leader."""
    # We're already the leader
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-1"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    result = await election_coordinator.start_election()

    assert result is True
    assert election_coordinator._election_state.is_elected()


@pytest.mark.asyncio
async def test_start_election_lost_race(election_coordinator, mock_kv_store):
    """Test election when losing the race to another instance."""
    # No existing leader initially
    mock_kv_store.get.return_value = None
    # Put fails - someone else won
    mock_kv_store.put.side_effect = Exception("Key already exists")

    result = await election_coordinator.start_election()

    assert result is False
    assert election_coordinator._election_state.is_failed()


@pytest.mark.asyncio
async def test_start_election_existing_leader(election_coordinator, mock_kv_store):
    """Test election when another instance is already leader."""
    # Another instance is leader
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-2"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    result = await election_coordinator.start_election()

    assert result is False
    # Should fail after retries
    assert election_coordinator._election_state.is_failed()


@pytest.mark.asyncio
async def test_start_election_timeout(election_coordinator):
    """Test election timeout."""

    # Make the election take too long
    async def slow_election():
        await asyncio.sleep(10)
        return True

    with patch.object(election_coordinator, "_run_election", side_effect=slow_election):
        # Use a very short timeout
        from aegis_sdk.domain.value_objects import Duration

        election_coordinator._failover_policy = FailoverPolicy(
            mode="balanced",
            election_delay=Duration(seconds=0.05),  # Set election delay shorter
            max_election_time=Duration(seconds=0.1),
        )

        result = await election_coordinator.start_election()

        assert result is False
        assert election_coordinator._election_state.is_failed()
        assert "timed out" in election_coordinator._election_state.last_error.lower()


@pytest.mark.asyncio
async def test_release_leadership(election_coordinator, mock_kv_store, mock_service_registry):
    """Test releasing leadership."""
    # We're the current leader
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-1"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    await election_coordinator.release_leadership()

    # Verify leader key was deleted
    mock_kv_store.delete.assert_called_once_with("sticky-active.test-service.test-group.leader")

    # Verify instance status was updated
    mock_service_registry.update_instance.assert_called_once()
    assert mock_instance.sticky_active_status == StickyActiveStatus.STANDBY.value


@pytest.mark.asyncio
async def test_release_leadership_not_leader(election_coordinator, mock_kv_store):
    """Test releasing leadership when not the leader."""
    # Another instance is leader
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-2"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    await election_coordinator.release_leadership()

    # Should not delete the key
    mock_kv_store.delete.assert_not_called()


@pytest.mark.asyncio
async def test_release_leadership_with_callback(
    election_coordinator, mock_kv_store, mock_service_registry
):
    """Test releasing leadership with callback."""
    # We're the current leader
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-1"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    # Set callback
    on_lost = AsyncMock()
    election_coordinator.set_on_lost_callback(on_lost)

    await election_coordinator.release_leadership()

    # Verify callback was invoked
    on_lost.assert_called_once()


@pytest.mark.asyncio
async def test_check_leadership_is_leader(election_coordinator, mock_kv_store):
    """Test checking leadership when we are the leader."""
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-1"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    is_leader = await election_coordinator.check_leadership()
    assert is_leader is True


@pytest.mark.asyncio
async def test_check_leadership_not_leader(election_coordinator, mock_kv_store):
    """Test checking leadership when we are not the leader."""
    mock_kv_store.get.return_value = KVEntry(
        key="sticky-active.test-service.test-group.leader",
        value={"instance_id": "instance-2"},
        revision=1,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    is_leader = await election_coordinator.check_leadership()
    assert is_leader is False


@pytest.mark.asyncio
async def test_check_leadership_no_leader(election_coordinator, mock_kv_store):
    """Test checking leadership when no leader exists."""
    mock_kv_store.get.return_value = None

    is_leader = await election_coordinator.check_leadership()
    assert is_leader is False


@pytest.mark.asyncio
async def test_check_leadership_error(election_coordinator, mock_kv_store, mock_logger):
    """Test checking leadership with error."""
    mock_kv_store.get.side_effect = Exception("KV store error")

    is_leader = await election_coordinator.check_leadership()

    assert is_leader is False
    mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_get_leader_key(election_coordinator):
    """Test leader key generation."""
    key = election_coordinator._get_leader_key()
    assert key == "sticky-active.test-service.test-group.leader"


@pytest.mark.asyncio
async def test_get_election_state(election_coordinator):
    """Test getting election state."""
    state = election_coordinator.get_election_state()
    assert isinstance(state, ElectionState)
    assert state.is_idle()


@pytest.mark.asyncio
async def test_is_elected(election_coordinator):
    """Test is_elected method."""
    assert election_coordinator.is_elected() is False

    # Simulate successful election
    election_coordinator._election_state = ElectionState(
        state=ElectionState.ELECTED,
        instance_id="instance-1",
    )

    assert election_coordinator.is_elected() is True


@pytest.mark.asyncio
async def test_update_instance_status(election_coordinator, mock_service_registry):
    """Test updating instance status in registry."""
    # Mock service instance
    mock_instance = MagicMock()
    mock_instance.sticky_active_status = None
    mock_service_registry.get_instance.return_value = mock_instance

    await election_coordinator._update_instance_status(StickyActiveStatus.ACTIVE.value)

    # Verify instance was updated
    assert mock_instance.sticky_active_status == StickyActiveStatus.ACTIVE.value
    mock_service_registry.update_instance.assert_called_once_with(mock_instance)


@pytest.mark.asyncio
async def test_update_instance_status_not_found(
    election_coordinator, mock_service_registry, mock_logger
):
    """Test updating instance status when instance not found."""
    mock_service_registry.get_instance.return_value = None

    await election_coordinator._update_instance_status(StickyActiveStatus.ACTIVE.value)

    # Should log warning
    mock_logger.warning.assert_called()
    mock_service_registry.update_instance.assert_not_called()


@pytest.mark.asyncio
async def test_election_with_callback(election_coordinator, mock_kv_store, mock_service_registry):
    """Test election with on_elected callback."""
    # No existing leader
    mock_kv_store.get.return_value = None
    # Put succeeds (we win)
    mock_kv_store.put.return_value = 1

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    # Set callback
    on_elected = AsyncMock()
    election_coordinator.set_on_elected_callback(on_elected)

    result = await election_coordinator.start_election()

    assert result is True
    # Verify callback was invoked
    on_elected.assert_called_once()


@pytest.mark.asyncio
async def test_election_with_sync_callback(
    election_coordinator, mock_kv_store, mock_service_registry
):
    """Test election with synchronous callback."""
    # No existing leader
    mock_kv_store.get.return_value = None
    # Put succeeds (we win)
    mock_kv_store.put.return_value = 1

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    # Set synchronous callback
    on_elected = Mock()
    election_coordinator.set_on_elected_callback(on_elected)

    result = await election_coordinator.start_election()

    assert result is True
    # Verify callback was invoked
    on_elected.assert_called_once()


@pytest.mark.asyncio
async def test_election_callback_error_handling(
    election_coordinator, mock_kv_store, mock_service_registry, mock_logger
):
    """Test election with callback that raises an error."""
    # No existing leader
    mock_kv_store.get.return_value = None
    # Put succeeds (we win)
    mock_kv_store.put.return_value = 1

    # Mock service instance
    mock_instance = MagicMock()
    mock_service_registry.get_instance.return_value = mock_instance

    # Set callback that raises error
    on_elected = Mock(side_effect=Exception("Callback error"))
    election_coordinator.set_on_elected_callback(on_elected)

    result = await election_coordinator.start_election()

    assert result is True
    # Should still succeed despite callback error
    mock_logger.error.assert_called()
    assert "on_elected callback" in str(mock_logger.error.call_args)
