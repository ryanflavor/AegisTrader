"""Comprehensive tests for domain aggregates following TDD principles."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.aggregates import ServiceAggregate, ServiceLifecycleEvent, ServiceStatus
from aegis_sdk.domain.value_objects import InstanceId, ServiceName


class TestServiceAggregate:
    """Test cases for ServiceAggregate following DDD principles."""

    def test_aggregate_creation(self):
        """Test creating a new service aggregate."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        aggregate = ServiceAggregate(
            service_name=service_name,
            instance_id=instance_id,
            version="2.0.0",
            metadata={"region": "us-east-1"},
        )

        assert aggregate.service_name == service_name
        assert aggregate.instance_id == instance_id
        assert aggregate.version == "2.0.0"
        assert aggregate.status == ServiceStatus.ACTIVE
        assert aggregate.metadata == {"region": "us-east-1"}
        assert isinstance(aggregate.registered_at, datetime)
        assert isinstance(aggregate.last_heartbeat, datetime)

        # Should have a creation event
        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.registered"

    def test_aggregate_default_values(self):
        """Test aggregate with default values."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        aggregate = ServiceAggregate(service_name=service_name, instance_id=instance_id)

        assert aggregate.version == "1.0.0"
        assert aggregate.status == ServiceStatus.ACTIVE
        assert aggregate.metadata == {}

    def test_is_healthy_property(self):
        """Test the is_healthy computed property."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )

        # Fresh aggregate should be healthy
        assert aggregate.is_healthy is True

        # Set last heartbeat to old time (more than 30 seconds ago)
        old_time = datetime.now(UTC) - timedelta(seconds=40)
        aggregate.last_heartbeat = old_time
        assert aggregate.is_healthy is False

        # Unhealthy status should always be unhealthy
        aggregate.status = ServiceStatus.UNHEALTHY
        aggregate.last_heartbeat = datetime.now(UTC)
        assert aggregate.is_healthy is False

    def test_uptime_seconds_property(self):
        """Test the uptime_seconds computed property."""
        # Create aggregate with known registration time
        past_time = datetime.now(UTC) - timedelta(seconds=60)
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        # Manually set the registration time to a known past value
        aggregate.registered_at = past_time

        # Uptime should be approximately 60 seconds
        assert aggregate.uptime_seconds == pytest.approx(60.0, abs=1.0)

    def test_heartbeat_from_active(self):
        """Test sending heartbeat from active service."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.mark_events_committed()  # Clear creation event

        old_heartbeat = aggregate.last_heartbeat
        aggregate.heartbeat()

        assert aggregate.last_heartbeat > old_heartbeat
        assert aggregate.status == ServiceStatus.ACTIVE

        # No events for normal heartbeat
        events = aggregate.get_uncommitted_events()
        assert len(events) == 0

    def test_heartbeat_from_unhealthy(self):
        """Test heartbeat recovers unhealthy service."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.mark_unhealthy("Test failure")
        aggregate.mark_events_committed()

        aggregate.heartbeat()

        assert aggregate.status == ServiceStatus.ACTIVE

        # Should have recovery event
        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.recovered"
        assert events[0].details["previous_status"] == ServiceStatus.UNHEALTHY

    def test_heartbeat_from_shutdown_fails(self):
        """Test heartbeat from shutdown service raises error."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.shutdown()

        with pytest.raises(ValueError, match="Cannot send heartbeat from shutdown service"):
            aggregate.heartbeat()

    def test_activate_transitions(self):
        """Test activate method state transitions."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )

        # Already active - no change
        aggregate.mark_events_committed()
        aggregate.activate()
        assert aggregate.status == ServiceStatus.ACTIVE
        assert len(aggregate.get_uncommitted_events()) == 0

        # From standby to active
        aggregate.standby()
        aggregate.mark_events_committed()
        aggregate.activate()
        assert aggregate.status == ServiceStatus.ACTIVE
        events = aggregate.get_uncommitted_events()
        assert events[-1].event_type == "service.activated"
        assert events[-1].details["previous_status"] == ServiceStatus.STANDBY

        # From unhealthy to active
        aggregate.mark_unhealthy("Test")
        aggregate.mark_events_committed()
        aggregate.activate()
        assert aggregate.status == ServiceStatus.ACTIVE
        events = aggregate.get_uncommitted_events()
        assert events[-1].event_type == "service.activated"
        assert events[-1].details["previous_status"] == ServiceStatus.UNHEALTHY

    def test_activate_from_shutdown_fails(self):
        """Test activate from shutdown state raises error."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.shutdown()

        with pytest.raises(ValueError, match="Cannot activate a shutdown service"):
            aggregate.activate()

    def test_standby_transitions(self):
        """Test standby method state transitions."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )

        # From active to standby
        aggregate.mark_events_committed()
        aggregate.standby()
        assert aggregate.status == ServiceStatus.STANDBY
        events = aggregate.get_uncommitted_events()
        assert events[0].event_type == "service.standby"
        assert events[0].details["previous_status"] == ServiceStatus.ACTIVE

        # Already in standby - no change
        aggregate.mark_events_committed()
        aggregate.standby()
        assert len(aggregate.get_uncommitted_events()) == 0

    def test_standby_from_shutdown_fails(self):
        """Test standby from shutdown state raises error."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.shutdown()

        with pytest.raises(ValueError, match="Cannot put shutdown service in standby"):
            aggregate.standby()

    def test_mark_unhealthy(self):
        """Test marking service as unhealthy."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.mark_events_committed()

        aggregate.mark_unhealthy("High memory usage")

        assert aggregate.status == ServiceStatus.UNHEALTHY
        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.unhealthy"
        assert events[0].details["previous_status"] == ServiceStatus.ACTIVE
        assert events[0].details["reason"] == "High memory usage"

    def test_mark_unhealthy_from_shutdown_fails(self):
        """Test marking shutdown service as unhealthy raises error."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.shutdown()

        with pytest.raises(ValueError, match="Cannot mark shutdown service as unhealthy"):
            aggregate.mark_unhealthy("Test")

    def test_shutdown_is_terminal(self):
        """Test shutdown is a terminal state."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.mark_events_committed()

        # Can shutdown from any state
        aggregate.shutdown()
        assert aggregate.status == ServiceStatus.SHUTDOWN
        events = aggregate.get_uncommitted_events()
        assert events[0].event_type == "service.shutdown"
        assert events[0].details["previous_status"] == ServiceStatus.ACTIVE

        # Already shutdown - no change
        aggregate.mark_events_committed()
        aggregate.shutdown()
        assert len(aggregate.get_uncommitted_events()) == 0

    def test_update_metadata(self):
        """Test updating service metadata."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
            metadata={"region": "us-east-1", "zone": "a"},
        )
        aggregate.mark_events_committed()

        # Update metadata
        new_metadata = {"zone": "b", "cluster": "prod"}
        aggregate.update_metadata(new_metadata)

        # Should merge with existing
        assert aggregate.metadata == {"region": "us-east-1", "zone": "b", "cluster": "prod"}

        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.metadata_updated"
        assert events[0].details["old_metadata"] == {"region": "us-east-1", "zone": "a"}

    def test_update_metadata_on_shutdown_fails(self):
        """Test updating metadata of shutdown service raises error."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.shutdown()

        with pytest.raises(ValueError, match="Cannot update metadata of shutdown service"):
            aggregate.update_metadata({"key": "value"})

    def test_to_service_info(self):
        """Test converting aggregate to ServiceInfo model."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
            version="2.0.0",
            metadata={"region": "us-east-1"},
        )

        service_info = aggregate.to_service_info()

        assert service_info.service_name == "test-service"
        assert service_info.instance_id == "instance-123"
        assert service_info.version == "2.0.0"
        assert service_info.status == "ACTIVE"
        assert service_info.metadata == {"region": "us-east-1"}
        assert isinstance(service_info.registered_at, str)
        assert isinstance(service_info.last_heartbeat, str)

    def test_event_tracking(self):
        """Test domain event tracking and management."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )

        # Should have registration event
        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.registered"

        # Perform some operations
        aggregate.standby()
        aggregate.activate()
        aggregate.update_metadata({"key": "value"})

        # Should have all events
        events = aggregate.get_uncommitted_events()
        assert len(events) == 4
        event_types = [e.event_type for e in events]
        assert event_types == [
            "service.registered",
            "service.standby",
            "service.activated",
            "service.metadata_updated",
        ]

        # Mark as committed
        aggregate.mark_events_committed()
        assert len(aggregate.get_uncommitted_events()) == 0

        # New events should be tracked
        aggregate.shutdown()
        events = aggregate.get_uncommitted_events()
        assert len(events) == 1
        assert events[0].event_type == "service.shutdown"

    def test_service_lifecycle_event(self):
        """Test ServiceLifecycleEvent structure."""
        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-123")

        event = ServiceLifecycleEvent(
            service_name=service_name,
            instance_id=instance_id,
            event_type="service.activated",
            timestamp=datetime.now(UTC),
            details={"previous_status": "STANDBY"},
        )

        assert event.service_name == service_name
        assert event.instance_id == instance_id
        assert event.event_type == "service.activated"
        assert isinstance(event.timestamp, datetime)
        assert event.details == {"previous_status": "STANDBY"}

        # Should be immutable
        with pytest.raises(ValidationError):
            event.event_type = "service.shutdown"  # type: ignore

    def test_string_representation(self):
        """Test aggregate string representation."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )

        assert str(aggregate) == "ServiceAggregate(test-service/instance-123 - ACTIVE)"

        aggregate.shutdown()
        assert str(aggregate) == "ServiceAggregate(test-service/instance-123 - SHUTDOWN)"

    def test_complex_lifecycle_scenario(self):
        """Test a complex service lifecycle scenario."""
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="instance-123"),
        )
        aggregate.mark_events_committed()

        # Service starts active, goes to standby
        aggregate.standby()
        assert aggregate.status == ServiceStatus.STANDBY

        # Becomes unhealthy while in standby
        aggregate.mark_unhealthy("Network issues")
        assert aggregate.status == ServiceStatus.UNHEALTHY

        # Heartbeat recovers it to active
        aggregate.heartbeat()
        assert aggregate.status == ServiceStatus.ACTIVE

        # Update metadata while active
        aggregate.update_metadata({"version": "2.0.0"})
        assert aggregate.metadata == {"version": "2.0.0"}

        # Finally shutdown
        aggregate.shutdown()
        assert aggregate.status == ServiceStatus.SHUTDOWN

        # Check all events were recorded
        events = aggregate.get_uncommitted_events()
        event_types = [e.event_type for e in events]
        assert event_types == [
            "service.standby",
            "service.unhealthy",
            "service.recovered",
            "service.metadata_updated",
            "service.shutdown",
        ]
