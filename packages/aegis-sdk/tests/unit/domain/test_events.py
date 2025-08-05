"""Unit tests for domain events."""

import uuid
from datetime import UTC, datetime

import pytest

from aegis_sdk.domain.events import (
    DomainEvent,
    ServiceDeregisteredEvent,
    ServiceHeartbeatMissedEvent,
    ServiceRegisteredEvent,
    ServiceStatusChangedEvent,
)


class TestDomainEvent:
    """Test base DomainEvent class."""

    def test_domain_event_creation(self):
        """Test creating a domain event with required fields."""
        event = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
        )

        assert event.aggregate_id == "service-123"
        assert event.aggregate_type == "ServiceInstance"
        assert event.event_type == "TestEvent"
        assert event.event_version == "1.0"
        assert event.metadata == {}
        assert isinstance(event.event_id, str)
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo is not None

    def test_domain_event_with_metadata(self):
        """Test creating a domain event with metadata."""
        metadata = {"user_id": "user-456", "source": "api"}
        event = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
            metadata=metadata,
        )

        assert event.metadata == metadata

    def test_domain_event_with_custom_version(self):
        """Test creating a domain event with custom version."""
        event = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
            event_version="2.0",
        )

        assert event.event_version == "2.0"

    def test_domain_event_timestamp(self):
        """Test domain event timestamp is set correctly."""
        # Create event and check timestamp is set
        before = datetime.now(UTC)
        event = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
        )
        after = datetime.now(UTC)

        # Timestamp should be between before and after
        assert before <= event.occurred_at <= after
        assert event.occurred_at.tzinfo is not None

    def test_domain_event_unique_id(self):
        """Test each domain event has a unique ID."""
        event1 = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
        )
        event2 = DomainEvent(
            aggregate_id="service-123",
            aggregate_type="ServiceInstance",
            event_type="TestEvent",
        )

        assert event1.event_id != event2.event_id
        assert uuid.UUID(event1.event_id)  # Validate it's a valid UUID
        assert uuid.UUID(event2.event_id)

    def test_domain_event_required_fields(self):
        """Test domain event requires all fields."""
        # Test missing required fields
        with pytest.raises(ValueError):
            DomainEvent(
                aggregate_type="ServiceInstance",
                event_type="TestEvent",
                # Missing aggregate_id
            )

    def test_domain_event_extra_fields_forbidden(self):
        """Test extra fields are not allowed."""
        with pytest.raises(ValueError):
            DomainEvent(
                aggregate_id="service-123",
                aggregate_type="ServiceInstance",
                event_type="TestEvent",
                extra_field="not_allowed",
            )


class TestServiceRegisteredEvent:
    """Test ServiceRegisteredEvent."""

    def test_service_registered_event_creation(self):
        """Test creating a service registered event."""
        event = ServiceRegisteredEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            version="1.0.0",
            initial_status="ACTIVE",
            ttl_seconds=30,
        )

        assert event.event_type == "ServiceRegistered"
        assert event.aggregate_type == "ServiceInstance"
        assert event.aggregate_id == "service-123"
        assert event.service_name == "order-service"
        assert event.instance_id == "instance-001"
        assert event.version == "1.0.0"
        assert event.initial_status == "ACTIVE"
        assert event.ttl_seconds == 30

    def test_service_registered_event_auto_fields(self):
        """Test event type and aggregate type are set automatically."""
        event = ServiceRegisteredEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            version="1.0.0",
            initial_status="ACTIVE",
            ttl_seconds=30,
        )

        # These should be set by __init__
        assert event.event_type == "ServiceRegistered"
        assert event.aggregate_type == "ServiceInstance"

    def test_service_registered_event_with_metadata(self):
        """Test service registered event can include metadata."""
        metadata = {"region": "us-east-1", "environment": "production"}
        event = ServiceRegisteredEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            version="1.0.0",
            initial_status="ACTIVE",
            ttl_seconds=30,
            metadata=metadata,
        )

        assert event.metadata == metadata


class TestServiceDeregisteredEvent:
    """Test ServiceDeregisteredEvent."""

    def test_service_deregistered_event_creation(self):
        """Test creating a service deregistered event."""
        event = ServiceDeregisteredEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            reason="Graceful shutdown",
        )

        assert event.event_type == "ServiceDeregistered"
        assert event.aggregate_type == "ServiceInstance"
        assert event.aggregate_id == "service-123"
        assert event.service_name == "order-service"
        assert event.instance_id == "instance-001"
        assert event.reason == "Graceful shutdown"

    def test_service_deregistered_event_different_reasons(self):
        """Test service deregistered event with different reasons."""
        reasons = [
            "Graceful shutdown",
            "Health check failure",
            "Manual deregistration",
            "TTL expired",
        ]

        for reason in reasons:
            event = ServiceDeregisteredEvent(
                aggregate_id="service-123",
                service_name="order-service",
                instance_id="instance-001",
                reason=reason,
            )
            assert event.reason == reason


class TestServiceStatusChangedEvent:
    """Test ServiceStatusChangedEvent."""

    def test_service_status_changed_event_creation(self):
        """Test creating a service status changed event."""
        event = ServiceStatusChangedEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            old_status="ACTIVE",
            new_status="STANDBY",
            reason="Load balancing",
        )

        assert event.event_type == "ServiceStatusChanged"
        assert event.aggregate_type == "ServiceInstance"
        assert event.aggregate_id == "service-123"
        assert event.service_name == "order-service"
        assert event.instance_id == "instance-001"
        assert event.old_status == "ACTIVE"
        assert event.new_status == "STANDBY"
        assert event.reason == "Load balancing"

    def test_service_status_changed_event_without_reason(self):
        """Test service status changed event without reason."""
        event = ServiceStatusChangedEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            old_status="ACTIVE",
            new_status="UNHEALTHY",
        )

        assert event.old_status == "ACTIVE"
        assert event.new_status == "UNHEALTHY"
        assert event.reason is None

    def test_service_status_changed_event_various_transitions(self):
        """Test various status transitions."""
        transitions = [
            ("ACTIVE", "STANDBY"),
            ("STANDBY", "ACTIVE"),
            ("ACTIVE", "UNHEALTHY"),
            ("UNHEALTHY", "ACTIVE"),
            ("ACTIVE", "SHUTDOWN"),
        ]

        for old_status, new_status in transitions:
            event = ServiceStatusChangedEvent(
                aggregate_id="service-123",
                service_name="order-service",
                instance_id="instance-001",
                old_status=old_status,
                new_status=new_status,
            )
            assert event.old_status == old_status
            assert event.new_status == new_status


class TestServiceHeartbeatMissedEvent:
    """Test ServiceHeartbeatMissedEvent."""

    def test_service_heartbeat_missed_event_creation(self):
        """Test creating a service heartbeat missed event."""
        last_heartbeat = datetime.now(UTC)
        event = ServiceHeartbeatMissedEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            last_heartbeat=last_heartbeat,
            missed_count=3,
        )

        assert event.event_type == "ServiceHeartbeatMissed"
        assert event.aggregate_type == "ServiceInstance"
        assert event.aggregate_id == "service-123"
        assert event.service_name == "order-service"
        assert event.instance_id == "instance-001"
        assert event.last_heartbeat == last_heartbeat
        assert event.missed_count == 3

    def test_service_heartbeat_missed_event_with_timestamps(self):
        """Test heartbeat missed event with specific timestamps."""
        # Create a specific last heartbeat time
        last_heartbeat = datetime.now(UTC)
        event = ServiceHeartbeatMissedEvent(
            aggregate_id="service-123",
            service_name="order-service",
            instance_id="instance-001",
            last_heartbeat=last_heartbeat,
            missed_count=1,
        )

        # Event occurred after last heartbeat
        assert event.occurred_at >= last_heartbeat
        assert event.last_heartbeat == last_heartbeat
        # Time since heartbeat should be small (just created)
        time_since_heartbeat = (event.occurred_at - event.last_heartbeat).total_seconds()
        assert time_since_heartbeat >= 0
        assert time_since_heartbeat < 1.0  # Should be less than 1 second

    def test_service_heartbeat_missed_event_multiple_misses(self):
        """Test heartbeat missed event with different missed counts."""
        for missed_count in [1, 2, 3, 5, 10]:
            event = ServiceHeartbeatMissedEvent(
                aggregate_id="service-123",
                service_name="order-service",
                instance_id="instance-001",
                last_heartbeat=datetime.now(UTC),
                missed_count=missed_count,
            )
            assert event.missed_count == missed_count
