"""Comprehensive tests for domain models."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.models import (
    Command,
    Event,
    KVEntry,
    KVOptions,
    KVWatchEvent,
    Message,
    RPCRequest,
    RPCResponse,
    ServiceInfo,
    ServiceInstance,
)


class TestMessage:
    """Test cases for Message model."""

    def test_message_timestamp_validation_invalid(self):
        """Test timestamp validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            Message(message_id="123", trace_id="456", timestamp="not-a-timestamp")
        assert "Invalid ISO timestamp format" in str(exc_info.value)


class TestMessageOriginal:
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

    def test_rpc_request_method_validation_empty_string(self):
        """Test method validation with empty string after stripping."""
        with pytest.raises(ValidationError) as exc_info:
            RPCRequest(method="   ")
        assert "Method name cannot be empty" in str(exc_info.value)

    def test_rpc_request_method_validation_non_string(self):
        """Test method validation with non-string input."""
        # The strict mode will catch non-string values before the validator
        with pytest.raises(ValidationError) as exc_info:
            RPCRequest(method=123)
        assert "type=string_type" in str(exc_info.value)


class TestRPCRequestOriginal:
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

    def test_rpc_response_error_consistency_validation(self):
        """Test error consistency validation."""
        # Success=True with error should fail
        with pytest.raises(ValidationError) as exc_info:
            RPCResponse(success=True, error="Some error")
        assert "Error must be None when success is True" in str(exc_info.value)

        # Success=False without error should fail
        with pytest.raises(ValidationError) as exc_info:
            RPCResponse(success=False, error=None)
        assert "Error message required when success is False" in str(exc_info.value)


class TestRPCResponseOriginal:
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

    def test_event_version_validation_invalid(self):
        """Test version validation with invalid format."""
        invalid_versions = [
            "1",  # Missing minor version
            "v1.0.0",  # Has 'v' prefix
            "1.0.0.1",  # Too many parts
            "1.a.0",  # Non-numeric
            "1.0-beta",  # Has suffix
        ]
        for invalid_version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                Event(domain="test", event_type="test.event", version=invalid_version)
            assert "Invalid version format" in str(exc_info.value)


class TestEventOriginal:
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

    def test_command_validation_empty_string(self):
        """Test command validation with empty string after stripping."""
        with pytest.raises(ValidationError) as exc_info:
            Command(command="   ")
        assert "Command name cannot be empty" in str(exc_info.value)

    def test_command_validation_non_string(self):
        """Test command validation with non-string input."""
        # The strict mode will catch non-string values before the validator
        with pytest.raises(ValidationError) as exc_info:
            Command(command=123)
        assert "type=string_type" in str(exc_info.value)


class TestCommandOriginal:
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

    def test_service_info_version_validation_invalid(self):
        """Test version validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceInfo(
                service_name="test",
                instance_id="123",
                version="1.0",  # Missing patch version
            )
        assert "Invalid version format" in str(exc_info.value)

    def test_service_info_timestamp_validation_invalid(self):
        """Test timestamp validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceInfo(service_name="test", instance_id="123", registered_at="not-a-timestamp")
        assert "Invalid ISO timestamp format" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ServiceInfo(service_name="test", instance_id="123", last_heartbeat="invalid-date")
        assert "Invalid ISO timestamp format" in str(exc_info.value)


class TestServiceInfoOriginal:
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


class TestKVEntry:
    """Test cases for KVEntry model."""

    def test_kv_entry_timestamp_validation_invalid(self):
        """Test timestamp validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at="not-a-timestamp",
                updated_at="2025-01-01T00:00:00Z",
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_kv_entry_timestamp_order_validation(self):
        """Test validation that updated_at cannot be before created_at."""
        with pytest.raises(ValidationError) as exc_info:
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at="2025-01-01T12:00:00Z",
                updated_at="2025-01-01T11:00:00Z",  # Before created_at
            )
        assert "updated_at cannot be before created_at" in str(exc_info.value)


class TestKVEntryOriginal:
    """Test cases for KVEntry model."""

    def test_kventry_basic(self):
        """Test basic KVEntry creation."""
        now = datetime.now(UTC).isoformat()
        entry = KVEntry(
            key="user:123",
            value={"name": "John", "age": 30},
            revision=1,
            created_at=now,
            updated_at=now,
        )

        assert entry.key == "user:123"
        assert entry.value == {"name": "John", "age": 30}
        assert entry.revision == 1
        assert entry.created_at == now
        assert entry.updated_at == now
        assert entry.ttl is None

    def test_kventry_with_ttl(self):
        """Test KVEntry with TTL."""
        now = datetime.now(UTC).isoformat()
        entry = KVEntry(
            key="temp:456",
            value="temporary data",
            revision=2,
            created_at=now,
            updated_at=now,
            ttl=3600,  # 1 hour
        )

        assert entry.ttl == 3600

    def test_kventry_invalid_timestamps(self):
        """Test KVEntry with invalid timestamps - covers lines 203-204."""
        # Invalid created_at timestamp
        with pytest.raises(ValidationError) as exc_info:
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at="not-a-timestamp",
                updated_at=datetime.now(UTC).isoformat(),
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

        # Invalid updated_at timestamp
        with pytest.raises(ValidationError) as exc_info:
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at=datetime.now(UTC).isoformat(),
                updated_at="2025-13-45T25:99:99",  # Invalid date/time
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_kventry_timestamp_order_validation(self):
        """Test KVEntry timestamp order validation - covers line 213."""
        created = datetime.now(UTC)
        updated = created.replace(microsecond=created.microsecond - 1000)  # Earlier than created

        with pytest.raises(ValidationError) as exc_info:
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at=created.isoformat(),
                updated_at=updated.isoformat(),
            )
        assert "updated_at cannot be before created_at" in str(exc_info.value)

    def test_kventry_valid_timestamp_order(self):
        """Test KVEntry with valid timestamp order."""
        created = datetime.now(UTC)
        updated = created.replace(microsecond=created.microsecond + 1000)  # Later than created

        entry = KVEntry(
            key="test",
            value="data",
            revision=1,
            created_at=created.isoformat(),
            updated_at=updated.isoformat(),
        )

        assert entry.created_at == created.isoformat()
        assert entry.updated_at == updated.isoformat()

    def test_kventry_same_timestamps(self):
        """Test KVEntry with same created and updated timestamps."""
        now = datetime.now(UTC).isoformat()

        entry = KVEntry(
            key="test",
            value="data",
            revision=1,
            created_at=now,
            updated_at=now,
        )

        assert entry.created_at == entry.updated_at

    def test_kventry_ttl_validation(self):
        """Test KVEntry TTL validation."""
        now = datetime.now(UTC).isoformat()

        # Zero TTL should fail
        with pytest.raises(ValidationError):
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at=now,
                updated_at=now,
                ttl=0,
            )

        # Negative TTL should fail
        with pytest.raises(ValidationError):
            KVEntry(
                key="test",
                value="data",
                revision=1,
                created_at=now,
                updated_at=now,
                ttl=-10,
            )


class TestKVOptions:
    """Test cases for KVOptions model."""

    def test_kv_options_exclusivity_validation(self):
        """Test that create_only and update_only are mutually exclusive."""
        with pytest.raises(ValidationError) as exc_info:
            KVOptions(create_only=True, update_only=True)
        assert "create_only and update_only are mutually exclusive" in str(exc_info.value)


class TestKVOptionsOriginal:
    """Test cases for KVOptions model."""

    def test_kvoptions_defaults(self):
        """Test KVOptions with default values."""
        options = KVOptions()

        assert options.ttl is None
        assert options.revision is None
        assert options.create_only is False
        assert options.update_only is False

    def test_kvoptions_with_values(self):
        """Test KVOptions with custom values."""
        options = KVOptions(
            ttl=3600,
            revision=5,
            create_only=True,
        )

        assert options.ttl == 3600
        assert options.revision == 5
        assert options.create_only is True
        assert options.update_only is False

    def test_kvoptions_mutually_exclusive_validation(self):
        """Test KVOptions mutual exclusivity validation - covers line 242."""
        with pytest.raises(ValidationError) as exc_info:
            KVOptions(
                create_only=True,
                update_only=True,
            )
        assert "create_only and update_only are mutually exclusive" in str(exc_info.value)

    def test_kvoptions_create_only(self):
        """Test KVOptions with create_only."""
        options = KVOptions(create_only=True)
        assert options.create_only is True
        assert options.update_only is False

    def test_kvoptions_update_only(self):
        """Test KVOptions with update_only."""
        options = KVOptions(update_only=True)
        assert options.create_only is False
        assert options.update_only is True


class TestKVWatchEvent:
    """Test cases for KVWatchEvent model."""

    def test_kv_watch_event_timestamp_validation_invalid(self):
        """Test timestamp validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            KVWatchEvent(operation="PUT", timestamp="not-a-timestamp")
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_kv_watch_event_entry_consistency_validation(self):
        """Test that PUT operation requires an entry."""
        with pytest.raises(ValidationError) as exc_info:
            KVWatchEvent(
                operation="PUT",
                entry=None,  # PUT requires an entry
            )
        assert "PUT operation requires an entry" in str(exc_info.value)


class TestKVWatchEventOriginal:
    """Test cases for KVWatchEvent model."""

    def test_kvwatchevent_put_operation(self):
        """Test KVWatchEvent with PUT operation."""
        now = datetime.now(UTC).isoformat()
        entry = KVEntry(
            key="test",
            value="data",
            revision=1,
            created_at=now,
            updated_at=now,
        )

        event = KVWatchEvent(
            operation="PUT",
            entry=entry,
        )

        assert event.operation == "PUT"
        assert event.entry == entry
        assert event.timestamp  # Should have auto-generated timestamp

    def test_kvwatchevent_delete_operation(self):
        """Test KVWatchEvent with DELETE operation."""
        event = KVWatchEvent(
            operation="DELETE",
            entry=None,
        )

        assert event.operation == "DELETE"
        assert event.entry is None

    def test_kvwatchevent_invalid_timestamp(self):
        """Test KVWatchEvent with invalid timestamp - covers lines 267-271."""
        with pytest.raises(ValidationError) as exc_info:
            KVWatchEvent(
                operation="PUT",
                entry=None,
                timestamp="invalid-timestamp-format",
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_kvwatchevent_put_requires_entry(self):
        """Test KVWatchEvent PUT operation requires entry - covers line 277."""
        with pytest.raises(ValidationError) as exc_info:
            KVWatchEvent(
                operation="PUT",
                entry=None,
            )
        assert "PUT operation requires an entry" in str(exc_info.value)

    def test_kvwatchevent_delete_without_entry(self):
        """Test KVWatchEvent DELETE operation without entry is valid."""
        event = KVWatchEvent(
            operation="DELETE",
            entry=None,
        )
        assert event.operation == "DELETE"
        assert event.entry is None

    def test_kvwatchevent_purge_operation(self):
        """Test KVWatchEvent with PURGE operation."""
        event = KVWatchEvent(
            operation="PURGE",
            entry=None,
        )
        assert event.operation == "PURGE"
        assert event.entry is None

    def test_kvwatchevent_invalid_operation(self):
        """Test KVWatchEvent with invalid operation."""
        with pytest.raises(ValidationError):
            KVWatchEvent(
                operation="INVALID",
                entry=None,
            )

    def test_kvwatchevent_custom_timestamp(self):
        """Test KVWatchEvent with custom valid timestamp."""
        custom_time = "2025-01-01T12:00:00+00:00"
        event = KVWatchEvent(
            operation="DELETE",
            entry=None,
            timestamp=custom_time,
        )
        assert event.timestamp == custom_time


class TestServiceInstance:
    """Test cases for ServiceInstance model."""

    def test_service_instance_basic(self):
        """Test basic ServiceInstance creation."""
        instance = ServiceInstance(
            service_name="trading-service",
            instance_id="trading-service-a1b2c3d4",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat="2025-01-01T00:00:00+08:00",
        )

        assert instance.service_name == "trading-service"
        assert instance.instance_id == "trading-service-a1b2c3d4"
        assert instance.version == "1.0.0"
        assert instance.status == "ACTIVE"
        assert instance.sticky_active_group is None
        assert isinstance(instance.last_heartbeat, datetime)
        assert instance.metadata == {}  # Default is empty dict, not None

    def test_service_instance_with_all_fields(self):
        """Test ServiceInstance with all fields."""
        metadata = {"region": "us-east-1", "zone": "zone-a"}
        instance = ServiceInstance(
            service_name="order-service",
            instance_id="order-service-12345678",
            version="2.3.1",
            status="STANDBY",
            sticky_active_group="group-1",
            last_heartbeat="2025-01-02T10:30:00+08:00",
            metadata=metadata,
        )

        assert instance.service_name == "order-service"
        assert instance.instance_id == "order-service-12345678"
        assert instance.version == "2.3.1"
        assert instance.status == "STANDBY"
        assert instance.sticky_active_group == "group-1"
        assert isinstance(instance.last_heartbeat, datetime)
        assert instance.metadata == metadata

    def test_service_instance_status_validation(self):
        """Test status validation."""
        # Valid statuses
        for status in ["ACTIVE", "UNHEALTHY", "STANDBY"]:
            instance = ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version="1.0.0",
                status=status,
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
            assert instance.status == status

        # Invalid status
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version="1.0.0",
                status="RUNNING",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
        assert "String should match pattern" in str(exc_info.value)

    def test_service_instance_version_validation(self):
        """Test version format validation."""
        # Valid versions
        for version in ["1.0.0", "10.20.30", "0.0.1"]:
            instance = ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version=version,
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
            assert instance.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "1.a.0", ""]
        for invalid_version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                ServiceInstance(
                    service_name="test-service",
                    instance_id="test-id",
                    version=invalid_version,
                    status="ACTIVE",
                    last_heartbeat="2025-01-01T00:00:00+08:00",
                )
            assert "Invalid version format" in str(
                exc_info.value
            ) or "String should have at least 1 character" in str(exc_info.value)

    def test_service_instance_lastheartbeat_validation(self):
        """Test lastHeartbeat timestamp validation."""
        # Valid timestamps
        valid_timestamps = [
            "2025-01-01T00:00:00+08:00",
            "2025-01-01T12:30:45.123456+00:00",
            "2025-12-31T23:59:59Z",
        ]
        for timestamp in valid_timestamps:
            instance = ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=timestamp,
            )
            assert isinstance(instance.last_heartbeat, datetime)

        # Invalid timestamp
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="not-a-timestamp",
            )
        assert "Invalid ISO timestamp format" in str(exc_info.value)

    def test_service_instance_service_name_validation(self):
        """Test service name validation."""
        # Valid service names (based on SubjectPatterns)
        valid_names = ["trading-service", "order_service", "user-api", "payment_gateway"]
        for name in valid_names:
            instance = ServiceInstance(
                service_name=name,
                instance_id="test-id",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
            assert instance.service_name == name

        # Invalid service names
        invalid_names = ["", "service with spaces", "service.with.dots", "123-start-with-number"]
        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                ServiceInstance(
                    service_name=invalid_name,
                    instance_id="test-id",
                    version="1.0.0",
                    status="ACTIVE",
                    last_heartbeat="2025-01-01T00:00:00+08:00",
                )
            assert "Invalid service name format" in str(
                exc_info.value
            ) or "String should have at least 1 character" in str(exc_info.value)

    def test_service_instance_required_fields(self):
        """Test that all required fields must be provided."""
        # Missing service_name
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                instance_id="test-id",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
        assert "Field required" in str(exc_info.value)

        # Missing instance_id
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
        assert "Field required" in str(exc_info.value)

        # Missing version
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
            )
        assert "Field required" in str(exc_info.value)

        # Status has default, so no error
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-id",
            version="1.0.0",
            # last_heartbeat has default_factory, so no error
        )
        assert instance.status == "ACTIVE"
        assert isinstance(instance.last_heartbeat, datetime)

    def test_service_instance_strict_mode(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-id",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="2025-01-01T00:00:00+08:00",
                extra_field="not allowed",
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_service_instance_serialization(self):
        """Test ServiceInstance serialization."""
        metadata = {"region": "us-west-2", "custom": "data"}
        instance = ServiceInstance(
            service_name="api-gateway",
            instance_id="api-gateway-xyz789",
            version="3.2.1",
            status="ACTIVE",
            sticky_active_group="primary",
            last_heartbeat="2025-01-01T15:30:00+08:00",
            metadata=metadata,
        )

        # Test model_dump with snake_case (default)
        data = instance.model_dump()
        assert data["service_name"] == "api-gateway"
        assert data["instance_id"] == "api-gateway-xyz789"
        assert data["version"] == "3.2.1"
        assert data["status"] == "ACTIVE"
        assert data["sticky_active_group"] == "primary"
        assert isinstance(data["last_heartbeat"], str)  # Converted to ISO string
        assert data["metadata"] == metadata

        # Test model_dump with camelCase (by_alias=True)
        camel_data = instance.model_dump(by_alias=True)
        assert camel_data["serviceName"] == "api-gateway"
        assert camel_data["instanceId"] == "api-gateway-xyz789"
        assert camel_data["stickyActiveGroup"] == "primary"
        assert camel_data["lastHeartbeat"] is not None

        # Test model_dump_json (always uses camelCase)
        json_str = instance.model_dump_json()
        assert isinstance(json_str, str)
        assert "serviceName" in json_str
        assert "api-gateway" in json_str
        assert "3.2.1" in json_str

    def test_service_instance_deserialization(self):
        """Test ServiceInstance deserialization from dict."""
        # Test with snake_case
        data = {
            "service_name": "cache-service",
            "instance_id": "cache-service-abc123",
            "version": "1.5.0",
            "status": "UNHEALTHY",
            "sticky_active_group": None,
            "last_heartbeat": "2025-01-01T20:00:00+08:00",
            "metadata": {"memory": "8GB", "cpu": "4"},
        }

        instance = ServiceInstance(**data)
        assert instance.service_name == "cache-service"
        assert instance.instance_id == "cache-service-abc123"
        assert instance.version == "1.5.0"
        assert instance.status == "UNHEALTHY"
        assert instance.sticky_active_group is None
        assert isinstance(instance.last_heartbeat, datetime)
        assert instance.metadata == {"memory": "8GB", "cpu": "4"}

        # Test with camelCase (backward compatibility)
        camel_data = {
            "serviceName": "cache-service",
            "instanceId": "cache-service-abc123",
            "version": "1.5.0",
            "status": "UNHEALTHY",
            "stickyActiveGroup": None,
            "lastHeartbeat": "2025-01-01T20:00:00+08:00",
            "metadata": {"memory": "8GB", "cpu": "4"},
        }

        # Should work with populate_by_name=True
        instance2 = ServiceInstance(**camel_data)
        assert instance2.service_name == "cache-service"
        assert instance2.instance_id == "cache-service-abc123"

    def test_service_instance_domain_methods(self):
        """Test ServiceInstance domain methods."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
        )

        # Test is_healthy
        assert instance.is_healthy() is True
        instance.status = "STANDBY"
        assert instance.is_healthy() is True
        instance.status = "UNHEALTHY"
        assert instance.is_healthy() is False

        # Test is_active
        assert instance.is_active() is False
        instance.status = "ACTIVE"
        assert instance.is_active() is True

        # Test mark_unhealthy
        instance.mark_unhealthy()
        assert instance.status == "UNHEALTHY"

        # Test update_heartbeat
        old_heartbeat = instance.last_heartbeat
        import time

        time.sleep(0.01)  # Small delay to ensure timestamp changes
        instance.update_heartbeat()
        assert instance.last_heartbeat > old_heartbeat

        # Test seconds_since_heartbeat
        seconds = instance.seconds_since_heartbeat()
        assert seconds >= 0
        assert seconds < 1  # Should be very recent

        # Test is_stale
        assert instance.is_stale(60) is False  # Not stale with 60s threshold
        # Force stale by setting old heartbeat
        instance.last_heartbeat = datetime.now(UTC) - timedelta(seconds=120)
        assert instance.is_stale(60) is True  # Now stale with 60s threshold

    def test_service_instance_mark_unhealthy(self):
        """Test mark_unhealthy method in detail."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
        )

        # Initially active
        assert instance.status == "ACTIVE"
        assert instance.is_active() is True
        assert instance.is_healthy() is True

        # Mark unhealthy
        instance.mark_unhealthy()
        assert instance.status == "UNHEALTHY"
        assert instance.is_active() is False
        assert instance.is_healthy() is False

        # Mark unhealthy again (idempotent)
        instance.mark_unhealthy()
        assert instance.status == "UNHEALTHY"

    def test_service_instance_update_heartbeat_with_custom_timestamp(self):
        """Test update_heartbeat with custom timestamp."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
        )

        # Update with custom timestamp
        custom_time = datetime.now(UTC) + timedelta(minutes=5)
        instance.update_heartbeat(custom_time)
        assert instance.last_heartbeat == custom_time

        # Update with None (should use current time)
        # Set old heartbeat to past time to ensure new time is greater
        instance.last_heartbeat = datetime.now(UTC) - timedelta(seconds=10)
        old_heartbeat = instance.last_heartbeat

        instance.update_heartbeat(None)
        assert instance.last_heartbeat > old_heartbeat
        assert instance.last_heartbeat <= datetime.now(UTC)

    def test_service_instance_seconds_since_heartbeat_accuracy(self):
        """Test seconds_since_heartbeat calculation accuracy."""
        # Create instance with specific heartbeat time
        past_time = datetime.now(UTC) - timedelta(seconds=30.5)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=past_time.isoformat(),
        )

        # Check seconds calculation
        seconds = instance.seconds_since_heartbeat()
        # Should be approximately 30.5 seconds (with small tolerance for execution time)
        assert 30.0 <= seconds <= 31.0

        # Test with very recent heartbeat
        instance.update_heartbeat()
        seconds = instance.seconds_since_heartbeat()
        assert 0.0 <= seconds <= 0.1

    def test_service_instance_is_stale_various_thresholds(self):
        """Test is_stale with various threshold values."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
        )

        # Fresh instance - not stale for any reasonable threshold
        assert instance.is_stale(1) is False
        assert instance.is_stale(10) is False
        assert instance.is_stale(60) is False
        assert instance.is_stale(3600) is False

        # Set heartbeat to 45 seconds ago
        instance.last_heartbeat = datetime.now(UTC) - timedelta(seconds=45)

        # Test various thresholds
        assert instance.is_stale(30) is True  # Stale for 30s threshold
        assert instance.is_stale(40) is True  # Stale for 40s threshold
        assert instance.is_stale(50) is False  # Not stale for 50s threshold
        assert instance.is_stale(60) is False  # Not stale for 60s threshold

        # Test with exact threshold (edge case)
        instance.last_heartbeat = datetime.now(UTC) - timedelta(seconds=60)
        assert instance.is_stale(60) is True  # Greater than or equal to threshold, is stale
        assert instance.is_stale(61) is False  # Not stale for slightly higher threshold

    def test_service_instance_should_be_active_no_sticky_group(self):
        """Test should_be_active when no sticky group is configured."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_group=None,  # No sticky group
        )

        # Without sticky group, should_be_active depends only on health
        assert instance.should_be_active() is True  # ACTIVE status

        instance.status = "STANDBY"
        assert instance.should_be_active() is True  # STANDBY is healthy

        instance.status = "UNHEALTHY"
        assert instance.should_be_active() is False  # UNHEALTHY is not

    def test_service_instance_should_be_active_with_sticky_group(self):
        """Test should_be_active when sticky group is configured."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_group="group-primary",
        )

        # With sticky group, currently returns health status (TODO: implement full logic)
        assert instance.should_be_active() is True  # ACTIVE status

        instance.status = "STANDBY"
        assert instance.should_be_active() is True  # STANDBY is healthy

        instance.status = "UNHEALTHY"
        assert instance.should_be_active() is False  # UNHEALTHY is not

        # Test with empty string sticky group
        instance.sticky_active_group = ""
        instance.status = "ACTIVE"
        assert instance.should_be_active() is True  # Empty string is falsy

    def test_service_instance_heartbeat_timezone_handling(self):
        """Test heartbeat handles different timezone scenarios correctly."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
        )

        # Update with current UTC time
        utc_time = datetime.now(UTC)
        instance.update_heartbeat(utc_time)
        assert instance.last_heartbeat.tzinfo is not None
        assert instance.last_heartbeat.tzinfo == UTC

        # Verify seconds calculation works with UTC
        seconds = instance.seconds_since_heartbeat()
        assert seconds >= 0
        assert seconds < 1  # Should be very recent

    def test_service_instance_parse_heartbeat_edge_cases(self):
        """Test parse_heartbeat field validator edge cases."""
        # Test with datetime object that has non-UTC timezone
        eastern_tz = datetime.now().astimezone().tzinfo  # Get local timezone
        eastern_time = datetime.now(eastern_tz)

        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=eastern_time,
        )

        # Should be converted to UTC
        assert instance.last_heartbeat.tzinfo == UTC

        # Test with invalid type (should raise TypeError from validator)
        with pytest.raises(TypeError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-123",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=12345,  # Invalid type
            )
        assert "Expected datetime or str, got int" in str(exc_info.value)

    def test_service_instance_parse_heartbeat_timezone_naive(self):
        """Test parse_heartbeat with timezone-naive datetime."""
        # Test with timezone-naive datetime
        naive_time = datetime(2025, 1, 1, 12, 0, 0)  # No timezone

        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=naive_time,
        )

        # Should be treated as UTC
        assert instance.last_heartbeat.tzinfo == UTC
        assert instance.last_heartbeat.year == 2025
        assert instance.last_heartbeat.month == 1
        assert instance.last_heartbeat.day == 1
        assert instance.last_heartbeat.hour == 12

    def test_service_instance_parse_heartbeat_string_timezone_naive(self):
        """Test parse_heartbeat with timezone-naive string."""
        # Test with timezone-naive ISO string (no Z or timezone)
        naive_string = "2025-01-01T12:00:00"

        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=naive_string,
        )

        # Should be treated as UTC
        assert instance.last_heartbeat.tzinfo == UTC
        assert instance.last_heartbeat.isoformat() == "2025-01-01T12:00:00+00:00"
