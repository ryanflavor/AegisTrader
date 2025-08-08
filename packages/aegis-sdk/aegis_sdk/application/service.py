"""Service base class for building microservices following hexagonal architecture."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator

from aegis_sdk.domain.enums import (
    CommandPriority,
    ServiceLifecycleState,
    ServiceStatus,
    SubscriptionMode,
)
from aegis_sdk.domain.exceptions import ServiceUnavailableError
from aegis_sdk.domain.models import Command, Event, RPCRequest, ServiceInfo, ServiceInstance
from aegis_sdk.domain.patterns import SubjectPatterns
from aegis_sdk.domain.types import CommandHandler, EventHandler, RPCHandler

if TYPE_CHECKING:
    from aegis_sdk.ports.logger import LoggerPort
    from aegis_sdk.ports.message_bus import MessageBusPort
    from aegis_sdk.ports.service_discovery import SelectionStrategy, ServiceDiscoveryPort
    from aegis_sdk.ports.service_registry import ServiceRegistryPort


# DTOs for Service Configuration
class ServiceConfig(BaseModel):
    """Configuration DTO for Service initialization with strict validation."""

    service_name: str = Field(..., min_length=1, max_length=128)
    instance_id: str | None = Field(default=None, max_length=256)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    registry_ttl: float = Field(default=30, ge=0.001, le=3600)
    heartbeat_interval: float = Field(default=10, ge=0.001, le=300)
    enable_registration: bool = Field(default=True)

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name format."""
        if not SubjectPatterns.is_valid_service_name(v):
            raise ValueError(f"Invalid service name: {v}")
        return v


class HandlerRegistry:
    """Manages handler registrations with thread safety."""

    def __init__(self) -> None:
        """Initialize handler registry."""
        self._rpc_handlers: dict[str, RPCHandler] = {}
        self._event_handlers: dict[str, list[tuple[EventHandler, str]]] = {}
        self._command_handlers: dict[str, CommandHandler] = {}
        self._lock = asyncio.Lock()

    async def register_rpc(self, method: str, handler: RPCHandler) -> None:
        """Register RPC handler."""
        if not SubjectPatterns.is_valid_method_name(method):
            raise ValueError(f"Invalid method name: {method}")
        async with self._lock:
            self._rpc_handlers[method] = handler

    async def unregister_rpc(self, method: str) -> bool:
        """Unregister RPC handler."""
        async with self._lock:
            if method in self._rpc_handlers:
                del self._rpc_handlers[method]
                return True
            return False

    async def register_event(
        self, pattern: str, handler: EventHandler, mode: SubscriptionMode
    ) -> None:
        """Register event handler."""
        if not SubjectPatterns.is_valid_event_pattern(pattern):
            raise ValueError(f"Invalid event pattern: {pattern}")
        async with self._lock:
            if pattern not in self._event_handlers:
                self._event_handlers[pattern] = []
            self._event_handlers[pattern].append((handler, mode.value))

    async def unregister_event(self, pattern: str, handler: EventHandler | None = None) -> bool:
        """Unregister event handler."""
        async with self._lock:
            if pattern not in self._event_handlers:
                return False

            if handler is None:
                del self._event_handlers[pattern]
                return True
            else:
                handlers = self._event_handlers[pattern]
                original_count = len(handlers)
                self._event_handlers[pattern] = [(h, m) for h, m in handlers if h != handler]
                if not self._event_handlers[pattern]:
                    del self._event_handlers[pattern]
                return len(self._event_handlers.get(pattern, [])) < original_count

    async def register_command(self, command_name: str, handler: CommandHandler) -> None:
        """Register command handler."""
        async with self._lock:
            self._command_handlers[command_name] = handler

    async def unregister_command(self, command_name: str) -> bool:
        """Unregister command handler."""
        async with self._lock:
            if command_name in self._command_handlers:
                del self._command_handlers[command_name]
                return True
            return False

    @property
    def rpc_handlers(self) -> dict[str, RPCHandler]:
        """Get RPC handlers."""
        return self._rpc_handlers.copy()

    @property
    def event_handlers(self) -> dict[str, list[tuple[EventHandler, str]]]:
        """Get event handlers."""
        return self._event_handlers.copy()

    @property
    def command_handlers(self) -> dict[str, CommandHandler]:
        """Get command handlers."""
        return self._command_handlers.copy()


class LifecycleManager:
    """Manages service lifecycle state transitions."""

    def __init__(self, logger: LoggerPort | None = None) -> None:
        """Initialize lifecycle manager."""
        self._state = ServiceLifecycleState.INITIALIZING
        self._lock = asyncio.Lock()
        self._logger = logger

    async def transition_to(
        self, new_state: ServiceLifecycleState, allowed_from: list[ServiceLifecycleState]
    ) -> None:
        """Transition to a new lifecycle state with validation."""
        async with self._lock:
            if self._state not in allowed_from:
                raise RuntimeError(
                    f"Cannot transition from {self._state.value} to {new_state.value}. "
                    f"Allowed from: {[s.value for s in allowed_from]}"
                )

            old_state = self._state
            self._state = new_state

            if self._logger:
                self._logger.info(
                    "Service lifecycle state changed",
                    old_state=old_state.value,
                    new_state=new_state.value,
                )

    @property
    def state(self) -> ServiceLifecycleState:
        """Get current state."""
        return self._state

    def is_operational(self) -> bool:
        """Check if service is operational."""
        return self._state == ServiceLifecycleState.STARTED


class HealthManager:
    """Manages service health and heartbeat operations."""

    def __init__(
        self,
        service_name: str,
        instance_id: str,
        heartbeat_interval: float,
        registry_ttl: float,
        message_bus: MessageBusPort,
        registry: ServiceRegistryPort | None = None,
        logger: LoggerPort | None = None,
        on_unhealthy_callback: callable | None = None,
    ) -> None:
        """Initialize health manager."""
        self.service_name = service_name
        self.instance_id = instance_id
        self.heartbeat_interval = heartbeat_interval
        self.registry_ttl = registry_ttl
        self._bus = message_bus
        self._registry = registry
        self._logger = logger
        self._on_unhealthy = on_unhealthy_callback
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    async def start_heartbeat(self, service_instance: ServiceInstance | None) -> None:
        """Start heartbeat loop."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(service_instance))

    async def stop_heartbeat(self) -> None:
        """Stop heartbeat loop."""
        self._shutdown_event.set()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task

    async def _heartbeat_loop(self, service_instance: ServiceInstance | None) -> None:
        """Send periodic heartbeats."""
        while not self._shutdown_event.is_set():
            try:
                await self._send_heartbeat(service_instance)
                self._consecutive_failures = 0
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                await self._handle_heartbeat_failure(e)
                if self._consecutive_failures >= self._max_consecutive_failures:
                    # Mark service as unhealthy when max failures reached
                    if self._on_unhealthy:
                        self._on_unhealthy()
                    break
                await self._backoff_sleep()

    async def _send_heartbeat(self, service_instance: ServiceInstance | None) -> None:
        """Send heartbeat to message bus and registry."""
        await self._bus.send_heartbeat(self.service_name, self.instance_id)
        if self._registry and service_instance:
            service_instance.update_heartbeat()
            await self._registry.update_heartbeat(service_instance, int(self.registry_ttl))

    async def _handle_heartbeat_failure(self, error: Exception) -> None:
        """Handle heartbeat failure."""
        # Increment failures first (was missing)
        self._consecutive_failures += 1

        if self._logger:
            self._logger.warning(
                "Heartbeat error",
                error=str(error),
                service=self.service_name,
                instance=self.instance_id,
                consecutive_failures=self._consecutive_failures,
            )
        else:
            print(
                f"❌ Heartbeat error ({self._consecutive_failures}/{self._max_consecutive_failures}): {error}"
            )

    async def _backoff_sleep(self) -> None:
        """Sleep with exponential backoff."""
        import secrets

        base_backoff = min(2**self._consecutive_failures, 10)
        jitter = secrets.SystemRandom().uniform(0, 1)
        backoff = base_backoff + jitter
        await asyncio.sleep(backoff)

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._consecutive_failures < self._max_consecutive_failures


class ServiceNameResolver:
    """Resolves service names vs instance IDs."""

    def __init__(self, discovery: ServiceDiscoveryPort | None = None) -> None:
        """Initialize resolver."""
        self._discovery = discovery

    async def is_service_name(self, target: str) -> bool:
        """Check if target is a service name vs instance ID."""
        if not SubjectPatterns.is_valid_service_name(target):
            return False

        if self._discovery:
            try:
                instances = await self._discovery.discover_instances(target)
                if instances:
                    return True
            except Exception:
                # If discovery fails, fall back to pattern matching
                pass  # nosec B110

        # Check instance ID pattern
        parts = target.split("-")
        if len(parts) >= 2:
            potential_uuid = parts[-1]
            if len(potential_uuid) >= 8 and all(
                c in "0123456789abcdef" for c in potential_uuid.lower()
            ):
                return False

        return True


class Service:
    """Base service class following hexagonal architecture and DDD principles."""

    def __init__(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        registry_ttl: float = 30,
        heartbeat_interval: float = 10,
        enable_registration: bool = True,
    ):
        """Initialize service with dependency injection."""
        # Validate configuration
        config = ServiceConfig(
            service_name=service_name,
            instance_id=instance_id,
            version=version,
            registry_ttl=registry_ttl,
            heartbeat_interval=heartbeat_interval,
            enable_registration=enable_registration,
        )

        # Core properties
        self.service_name = config.service_name
        self.instance_id = config.instance_id or f"{config.service_name}-{uuid.uuid4().hex[:8]}"
        self.version = config.version

        # Ports (dependencies)
        self._bus = message_bus
        self._registry = service_registry
        self._discovery = service_discovery
        self._logger = logger

        # Domain model
        self._info = ServiceInfo(
            service_name=self.service_name,
            instance_id=self.instance_id,
            version=self.version,
        )
        self._service_instance: ServiceInstance | None = None

        # Managers (application services)
        self._handler_registry = HandlerRegistry()
        self._lifecycle = LifecycleManager(logger)
        self._health_manager = HealthManager(
            self.service_name,
            self.instance_id,
            config.heartbeat_interval,
            config.registry_ttl,
            message_bus,
            service_registry,
            logger,
            lambda: self.set_status(ServiceStatus.UNHEALTHY),
        )
        self._resolver = ServiceNameResolver(service_discovery)

        # Configuration
        self._config = config
        self._start_time: datetime | None = None
        self._status_update_task: asyncio.Task | None = None

    # Lifecycle Management
    @property
    def lifecycle_state(self) -> ServiceLifecycleState:
        """Get current lifecycle state."""
        return self._lifecycle.state

    def is_operational(self) -> bool:
        """Check if service is operational."""
        return self._lifecycle.is_operational()

    async def start(self) -> None:
        """Start the service."""
        await self._lifecycle.transition_to(
            ServiceLifecycleState.STARTING,
            [ServiceLifecycleState.INITIALIZING, ServiceLifecycleState.STOPPED],
        )

        try:
            self._start_time = datetime.now(UTC)
            await self.on_start()
            await self._initialize_service_instance()
            await self._register_with_infrastructure()
            await self._health_manager.start_heartbeat(self._service_instance)

            await self._lifecycle.transition_to(
                ServiceLifecycleState.STARTED,
                [ServiceLifecycleState.STARTING],
            )

            self._log_start_success()
            await self.on_started()

        except Exception as e:
            await self._handle_start_failure(e)
            raise

    async def stop(self) -> None:
        """Stop the service."""
        await self._lifecycle.transition_to(
            ServiceLifecycleState.STOPPING,
            [
                ServiceLifecycleState.STARTED,
                ServiceLifecycleState.STARTING,
                ServiceLifecycleState.FAILED,
                ServiceLifecycleState.INITIALIZING,
            ],
        )

        try:
            await self.on_stop()
            await self._health_manager.stop_heartbeat()
            await self._cancel_status_update_task()
            await self._deregister_from_infrastructure()

            await self._lifecycle.transition_to(
                ServiceLifecycleState.STOPPED,
                [ServiceLifecycleState.STOPPING],
            )

            self._log_stop_success()
            await self.on_stopped()

        except Exception as e:
            await self._handle_stop_failure(e)
            raise

    async def _initialize_service_instance(self) -> None:
        """Initialize service instance for registration."""
        if self._config.enable_registration:
            self._service_instance = ServiceInstance(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                status=ServiceStatus.ACTIVE.value,
                metadata={
                    "start_time": self._start_time.isoformat() if self._start_time else None,
                },
            )
            if self._registry:
                try:
                    await self._registry.register(
                        self._service_instance,
                        int(self._config.registry_ttl),
                    )
                except Exception as e:
                    if self._logger:
                        self._logger.error(
                            "Failed to register service instance",
                            service=self.service_name,
                            instance=self.instance_id,
                            error=str(e),
                        )
                    raise

    async def _register_with_infrastructure(self) -> None:
        """Register handlers with message bus."""
        await self._bus.register_service(self.service_name, self.instance_id)

        # Register RPC handlers
        for method, handler in self._handler_registry.rpc_handlers.items():
            await self._bus.register_rpc_handler(self.service_name, method, handler)

        # Register event subscriptions
        for pattern, handler_tuples in self._handler_registry.event_handlers.items():
            for event_handler, mode in handler_tuples:
                durable_name = (
                    f"{self.service_name}-{pattern.replace('*', 'star').replace('.', '-')}"
                )
                await self._bus.subscribe_event(pattern, event_handler, durable_name, mode=mode)

        # Register command handlers
        for command_name, cmd_handler in self._handler_registry.command_handlers.items():
            await self._bus.register_command_handler(self.service_name, command_name, cmd_handler)

    async def _deregister_from_infrastructure(self) -> None:
        """Deregister from infrastructure services."""
        if self._config.enable_registration and self._registry and self._service_instance:
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

        await self._bus.unregister_service(self.service_name, self.instance_id)

    async def _handle_start_failure(self, error: Exception) -> None:
        """Handle service start failure."""
        self._lifecycle._state = ServiceLifecycleState.FAILED
        if self._logger:
            self._logger.error(
                "Service start failed",
                service=self.service_name,
                instance=self.instance_id,
                error=str(error),
            )

    async def _handle_stop_failure(self, error: Exception) -> None:
        """Handle service stop failure."""
        if self._logger:
            self._logger.error(
                "Error during service stop",
                service=self.service_name,
                instance=self.instance_id,
                error=str(error),
            )
        self._lifecycle._state = ServiceLifecycleState.STOPPED

    def _log_start_success(self) -> None:
        """Log successful service start."""
        if self._logger:
            self._logger.info(
                "Service started",
                service=self.service_name,
                instance=self.instance_id,
            )
        else:
            print(f"✅ Service started: {self.service_name}/{self.instance_id}")

    def _log_stop_success(self) -> None:
        """Log successful service stop."""
        if self._logger:
            self._logger.info(
                "Service stopped",
                service=self.service_name,
                instance=self.instance_id,
            )
        else:
            print(f"👋 Service stopped: {self.service_name}/{self.instance_id}")

    async def _cancel_status_update_task(self) -> None:
        """Cancel any pending status update task."""
        if self._status_update_task:
            self._status_update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._status_update_task

    # RPC Methods
    def rpc(self, method: str) -> Callable[[RPCHandler], RPCHandler]:
        """Decorator to register RPC handler."""

        def decorator(handler: RPCHandler) -> RPCHandler:
            # Use synchronous registration for decorators (called at definition time)
            if not SubjectPatterns.is_valid_method_name(method):
                raise ValueError(f"Invalid method name: {method}")
            self._handler_registry._rpc_handlers[method] = handler
            return handler

        return decorator

    def unregister_rpc(self, method: str) -> bool:
        """Unregister RPC handler."""
        if method in self._handler_registry._rpc_handlers:
            del self._handler_registry._rpc_handlers[method]
            return True
        return False

    async def call_rpc(
        self,
        request: RPCRequest,
        discovery_enabled: bool = True,
        selection_strategy: SelectionStrategy | None = None,
        preferred_instance_id: str | None = None,
    ) -> Any:
        """Call RPC method on another service."""
        if request.source is None:
            request.source = self.instance_id

        target = request.target
        if discovery_enabled and self._discovery and target:
            if await self._resolver.is_service_name(target):
                from aegis_sdk.ports.service_discovery import SelectionStrategy

                strategy = selection_strategy or SelectionStrategy.ROUND_ROBIN
                instance = await self._discovery.select_instance(
                    target,
                    strategy=strategy,
                    preferred_instance_id=preferred_instance_id,
                )
                if not instance:
                    raise ServiceUnavailableError(target)

                if self._logger:
                    self._logger.debug(
                        "Selected instance for RPC",
                        service=target,
                        instance=instance.instance_id,
                        method=request.method,
                    )

        try:
            response = await self._bus.call_rpc(request)
            if not response.success:
                raise Exception(f"RPC failed: {response.error}")
            return response.result
        except Exception:
            if discovery_enabled and self._discovery and target:
                if await self._resolver.is_service_name(target):
                    await self._discovery.invalidate_cache(target)
            raise

    def create_rpc_request(
        self,
        service: str,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> RPCRequest:
        """Factory method to create an RPCRequest."""
        return RPCRequest(
            method=method,
            params=params or {},
            source=self.instance_id,
            target=service,
            timeout=timeout,
        )

    # Event Methods
    def subscribe(
        self, pattern: str, mode: SubscriptionMode | str = SubscriptionMode.COMPETE
    ) -> Callable[[EventHandler], EventHandler]:
        """Decorator to subscribe to events."""
        if isinstance(mode, str):
            mode = SubscriptionMode(mode)

        if not SubjectPatterns.is_valid_event_pattern(pattern):
            raise ValueError(f"Invalid event pattern: {pattern}")

        def decorator(handler: EventHandler) -> EventHandler:
            # Use synchronous registration for decorators
            if pattern not in self._handler_registry._event_handlers:
                self._handler_registry._event_handlers[pattern] = []
            self._handler_registry._event_handlers[pattern].append((handler, mode.value))
            return handler

        return decorator

    def unsubscribe(self, pattern: str, handler: EventHandler | None = None) -> bool:
        """Unsubscribe from event pattern."""
        if pattern not in self._handler_registry._event_handlers:
            return False

        if handler is None:
            del self._handler_registry._event_handlers[pattern]
            return True
        else:
            handlers = self._handler_registry._event_handlers[pattern]
            original_count = len(handlers)
            self._handler_registry._event_handlers[pattern] = [
                (h, m) for h, m in handlers if h != handler
            ]
            if not self._handler_registry._event_handlers[pattern]:
                del self._handler_registry._event_handlers[pattern]
            return len(self._handler_registry._event_handlers.get(pattern, [])) < original_count

    async def publish_event(self, event: Event) -> None:
        """Publish a domain event."""
        if not self.is_operational():
            raise RuntimeError(
                f"Cannot publish events while service is in {self._lifecycle.state.value} state"
            )
        if event.source is None:
            event.source = self.instance_id
        await self._bus.publish_event(event)

    def create_event(
        self, domain: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> Event:
        """Factory method to create an Event."""
        return Event(
            domain=domain,
            event_type=event_type,
            payload=payload or {},
            source=self.instance_id,
        )

    # Command Methods
    def command(self, command_name: str) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register command handler."""

        def decorator(handler: CommandHandler) -> CommandHandler:
            # Use synchronous registration for decorators
            self._handler_registry._command_handlers[command_name] = handler
            return handler

        return decorator

    def unregister_command(self, command_name: str) -> bool:
        """Unregister command handler."""
        if command_name in self._handler_registry._command_handlers:
            del self._handler_registry._command_handlers[command_name]
            return True
        return False

    async def send_command(self, command: Command, track_progress: bool = True) -> dict[str, Any]:
        """Send command to another service."""
        if command.source is None:
            command.source = self.instance_id
        return await self._bus.send_command(command, track_progress)

    def create_command(
        self,
        service: str,
        command_name: str,
        payload: dict[str, Any] | None = None,
        priority: CommandPriority | str = CommandPriority.NORMAL,
        max_retries: int = 3,
        timeout: float = 300.0,
    ) -> Command:
        """Factory method to create a Command."""
        if isinstance(priority, str):
            priority = CommandPriority(priority)

        if not 0 <= max_retries <= 100:
            raise ValueError("max_retries must be between 0 and 100")
        if not 0 < timeout <= 3600:
            raise ValueError("timeout must be between 0 and 3600 seconds")

        return Command(
            command=command_name,
            payload=payload or {},
            priority=priority.value,
            source=self.instance_id,
            target=service,
            max_retries=max_retries,
            timeout=timeout,
        )

    # Health Management
    @property
    def info(self) -> ServiceInfo:
        """Get service information."""
        return self._info

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        if not self._start_time:
            return False
        if self._lifecycle.state != ServiceLifecycleState.STARTED:
            return False
        if not self._health_manager.is_healthy():
            return False
        return self._info.status not in (
            ServiceStatus.UNHEALTHY.value,
            ServiceStatus.SHUTDOWN.value,
        )

    def set_status(self, status: ServiceStatus | str) -> None:
        """Update service status."""
        if isinstance(status, str):
            status = ServiceStatus(status)

        self._info.status = status.value
        if self._service_instance:
            self._service_instance.status = status.value

        if status == ServiceStatus.UNHEALTHY:
            self._health_manager._consecutive_failures = (
                self._health_manager._max_consecutive_failures
            )
            if not self._logger:
                print(f"⚠️  Service marked as UNHEALTHY: {self.service_name}/{self.instance_id}")

        if self._config.enable_registration and self._registry and self._service_instance:
            if self._status_update_task:
                self._status_update_task.cancel()
            self._status_update_task = asyncio.create_task(
                self._update_registry_status(), name=f"status_update_{status}"
            )

    async def _update_registry_status(self) -> None:
        """Update service status in registry."""
        if not self._registry or not self._service_instance:
            return

        try:
            await self._registry.update_heartbeat(
                self._service_instance,
                int(self._config.registry_ttl),
            )
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    "Failed to update registry status",
                    error=str(e),
                    service=self.service_name,
                    instance=self.instance_id,
                    status=self._service_instance.status,
                )

    # Lifecycle Hooks
    async def on_start(self) -> None:
        """Hook for subclasses to perform initialization during start."""
        pass

    async def on_started(self) -> None:
        """Hook called after service has successfully started."""
        pass

    async def on_stop(self) -> None:
        """Hook called before service begins stopping."""
        pass

    async def on_stopped(self) -> None:
        """Hook called after service has successfully stopped."""
        pass

    # Helper methods for backward compatibility
    async def register_rpc_method(self, method: str, handler: RPCHandler) -> None:
        """Register an RPC method handler."""
        await self._handler_registry.register_rpc(method, handler)

    async def register_command_handler(self, command_name: str, handler: CommandHandler) -> None:
        """Register a command handler."""
        await self._handler_registry.register_command(command_name, handler)

    async def subscribe_event(
        self,
        domain: str,
        event_type: str,
        handler: EventHandler,
        mode: SubscriptionMode | str = SubscriptionMode.COMPETE,
    ) -> None:
        """Subscribe to an event pattern."""
        if isinstance(mode, str):
            mode = SubscriptionMode(mode)
        pattern = SubjectPatterns.event(domain, event_type)
        await self._handler_registry.register_event(pattern, handler, mode)

    async def _is_service_name(self, target: str) -> bool:
        """Check if target is a service name (backward compatibility)."""
        return await self._resolver.is_service_name(target)
