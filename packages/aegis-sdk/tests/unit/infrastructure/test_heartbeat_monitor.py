"""Unit tests for HeartbeatMonitor class."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk.domain.value_objects import (
    Duration,
    FailoverPolicy,
    HeartbeatStatus,
    InstanceId,
    ServiceName,
)
from aegis_sdk.infrastructure.heartbeat_monitor import HeartbeatMonitor
from aegis_sdk.ports.kv_store import KVStorePort as KVStore
from aegis_sdk.ports.logger import LoggerPort


class MockElectionTrigger:
    """Mock implementation of ElectionTrigger protocol."""

    def __init__(self):
        self.trigger_election = AsyncMock()


@pytest.fixture
def mock_kv_store():
    """Create a mock KV store."""
    store = Mock(spec=KVStore)
    store.get = AsyncMock()
    store.put = AsyncMock()
    store.delete = AsyncMock()
    return store


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
def mock_election_trigger():
    """Create a mock election trigger."""
    return MockElectionTrigger()


@pytest.fixture
def heartbeat_monitor(mock_kv_store, mock_logger):
    """Create a HeartbeatMonitor instance with mocked dependencies."""
    return HeartbeatMonitor(
        kv_store=mock_kv_store,
        service_name=ServiceName(value="test-service"),
        instance_id=InstanceId(value="instance-1"),
        group_id="test-group",
        failover_policy=FailoverPolicy.aggressive(),
        logger=mock_logger,
    )


@pytest.mark.asyncio
async def test_heartbeat_monitor_initialization():
    """Test HeartbeatMonitor initialization with various configurations."""
    mock_store = Mock(spec=KVStore)

    # Test with minimal configuration
    monitor = HeartbeatMonitor(
        kv_store=mock_store,
        service_name=ServiceName(value="service"),
        instance_id=InstanceId(value="instance"),
        group_id="group",
    )

    assert monitor._service_name.value == "service"
    assert monitor._instance_id.value == "instance"
    assert monitor._group_id == "group"
    assert monitor._failover_policy.is_balanced()

    # Test with custom failover policy
    aggressive_policy = FailoverPolicy.aggressive()
    monitor = HeartbeatMonitor(
        kv_store=mock_store,
        service_name=ServiceName(value="service"),
        instance_id=InstanceId(value="instance"),
        group_id="group",
        failover_policy=aggressive_policy,
    )

    assert monitor._failover_policy.is_aggressive()


@pytest.mark.asyncio
async def test_set_heartbeat_interval(heartbeat_monitor):
    """Test setting custom heartbeat interval."""
    # Valid interval
    interval = Duration(seconds=1.0)
    heartbeat_monitor.set_heartbeat_interval(interval)
    assert heartbeat_monitor._heartbeat_interval.seconds == 1.0

    # Too short interval
    with pytest.raises(ValueError, match="at least 100ms"):
        heartbeat_monitor.set_heartbeat_interval(Duration(seconds=0.05))

    # Too long interval
    with pytest.raises(ValueError, match="not exceed 10 seconds"):
        heartbeat_monitor.set_heartbeat_interval(Duration(seconds=15))


@pytest.mark.asyncio
async def test_set_election_trigger(heartbeat_monitor, mock_election_trigger):
    """Test setting election trigger."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)
    assert heartbeat_monitor._election_trigger == mock_election_trigger


@pytest.mark.asyncio
async def test_start_monitoring(heartbeat_monitor, mock_logger):
    """Test starting heartbeat monitoring."""
    await heartbeat_monitor.start_monitoring()

    # Verify monitoring started
    assert heartbeat_monitor._monitor_task is not None
    assert not heartbeat_monitor._monitor_task.done()

    # Verify logging
    mock_logger.info.assert_called()
    call_args = mock_logger.info.call_args
    assert "Started heartbeat monitoring" in str(call_args)

    # Cleanup
    await heartbeat_monitor.stop_monitoring()


@pytest.mark.asyncio
async def test_stop_monitoring(heartbeat_monitor, mock_logger):
    """Test stopping heartbeat monitoring."""
    # Start monitoring first
    await heartbeat_monitor.start_monitoring()
    assert heartbeat_monitor._monitor_task is not None

    # Stop monitoring
    await heartbeat_monitor.stop_monitoring()

    # Verify task is completed
    assert heartbeat_monitor._monitor_task.done()

    # Verify logging
    mock_logger.info.assert_called()
    call_args = mock_logger.info.call_args
    assert "Stopped heartbeat monitoring" in str(call_args)


@pytest.mark.asyncio
async def test_check_heartbeat_healthy(heartbeat_monitor, mock_kv_store):
    """Test checking a healthy heartbeat."""
    now = datetime.now(UTC)
    mock_kv_store.get.return_value = {
        "timestamp": now.isoformat(),
        "ttl": 5,
        "instance_id": "leader-1",
    }

    status = await heartbeat_monitor._check_heartbeat("leader-1")

    assert status is not None
    assert status.instance_id == "leader-1"
    assert status.is_healthy()
    assert not status.is_expired
    assert status.time_remaining() > 0


@pytest.mark.asyncio
async def test_check_heartbeat_expired(heartbeat_monitor, mock_kv_store):
    """Test checking an expired heartbeat."""
    old_time = datetime.now(UTC) - timedelta(seconds=10)
    mock_kv_store.get.return_value = {
        "timestamp": old_time.isoformat(),
        "ttl": 5,
        "instance_id": "leader-1",
    }

    status = await heartbeat_monitor._check_heartbeat("leader-1")

    assert status is not None
    assert status.instance_id == "leader-1"
    assert not status.is_healthy()
    assert status.is_expired
    assert status.time_remaining() < 0


@pytest.mark.asyncio
async def test_check_heartbeat_missing(heartbeat_monitor, mock_kv_store):
    """Test checking heartbeat when key is missing."""
    mock_kv_store.get.return_value = None

    status = await heartbeat_monitor._check_heartbeat("leader-1")

    assert status is not None
    assert status.instance_id == "leader-1"
    assert status.is_expired
    assert not status.is_healthy()


@pytest.mark.asyncio
async def test_handle_heartbeat_expiration(heartbeat_monitor, mock_election_trigger, mock_logger):
    """Test handling heartbeat expiration."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)

    # Create expired heartbeat status
    expired_status = HeartbeatStatus(
        instance_id="leader-1",
        last_seen=datetime.now(UTC) - timedelta(seconds=10),
        ttl_seconds=5,
        is_expired=True,
        time_since_last=10.0,
    )

    # Mock recheck to confirm expiration
    with patch.object(heartbeat_monitor, "_check_heartbeat", return_value=expired_status):
        await heartbeat_monitor._handle_heartbeat_expiration(expired_status)

    # Verify election was triggered
    mock_election_trigger.trigger_election.assert_called_once_with("test-service", "test-group")

    # Verify logging
    mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_handle_heartbeat_recovery(heartbeat_monitor, mock_election_trigger, mock_logger):
    """Test handling heartbeat recovery during detection threshold."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)

    # Create expired then recovered heartbeat
    expired_status = HeartbeatStatus(
        instance_id="leader-1",
        last_seen=datetime.now(UTC) - timedelta(seconds=10),
        ttl_seconds=5,
        is_expired=True,
        time_since_last=10.0,
    )

    recovered_status = HeartbeatStatus(
        instance_id="leader-1",
        last_seen=datetime.now(UTC),
        ttl_seconds=5,
        is_expired=False,
        time_since_last=0.5,
    )

    # Mock recheck to show recovery
    with patch.object(heartbeat_monitor, "_check_heartbeat", return_value=recovered_status):
        await heartbeat_monitor._handle_heartbeat_expiration(expired_status)

    # Verify election was NOT triggered
    mock_election_trigger.trigger_election.assert_not_called()

    # Verify recovery logging
    mock_logger.info.assert_called()
    call_args = mock_logger.info.call_args
    assert "Heartbeat recovered" in str(call_args)


@pytest.mark.asyncio
async def test_handle_leader_loss(heartbeat_monitor, mock_election_trigger, mock_logger):
    """Test handling leader key loss."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)

    await heartbeat_monitor._handle_leader_loss("previous-leader")

    # Verify election was triggered
    mock_election_trigger.trigger_election.assert_called_once_with("test-service", "test-group")

    # Verify logging
    mock_logger.warning.assert_called()
    call_args = mock_logger.warning.call_args
    assert "Leader key lost" in str(call_args)


@pytest.mark.asyncio
async def test_trigger_election_without_trigger(heartbeat_monitor, mock_logger):
    """Test triggering election without configured trigger."""
    # Don't set election trigger
    await heartbeat_monitor._trigger_election_if_configured()

    # Verify warning logged
    mock_logger.warning.assert_called()
    call_args = mock_logger.warning.call_args
    assert "No election trigger configured" in str(call_args)


@pytest.mark.asyncio
async def test_trigger_election_with_error(heartbeat_monitor, mock_election_trigger, mock_logger):
    """Test handling election trigger errors."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)

    # Make trigger raise an error
    mock_election_trigger.trigger_election.side_effect = Exception("Election failed")

    await heartbeat_monitor._trigger_election_if_configured()

    # Verify error logged
    mock_logger.error.assert_called()
    call_args = mock_logger.error.call_args
    assert "Failed to trigger election" in str(call_args)


@pytest.mark.asyncio
async def test_get_leader_key(heartbeat_monitor):
    """Test leader key generation."""
    key = heartbeat_monitor._get_leader_key()
    assert key == "sticky-active.test-service.test-group.leader"


@pytest.mark.asyncio
async def test_get_status(heartbeat_monitor):
    """Test getting monitor status."""
    status = heartbeat_monitor.get_status()

    assert status["monitoring"] is False
    assert status["service"] == "test-service"
    assert status["instance"] == "instance-1"
    assert status["group"] == "test-group"
    assert status["current_leader"] is None
    assert status["last_heartbeat"] is None
    assert status["check_interval"] == 0.5
    assert status["failover_policy"] == "aggressive"

    # Start monitoring and check status
    await heartbeat_monitor.start_monitoring()
    status = heartbeat_monitor.get_status()
    assert status["monitoring"] is True

    # Cleanup
    await heartbeat_monitor.stop_monitoring()


@pytest.mark.asyncio
async def test_monitor_loop_no_leader(heartbeat_monitor, mock_kv_store, mock_election_trigger):
    """Test monitor loop when no leader exists."""
    heartbeat_monitor.set_election_trigger(mock_election_trigger)
    mock_kv_store.get.return_value = None  # No leader

    # Start monitoring
    await heartbeat_monitor.start_monitoring()

    # Let it run briefly
    await asyncio.sleep(0.6)

    # Stop monitoring
    await heartbeat_monitor.stop_monitoring()

    # Verify KV store was checked
    mock_kv_store.get.assert_called()


@pytest.mark.asyncio
async def test_monitor_loop_with_healthy_leader(heartbeat_monitor, mock_kv_store):
    """Test monitor loop with healthy leader."""
    now = datetime.now(UTC)

    # Mock leader key
    mock_kv_store.get.side_effect = [
        {"instance_id": "leader-1"},  # Leader exists
        {  # Healthy heartbeat
            "timestamp": now.isoformat(),
            "ttl": 5,
            "instance_id": "leader-1",
        },
    ]

    # Start monitoring
    await heartbeat_monitor.start_monitoring()

    # Let it run briefly
    await asyncio.sleep(0.6)

    # Stop monitoring
    await heartbeat_monitor.stop_monitoring()

    # Verify leader was tracked
    assert heartbeat_monitor._current_leader == "leader-1"


@pytest.mark.asyncio
async def test_monitor_loop_error_handling(heartbeat_monitor, mock_kv_store, mock_logger):
    """Test monitor loop error handling."""
    # Make KV store raise an error
    mock_kv_store.get.side_effect = Exception("KV store error")

    # Start monitoring
    await heartbeat_monitor.start_monitoring()

    # Let it run briefly
    await asyncio.sleep(0.6)

    # Stop monitoring
    await heartbeat_monitor.stop_monitoring()

    # Verify error was logged
    mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_monitor_loop_consecutive_failures(heartbeat_monitor, mock_kv_store, mock_logger):
    """Test monitor loop stops after too many consecutive failures."""
    # Make KV store always raise an error
    mock_kv_store.get.side_effect = Exception("Persistent error")

    # Start monitoring
    await heartbeat_monitor.start_monitoring()

    # Wait for failures to accumulate
    # With exponential backoff: first check (immediate fail), 2s sleep, second check (fail), 4s sleep, third check (fail), stops
    # Total time needed: ~6 seconds + processing time
    await asyncio.sleep(7.0)

    # Task should have stopped itself
    assert heartbeat_monitor._monitor_task.done()

    # Verify error logged
    mock_logger.error.assert_called()
    call_args = [str(call) for call in mock_logger.error.call_args_list]
    assert any("Too many consecutive monitoring failures" in arg for arg in call_args)
