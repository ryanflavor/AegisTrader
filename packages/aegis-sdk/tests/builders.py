"""Test builders for creating test data following the Builder pattern.

These builders provide a fluent interface for creating test objects,
making tests more readable and maintainable.
"""

from typing import Any

from aegis_sdk.domain.models import Command, Event, RPCRequest, RPCResponse, ServiceInfo
from aegis_sdk.domain.value_objects import EventType, InstanceId, MethodName, Priority, ServiceName


class RPCRequestBuilder:
    """Builder for creating RPCRequest objects in tests."""

    def __init__(self):
        """Initialize with default values."""
        self._method = "test_method"
        self._params: dict[str, Any] = {}
        self._timeout = 5.0
        self._source = "test_service"
        self._target = "target_service"
        self._trace_id = None
        self._correlation_id = None

    def with_method(self, method: str) -> "RPCRequestBuilder":
        """Set the method name."""
        self._method = method
        return self

    def with_params(self, **params: Any) -> "RPCRequestBuilder":
        """Set the parameters."""
        self._params = params
        return self

    def with_timeout(self, timeout: float) -> "RPCRequestBuilder":
        """Set the timeout."""
        self._timeout = timeout
        return self

    def with_source(self, source: str) -> "RPCRequestBuilder":
        """Set the source service."""
        self._source = source
        return self

    def with_target(self, target: str) -> "RPCRequestBuilder":
        """Set the target service."""
        self._target = target
        return self

    def with_trace_id(self, trace_id: str) -> "RPCRequestBuilder":
        """Set the trace ID."""
        self._trace_id = trace_id
        return self

    def with_correlation_id(self, correlation_id: str) -> "RPCRequestBuilder":
        """Set the correlation ID."""
        self._correlation_id = correlation_id
        return self

    def build(self) -> RPCRequest:
        """Build the RPCRequest object."""
        request = RPCRequest(
            method=self._method,
            params=self._params,
            timeout=self._timeout,
            source=self._source,
            target=self._target,
        )

        if self._trace_id:
            request.trace_id = self._trace_id
        if self._correlation_id:
            request.correlation_id = self._correlation_id

        return request


class RPCResponseBuilder:
    """Builder for creating RPCResponse objects in tests."""

    def __init__(self):
        """Initialize with default success response."""
        self._success = True
        self._result: Any = {"status": "ok"}
        self._error: str | None = None
        self._correlation_id = None

    def successful(self) -> "RPCResponseBuilder":
        """Create a successful response."""
        self._success = True
        self._error = None
        return self

    def failed(self, error: str = "Test error") -> "RPCResponseBuilder":
        """Create a failed response."""
        self._success = False
        self._error = error
        self._result = None
        return self

    def with_result(self, result: Any) -> "RPCResponseBuilder":
        """Set the result data."""
        self._result = result
        return self

    def with_correlation_id(self, correlation_id: str) -> "RPCResponseBuilder":
        """Set the correlation ID."""
        self._correlation_id = correlation_id
        return self

    def build(self) -> RPCResponse:
        """Build the RPCResponse object."""
        response = RPCResponse(
            success=self._success,
            result=self._result,
            error=self._error,
        )

        if self._correlation_id:
            response.correlation_id = self._correlation_id

        return response


class EventBuilder:
    """Builder for creating Event objects in tests."""

    def __init__(self):
        """Initialize with default values."""
        self._domain = "test"
        self._event_type = "created"
        self._payload: dict[str, Any] = {}
        self._version = "1.0"
        self._source = "test_service"

    def with_domain(self, domain: str) -> "EventBuilder":
        """Set the event domain."""
        self._domain = domain
        return self

    def with_type(self, event_type: str) -> "EventBuilder":
        """Set the event type."""
        self._event_type = event_type
        return self

    def with_payload(self, **payload: Any) -> "EventBuilder":
        """Set the event payload."""
        self._payload = payload
        return self

    def with_version(self, version: str) -> "EventBuilder":
        """Set the event version."""
        self._version = version
        return self

    def with_source(self, source: str) -> "EventBuilder":
        """Set the source service."""
        self._source = source
        return self

    def build(self) -> Event:
        """Build the Event object."""
        return Event(
            domain=self._domain,
            event_type=self._event_type,
            payload=self._payload,
            version=self._version,
            source=self._source,
        )


class CommandBuilder:
    """Builder for creating Command objects in tests."""

    def __init__(self):
        """Initialize with default values."""
        self._command = "test_command"
        self._payload: dict[str, Any] = {}
        self._priority = "normal"
        self._max_retries = 3
        self._timeout = 300.0
        self._target = "test_service"

    def with_command(self, command: str) -> "CommandBuilder":
        """Set the command name."""
        self._command = command
        return self

    def with_payload(self, **payload: Any) -> "CommandBuilder":
        """Set the command payload."""
        self._payload = payload
        return self

    def with_priority(self, priority: str) -> "CommandBuilder":
        """Set the command priority."""
        self._priority = priority
        return self

    def high_priority(self) -> "CommandBuilder":
        """Set high priority."""
        self._priority = Priority.HIGH
        return self

    def critical_priority(self) -> "CommandBuilder":
        """Set critical priority."""
        self._priority = Priority.CRITICAL
        return self

    def with_retries(self, max_retries: int) -> "CommandBuilder":
        """Set max retries."""
        self._max_retries = max_retries
        return self

    def with_timeout(self, timeout: float) -> "CommandBuilder":
        """Set the timeout."""
        self._timeout = timeout
        return self

    def with_target(self, target: str) -> "CommandBuilder":
        """Set the target service."""
        self._target = target
        return self

    def build(self) -> Command:
        """Build the Command object."""
        return Command(
            command=self._command,
            payload=self._payload,
            priority=self._priority,
            max_retries=self._max_retries,
            timeout=self._timeout,
            target=self._target,
        )


class ServiceInfoBuilder:
    """Builder for creating ServiceInfo objects in tests."""

    def __init__(self):
        """Initialize with default values."""
        self._service_name = "test_service"
        self._instance_id = "test-instance-123"
        self._version = "1.0.0"
        self._status = "ACTIVE"
        self._metadata: dict[str, Any] = {}

    def with_name(self, name: str) -> "ServiceInfoBuilder":
        """Set the service name."""
        self._service_name = name
        return self

    def with_instance_id(self, instance_id: str) -> "ServiceInfoBuilder":
        """Set the instance ID."""
        self._instance_id = instance_id
        return self

    def with_version(self, version: str) -> "ServiceInfoBuilder":
        """Set the version."""
        self._version = version
        return self

    def active(self) -> "ServiceInfoBuilder":
        """Set status to ACTIVE."""
        self._status = "ACTIVE"
        return self

    def unhealthy(self) -> "ServiceInfoBuilder":
        """Set status to UNHEALTHY."""
        self._status = "UNHEALTHY"
        return self

    def shutdown(self) -> "ServiceInfoBuilder":
        """Set status to SHUTDOWN."""
        self._status = "SHUTDOWN"
        return self

    def with_metadata(self, **metadata: Any) -> "ServiceInfoBuilder":
        """Set service metadata."""
        self._metadata = metadata
        return self

    def build(self) -> ServiceInfo:
        """Build the ServiceInfo object."""
        return ServiceInfo(
            service_name=self._service_name,
            instance_id=self._instance_id,
            version=self._version,
            status=self._status,
            metadata=self._metadata,
        )


class ValueObjectBuilder:
    """Builder for creating value objects in tests."""

    @staticmethod
    def service_name(value: str = "test_service") -> ServiceName:
        """Create a ServiceName value object."""
        return ServiceName(value=value)

    @staticmethod
    def instance_id(value: str = "test-instance-123") -> InstanceId:
        """Create an InstanceId value object."""
        return InstanceId(value=value)

    @staticmethod
    def event_type(value: str = "test.created") -> EventType:
        """Create an EventType value object."""
        return EventType(value=value)

    @staticmethod
    def method_name(value: str = "test_method") -> MethodName:
        """Create a MethodName value object."""
        return MethodName(value=value)

    @staticmethod
    def priority(value: str = "normal") -> Priority:
        """Create a Priority value object."""
        return Priority(value=value)
