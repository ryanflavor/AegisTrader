"""Service base class for building microservices."""

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..domain.models import Command, Event, RPCRequest, ServiceInfo, ServiceInstance
from ..domain.patterns import SubjectPatterns
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.service_registry import ServiceRegistryPort


class Service:
    """Base service class following DDD principles."""

    def __init__(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
        service_registry: ServiceRegistryPort | None = None,
        logger: LoggerPort | None = None,
        registry_ttl: int = 30,  # 30 seconds default TTL
        heartbeat_interval: int = 10,  # 10 seconds default heartbeat interval
        enable_registration: bool = True,  # Can be disabled for testing
    ):
        """Initialize service.

        Args:
            service_name: Name of the service
            message_bus: Message bus implementation
            instance_id: Optional instance ID (auto-generated if not provided)
            version: Service version
            service_registry: Optional service registry implementation
            logger: Optional logger implementation
            registry_ttl: TTL for registry entries in seconds (default: 30)
            heartbeat_interval: Heartbeat interval in seconds (default: 10)
            enable_registration: Whether to enable service registration (default: True)
        """
        if not SubjectPatterns.is_valid_service_name(service_name):
            raise ValueError(f"Invalid service name: {service_name}")

        self.service_name = service_name
        self.instance_id = instance_id or f"{service_name}-{uuid.uuid4().hex[:8]}"
        self.version = version
        self._bus = message_bus
        self._info = ServiceInfo(
            service_name=service_name,
            instance_id=self.instance_id,
            version=version,
        )

        # Dependencies
        self._registry = service_registry
        self._logger = logger

        # Registry configuration
        self._registry_ttl = registry_ttl
        self._heartbeat_interval = heartbeat_interval
        self._enable_registration = enable_registration
        self._service_instance: ServiceInstance | None = None

        # Handler registries
        self._rpc_handlers: dict[str, Callable] = {}
        self._event_handlers: dict[str, list[Callable]] = {}
        self._command_handlers: dict[str, Callable] = {}

        # Health management
        self._heartbeat_task: asyncio.Task | None = None
        self._status_update_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._start_time: datetime | None = None

    async def start(self) -> None:
        """Start the service."""
        # Set start time
        self._start_time = datetime.now(UTC)

        # Call on_start hook for subclasses to register handlers
        await self.on_start()

        # Initialize service instance model
        if self._enable_registration:
            self._service_instance = ServiceInstance(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                status="ACTIVE",
                metadata={
                    "start_time": self._start_time.isoformat() if self._start_time else None,
                },
            )

            # Register if registry is provided
            if self._registry:
                await self._register_instance()

        # Register service with message bus
        await self._bus.register_service(self.service_name, self.instance_id)

        # Register all RPC handlers
        for method, handler in self._rpc_handlers.items():
            await self._bus.register_rpc_handler(self.service_name, method, handler)

        # Register all event handlers
        for pattern, handlers in self._event_handlers.items():
            for handler in handlers:
                durable_name = (
                    f"{self.service_name}-{pattern.replace('*', 'star').replace('.', '-')}"
                )
                await self._bus.subscribe_event(pattern, handler, durable_name)

        # Register all command handlers
        for command_name, handler in self._command_handlers.items():
            await self._bus.register_command_handler(self.service_name, command_name, handler)

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        print(f"✅ Service started: {self.service_name}/{self.instance_id}")

    async def stop(self) -> None:
        """Stop the service gracefully."""
        self._shutdown_event.set()

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task

        # Cancel any pending status update
        if self._status_update_task:
            self._status_update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._status_update_task

        # Deregister service instance
        if self._enable_registration and self._registry and self._service_instance:
            try:
                await self._registry.deregister(
                    self._service_instance.service_name,
                    self._service_instance.instance_id,
                )
            except Exception as e:
                if self._logger:
                    self._logger.warning(
                        "Failed to remove service instance from registry",
                        error=str(e),
                        service=self.service_name,
                        instance=self.instance_id,
                    )

        # Unregister service from message bus
        await self._bus.unregister_service(self.service_name, self.instance_id)

        print(f"👋 Service stopped: {self.service_name}/{self.instance_id}")

    # RPC Methods
    def rpc(self, method: str) -> Callable[[Callable], Callable]:
        """Decorator to register RPC handler.

        Example:
            @service.rpc("get_user")
            async def get_user(params: dict) -> dict:
                return {"user_id": params["id"], "name": "John"}
        """

        def decorator(handler: Callable) -> Callable:
            if not SubjectPatterns.is_valid_method_name(method):
                raise ValueError(f"Invalid method name: {method}")

            self._rpc_handlers[method] = handler

            return handler

        return decorator

    async def call_rpc(
        self, service: str, method: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Call RPC method on another service."""
        request = RPCRequest(
            method=method,
            params=params or {},
            source=self.instance_id,
            target=service,
        )

        response = await self._bus.call_rpc(request)

        if not response.success:
            raise Exception(f"RPC failed: {response.error}")

        return response.result

    # Event Methods
    def subscribe(self, pattern: str, durable: bool = True) -> Callable[[Callable], Callable]:
        """Decorator to subscribe to events.

        Example:
            @service.subscribe("order.*")
            async def handle_order_event(event: Event):
                print(f"Order event: {event.event_type}")
        """

        def decorator(handler: Callable) -> Callable:
            if pattern not in self._event_handlers:
                self._event_handlers[pattern] = []
            self._event_handlers[pattern].append(handler)

            # Durable subscription name will be created during registration

            # Registration will happen in start()

            return handler

        return decorator

    async def publish_event(
        self, domain: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        """Publish a domain event."""
        event = Event(
            domain=domain,
            event_type=event_type,
            payload=payload or {},
            source=self.instance_id,
        )

        await self._bus.publish_event(event)

    # Command Methods
    def command(self, command_name: str) -> Callable[[Callable], Callable]:
        """Decorator to register command handler.

        Example:
            @service.command("process_batch")
            async def process_batch(cmd: Command, progress: Callable):
                for i in range(10):
                    await progress(i * 10, "Processing...")
                return {"processed": 10}
        """

        def decorator(handler: Callable) -> Callable:
            self._command_handlers[command_name] = handler

            # Registration will happen in start()

            return handler

        return decorator

    async def send_command(
        self,
        service: str,
        command_name: str,
        payload: dict[str, Any] | None = None,
        priority: str = "normal",
        track_progress: bool = True,
    ) -> dict[str, Any]:
        """Send command to another service."""
        command = Command(
            command=command_name,
            payload=payload or {},
            priority=priority,
            source=self.instance_id,
            target=service,
        )

        return await self._bus.send_command(command, track_progress)

    # Health Management
    async def _register_instance(self) -> None:
        """Register service instance in registry."""
        if not self._registry or not self._service_instance:
            return

        try:
            await self._registry.register(
                self._service_instance,
                self._registry_ttl,
            )
        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Failed to register service instance",
                    error=str(e),
                    service=self.service_name,
                    instance=self.instance_id,
                )
            raise

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats and update registry.

        This method coordinates heartbeats between the message bus and registry.
        Failures are logged but don't stop the heartbeat loop.
        """
        consecutive_failures = 0
        max_consecutive_failures = 3

        while not self._shutdown_event.is_set():
            try:
                # Send heartbeat to message bus
                await self._bus.send_heartbeat(self.service_name, self.instance_id)

                # Update registry entry if enabled
                if self._enable_registration and self._registry and self._service_instance:
                    await self._update_registry_heartbeat()

                # Reset failure counter on success
                consecutive_failures = 0
                await asyncio.sleep(self._heartbeat_interval)

            except Exception as e:
                consecutive_failures += 1

                if self._logger:
                    self._logger.warning(
                        "Heartbeat error",
                        error=str(e),
                        service=self.service_name,
                        instance=self.instance_id,
                        consecutive_failures=consecutive_failures,
                    )
                else:
                    print(
                        f"❌ Heartbeat error ({consecutive_failures}/{max_consecutive_failures}): {e}"
                    )

                # If too many consecutive failures, mark service as unhealthy
                if consecutive_failures >= max_consecutive_failures:
                    self.set_status("UNHEALTHY")

                # Exponential backoff with jitter for retries
                backoff = min(2**consecutive_failures, 10) + asyncio.get_event_loop().time() % 1
                await asyncio.sleep(backoff)

    async def _update_registry_heartbeat(self) -> None:
        """Update the heartbeat timestamp in the registry.

        This method handles the case where the registry entry might have been
        lost and needs re-registration.
        """
        if not self._registry or not self._service_instance:
            return

        try:
            # Update heartbeat in domain model first
            self._service_instance.update_heartbeat()

            await self._registry.update_heartbeat(
                self._service_instance,
                self._registry_ttl,
            )
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    "Failed to update registry heartbeat",
                    error=str(e),
                    service=self.service_name,
                    instance=self.instance_id,
                )
            # Re-raise to let heartbeat loop handle it
            raise

    @property
    def info(self) -> ServiceInfo:
        """Get service information."""
        return self._info

    def set_status(self, status: str) -> None:
        """Update service status.

        This method updates the status in multiple places:
        1. Local ServiceInfo object
        2. ServiceInstance domain model (if registration enabled)
        3. Service registry (async, if available)

        Args:
            status: One of ACTIVE, STANDBY, UNHEALTHY, or SHUTDOWN

        Raises:
            ValueError: If status is not valid
        """
        valid_statuses = ["ACTIVE", "STANDBY", "UNHEALTHY", "SHUTDOWN"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        # Update local info
        self._info.status = status

        # Update domain model
        if self._service_instance:
            self._service_instance.status = status

        # Schedule registry update if enabled
        if self._enable_registration and self._registry and self._service_instance:
            # Create a tracked task for proper cleanup
            if hasattr(self, "_status_update_task") and self._status_update_task:
                self._status_update_task.cancel()

            self._status_update_task = asyncio.create_task(
                self._update_registry_status(status), name=f"status_update_{status}"
            )

    async def _update_registry_status(self, status: str) -> None:
        """Update the service status in the registry."""
        if not self._registry or not self._service_instance:
            return

        try:
            # Update heartbeat with new status
            await self._registry.update_heartbeat(
                self._service_instance,
                self._registry_ttl,
            )
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    "Failed to update registry status",
                    error=str(e),
                    service=self.service_name,
                    instance=self.instance_id,
                    status=status,
                )

    async def on_start(self) -> None:
        """Hook for subclasses to perform initialization during start.

        Override this method to register handlers or perform other initialization.
        This is called before the service registers with the message bus.
        """
        pass

    async def register_rpc_method(self, method: str, handler: Callable) -> None:
        """Register an RPC method handler.

        Args:
            method: The method name
            handler: The handler function
        """
        if not SubjectPatterns.is_valid_method_name(method):
            raise ValueError(f"Invalid method name: {method}")
        self._rpc_handlers[method] = handler

    async def register_command_handler(self, command_name: str, handler: Callable) -> None:
        """Register a command handler.

        Args:
            command_name: The command name
            handler: The handler function
        """
        self._command_handlers[command_name] = handler

    async def subscribe_event(self, domain: str, event_type: str, handler: Callable) -> None:
        """Subscribe to an event pattern.

        Args:
            domain: The event domain
            event_type: The event type (can include wildcards)
            handler: The handler function
        """
        # Use the full event pattern that matches SubjectPatterns.event()
        pattern = SubjectPatterns.event(domain, event_type)
        if pattern not in self._event_handlers:
            self._event_handlers[pattern] = []
        self._event_handlers[pattern].append(handler)

    async def emit_event(self, domain: str, event_type: str, payload: dict[str, Any]) -> None:
        """Emit an event.

        Args:
            domain: The event domain
            event_type: The event type
            payload: The event payload
        """
        event = Event(
            domain=domain,
            event_type=event_type,
            payload=payload,
            source=self.instance_id,
        )
        await self._bus.publish_event(event)
