"""Unit tests for NatsKvElectionRepository."""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis_sdk.domain.aggregates import StickyActiveElection, StickyActiveElectionState
from aegis_sdk.domain.exceptions import KVKeyAlreadyExistsError
from aegis_sdk.domain.models import KVEntry, KVOptions, KVWatchEvent
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository


class TestNatsKvElectionRepositoryInit:
    """Test NatsKvElectionRepository initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        mock_kv_store = MagicMock()
        repo = NatsKvElectionRepository(kv_store=mock_kv_store)

        assert repo._kv_store == mock_kv_store
        assert repo._logger is not None
        assert repo._metrics is not None
        assert repo._election_service is not None
        assert repo._watch_tasks == {}

    def test_init_with_custom_components(self):
        """Test initialization with custom components."""
        mock_kv_store = MagicMock()
        mock_logger = MagicMock()
        mock_metrics = MagicMock()

        repo = NatsKvElectionRepository(
            kv_store=mock_kv_store, logger=mock_logger, metrics=mock_metrics
        )

        assert repo._kv_store == mock_kv_store
        assert repo._logger == mock_logger
        assert repo._metrics == mock_metrics


class TestNatsKvElectionRepositoryLeadershipAttempt:
    """Test leadership attempt functionality."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_attempt_leadership_success(self, repo):
        """Test successful leadership acquisition."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock election service
        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                result = await repo.attempt_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                    metadata={"version": "1.0"},
                )

        assert result is True

        # Verify KV store called with correct parameters
        repo._kv_store.put.assert_called_once()
        call_args = repo._kv_store.put.call_args
        assert call_args[0][0] == "leader.test-service.group1"  # key
        assert call_args[0][1] == {"leader_id": "instance-123"}  # value
        assert isinstance(call_args[0][2], KVOptions)  # options
        assert call_args[0][2].create_only is True
        assert call_args[0][2].ttl == 30

        # Verify metrics
        repo._metrics.increment.assert_called_with("election.leadership.acquired")

    @pytest.mark.asyncio
    async def test_attempt_leadership_already_exists(self, repo):
        """Test leadership attempt when leader already exists."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock KV store to raise key already exists error
        repo._kv_store.put.side_effect = KVKeyAlreadyExistsError("leader.test-service.group1")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                result = await repo.attempt_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                )

        assert result is False
        repo._metrics.increment.assert_called_with("election.leadership.exists")

    @pytest.mark.asyncio
    async def test_attempt_leadership_error(self, repo):
        """Test leadership attempt with general error."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock KV store to raise general error
        repo._kv_store.put.side_effect = Exception("Connection error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                with pytest.raises(Exception, match="Connection error"):
                    await repo.attempt_leadership(
                        service_name=service_name,
                        instance_id=instance_id,
                        group_id="group1",
                        ttl_seconds=30,
                    )

        repo._metrics.increment.assert_called_with("election.leadership.error")


class TestNatsKvElectionRepositoryUpdateLeadership:
    """Test leadership update functionality."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_update_leadership_success(self, repo):
        """Test successful leadership update."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock existing leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123", "last_heartbeat": time.time(), "metadata": {}},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry
        repo._kv_store.put.return_value = 6

        # Mock election service methods
        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", time.time(), {}),
            ):
                with patch.object(
                    repo._election_service,
                    "create_leader_value",
                    return_value={"leader_id": "instance-123", "updated": True},
                ):
                    result = await repo.update_leadership(
                        service_name=service_name,
                        instance_id=instance_id,
                        group_id="group1",
                        ttl_seconds=30,
                        metadata={"version": "1.1"},
                    )

        assert result is True

        # Verify get and put called
        repo._kv_store.get.assert_called_once_with("leader.test-service.group1")
        repo._kv_store.put.assert_called_once()

        # Verify put parameters
        put_args = repo._kv_store.put.call_args
        assert put_args[0][0] == "leader.test-service.group1"
        assert put_args[0][1] == {"leader_id": "instance-123", "updated": True}
        assert isinstance(put_args[0][2], KVOptions)
        assert put_args[0][2].revision == 5
        assert put_args[0][2].ttl == 30

        repo._metrics.increment.assert_called_with("election.leadership.updated")

    @pytest.mark.asyncio
    async def test_update_leadership_no_leader(self, repo):
        """Test leadership update when no current leader."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock no existing leader
        repo._kv_store.get.return_value = None

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            result = await repo.update_leadership(
                service_name=service_name,
                instance_id=instance_id,
                group_id="group1",
                ttl_seconds=30,
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_leadership_wrong_leader(self, repo):
        """Test leadership update when instance is not the current leader."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock existing leader entry with different leader
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "different-instance"},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("different-instance", time.time(), {}),
            ):
                result = await repo.update_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_leadership_error(self, repo):
        """Test leadership update with error."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock get to raise error
        repo._kv_store.get.side_effect = Exception("Connection error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            result = await repo.update_leadership(
                service_name=service_name,
                instance_id=instance_id,
                group_id="group1",
                ttl_seconds=30,
            )

        assert result is False
        repo._metrics.increment.assert_called_with("election.leadership.update_error")


class TestNatsKvElectionRepositoryGetCurrentLeader:
    """Test get current leader functionality."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_get_current_leader_success(self, repo):
        """Test successful get current leader."""
        service_name = ServiceName(value="test-service")

        # Mock leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123", "metadata": {"version": "1.0"}},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry

        current_time = time.time()
        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", current_time, {"version": "1.0"}),
            ):
                with patch.object(repo._election_service, "is_leader_expired", return_value=False):
                    leader_id, metadata = await repo.get_current_leader(
                        service_name=service_name, group_id="group1"
                    )

        assert leader_id == InstanceId(value="instance-123")
        assert metadata == {"version": "1.0"}

    @pytest.mark.asyncio
    async def test_get_current_leader_not_found(self, repo):
        """Test get current leader when no leader exists."""
        service_name = ServiceName(value="test-service")

        # Mock no leader entry
        repo._kv_store.get.return_value = None

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            leader_id, metadata = await repo.get_current_leader(
                service_name=service_name, group_id="group1"
            )

        assert leader_id is None
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_get_current_leader_expired(self, repo):
        """Test get current leader when leader is expired."""
        service_name = ServiceName(value="test-service")

        # Mock leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123"},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry

        old_time = time.time() - 3600  # 1 hour ago
        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", old_time, {}),
            ):
                with patch.object(repo._election_service, "is_leader_expired", return_value=True):
                    leader_id, metadata = await repo.get_current_leader(
                        service_name=service_name, group_id="group1"
                    )

        assert leader_id is None
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_get_current_leader_error(self, repo):
        """Test get current leader with error."""
        service_name = ServiceName(value="test-service")

        # Mock error
        repo._kv_store.get.side_effect = Exception("Connection error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            leader_id, metadata = await repo.get_current_leader(
                service_name=service_name, group_id="group1"
            )

        assert leader_id is None
        assert metadata == {}


class TestNatsKvElectionRepositoryReleaseLeadership:
    """Test release leadership functionality."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_release_leadership_success(self, repo):
        """Test successful leadership release."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123"},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry
        repo._kv_store.delete.return_value = True

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", time.time(), {}),
            ):
                result = await repo.release_leadership(
                    service_name=service_name, instance_id=instance_id, group_id="group1"
                )

        assert result is True

        # Verify delete called with revision
        repo._kv_store.delete.assert_called_once_with("leader.test-service.group1", 5)
        repo._metrics.increment.assert_called_with("election.leadership.released")

    @pytest.mark.asyncio
    async def test_release_leadership_no_leader(self, repo):
        """Test release leadership when no current leader."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock no leader entry
        repo._kv_store.get.return_value = None

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            result = await repo.release_leadership(
                service_name=service_name, instance_id=instance_id, group_id="group1"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_release_leadership_wrong_leader(self, repo):
        """Test release leadership when instance is not the current leader."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock leader entry with different leader
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "different-instance"},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("different-instance", time.time(), {}),
            ):
                result = await repo.release_leadership(
                    service_name=service_name, instance_id=instance_id, group_id="group1"
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_release_leadership_delete_failed(self, repo):
        """Test release leadership when delete fails."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123"},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry
        repo._kv_store.delete.return_value = False

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", time.time(), {}),
            ):
                result = await repo.release_leadership(
                    service_name=service_name, instance_id=instance_id, group_id="group1"
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_release_leadership_error(self, repo):
        """Test release leadership with error."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock error
        repo._kv_store.get.side_effect = Exception("Connection error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            result = await repo.release_leadership(
                service_name=service_name, instance_id=instance_id, group_id="group1"
            )

        assert result is False
        repo._metrics.increment.assert_called_with("election.leadership.release_error")


class TestNatsKvElectionRepositoryWatchLeadership:
    """Test leadership watching functionality."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_watch_leadership_elected_event(self, repo):
        """Test watching leadership with elected event."""
        service_name = ServiceName(value="test-service")

        # Mock watch event - new leader elected
        mock_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123", "metadata": {"version": "1.0"}},
            revision=1,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        watch_event = KVWatchEvent(operation="PUT", entry=mock_entry)

        # Create async iterator mock
        class AsyncIterMock:
            def __init__(self, events):
                self.events = iter(events)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.events)
                except StopIteration:
                    raise StopAsyncIteration

        # Mock the watch method to return the async iterator directly
        mock_async_iter = AsyncIterMock([watch_event])

        # Replace the AsyncMock.watch with a simple method that returns the iterator
        def watch_method(key):
            return mock_async_iter

        repo._kv_store.watch = watch_method

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "parse_leader_value",
                return_value=("instance-123", time.time(), {"version": "1.0"}),
            ):
                watch_iter = repo.watch_leadership(service_name, "group1")
                event = await watch_iter.__anext__()

        assert event["type"] == "elected"
        assert event["leader_id"] == "instance-123"
        assert event["metadata"] == {"version": "1.0"}

    @pytest.mark.asyncio
    async def test_watch_leadership_lost_event(self, repo):
        """Test watching leadership with lost event."""
        service_name = ServiceName(value="test-service")

        # Mock watch event - leader lost
        watch_event = KVWatchEvent(operation="DELETE", entry=None)

        # Create async iterator mock
        class AsyncIterMock:
            def __init__(self, events):
                self.events = iter(events)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.events)
                except StopIteration:
                    raise StopAsyncIteration

        # Mock the watch method to return the async iterator directly
        mock_async_iter = AsyncIterMock([watch_event])

        # Replace the AsyncMock.watch with a simple method that returns the iterator
        def watch_method(key):
            return mock_async_iter

        repo._kv_store.watch = watch_method

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            watch_iter = repo.watch_leadership(service_name, "group1")
            event = await watch_iter.__anext__()

        assert event["type"] == "expired"
        assert event["leader_id"] is None
        assert event["metadata"] == {}

    @pytest.mark.asyncio
    async def test_watch_leadership_error(self, repo):
        """Test watching leadership with error."""
        service_name = ServiceName(value="test-service")

        # Create async iterator mock that raises error
        class AsyncIterMock:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise Exception("Watch error")

        # Mock the watch method to return the error async iterator directly
        mock_async_iter = AsyncIterMock()

        # Replace the AsyncMock.watch with a simple method that returns the iterator
        def watch_method(key):
            return mock_async_iter

        repo._kv_store.watch = watch_method

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with pytest.raises(Exception, match="Watch error"):
                watch_iter = repo.watch_leadership(service_name, "group1")
                await watch_iter.__anext__()


class TestNatsKvElectionRepositoryElectionState:
    """Test election state management."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.fixture
    def sample_election(self):
        """Create sample election aggregate."""
        return StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
            group_id="group1",
            status=StickyActiveElectionState.STANDBY,
            leader_instance_id=InstanceId(value="leader-instance"),
            last_leader_heartbeat=datetime.now(),
            leader_ttl_seconds=30,
            heartbeat_interval_seconds=10,
            election_timeout_seconds=60,
            started_at=datetime.now(),
            last_election_attempt=datetime.now(),
            became_leader_at=None,
        )

    @pytest.mark.asyncio
    async def test_save_election_state(self, repo, sample_election):
        """Test saving election state."""
        await repo.save_election_state(sample_election)

        # Verify KV store put was called
        repo._kv_store.put.assert_called_once()

        # Verify key format
        call_args = repo._kv_store.put.call_args
        expected_key = "election-state.test-service.instance-123.group1"
        assert call_args[0][0] == expected_key

        # Verify data structure
        state_data = call_args[0][1]
        assert state_data["service_name"] == "test-service"
        assert state_data["instance_id"] == "instance-123"
        assert state_data["group_id"] == "group1"
        assert state_data["status"] == "STANDBY"
        assert state_data["leader_instance_id"] == "leader-instance"

    @pytest.mark.asyncio
    async def test_get_election_state_success(self, repo):
        """Test successful retrieval of election state."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock stored state
        state_data = {
            "service_name": "test-service",
            "instance_id": "instance-123",
            "group_id": "group1",
            "status": "STANDBY",
            "leader_instance_id": "leader-instance",
            "last_leader_heartbeat": "2025-01-01T00:00:00+00:00",
            "leader_ttl_seconds": 30,
            "heartbeat_interval_seconds": 10,
            "election_timeout_seconds": 60,
            "started_at": "2025-01-01T00:00:00+00:00",
            "last_election_attempt": "2025-01-01T00:00:00+00:00",
            "became_leader_at": None,
        }

        kv_entry = KVEntry(
            key="election-state.test-service.instance-123.group1",
            value=state_data,
            revision=1,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = kv_entry

        result = await repo.get_election_state(service_name, instance_id, "group1")

        assert result is not None
        assert result.service_name == service_name
        assert result.instance_id == instance_id
        assert result.group_id == "group1"
        assert result.status == StickyActiveElectionState.STANDBY
        assert result.leader_instance_id == InstanceId(value="leader-instance")

    @pytest.mark.asyncio
    async def test_get_election_state_not_found(self, repo):
        """Test retrieval when election state doesn't exist."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock no state found
        repo._kv_store.get.return_value = None

        result = await repo.get_election_state(service_name, instance_id, "group1")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_election_state_error(self, repo):
        """Test retrieval with error."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock error
        repo._kv_store.get.side_effect = Exception("Connection error")

        result = await repo.get_election_state(service_name, instance_id, "group1")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_election_state_success(self, repo):
        """Test successful deletion of election state."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        await repo.delete_election_state(service_name, instance_id, "group1")

        # Verify delete called with correct key
        expected_key = "election-state.test-service.instance-123.group1"
        repo._kv_store.delete.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_delete_election_state_error(self, repo):
        """Test deletion with error."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock error (should not raise, just log)
        repo._kv_store.delete.side_effect = Exception("Connection error")

        # Should not raise exception
        await repo.delete_election_state(service_name, instance_id, "group1")


class TestNatsKvElectionRepositoryIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    def test_election_service_integration(self, repo):
        """Test that election service methods are called correctly."""
        # Verify election service is initialized
        assert repo._election_service is not None

        # Test that election service methods exist
        assert hasattr(repo._election_service, "create_leader_key")
        assert hasattr(repo._election_service, "create_leader_value")
        assert hasattr(repo._election_service, "parse_leader_value")
        assert hasattr(repo._election_service, "is_leader_expired")

    @pytest.mark.asyncio
    async def test_leader_key_creation(self, repo):
        """Test leader key creation through election service."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        with patch.object(repo._election_service, "create_leader_key") as mock_create_key:
            mock_create_key.return_value = "leader.test-service.group1"

            # Any method that uses create_leader_key
            await repo.attempt_leadership(
                service_name=service_name,
                instance_id=instance_id,
                group_id="group1",
                ttl_seconds=30,
            )

            mock_create_key.assert_called_once_with("test-service", "group1")

    @pytest.mark.asyncio
    async def test_leader_value_creation(self, repo):
        """Test leader value creation through election service."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(repo._election_service, "create_leader_value") as mock_create_value:
                mock_create_value.return_value = {
                    "leader_id": "instance-123",
                    "metadata": {"test": "data"},
                }

                await repo.attempt_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                    metadata={"test": "data"},
                )

                mock_create_value.assert_called_once_with("instance-123", {"test": "data"})

    @pytest.mark.asyncio
    async def test_leader_value_parsing(self, repo):
        """Test leader value parsing through election service."""
        service_name = ServiceName(value="test-service")

        # Mock leader entry
        leader_entry = KVEntry(
            key="leader.test-service.group1",
            value={"leader_id": "instance-123", "metadata": {"version": "1.0"}},
            revision=5,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        repo._kv_store.get.return_value = leader_entry

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(repo._election_service, "parse_leader_value") as mock_parse:
                mock_parse.return_value = ("instance-123", time.time(), {"version": "1.0"})

                with patch.object(repo._election_service, "is_leader_expired", return_value=False):
                    leader_id, metadata = await repo.get_current_leader(
                        service_name=service_name, group_id="group1"
                    )

                # Verify parse_leader_value was called with JSON string
                mock_parse.assert_called_once()
                call_args = mock_parse.call_args[0][0]
                # Should be JSON string representation of the leader value
                assert '"leader_id": "instance-123"' in call_args


class TestNatsKvElectionRepositoryErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_kv_store_connection_error(self, repo):
        """Test handling of KV store connection errors."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock KV store connection error
        repo._kv_store.put.side_effect = Exception("Connection lost")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                with pytest.raises(Exception, match="Connection lost"):
                    await repo.attempt_leadership(
                        service_name=service_name,
                        instance_id=instance_id,
                        group_id="group1",
                        ttl_seconds=30,
                    )

    def test_invalid_service_name(self, repo):
        """Test handling of invalid service name."""
        # Should be handled by ServiceName validation
        with pytest.raises(ValueError):
            ServiceName(value="")

    def test_invalid_instance_id(self, repo):
        """Test handling of invalid instance ID."""
        # Should be handled by InstanceId validation
        with pytest.raises(ValueError):
            InstanceId(value="")

    @pytest.mark.asyncio
    async def test_serialization_error_in_state_management(self, repo):
        """Test handling of serialization errors in state management."""
        # Create election with datetime that might cause serialization issues
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
            group_id="group1",
            status=StickyActiveElectionState.STANDBY,
            leader_ttl_seconds=30,
            heartbeat_interval_seconds=10,
            election_timeout_seconds=60,
        )

        # Mock KV store serialization error
        repo._kv_store.put.side_effect = Exception("Serialization failed")

        with pytest.raises(Exception, match="Serialization failed"):
            await repo.save_election_state(election)


class TestNatsKvElectionRepositoryMetrics:
    """Test metrics integration."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_metrics = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, metrics=mock_metrics)

    @pytest.mark.asyncio
    async def test_leadership_metrics(self, repo):
        """Test that all leadership operations track metrics."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Test successful leadership acquisition
        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                await repo.attempt_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                )

        repo._metrics.increment.assert_called_with("election.leadership.acquired")

    @pytest.mark.asyncio
    async def test_error_metrics(self, repo):
        """Test that errors are tracked in metrics."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock error
        repo._kv_store.put.side_effect = Exception("Test error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                with pytest.raises(Exception):
                    await repo.attempt_leadership(
                        service_name=service_name,
                        instance_id=instance_id,
                        group_id="group1",
                        ttl_seconds=30,
                    )

        repo._metrics.increment.assert_called_with("election.leadership.error")


class TestNatsKvElectionRepositoryLogging:
    """Test logging integration."""

    @pytest.fixture
    def repo(self):
        """Create repository with mocked dependencies."""
        mock_kv_store = AsyncMock()
        mock_logger = MagicMock()
        return NatsKvElectionRepository(kv_store=mock_kv_store, logger=mock_logger)

    @pytest.mark.asyncio
    async def test_leadership_logging(self, repo):
        """Test that leadership operations are logged."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                await repo.attempt_leadership(
                    service_name=service_name,
                    instance_id=instance_id,
                    group_id="group1",
                    ttl_seconds=30,
                )

        # Verify info logging for successful acquisition
        repo._logger.info.assert_called()
        log_call = repo._logger.info.call_args[0][0]
        assert "Leadership acquired" in log_call

    @pytest.mark.asyncio
    async def test_error_logging(self, repo):
        """Test that errors are logged."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        # Mock error
        repo._kv_store.put.side_effect = Exception("Test error")

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            with patch.object(
                repo._election_service,
                "create_leader_value",
                return_value={"leader_id": "instance-123"},
            ):
                with pytest.raises(Exception):
                    await repo.attempt_leadership(
                        service_name=service_name,
                        instance_id=instance_id,
                        group_id="group1",
                        ttl_seconds=30,
                    )

        # Verify exception logging
        repo._logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_watch_logging(self, repo):
        """Test that watch operations are logged."""
        service_name = ServiceName(value="test-service")

        # Create async iterator mock with no events
        class AsyncIterMock:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration  # No events

        # Mock the watch method to return the async iterator directly
        mock_async_iter = AsyncIterMock()

        # Replace the AsyncMock.watch with a simple method that returns the iterator
        def watch_method(key):
            return mock_async_iter

        repo._kv_store.watch = watch_method

        with patch.object(
            repo._election_service, "create_leader_key", return_value="leader.test-service.group1"
        ):
            # Create and try to iterate once to trigger the logging
            watch_iter = repo.watch_leadership(service_name, "group1")
            try:
                await watch_iter.__anext__()
            except StopAsyncIteration:
                pass  # Expected when mock_watch returns immediately

        # Verify info logging for watch start
        repo._logger.info.assert_called()
        log_call = repo._logger.info.call_args[0][0]
        assert "Starting leadership watch" in log_call
