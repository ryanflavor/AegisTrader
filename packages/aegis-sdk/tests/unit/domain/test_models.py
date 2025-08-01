"""Comprehensive tests for domain models."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.models import (
    Command,
    Event,
    Message,
    RPCRequest,
    RPCResponse,
    ServiceInfo,
)


class TestMessage:
    """Test cases for Message base model."""

    def test_message_default_values(self):
        """Test Message creation with default values."""
        message = Message()

        assert isinstance(message.message_id, str)
        assert len(message.message_id) == 36  # UUID format
        assert isinstance(message.trace_id, str)
        assert len(message.trace_id) == 36
        assert message.correlation_id is None
        assert isinstance(message.timestamp, str)
        assert message.source is None
        assert message.target is None

    def test_message_with_custom_values(self):
        """Test Message creation with custom values."""
        custom_id = str(uuid.uuid4())
        custom_trace = str(uuid.uuid4())
        custom_timestamp = datetime.now(UTC).isoformat()

        message = Message(
            message_id=custom_id,
            trace_id=custom_trace,
            correlation_id="corr-123",
            timestamp=custom_timestamp,
            source="service-a",
            target="service-b",
        )

        assert message.message_id == custom_id
        assert message.trace_id == custom_trace
        assert message.correlation_id == "corr-123"
        assert message.timestamp == custom_timestamp
        assert message.source == "service-a"
        assert message.target == "service-b"

    def test_message_timestamp_validation(self):
        """Test timestamp validation."""
        # Valid ISO timestamp
        message = Message(timestamp="2025-01-01T00:00:00+00:00")
        assert message.timestamp == "2025-01-01T00:00:00+00:00"

        # Invalid timestamp format
        with pytest.raises(ValidationError) as exc_info:
            Message(timestamp="not-a-timestamp")
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_message_strict_mode(self):
        """Test that strict mode is enabled."""
        with pytest.raises(ValidationError):
            Message(extra_field="not allowed")

    def test_message_serialization(self):
        """Test Message serialization."""
        message = Message(source="test-service")
        data = message.model_dump()

        assert "message_id" in data
        assert "trace_id" in data
        assert data["source"] == "test-service"

        # Test JSON serialization
        json_str = message.model_dump_json()
        assert isinstance(json_str, str)
        assert "test-service" in json_str


class TestRPCRequest:
    """Test cases for RPCRequest model."""

    def test_rpc_request_basic(self):
        """Test basic RPCRequest creation."""
        request = RPCRequest(method="get_user")

        assert request.method == "get_user"
        assert request.params == {}
        assert request.timeout == 5.0

    def test_rpc_request_with_params(self):
        """Test RPCRequest with parameters."""
        params = {"user_id": 123, "include_details": True}
        request = RPCRequest(method="get_user", params=params, timeout=10.0)

        assert request.method == "get_user"
        assert request.params == params
        assert request.timeout == 10.0

    def test_rpc_request_method_validation(self):
        """Test method name validation."""
        # Empty method
        with pytest.raises(ValidationError) as exc_info:
            RPCRequest(method="")
        assert "Method name cannot be empty" in str(exc_info.value)

        # Whitespace-only method
        with pytest.raises(ValidationError) as exc_info:
            RPCRequest(method="   ")
        assert "Method name cannot be empty" in str(exc_info.value)

        # Method with whitespace is trimmed
        request = RPCRequest(method="  get_user  ")
        assert request.method == "get_user"

    def test_rpc_request_timeout_validation(self):
        """Test timeout validation."""
        # Negative timeout
        with pytest.raises(ValidationError):
            RPCRequest(method="test", timeout=-1.0)

        # Zero timeout
        with pytest.raises(ValidationError):
            RPCRequest(method="test", timeout=0.0)

    def test_rpc_request_inheritance(self):
        """Test that RPCRequest inherits from Message."""
        request = RPCRequest(method="test", source="service-a")

        assert isinstance(request, Message)
        assert request.source == "service-a"
        assert hasattr(request, "message_id")
        assert hasattr(request, "trace_id")


class TestRPCResponse:
    """Test cases for RPCResponse model."""

    def test_rpc_response_success(self):
        """Test successful RPC response."""
        response = RPCResponse(result={"user_id": 123, "name": "John"})

        assert response.success is True
        assert response.result == {"user_id": 123, "name": "John"}
        assert response.error is None

    def test_rpc_response_failure(self):
        """Test failed RPC response."""
        response = RPCResponse(success=False, error="User not found")

        assert response.success is False
        assert response.result is None
        assert response.error == "User not found"

    def test_rpc_response_error_validation(self):
        """Test error field validation."""
        # Error with success=True should fail
        with pytest.raises(ValidationError) as exc_info:
            RPCResponse(success=True, error="This should fail")
        assert "Error must be None when success is True" in str(exc_info.value)

        # No error with success=False should fail
        with pytest.raises(ValidationError) as exc_info:
            RPCResponse(success=False)
        assert "Error message required when success is False" in str(exc_info.value)

    def test_rpc_response_with_correlation(self):
        """Test RPCResponse with correlation ID."""
        response = RPCResponse(correlation_id="req-123", result="OK")

        assert response.correlation_id == "req-123"
        assert response.result == "OK"


class TestEvent:
    """Test cases for Event model."""

    def test_event_basic(self):
        """Test basic Event creation."""
        event = Event(domain="order", event_type="created")

        assert event.domain == "order"
        assert event.event_type == "created"
        assert event.payload == {}
        assert event.version == "1.0"

    def test_event_with_payload(self):
        """Test Event with payload."""
        payload = {"order_id": "123", "amount": 99.99}
        event = Event(domain="order", event_type="created", payload=payload, version="2.0")

        assert event.domain == "order"
        assert event.event_type == "created"
        assert event.payload == payload
        assert event.version == "2.0"

    def test_event_domain_validation(self):
        """Test domain validation."""
        # Empty domain
        with pytest.raises(ValidationError):
            Event(domain="", event_type="created")

        # Missing domain
        with pytest.raises(ValidationError):
            Event(event_type="created")

    def test_event_version_validation(self):
        """Test version format validation."""
        # Valid versions
        Event(domain="test", event_type="test", version="1.0")
        Event(domain="test", event_type="test", version="1.0.0")
        Event(domain="test", event_type="test", version="2.1.3")

        # Invalid versions
        with pytest.raises(ValidationError) as exc_info:
            Event(domain="test", event_type="test", version="v1.0")
        assert "Invalid version format" in str(exc_info.value)

        with pytest.raises(ValidationError):
            Event(domain="test", event_type="test", version="1.0.0.0")

        with pytest.raises(ValidationError):
            Event(domain="test", event_type="test", version="1.a")


class TestCommand:
    """Test cases for Command model."""

    def test_command_basic(self):
        """Test basic Command creation."""
        command = Command(command="process_order")

        assert command.command == "process_order"
        assert command.payload == {}
        assert command.priority == "normal"
        assert command.max_retries == 3
        assert command.timeout == 300.0

    def test_command_with_options(self):
        """Test Command with all options."""
        payload = {"order_id": "123"}
        command = Command(
            command="process_order",
            payload=payload,
            priority="high",
            max_retries=5,
            timeout=600.0,
            target="order-processor",
        )

        assert command.command == "process_order"
        assert command.payload == payload
        assert command.priority == "high"
        assert command.max_retries == 5
        assert command.timeout == 600.0
        assert command.target == "order-processor"

    def test_command_priority_validation(self):
        """Test priority validation."""
        # Valid priorities
        for priority in ["low", "normal", "high", "critical"]:
            command = Command(command="test", priority=priority)
            assert command.priority == priority

        # Invalid priority
        with pytest.raises(ValidationError):
            Command(command="test", priority="urgent")

    def test_command_validation(self):
        """Test command name validation."""
        # Empty command
        with pytest.raises(ValidationError) as exc_info:
            Command(command="")
        assert "Command name cannot be empty" in str(exc_info.value)

        # Whitespace command
        with pytest.raises(ValidationError) as exc_info:
            Command(command="   ")
        assert "Command name cannot be empty" in str(exc_info.value)

        # Command with whitespace is trimmed
        command = Command(command="  process_order  ")
        assert command.command == "process_order"

    def test_command_retry_validation(self):
        """Test max_retries validation."""
        # Negative retries
        with pytest.raises(ValidationError):
            Command(command="test", max_retries=-1)

        # Zero retries is valid
        command = Command(command="test", max_retries=0)
        assert command.max_retries == 0


class TestServiceInfo:
    """Test cases for ServiceInfo model."""

    def test_service_info_basic(self):
        """Test basic ServiceInfo creation."""
        info = ServiceInfo(service_name="order-service", instance_id="inst-123")

        assert info.service_name == "order-service"
        assert info.instance_id == "inst-123"
        assert info.version == "1.0.0"
        assert info.status == "ACTIVE"
        assert info.metadata == {}
        assert isinstance(info.registered_at, str)
        assert isinstance(info.last_heartbeat, str)

    def test_service_info_full(self):
        """Test ServiceInfo with all fields."""
        metadata = {"region": "us-east-1", "zone": "a"}
        info = ServiceInfo(
            service_name="order-service",
            instance_id="inst-123",
            version="2.1.0",
            status="STANDBY",
            metadata=metadata,
        )

        assert info.service_name == "order-service"
        assert info.instance_id == "inst-123"
        assert info.version == "2.1.0"
        assert info.status == "STANDBY"
        assert info.metadata == metadata

    def test_service_info_status_validation(self):
        """Test status validation."""
        # Valid statuses
        for status in ["ACTIVE", "STANDBY", "UNHEALTHY", "SHUTDOWN"]:
            info = ServiceInfo(service_name="test", instance_id="test", status=status)
            assert info.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            ServiceInfo(service_name="test", instance_id="test", status="RUNNING")

    def test_service_info_version_validation(self):
        """Test version validation."""
        # Valid versions
        ServiceInfo(service_name="test", instance_id="test", version="1.0.0")
        ServiceInfo(service_name="test", instance_id="test", version="10.20.30")

        # Invalid versions
        with pytest.raises(ValidationError) as exc_info:
            ServiceInfo(service_name="test", instance_id="test", version="1.0")
        assert "Invalid version format" in str(exc_info.value)

        with pytest.raises(ValidationError):
            ServiceInfo(service_name="test", instance_id="test", version="v1.0.0")

    def test_service_info_timestamp_validation(self):
        """Test timestamp validation."""
        # Valid timestamps
        now = datetime.now(UTC).isoformat()
        info = ServiceInfo(
            service_name="test",
            instance_id="test",
            registered_at=now,
            last_heartbeat=now,
        )
        assert info.registered_at == now
        assert info.last_heartbeat == now

        # Invalid timestamp
        with pytest.raises(ValidationError) as exc_info:
            ServiceInfo(
                service_name="test",
                instance_id="test",
                registered_at="not-a-timestamp",
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_service_info_strict_mode(self):
        """Test that strict mode is enabled."""
        with pytest.raises(ValidationError):
            ServiceInfo(
                service_name="test",
                instance_id="test",
                extra_field="not allowed",
            )


class TestModelIntegration:
    """Integration tests for model interactions."""

    def test_rpc_request_response_correlation(self):
        """Test RPC request/response correlation."""
        request = RPCRequest(method="get_user", params={"id": 123})

        # Simulate processing
        response = RPCResponse(
            correlation_id=request.message_id,
            result={"id": 123, "name": "John"},
        )

        assert response.correlation_id == request.message_id

    def test_event_source_tracking(self):
        """Test event source tracking."""
        service_info = ServiceInfo(service_name="order-service", instance_id="inst-123")

        event = Event(
            domain="order",
            event_type="created",
            source=service_info.instance_id,
            payload={"order_id": "456"},
        )

        assert event.source == service_info.instance_id

    def test_command_from_event(self):
        """Test creating command from event."""
        event = Event(
            domain="order",
            event_type="created",
            payload={"order_id": "789"},
        )

        command = Command(
            command="process_payment",
            payload=event.payload,
            correlation_id=event.message_id,
        )

        assert command.payload == event.payload
        assert command.correlation_id == event.message_id
