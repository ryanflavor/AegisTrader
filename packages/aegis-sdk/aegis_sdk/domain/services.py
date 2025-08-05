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


class StickyActiveElectionService:
    """Domain service for sticky active election logic.

    This service encapsulates the business logic for leader election,
    failover detection, and coordination between instances.
    """

    def __init__(
        self,
        leader_ttl_seconds: int = 5,
        heartbeat_interval_seconds: int = 2,
        election_timeout_seconds: int = 10,
        failover_delay_seconds: float = 0.5,
    ):
        """Initialize election service with timing configuration.

        Args:
            leader_ttl_seconds: TTL for leader key in KV Store
            heartbeat_interval_seconds: Interval between leader heartbeats
            election_timeout_seconds: Maximum time to wait for election completion
            failover_delay_seconds: Delay before attempting to take over leadership
        """
        self.leader_ttl = leader_ttl_seconds
        self.heartbeat_interval = heartbeat_interval_seconds
        self.election_timeout = election_timeout_seconds
        self.failover_delay = failover_delay_seconds

        # Validate timing configuration
        if heartbeat_interval_seconds >= leader_ttl_seconds:
            raise ValueError("Heartbeat interval must be less than leader TTL")
        if election_timeout_seconds <= leader_ttl_seconds:
            raise ValueError("Election timeout should be greater than leader TTL")

    def create_leader_key(self, service_name: str, group_id: str = "default") -> str:
        """Create the NATS KV Store key for leader election.

        Args:
            service_name: Name of the service
            group_id: Service group identifier

        Returns:
            The leader key for KV Store
        """
        return f"sticky-active.{service_name}.{group_id}.leader"

    def create_leader_value(
        self, instance_id: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create the value to store for the leader.

        Args:
            instance_id: Instance identifier
            metadata: Optional metadata about the leader

        Returns:
            Dictionary to store as leader value
        """
        import time

        return {
            "instance_id": instance_id,
            "elected_at": time.time(),
            "last_heartbeat": time.time(),
            "metadata": metadata or {},
        }

    def parse_leader_value(self, value: bytes | str) -> tuple[str, float, dict[str, Any]]:
        """Parse the leader value from KV Store.

        Args:
            value: Raw value from KV Store

        Returns:
            Tuple of (instance_id, last_heartbeat_timestamp, metadata)

        Raises:
            ValueError: If value format is invalid
        """
        import json

        try:
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            data = json.loads(value)
            return (
                data["instance_id"],
                float(data.get("last_heartbeat", 0)),
                data.get("metadata", {}),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid leader value format: {e}") from e

    def is_leader_expired(self, last_heartbeat: float, current_time: float) -> bool:
        """Check if the current leader has expired.

        Args:
            last_heartbeat: Timestamp of last leader heartbeat
            current_time: Current timestamp

        Returns:
            True if leader is expired, False otherwise
        """
        elapsed = current_time - last_heartbeat
        return elapsed > self.leader_ttl

    def should_attempt_election(
        self,
        is_leader_expired: bool,
        last_election_attempt: float | None,
        current_time: float,
    ) -> bool:
        """Determine if an instance should attempt election.

        Args:
            is_leader_expired: Whether the current leader is expired
            last_election_attempt: Timestamp of last election attempt
            current_time: Current timestamp

        Returns:
            True if election should be attempted, False otherwise
        """
        if not is_leader_expired:
            return False

        if last_election_attempt is None:
            return True

        # Check if enough time has passed since last attempt
        elapsed = current_time - last_election_attempt
        return elapsed >= self.failover_delay

    def calculate_election_backoff(self, attempt_count: int) -> float:
        """Calculate exponential backoff for election retries.

        Args:
            attempt_count: Number of previous attempts

        Returns:
            Backoff duration in seconds
        """
        import random

        # Exponential backoff with jitter
        base_delay = min(self.failover_delay * (2**attempt_count), 30.0)
        jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
        return base_delay + jitter

    def validate_election_transition(
        self,
        current_status: str,
        target_status: str,
    ) -> None:
        """Validate if a status transition is allowed.

        Args:
            current_status: Current election status
            target_status: Target election status

        Raises:
            ValueError: If transition is not allowed
        """
        allowed_transitions = {
            "STANDBY": ["ELECTING", "ACTIVE"],  # Can start election or become active directly
            "ELECTING": ["ACTIVE", "STANDBY"],  # Can win or lose election
            "ACTIVE": ["STANDBY"],  # Can only step down
        }

        if target_status not in allowed_transitions.get(current_status, []):
            raise ValueError(f"Invalid transition from {current_status} to {target_status}")
