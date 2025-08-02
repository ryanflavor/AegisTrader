"""Comprehensive tests for domain value objects following TDD principles."""

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.value_objects import (
    EventType,
    InstanceId,
    MethodName,
    Priority,
    ServiceName,
)


class TestServiceName:
    """Test cases for ServiceName value object."""

    def test_valid_service_names(self):
        """Test creation with valid service names."""
        # Single letter
        assert ServiceName(value="a").value == "a"

        # Simple name
        assert ServiceName(value="user-service").value == "user-service"

        # With underscores
        assert ServiceName(value="user_service").value == "user_service"

        # Mixed case (normalized to lowercase)
        assert ServiceName(value="UserService").value == "userservice"

        # Numbers
        assert ServiceName(value="service123").value == "service123"

    def test_invalid_service_names(self):
        """Test validation rejects invalid service names."""
        # Empty string
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="")
        assert "at least 1 character" in str(exc_info.value)

        # Starts with number
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="123service")
        assert "Must start with a letter" in str(exc_info.value)

        # Ends with hyphen
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="service-")
        assert "not end with a hyphen or underscore" in str(exc_info.value)

        # Ends with underscore
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="service_")
        assert "not end with a hyphen or underscore" in str(exc_info.value)

        # Special characters
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="service@123")
        assert "Invalid service name" in str(exc_info.value)

        # Too long (>64 chars)
        with pytest.raises(ValidationError) as exc_info:
            ServiceName(value="a" * 65)
        assert "at most 64 characters" in str(exc_info.value)

    def test_service_name_immutability(self):
        """Test that ServiceName is immutable."""
        service = ServiceName(value="test-service")
        with pytest.raises(ValidationError):
            service.value = "new-service"  # type: ignore

    def test_service_name_equality(self):
        """Test equality comparison."""
        service1 = ServiceName(value="test-service")
        service2 = ServiceName(value="test-service")
        service3 = ServiceName(value="other-service")

        # Same value
        assert service1 == service2
        assert service1 == "test-service"

        # Different value
        assert service1 != service3
        assert service1 != "other-service"
        assert service1 != 123
        assert service1 != None

    def test_service_name_hashable(self):
        """Test that ServiceName can be used in sets and dicts."""
        service1 = ServiceName(value="service1")
        service2 = ServiceName(value="service2")
        service_dup = ServiceName(value="service1")

        # Can be used in set
        service_set = {service1, service2, service_dup}
        assert len(service_set) == 2

        # Can be used as dict key
        service_dict = {service1: "value1", service2: "value2"}
        assert service_dict[service_dup] == "value1"

    def test_service_name_string_representation(self):
        """Test string representation."""
        service = ServiceName(value="test-service")
        assert str(service) == "test-service"


class TestInstanceId:
    """Test cases for InstanceId value object."""

    def test_valid_instance_ids(self):
        """Test creation with valid instance IDs."""
        # UUID style
        assert (
            InstanceId(value="550e8400-e29b-41d4-a716-446655440000").value
            == "550e8400-e29b-41d4-a716-446655440000"
        )

        # Simple ID
        assert InstanceId(value="instance-123").value == "instance-123"

        # Pod name style
        assert (
            InstanceId(value="service-deployment-7d8f9c-x2kj9").value
            == "service-deployment-7d8f9c-x2kj9"
        )

    def test_invalid_instance_ids(self):
        """Test validation rejects invalid instance IDs."""
        # Empty string
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="")
        assert "at least 1 character" in str(exc_info.value)

        # Only whitespace
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="   ")
        assert "cannot be empty or whitespace" in str(exc_info.value)

        # Contains spaces
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="instance 123")
        assert "cannot contain whitespace" in str(exc_info.value)

        # Contains newline
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="instance\n123")
        assert "cannot contain whitespace" in str(exc_info.value)

        # Contains control characters
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="instance\x00123")
        assert "control characters" in str(exc_info.value)

        # Too long (>128 chars)
        with pytest.raises(ValidationError) as exc_info:
            InstanceId(value="a" * 129)
        assert "at most 128 characters" in str(exc_info.value)

    def test_instance_id_immutability(self):
        """Test that InstanceId is immutable."""
        instance = InstanceId(value="test-123")
        with pytest.raises(ValidationError):
            instance.value = "new-123"  # type: ignore

    def test_instance_id_equality(self):
        """Test equality comparison."""
        instance1 = InstanceId(value="test-123")
        instance2 = InstanceId(value="test-123")
        instance3 = InstanceId(value="test-456")

        assert instance1 == instance2
        assert instance1 == "test-123"
        assert instance1 != instance3
        assert instance1 != "test-456"

    def test_instance_id_hashable(self):
        """Test that InstanceId can be used in sets and dicts."""
        instance1 = InstanceId(value="id1")
        instance2 = InstanceId(value="id2")

        instances = {instance1, instance2, instance1}
        assert len(instances) == 2


class TestEventType:
    """Test cases for EventType value object."""

    def test_valid_event_types(self):
        """Test creation with valid event types."""
        # Simple event
        assert EventType(value="created").value == "created"

        # Dot notation
        assert EventType(value="order.created").value == "order.created"

        # Multiple levels
        assert EventType(value="order.payment.processed").value == "order.payment.processed"

        # With underscores
        assert EventType(value="user_profile.updated").value == "user_profile.updated"

        # Mixed case (normalized to lowercase)
        assert EventType(value="Order.Created").value == "order.created"

    def test_invalid_event_types(self):
        """Test validation rejects invalid event types."""
        # Empty string
        with pytest.raises(ValidationError) as exc_info:
            EventType(value="")
        assert "at least 1 character" in str(exc_info.value)

        # Starts with dot
        with pytest.raises(ValidationError) as exc_info:
            EventType(value=".created")
        assert "Invalid event type" in str(exc_info.value)

        # Ends with dot
        with pytest.raises(ValidationError) as exc_info:
            EventType(value="order.")
        assert "Invalid event type" in str(exc_info.value)

        # Consecutive dots
        with pytest.raises(ValidationError) as exc_info:
            EventType(value="order..created")
        assert "Invalid event type" in str(exc_info.value)

        # Special characters
        with pytest.raises(ValidationError) as exc_info:
            EventType(value="order@created")
        assert "Invalid event type" in str(exc_info.value)

        # Too long (>64 chars)
        with pytest.raises(ValidationError) as exc_info:
            EventType(value="a" * 65)
        assert "at most 64 characters" in str(exc_info.value)

    def test_event_type_properties(self):
        """Test domain and action properties."""
        # Simple event
        event = EventType(value="created")
        assert event.domain == "created"
        assert event.action == "created"

        # Dot notation
        event = EventType(value="order.created")
        assert event.domain == "order"
        assert event.action == "created"

        # Multiple levels
        event = EventType(value="order.payment.processed")
        assert event.domain == "order"
        assert event.action == "processed"

    def test_event_type_equality(self):
        """Test equality comparison."""
        event1 = EventType(value="order.created")
        event2 = EventType(value="order.created")
        event3 = EventType(value="order.updated")

        assert event1 == event2
        assert event1 == "order.created"
        assert event1 != event3


class TestMethodName:
    """Test cases for MethodName value object."""

    def test_valid_method_names(self):
        """Test creation with valid method names."""
        # Simple method
        assert MethodName(value="get_user").value == "get_user"

        # Single word
        assert MethodName(value="list").value == "list"

        # With numbers
        assert MethodName(value="get_user_v2").value == "get_user_v2"

    def test_invalid_method_names(self):
        """Test validation rejects invalid method names."""
        # Empty string
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="")
        assert "at least 1 character" in str(exc_info.value)

        # Starts with uppercase (not snake_case)
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="GetUser")
        assert "Must start with a lowercase letter" in str(exc_info.value)

        # Contains uppercase (not snake_case)
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="getUser")
        assert "follow snake_case convention" in str(exc_info.value)

        # Starts with number
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="2get_user")
        assert "Must start with a lowercase letter" in str(exc_info.value)

        # Contains hyphen (not snake_case)
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="get-user")
        assert "follow snake_case convention" in str(exc_info.value)

        # Too long (>64 chars)
        with pytest.raises(ValidationError) as exc_info:
            MethodName(value="a" * 65)
        assert "at most 64 characters" in str(exc_info.value)

    def test_method_name_immutability(self):
        """Test that MethodName is immutable."""
        method = MethodName(value="get_user")
        with pytest.raises(ValidationError):
            method.value = "set_user"  # type: ignore

    def test_method_name_equality(self):
        """Test equality comparison."""
        method1 = MethodName(value="get_user")
        method2 = MethodName(value="get_user")
        method3 = MethodName(value="set_user")

        assert method1 == method2
        assert method1 == "get_user"
        assert method1 != method3


class TestPriority:
    """Test cases for Priority value object."""

    def test_valid_priorities(self):
        """Test creation with valid priorities."""
        assert Priority(value="low").value == "low"
        assert Priority(value="normal").value == "normal"
        assert Priority(value="high").value == "high"
        assert Priority(value="critical").value == "critical"

        # Default value
        assert Priority().value == "normal"

    def test_invalid_priorities(self):
        """Test validation rejects invalid priorities."""
        with pytest.raises(ValidationError) as exc_info:
            Priority(value="urgent")
        assert "String should match pattern" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            Priority(value="")
        assert "String should match pattern" in str(exc_info.value)

    def test_priority_constants(self):
        """Test priority class constants."""
        assert Priority.LOW == "low"
        assert Priority.NORMAL == "normal"
        assert Priority.HIGH == "high"
        assert Priority.CRITICAL == "critical"

    def test_priority_comparison(self):
        """Test priority ordering."""
        low = Priority(value="low")
        normal = Priority(value="normal")
        high = Priority(value="high")
        critical = Priority(value="critical")

        # Less than comparisons
        assert low < normal
        assert normal < high
        assert high < critical
        assert low < critical

        # Not less than
        assert not (high < normal)
        assert not (critical < low)

        # Equality
        assert low == Priority(value="low")
        assert low == "low"

        # Invalid comparison
        with pytest.raises(TypeError):
            low < "string"

    def test_priority_immutability(self):
        """Test that Priority is immutable."""
        priority = Priority(value="high")
        with pytest.raises(ValidationError):
            priority.value = "low"  # type: ignore

    def test_priority_hashable(self):
        """Test that Priority can be used in sets and dicts."""
        p1 = Priority(value="high")
        p2 = Priority(value="low")
        p3 = Priority(value="high")

        priority_set = {p1, p2, p3}
        assert len(priority_set) == 2

        priority_dict = {p1: "urgent", p2: "can wait"}
        assert priority_dict[p3] == "urgent"
