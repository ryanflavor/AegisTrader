"""Service base class for building microservices."""

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from typing import Any

from ..domain.models import Command, Event, RPCRequest, ServiceInfo
from ..domain.patterns import SubjectPatterns
from ..ports.message_bus import MessageBusPort


class Service:
    """Base service class following DDD principles."""

    def __init__(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
    ):
        """Initialize service.

        Args:
            service_name: Name of the service
            message_bus: Message bus implementation
            instance_id: Optional instance ID (auto-generated if not provided)
            version: Service version
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

        # Handler registries
        self._rpc_handlers: dict[str, Callable] = {}
        self._event_handlers: dict[str, list[Callable]] = {}
        self._command_handlers: dict[str, Callable] = {}

        # Health management
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._start_time = None

    async def start(self) -> None:
        """Start the service."""
        from datetime import datetime

        # Set start time
        self._start_time = datetime.now()

        # Call on_start hook for subclasses to register handlers
        await self.on_start()

        # Register service
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

        # Unregister service
        await self._bus.unregister_service(self.service_name, self.instance_id)

        print(f"👋 Service stopped: {self.service_name}/{self.instance_id}")

    # RPC Methods
    def rpc(self, method: str):
        """Decorator to register RPC handler.

        Example:
            @service.rpc("get_user")
            async def get_user(params: dict) -> dict:
                return {"user_id": params["id"], "name": "John"}
        """

        def decorator(handler: Callable):
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
    def subscribe(self, pattern: str, durable: bool = True):
        """Decorator to subscribe to events.

        Example:
            @service.subscribe("order.*")
            async def handle_order_event(event: Event):
                print(f"Order event: {event.event_type}")
        """

        def decorator(handler: Callable):
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
    def command(self, command_name: str):
        """Decorator to register command handler.

        Example:
            @service.command("process_batch")
            async def process_batch(cmd: Command, progress: Callable):
                for i in range(10):
                    await progress(i * 10, "Processing...")
                return {"processed": 10}
        """

        def decorator(handler: Callable):
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
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while not self._shutdown_event.is_set():
            try:
                await self._bus.send_heartbeat(self.service_name, self.instance_id)
                await asyncio.sleep(5)  # Every 5 seconds
            except Exception as e:
                print(f"❌ Heartbeat error: {e}")
                await asyncio.sleep(1)  # Retry faster on error

    @property
    def info(self) -> ServiceInfo:
        """Get service information."""
        return self._info

    def set_status(self, status: str) -> None:
        """Update service status."""
        if status not in ["ACTIVE", "STANDBY", "UNHEALTHY", "SHUTDOWN"]:
            raise ValueError(f"Invalid status: {status}")
        self._info.status = status

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
