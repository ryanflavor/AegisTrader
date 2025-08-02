"""Domain services containing business logic.

Following Domain-Driven Design principles, these services encapsulate
complex business logic that doesn't naturally belong to a single entity
or value object.
"""

from typing import Any, Protocol

from .models import Command, Event, RPCRequest
from .value_objects import EventType, MethodName, ServiceName


class MessageRoutingService:
    """Domain service for message routing logic.

    This service encapsulates the business logic for determining
    how messages should be routed based on their content.
    """

    @staticmethod
    def extract_service_and_method(
        request: RPCRequest,
    ) -> tuple[ServiceName, MethodName]:
        """Extract service name and method from RPC request.

        Args:
            request: The RPC request to analyze

        Returns:
            Tuple of (service_name, method_name)
        """
        if request.target:
            parts = request.target.split(".")
            if len(parts) >= 2:
                service_name = ServiceName(value=parts[0])
                method_name = MethodName(value=request.method)
            else:
                service_name = ServiceName(value=request.target)
                method_name = MethodName(value=request.method)
        else:
            # Default service name when no target specified
            service_name = ServiceName(value="unknown")
            method_name = MethodName(value=request.method)

        return service_name, method_name

    @staticmethod
    def extract_command_target(command: Command) -> ServiceName:
        """Extract target service from command.

        Args:
            command: The command to analyze

        Returns:
            The target service name
        """
        target = command.target or "unknown"
        return ServiceName(value=target)

    @staticmethod
    def create_event_subject(domain: str, event_type: str) -> str:
        """Create a subject for event routing.

        Args:
            domain: The event domain
            event_type: The event type

        Returns:
            The full event subject for routing
        """
        # Validate through value object
        full_type = EventType(value=f"{domain}.{event_type}")
        return f"events.{full_type.value}"


class MetricsNamingService:
    """Domain service for consistent metrics naming.

    This service ensures metrics names follow consistent patterns
    across the application.
    """

    @staticmethod
    def rpc_metric_name(service: ServiceName, method: MethodName, suffix: str) -> str:
        """Generate RPC metric name.

        Args:
            service: The service name
            method: The method name
            suffix: The metric suffix (e.g., 'success', 'error', 'timeout')

        Returns:
            The full metric name
        """
        return f"rpc.{service.value}.{method.value}.{suffix}"

    @staticmethod
    def rpc_client_metric_name(service: ServiceName, method: MethodName, suffix: str) -> str:
        """Generate RPC client metric name.

        Args:
            service: The service name
            method: The method name
            suffix: The metric suffix

        Returns:
            The full metric name
        """
        return f"rpc.client.{service.value}.{method.value}.{suffix}"

    @staticmethod
    def event_metric_name(event: Event, action: str) -> str:
        """Generate event metric name.

        Args:
            event: The event
            action: The action (e.g., 'published', 'processed')

        Returns:
            The full metric name
        """
        return f"events.{action}.{event.domain}.{event.event_type}"

    @staticmethod
    def command_metric_name(service: ServiceName, command: str, action: str) -> str:
        """Generate command metric name.

        Args:
            service: The service name
            command: The command name
            action: The action (e.g., 'processed', 'send')

        Returns:
            The full metric name
        """
        return f"commands.{action}.{service.value}.{command}"


class ServiceRegistryProtocol(Protocol):
    """Protocol for service registry operations.

    This protocol defines the contract for service registry
    implementations without coupling to specific infrastructure.
    """

    async def register(self, service: ServiceName, instance: str) -> None:
        """Register a service instance."""
        ...

    async def unregister(self, service: ServiceName, instance: str) -> None:
        """Unregister a service instance."""
        ...

    async def get_instances(self, service: ServiceName) -> list[str]:
        """Get all instances of a service."""
        ...


class HealthCheckService:
    """Domain service for health check logic.

    Encapsulates the business logic for determining service health
    based on various criteria.
    """

    def __init__(self, heartbeat_timeout_seconds: float = 30.0):
        """Initialize health check service.

        Args:
            heartbeat_timeout_seconds: Time before considering a service unhealthy
        """
        self.heartbeat_timeout = heartbeat_timeout_seconds

    def is_healthy(self, last_heartbeat_time: float, current_time: float) -> bool:
        """Determine if a service is healthy based on heartbeat.

        Args:
            last_heartbeat_time: Timestamp of last heartbeat
            current_time: Current timestamp

        Returns:
            True if healthy, False otherwise
        """
        time_since_heartbeat = current_time - last_heartbeat_time
        return time_since_heartbeat < self.heartbeat_timeout

    def calculate_health_score(self, metrics: dict[str, Any]) -> float:
        """Calculate a health score based on service metrics.

        Args:
            metrics: Service metrics dictionary

        Returns:
            Health score between 0.0 (unhealthy) and 1.0 (healthy)
        """
        score = 1.0

        # Check error rates
        if "counters" in metrics:
            counters = metrics["counters"]

            # RPC errors
            rpc_success = sum(v for k, v in counters.items() if k.endswith(".success"))
            rpc_errors = sum(v for k, v in counters.items() if k.endswith(".error"))
            if rpc_success + rpc_errors > 0:
                error_rate = rpc_errors / (rpc_success + rpc_errors)
                score *= 1.0 - error_rate

            # Event errors
            events_processed = counters.get("events.processed", 0)
            events_errors = counters.get("events.errors", 0)
            if events_processed + events_errors > 0:
                error_rate = events_errors / (events_processed + events_errors)
                score *= 1.0 - error_rate

        # Check latency (if available)
        if "summaries" in metrics:
            for name, summary in metrics["summaries"].items():
                if name.startswith("rpc.") and "p99" in summary:
                    # Penalize high latency (>1000ms p99)
                    if summary["p99"] > 1000:
                        score *= 0.8
                    elif summary["p99"] > 500:
                        score *= 0.9

        return max(0.0, min(1.0, score))
