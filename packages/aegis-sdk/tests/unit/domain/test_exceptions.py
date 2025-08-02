"""Tests for domain exceptions."""

import pytest

from aegis_sdk.domain.exceptions import (
    AegisError,
    CommandError,
    ConnectionError,
    EventError,
    MessageBusError,
    RPCError,
    SerializationError,
    ServiceError,
    TimeoutError,
    ValidationError,
)


class TestAegisError:
    """Test cases for AegisError base exception."""

    def test_aegis_error_basic(self):
        """Test basic AegisError creation."""
        error = AegisError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}

    def test_aegis_error_with_details(self):
        """Test AegisError with details."""
        details = {"code": "ERR001", "timestamp": "2025-01-01T00:00:00Z"}
        error = AegisError("Error occurred", details)
        assert error.message == "Error occurred"
        assert error.details == details
        assert error.details["code"] == "ERR001"

    def test_aegis_error_inheritance(self):
        """Test that AegisError inherits from Exception."""
        error = AegisError("Test error")
        assert isinstance(error, Exception)


class TestServiceError:
    """Test cases for ServiceError."""

    def test_service_error_basic(self):
        """Test ServiceError creation."""
        error = ServiceError("Service failed")
        assert str(error) == "Service failed"
        assert isinstance(error, AegisError)

    def test_service_error_with_details(self):
        """Test ServiceError with details."""
        error = ServiceError("Service unavailable", {"service": "order-service"})
        assert error.message == "Service unavailable"
        assert error.details["service"] == "order-service"


class TestMessageBusError:
    """Test cases for MessageBusError and its subclasses."""

    def test_message_bus_error(self):
        """Test MessageBusError creation."""
        error = MessageBusError("Bus communication failed")
        assert str(error) == "Bus communication failed"
        assert isinstance(error, AegisError)

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Failed to connect to NATS")
        assert str(error) == "Failed to connect to NATS"
        assert isinstance(error, MessageBusError)
        assert isinstance(error, AegisError)

    def test_timeout_error(self):
        """Test TimeoutError."""
        error = TimeoutError("Operation timed out after 5s")
        assert str(error) == "Operation timed out after 5s"
        assert isinstance(error, MessageBusError)

    def test_serialization_error(self):
        """Test SerializationError."""
        error = SerializationError("Failed to serialize message")
        assert str(error) == "Failed to serialize message"
        assert isinstance(error, MessageBusError)


class TestValidationError:
    """Test cases for ValidationError."""

    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError("Invalid input data")
        assert str(error) == "Invalid input data"
        assert isinstance(error, AegisError)

    def test_validation_error_with_field_details(self):
        """Test ValidationError with field information."""
        details = {"field": "email", "value": "invalid", "reason": "not an email"}
        error = ValidationError("Validation failed", details)
        assert error.details["field"] == "email"
        assert error.details["reason"] == "not an email"


class TestRPCError:
    """Test cases for RPCError."""

    def test_rpc_error_basic(self):
        """Test basic RPCError creation."""
        error = RPCError("RPC call failed")
        assert str(error) == "RPC call failed"
        assert error.service is None
        assert error.method is None
        assert error.details == {}

    def test_rpc_error_with_service_method(self):
        """Test RPCError with service and method."""
        error = RPCError("Method not found", service="user-service", method="get_user")
        assert error.message == "Method not found"
        assert error.service == "user-service"
        assert error.method == "get_user"
        assert error.details["service"] == "user-service"
        assert error.details["method"] == "get_user"

    def test_rpc_error_partial_info(self):
        """Test RPCError with only service or method."""
        # Only service
        error1 = RPCError("Service unavailable", service="order-service")
        assert error1.service == "order-service"
        assert error1.method is None
        assert "service" in error1.details
        assert "method" not in error1.details

        # Only method
        error2 = RPCError("Invalid parameters", method="create_order")
        assert error2.service is None
        assert error2.method == "create_order"
        assert "service" not in error2.details
        assert "method" in error2.details


class TestCommandError:
    """Test cases for CommandError."""

    def test_command_error_basic(self):
        """Test basic CommandError creation."""
        error = CommandError("Command processing failed")
        assert str(error) == "Command processing failed"
        assert error.command_id is None
        assert error.details == {}

    def test_command_error_with_id(self):
        """Test CommandError with command ID."""
        cmd_id = "123e4567-e89b-12d3-a456-426614174000"
        error = CommandError("Command timeout", command_id=cmd_id)
        assert error.message == "Command timeout"
        assert error.command_id == cmd_id
        assert error.details["command_id"] == cmd_id


class TestEventError:
    """Test cases for EventError."""

    def test_event_error_basic(self):
        """Test basic EventError creation."""
        error = EventError("Event processing failed")
        assert str(error) == "Event processing failed"
        assert error.event_type is None
        assert error.details == {}

    def test_event_error_with_type(self):
        """Test EventError with event type."""
        error = EventError("Handler not found", event_type="order.created")
        assert error.message == "Handler not found"
        assert error.event_type == "order.created"
        assert error.details["event_type"] == "order.created"


class TestExceptionHierarchy:
    """Test exception hierarchy and relationships."""

    def test_exception_hierarchy(self):
        """Test that all exceptions inherit correctly."""
        # All custom exceptions should inherit from AegisError
        assert issubclass(ServiceError, AegisError)
        assert issubclass(MessageBusError, AegisError)
        assert issubclass(ValidationError, AegisError)
        assert issubclass(RPCError, AegisError)
        assert issubclass(CommandError, AegisError)
        assert issubclass(EventError, AegisError)

        # MessageBus sub-exceptions
        assert issubclass(ConnectionError, MessageBusError)
        assert issubclass(TimeoutError, MessageBusError)
        assert issubclass(SerializationError, MessageBusError)

    def test_exception_catching(self):
        """Test exception catching with hierarchy."""
        # Can catch specific exceptions
        with pytest.raises(ConnectionError):
            raise ConnectionError("Connection failed")

        # Can catch parent exception
        with pytest.raises(MessageBusError):
            raise ConnectionError("Connection failed")

        # Can catch base exception
        with pytest.raises(AegisError):
            raise ConnectionError("Connection failed")

    def test_exception_type_checking(self):
        """Test isinstance checks across hierarchy."""
        conn_error = ConnectionError("Failed")
        assert isinstance(conn_error, ConnectionError)
        assert isinstance(conn_error, MessageBusError)
        assert isinstance(conn_error, AegisError)
        assert isinstance(conn_error, Exception)

        rpc_error = RPCError("Failed", service="test")
        assert isinstance(rpc_error, RPCError)
        assert isinstance(rpc_error, AegisError)
        assert not isinstance(rpc_error, MessageBusError)
