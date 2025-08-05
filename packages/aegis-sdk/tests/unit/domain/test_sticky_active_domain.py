"""Unit tests for sticky active domain models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.aggregates import (
    StickyActiveElection,
    StickyActiveElectionState,
)
from aegis_sdk.domain.services import StickyActiveElectionService
from aegis_sdk.domain.value_objects import (
    Duration,
    ElectionTimeout,
    InstanceId,
    LeaderKey,
    ServiceGroupId,
    ServiceName,
    StickyActiveStatus,
)


class TestStickyActiveStatus:
    """Test StickyActiveStatus value object."""

    def test_valid_statuses(self):
        """Test creation with valid statuses."""
        active = StickyActiveStatus(value="ACTIVE")
        assert active.value == "ACTIVE"
        assert active.is_active()
        assert not active.is_standby()
        assert not active.is_electing()

        standby = StickyActiveStatus(value="STANDBY")
        assert standby.value == "STANDBY"
        assert not standby.is_active()
        assert standby.is_standby()
        assert not standby.is_electing()

        electing = StickyActiveStatus(value="ELECTING")
        assert electing.value == "ELECTING"
        assert not electing.is_active()
        assert not electing.is_standby()
        assert electing.is_electing()

    def test_invalid_status(self):
        """Test creation with invalid status."""
        with pytest.raises(ValidationError):
            StickyActiveStatus(value="INVALID")

    def test_equality(self):
        """Test equality comparison."""
        status1 = StickyActiveStatus(value="ACTIVE")
        status2 = StickyActiveStatus(value="ACTIVE")
        status3 = StickyActiveStatus(value="STANDBY")

        assert status1 == status2
        assert status1 == "ACTIVE"
        assert status1 != status3
        assert status1 != "STANDBY"
        assert status1 != 123

    def test_immutability(self):
        """Test that value object is immutable."""
        status = StickyActiveStatus(value="ACTIVE")
        with pytest.raises(ValidationError):
            status.value = "STANDBY"

    def test_hashable(self):
        """Test that value object is hashable."""
        status1 = StickyActiveStatus(value="ACTIVE")
        status2 = StickyActiveStatus(value="ACTIVE")
        status3 = StickyActiveStatus(value="STANDBY")

        status_set = {status1, status2, status3}
        assert len(status_set) == 2  # Only two unique values


class TestLeaderKey:
    """Test LeaderKey value object."""

    def test_creation(self):
        """Test leader key creation."""
        service_name = ServiceName(value="test-service")
        key = LeaderKey(service_name=service_name)

        assert key.service_name == service_name
        assert key.group_id == "default"
        assert key.to_kv_key() == "sticky-active.test-service.default.leader"

    def test_custom_group_id(self):
        """Test leader key with custom group ID."""
        service_name = ServiceName(value="test-service")
        key = LeaderKey(service_name=service_name, group_id="group1")

        assert key.group_id == "group1"
        assert key.to_kv_key() == "sticky-active.test-service.group1.leader"

    def test_string_representation(self):
        """Test string representation."""
        service_name = ServiceName(value="test-service")
        key = LeaderKey(service_name=service_name)

        assert str(key) == "sticky-active.test-service.default.leader"


class TestElectionTimeout:
    """Test ElectionTimeout value object."""

    def test_default_values(self):
        """Test default timeout values."""
        timeout = ElectionTimeout()

        assert timeout.leader_ttl.seconds == 5
        assert timeout.heartbeat_interval.seconds == 2
        assert timeout.election_timeout.seconds == 10
        assert timeout.failover_delay.seconds == 0.5

    def test_custom_values(self):
        """Test custom timeout values."""
        timeout = ElectionTimeout(
            leader_ttl=Duration(seconds=10),
            heartbeat_interval=Duration(seconds=3),
            election_timeout=Duration(seconds=20),
            failover_delay=Duration(seconds=1),
        )

        assert timeout.leader_ttl.seconds == 10
        assert timeout.heartbeat_interval.seconds == 3
        assert timeout.election_timeout.seconds == 20
        assert timeout.failover_delay.seconds == 1

    def test_heartbeat_validation(self):
        """Test heartbeat interval validation."""
        # Heartbeat interval must be less than leader TTL
        with pytest.raises(ValidationError) as exc_info:
            ElectionTimeout(
                leader_ttl=Duration(seconds=5),
                heartbeat_interval=Duration(seconds=5),  # Equal to TTL
            )
        assert "Heartbeat interval must be less than leader TTL" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ElectionTimeout(
                leader_ttl=Duration(seconds=5),
                heartbeat_interval=Duration(seconds=10),  # Greater than TTL
            )
        assert "Heartbeat interval must be less than leader TTL" in str(exc_info.value)


class TestServiceGroupId:
    """Test ServiceGroupId value object."""

    def test_valid_group_id(self):
        """Test creation with valid group ID."""
        group = ServiceGroupId(value="production")
        assert group.value == "production"
        assert str(group) == "production"

    def test_invalid_group_id(self):
        """Test creation with invalid group ID."""
        # Empty or whitespace
        with pytest.raises(ValidationError):
            ServiceGroupId(value="")

        with pytest.raises(ValidationError):
            ServiceGroupId(value="   ")

        # Contains dots
        with pytest.raises(ValidationError) as exc_info:
            ServiceGroupId(value="prod.east")
        assert "cannot contain dots" in str(exc_info.value)

        # Contains whitespace
        with pytest.raises(ValidationError) as exc_info:
            ServiceGroupId(value="prod east")
        assert "cannot contain whitespace" in str(exc_info.value)

    def test_equality(self):
        """Test equality comparison."""
        group1 = ServiceGroupId(value="production")
        group2 = ServiceGroupId(value="production")
        group3 = ServiceGroupId(value="staging")

        assert group1 == group2
        assert group1 == "production"
        assert group1 != group3
        assert group1 != "staging"


class TestStickyActiveElection:
    """Test StickyActiveElection aggregate."""

    def test_initialization(self):
        """Test aggregate initialization."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        election = StickyActiveElection(
            service_name=service_name,
            instance_id=instance_id,
        )

        assert election.service_name == service_name
        assert election.instance_id == instance_id
        assert election.group_id == "default"
        assert election.status == StickyActiveElectionState.STANDBY
        assert election.leader_instance_id is None
        assert not election.is_leader
        assert not election.is_electing

        # Check that initialization event was recorded
        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "election.initialized"

    def test_timing_validation(self):
        """Test timing configuration validation."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Heartbeat interval >= leader TTL
        with pytest.raises(ValueError) as exc_info:
            StickyActiveElection(
                service_name=service_name,
                instance_id=instance_id,
                leader_ttl_seconds=5,
                heartbeat_interval_seconds=5,
            )
        assert "Heartbeat interval must be less than leader TTL" in str(exc_info.value)

        # Election timeout <= leader TTL
        with pytest.raises(ValueError) as exc_info:
            StickyActiveElection(
                service_name=service_name,
                instance_id=instance_id,
                leader_ttl_seconds=10,
                election_timeout_seconds=10,
            )
        assert "Election timeout should be greater than leader TTL" in str(exc_info.value)

    def test_start_election(self):
        """Test starting an election."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        election.mark_events_committed()  # Clear initialization event

        election.start_election()

        assert election.status == StickyActiveElectionState.ELECTING
        assert election.is_electing
        assert election.last_election_attempt is not None

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "election.started"

    def test_cannot_start_election_when_active(self):
        """Test that active instances cannot start election."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        election.status = StickyActiveElectionState.ACTIVE
        election.leader_instance_id = election.instance_id

        with pytest.raises(ValueError) as exc_info:
            election.start_election()
        assert "Cannot start election when already active" in str(exc_info.value)

    def test_win_election(self):
        """Test winning an election."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        election.start_election()
        election.mark_events_committed()

        election.win_election()

        assert election.status == StickyActiveElectionState.ACTIVE
        assert election.is_leader
        assert election.leader_instance_id == election.instance_id
        assert election.became_leader_at is not None
        assert election.last_leader_heartbeat is not None

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "election.won"

    def test_lose_election(self):
        """Test losing an election."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        winner_id = InstanceId(value="instance-2")

        election.start_election()
        election.mark_events_committed()

        election.lose_election(winner_id)

        assert election.status == StickyActiveElectionState.STANDBY
        assert not election.is_leader
        assert election.leader_instance_id == winner_id
        assert election.last_leader_heartbeat is not None

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "election.lost"

    def test_leader_heartbeat(self):
        """Test leader heartbeat update."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        election.start_election()
        election.win_election()
        election.mark_events_committed()

        old_heartbeat = election.last_leader_heartbeat
        with patch("aegis_sdk.domain.aggregates.datetime") as mock_dt:
            new_time = datetime.now(UTC) + timedelta(seconds=1)
            mock_dt.now.return_value = new_time

            election.update_leader_heartbeat()

        assert election.last_leader_heartbeat > old_heartbeat

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "leader.heartbeat_updated"

    def test_non_leader_cannot_update_heartbeat(self):
        """Test that non-leaders cannot update heartbeat."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )

        with pytest.raises(ValueError) as exc_info:
            election.update_leader_heartbeat()
        assert "Only the leader can update heartbeat" in str(exc_info.value)

    def test_observe_leader_heartbeat(self):
        """Test observing leader heartbeat as standby."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        leader_id = InstanceId(value="instance-2")

        election.observe_leader_heartbeat(leader_id)

        assert election.leader_instance_id == leader_id
        assert election.last_leader_heartbeat is not None

    def test_detect_leader_failure(self):
        """Test leader failure detection."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
            leader_ttl_seconds=5,
        )
        leader_id = InstanceId(value="instance-2")

        # No heartbeat received
        assert election.detect_leader_failure()

        # Recent heartbeat
        election.observe_leader_heartbeat(leader_id)
        assert not election.detect_leader_failure()

        # Expired heartbeat
        with patch("aegis_sdk.domain.aggregates.datetime") as mock_dt:
            expired_time = datetime.now(UTC) + timedelta(seconds=10)
            mock_dt.now.return_value = expired_time
            assert election.detect_leader_failure()

    def test_step_down(self):
        """Test stepping down from leadership."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        election.start_election()
        election.win_election()
        election.mark_events_committed()

        election.step_down("Manual shutdown")

        assert election.status == StickyActiveElectionState.STANDBY
        assert not election.is_leader
        assert election.leader_instance_id is None
        assert election.became_leader_at is None

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "leader.stepped_down"
        assert events[0].details["reason"] == "Manual shutdown"

    def test_handle_leader_expired(self):
        """Test handling expired leader."""
        election = StickyActiveElection(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-1"),
        )
        leader_id = InstanceId(value="instance-2")
        election.observe_leader_heartbeat(leader_id)
        election.mark_events_committed()

        election.handle_leader_expired()

        assert election.leader_instance_id is None
        assert election.last_leader_heartbeat is None

        events = election.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "leader.expired"
        assert events[0].details["expired_leader"] == str(leader_id)


class TestStickyActiveElectionService:
    """Test StickyActiveElectionService domain service."""

    def test_initialization(self):
        """Test service initialization."""
        service = StickyActiveElectionService()

        assert service.leader_ttl == 5
        assert service.heartbeat_interval == 2
        assert service.election_timeout == 10
        assert service.failover_delay == 0.5

    def test_timing_validation(self):
        """Test timing configuration validation."""
        # Heartbeat interval >= leader TTL
        with pytest.raises(ValueError) as exc_info:
            StickyActiveElectionService(
                leader_ttl_seconds=5,
                heartbeat_interval_seconds=5,
            )
        assert "Heartbeat interval must be less than leader TTL" in str(exc_info.value)

        # Election timeout <= leader TTL
        with pytest.raises(ValueError) as exc_info:
            StickyActiveElectionService(
                leader_ttl_seconds=10,
                election_timeout_seconds=10,
            )
        assert "Election timeout should be greater than leader TTL" in str(exc_info.value)

    def test_create_leader_key(self):
        """Test leader key creation."""
        service = StickyActiveElectionService()

        key = service.create_leader_key("test-service")
        assert key == "sticky-active.test-service.default.leader"

        key = service.create_leader_key("test-service", "group1")
        assert key == "sticky-active.test-service.group1.leader"

    def test_create_leader_value(self):
        """Test leader value creation."""
        service = StickyActiveElectionService()

        value = service.create_leader_value("instance-1")
        assert value["instance_id"] == "instance-1"
        assert "elected_at" in value
        assert "last_heartbeat" in value
        assert value["metadata"] == {}

        value = service.create_leader_value("instance-1", {"zone": "us-east-1"})
        assert value["metadata"] == {"zone": "us-east-1"}

    def test_parse_leader_value(self):
        """Test leader value parsing."""
        import json
        import time

        service = StickyActiveElectionService()

        # Valid JSON string
        value_dict = {
            "instance_id": "instance-1",
            "last_heartbeat": time.time(),
            "metadata": {"zone": "us-east-1"},
        }
        value_str = json.dumps(value_dict)

        instance_id, heartbeat, metadata = service.parse_leader_value(value_str)
        assert instance_id == "instance-1"
        assert isinstance(heartbeat, float)
        assert metadata == {"zone": "us-east-1"}

        # Valid JSON bytes
        value_bytes = value_str.encode("utf-8")
        instance_id, heartbeat, metadata = service.parse_leader_value(value_bytes)
        assert instance_id == "instance-1"

        # Invalid JSON
        with pytest.raises(ValueError) as exc_info:
            service.parse_leader_value("invalid json")
        assert "Invalid leader value format" in str(exc_info.value)

        # Missing required field
        with pytest.raises(ValueError) as exc_info:
            service.parse_leader_value(json.dumps({"last_heartbeat": time.time()}))
        assert "Invalid leader value format" in str(exc_info.value)

    def test_is_leader_expired(self):
        """Test leader expiration check."""
        service = StickyActiveElectionService(leader_ttl_seconds=5)

        current_time = 1000.0

        # Recent heartbeat
        assert not service.is_leader_expired(998.0, current_time)

        # Expired heartbeat
        assert service.is_leader_expired(990.0, current_time)

        # Edge case: exactly at TTL
        assert not service.is_leader_expired(995.0, current_time)
        assert service.is_leader_expired(994.9, current_time)

    def test_should_attempt_election(self):
        """Test election attempt decision."""
        service = StickyActiveElectionService(failover_delay_seconds=2.0)

        current_time = 1000.0

        # Leader not expired
        assert not service.should_attempt_election(False, None, current_time)

        # Leader expired, no previous attempt
        assert service.should_attempt_election(True, None, current_time)

        # Leader expired, recent attempt
        assert not service.should_attempt_election(True, 999.0, current_time)

        # Leader expired, old attempt
        assert service.should_attempt_election(True, 997.0, current_time)

    def test_calculate_election_backoff(self):
        """Test election backoff calculation."""
        service = StickyActiveElectionService(failover_delay_seconds=1.0)

        # First attempt
        backoff = service.calculate_election_backoff(0)
        assert 1.0 <= backoff <= 1.1  # Base delay + up to 10% jitter

        # Second attempt
        backoff = service.calculate_election_backoff(1)
        assert 2.0 <= backoff <= 2.2  # 2^1 * base + jitter

        # Third attempt
        backoff = service.calculate_election_backoff(2)
        assert 4.0 <= backoff <= 4.4  # 2^2 * base + jitter

        # Max backoff
        backoff = service.calculate_election_backoff(10)
        assert backoff <= 33.0  # Capped at 30 + max jitter

    def test_validate_election_transition(self):
        """Test election state transition validation."""
        service = StickyActiveElectionService()

        # Valid transitions from STANDBY
        service.validate_election_transition("STANDBY", "ELECTING")
        service.validate_election_transition("STANDBY", "ACTIVE")

        # Valid transitions from ELECTING
        service.validate_election_transition("ELECTING", "ACTIVE")
        service.validate_election_transition("ELECTING", "STANDBY")

        # Valid transitions from ACTIVE
        service.validate_election_transition("ACTIVE", "STANDBY")

        # Invalid transitions
        with pytest.raises(ValueError) as exc_info:
            service.validate_election_transition("ACTIVE", "ELECTING")
        assert "Invalid transition from ACTIVE to ELECTING" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            service.validate_election_transition("STANDBY", "INVALID")
        assert "Invalid transition from STANDBY to INVALID" in str(exc_info.value)
