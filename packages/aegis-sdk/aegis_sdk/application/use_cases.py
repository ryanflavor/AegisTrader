"""Application use cases following hexagonal architecture principles.

This module contains application services that orchestrate use cases
by coordinating between domain services, aggregates, and infrastructure ports.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from ..domain.aggregates import ServiceAggregate
from ..domain.models import Command, Event, RPCRequest
from ..domain.services import HealthCheckService, MessageRoutingService, MetricsNamingService
from ..domain.value_objects import InstanceId, ServiceName
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort


class UseCase(Protocol):
    """Protocol for use case implementations."""

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the use case with given parameters."""
        ...


class ServiceRegistrationRequest(BaseModel):
    """Request model for service registration use case."""

    service_name: str = Field(..., description="Name of the service to register")
    instance_id: str = Field(..., description="Unique instance identifier")
    version: str = Field(default="1.0.0", description="Service version")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Service metadata")


class ServiceRegistrationResponse(BaseModel):
    """Response model for service registration use case."""

    aggregate_id: str = Field(..., description="ID of the created service aggregate")
    service_name: str = Field(..., description="Registered service name")
    instance_id: str = Field(..., description="Registered instance ID")
    status: str = Field(..., description="Current service status")


class ServiceRegistrationUseCase:
    """Use case for registering a new service instance.

    This application service orchestrates the registration of a new service
    by coordinating between the domain layer and infrastructure ports.
    """

    def __init__(
        self,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        service_repository: "ServiceRepository",
    ):
        """Initialize the use case with required dependencies."""
        self._message_bus = message_bus
        self._metrics = metrics
        self._repository = service_repository

    async def execute(self, request: ServiceRegistrationRequest) -> ServiceRegistrationResponse:
        """Register a new service instance."""
        # Create value objects
        service_name = ServiceName(value=request.service_name)
        instance_id = InstanceId(value=request.instance_id)

        # Create aggregate
        aggregate = ServiceAggregate(
            service_name=service_name,
            instance_id=instance_id,
            version=request.version,
            metadata=request.metadata,
        )

        # Save aggregate
        await self._repository.save(aggregate)

        # Register with message bus
        await self._message_bus.register_service(
            str(service_name),
            str(instance_id),
        )

        # Track metrics
        self._metrics.increment("services.registered")
        self._metrics.increment(f"services.{request.service_name}.instances")

        # Publish domain events
        for event in aggregate.get_uncommitted_events():
            domain_event = Event(
                domain="service",
                event_type=event.event_type,
                payload={
                    "service_name": str(event.service_name),
                    "instance_id": str(event.instance_id),
                    "timestamp": event.timestamp.isoformat(),
                    "details": event.details,
                },
                source=str(instance_id),
            )
            await self._message_bus.publish_event(domain_event)

        # Mark events as committed
        aggregate.mark_events_committed()

        return ServiceRegistrationResponse(
            aggregate_id=f"{service_name}/{instance_id}",
            service_name=str(service_name),
            instance_id=str(instance_id),
            status=aggregate.status.value,
        )


class ServiceHeartbeatRequest(BaseModel):
    """Request model for service heartbeat use case."""

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Current metrics")


class ServiceHeartbeatUseCase:
    """Use case for processing service heartbeats.

    This application service handles heartbeat processing,
    health checks, and status updates.
    """

    def __init__(
        self,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        service_repository: "ServiceRepository",
        health_service: HealthCheckService,
    ):
        """Initialize the use case with required dependencies."""
        self._message_bus = message_bus
        self._metrics = metrics
        self._repository = service_repository
        self._health_service = health_service

    async def execute(self, request: ServiceHeartbeatRequest) -> None:
        """Process a service heartbeat."""
        # Create value objects
        service_name = ServiceName(value=request.service_name)
        instance_id = InstanceId(value=request.instance_id)

        # Load aggregate
        aggregate = await self._repository.get(service_name, instance_id)
        if not aggregate:
            raise ValueError(f"Service not found: {service_name}/{instance_id}")

        # Send heartbeat through aggregate
        aggregate.heartbeat()

        # Check health based on heartbeat time
        import time

        current_time = time.time()
        last_heartbeat_timestamp = aggregate.last_heartbeat.timestamp()
        is_healthy = self._health_service.is_healthy(last_heartbeat_timestamp, current_time)

        # Also check metrics-based health
        health_score = self._health_service.calculate_health_score(request.metrics)
        is_metrics_healthy = health_score > 0.5

        # Determine overall health
        is_overall_healthy = is_healthy and is_metrics_healthy

        # Update status if needed
        if not is_overall_healthy and aggregate.status.value != "UNHEALTHY":
            if not is_healthy:
                reason = "Heartbeat timeout"
            elif health_score < 0.5:
                reason = f"Low health score: {health_score:.2f}"
            else:
                reason = "Unknown health issue"
            aggregate.mark_unhealthy(reason)
        elif is_overall_healthy and aggregate.status.value == "UNHEALTHY":
            aggregate.activate()

        # Save updated aggregate
        await self._repository.save(aggregate)

        # Send heartbeat to message bus
        await self._message_bus.send_heartbeat(
            str(service_name),
            str(instance_id),
        )

        # Track metrics
        self._metrics.increment("heartbeats.processed")
        self._metrics.increment(f"heartbeats.{request.service_name}")

        # Publish domain events
        for event in aggregate.get_uncommitted_events():
            domain_event = Event(
                domain="service",
                event_type=event.event_type,
                payload={
                    "service_name": str(event.service_name),
                    "instance_id": str(event.instance_id),
                    "timestamp": event.timestamp.isoformat(),
                    "details": event.details,
                },
                source=str(instance_id),
            )
            await self._message_bus.publish_event(domain_event)

        # Mark events as committed
        aggregate.mark_events_committed()


class RPCCallRequest(BaseModel):
    """Request model for RPC call use case."""

    caller_service: str = Field(..., description="Service making the call")
    caller_instance: str = Field(..., description="Instance making the call")
    target_service: str = Field(..., description="Target service name")
    method: str = Field(..., description="Method to call")
    params: dict[str, Any] = Field(default_factory=dict, description="Method parameters")
    timeout: float = Field(default=30.0, description="Timeout in seconds")


class RPCCallUseCase:
    """Use case for making RPC calls between services.

    This application service handles RPC routing, metrics tracking,
    and error handling for inter-service communication.
    """

    def __init__(
        self,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        routing_service: MessageRoutingService,
        naming_service: MetricsNamingService,
    ):
        """Initialize the use case with required dependencies."""
        self._message_bus = message_bus
        self._metrics = metrics
        self._routing_service = routing_service
        self._naming_service = naming_service

    async def execute(self, request: RPCCallRequest) -> Any:
        """Execute an RPC call."""
        # Create RPC request
        rpc_request = RPCRequest(
            method=request.method,
            params=request.params,
            source=request.caller_instance,
            target=request.target_service,
            timeout=request.timeout,
        )

        # Track metrics
        # Import at the top of method to avoid circular imports
        from ..domain.value_objects import MethodName

        service_name = ServiceName(value=request.target_service)
        method_name = MethodName(value=request.method)
        metric_prefix = self._naming_service.rpc_client_metric_name(
            service_name, method_name, ""
        ).rstrip(".")

        with self._metrics.timer(metric_prefix):
            try:
                # Make the call
                response = await self._message_bus.call_rpc(rpc_request)

                if response.success:
                    self._metrics.increment(f"{metric_prefix}.success")
                    return response.result
                else:
                    self._metrics.increment(f"{metric_prefix}.error")
                    raise Exception(f"RPC call failed: {response.error}")

            except TimeoutError:
                self._metrics.increment(f"{metric_prefix}.timeout")
                raise


class ServiceRepository(ABC):
    """Abstract repository for service aggregates.

    This is a port that must be implemented by the infrastructure layer.
    """

    @abstractmethod
    async def save(self, aggregate: ServiceAggregate) -> None:
        """Save a service aggregate."""
        ...

    @abstractmethod
    async def get(
        self, service_name: ServiceName, instance_id: InstanceId
    ) -> ServiceAggregate | None:
        """Get a service aggregate by ID."""
        ...

    @abstractmethod
    async def list_by_service(self, service_name: ServiceName) -> list[ServiceAggregate]:
        """List all instances of a service."""
        ...

    @abstractmethod
    async def delete(self, service_name: ServiceName, instance_id: InstanceId) -> None:
        """Delete a service aggregate."""
        ...


class CommandProcessingRequest(BaseModel):
    """Request model for command processing use case."""

    command: Command = Field(..., description="Command to process")
    handler_service: str = Field(..., description="Service handling the command")
    handler_instance: str = Field(..., description="Instance handling the command")


class CommandProcessingUseCase:
    """Use case for processing commands with progress tracking.

    This application service orchestrates command execution,
    progress reporting, and result handling.
    """

    def __init__(
        self,
        message_bus: MessageBusPort,
        metrics: MetricsPort,
        repository: ServiceRepository,
    ):
        """Initialize the use case with required dependencies."""
        self._message_bus = message_bus
        self._metrics = metrics
        self._repository = repository

    async def execute(
        self,
        request: CommandProcessingRequest,
        handler: Callable[
            [Any, Callable[[float, str], Awaitable[None]]], Awaitable[dict[str, Any]]
        ],
    ) -> dict[str, Any]:
        """Process a command with progress tracking."""
        command = request.command

        # Track metrics
        metric_prefix = f"commands.{request.handler_service}.{command.command}"

        with self._metrics.timer(metric_prefix):
            try:
                # Create progress reporter
                async def report_progress(percent: float, status: str = "processing"):
                    progress_event = Event(
                        domain="command",
                        event_type="progress",
                        payload={
                            "command_id": command.message_id,
                            "percent": percent,
                            "status": status,
                            "handler": request.handler_instance,
                        },
                        source=request.handler_instance,
                    )
                    await self._message_bus.publish_event(progress_event)
                    self._metrics.gauge(f"{metric_prefix}.progress", percent)

                # Execute handler
                result = await handler(command, report_progress)

                # Publish completion event
                completion_event = Event(
                    domain="command",
                    event_type="completed",
                    payload={
                        "command_id": command.message_id,
                        "result": result,
                        "handler": request.handler_instance,
                    },
                    source=request.handler_instance,
                )
                await self._message_bus.publish_event(completion_event)

                self._metrics.increment(f"{metric_prefix}.success")
                return result

            except Exception as e:
                # Publish failure event
                failure_event = Event(
                    domain="command",
                    event_type="failed",
                    payload={
                        "command_id": command.message_id,
                        "error": str(e),
                        "handler": request.handler_instance,
                    },
                    source=request.handler_instance,
                )
                await self._message_bus.publish_event(failure_event)

                self._metrics.increment(f"{metric_prefix}.error")
                raise
