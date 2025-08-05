"""Service base class for building microservices."""

import asyncio
import contextlib
import random
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.domain.enums import (
    CommandPriority,
    ServiceLifecycleState,
    ServiceStatus,
    SubscriptionMode,
)

from ..domain.exceptions import ServiceUnavailableError
from ..domain.models import Command, Event, RPCRequest, ServiceInfo, ServiceInstance
from ..domain.patterns import SubjectPatterns
from ..domain.types import CommandHandler, EventHandler, RPCHandler
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.service_discovery import SelectionStrategy, ServiceDiscoveryPort
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
        service_discovery: ServiceDiscoveryPort | None = None,
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
            service_discovery: Optional service discovery implementation
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
        self._discovery = service_discovery
        self._logger = logger

        # Registry configuration
        self._registry_ttl = registry_ttl
        self._heartbeat_interval = heartbeat_interval
        self._enable_registration = enable_registration
        self._service_instance: ServiceInstance | None = None

        # Handler registries with thread safety
        self._rpc_handlers: dict[str, RPCHandler] = {}
        self._event_handlers: dict[str, list[tuple[EventHandler, str]]] = {}  # (handler, mode)
        self._command_handlers: dict[str, CommandHandler] = {}
        self._handler_lock = threading.RLock()  # Reentrant lock for handler operations

        # Health management
        self._heartbeat_task: asyncio.Task | None = None
        self._status_update_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._start_time: datetime | None = None

        # Lifecycle state management
        self._lifecycle_state = ServiceLifecycleState.INITIALIZING
        self._lifecycle_lock = threading.RLock()

    def _transition_lifecycle_state(
        self, new_state: ServiceLifecycleState, allowed_from: list[ServiceLifecycleState]
    ) -> None:
        """Transition to a new lifecycle state with validation.

        Args:
            new_state: The new lifecycle state
            allowed_from: List of states from which this transition is allowed

        Raises:
            RuntimeError: If the transition is not allowed
        """
        with self._lifecycle_lock:
            if self._lifecycle_state not in allowed_from:
                raise RuntimeError(
                    f"Cannot transition from {self._lifecycle_state.value} to {new_state.value}. "
                    f"Allowed from: {[s.value for s in allowed_from]}"
                )

            old_state = self._lifecycle_state
            self._lifecycle_state = new_state

            if self._logger:
                self._logger.info(
                    "Service lifecycle state changed",
                    service=self.service_name,
                    instance=self.instance_id,
                    old_state=old_state.value,
                    new_state=new_state.value,
                )

    @property
    def lifecycle_state(self) -> ServiceLifecycleState:
        """Get the current lifecycle state."""
        return self._lifecycle_state

    def is_operational(self) -> bool:
        """Check if the service is in an operational state.

        Returns:
            bool: True if service is STARTED, False otherwise
        """
        return self._lifecycle_state == ServiceLifecycleState.STARTED

    async def start(self) -> None:
        """Start the service."""
        # Transition to STARTING state
        self._transition_lifecycle_state(
            ServiceLifecycleState.STARTING,
            [ServiceLifecycleState.INITIALIZING, ServiceLifecycleState.STOPPED],
        )

        try:
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
                    status=ServiceStatus.ACTIVE.value,
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
            for pattern, handler_tuples in self._event_handlers.items():
                for event_handler, mode in handler_tuples:
                    durable_name = (
                        f"{self.service_name}-{pattern.replace('*', 'star').replace('.', '-')}"
                    )
                    await self._bus.subscribe_event(pattern, event_handler, durable_name, mode=mode)

            # Register all command handlers
            for command_name, cmd_handler in self._command_handlers.items():
                await self._bus.register_command_handler(
                    self.service_name, command_name, cmd_handler
                )

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Transition to STARTED state
            self._transition_lifecycle_state(
                ServiceLifecycleState.STARTED,
                [ServiceLifecycleState.STARTING],
            )

            if self._logger:
                self._logger.info(
                    "Service started",
                    service=self.service_name,
                    instance=self.instance_id,
                )
            else:
                # Fallback for development/debugging
                print(f"✅ Service started: {self.service_name}/{self.instance_id}")

            # Call on_started hook
            await self.on_started()

        except Exception as e:
            # Transition to FAILED state on error
            self._lifecycle_state = ServiceLifecycleState.FAILED
            if self._logger:
                self._logger.error(
                    "Service start failed",
                    service=self.service_name,
                    instance=self.instance_id,
                    error=str(e),
                )
            raise

    async def stop(self) -> None:
        """Stop the service gracefully."""
        # Transition to STOPPING state
        self._transition_lifecycle_state(
            ServiceLifecycleState.STOPPING,
            [
                ServiceLifecycleState.STARTED,
                ServiceLifecycleState.STARTING,
                ServiceLifecycleState.FAILED,
                ServiceLifecycleState.INITIALIZING,
            ],
        )

        try:
            # Call on_stop hook
            await self.on_stop()

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

            # Transition to STOPPED state
            self._transition_lifecycle_state(
                ServiceLifecycleState.STOPPED,
                [ServiceLifecycleState.STOPPING],
            )

            if self._logger:
                self._logger.info(
                    "Service stopped",
                    service=self.service_name,
                    instance=self.instance_id,
                )
            else:
                # Fallback for development/debugging
                print(f"👋 Service stopped: {self.service_name}/{self.instance_id}")

            # Call on_stopped hook
            await self.on_stopped()

        except Exception as e:
            # Log error but still transition to STOPPED
            if self._logger:
                self._logger.error(
                    "Error during service stop",
                    service=self.service_name,
                    instance=self.instance_id,
                    error=str(e),
                )
            # Force transition to STOPPED even on error
            self._lifecycle_state = ServiceLifecycleState.STOPPED
            raise

    # RPC Methods
    def rpc(self, method: str) -> Callable[[RPCHandler], RPCHandler]:
        """Decorator to register RPC handler.

        Example:
            @service.rpc("get_user")
            async def get_user(params: dict) -> dict:
                return {"user_id": params["id"], "name": "John"}
        """

        def decorator(handler: RPCHandler) -> RPCHandler:
            if not SubjectPatterns.is_valid_method_name(method):
                raise ValueError(f"Invalid method name: {method}")

            with self._handler_lock:
                self._rpc_handlers[method] = handler

            return handler

        return decorator

    def unregister_rpc(self, method: str) -> bool:
        """Unregister an RPC method handler.

        Args:
            method: The method name to unregister

        Returns:
            bool: True if the handler was removed, False if not found
        """
        with self._handler_lock:
            if method in self._rpc_handlers:
                del self._rpc_handlers[method]
                return True
            return False

    async def call_rpc(
        self,
        request: RPCRequest,
        discovery_enabled: bool = True,
        selection_strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN,
        preferred_instance_id: str | None = None,
    ) -> Any:
        """Call RPC method on another service.

        Args:
            request: The RPCRequest object containing method, params, and target
            discovery_enabled: Whether to use service discovery (default: True)
            selection_strategy: Instance selection strategy (default: ROUND_ROBIN)
            preferred_instance_id: Preferred instance for sticky selection

        Returns:
            RPC response result

        Raises:
            Exception: If RPC call fails or no healthy instances available
        """
        # Ensure request has source set
        if request.source is None:
            request.source = self.instance_id

        target = request.target
        original_service_name = target

        # Use service discovery if enabled and available
        if discovery_enabled and self._discovery and target and await self._is_service_name(target):
            instance = await self._discovery.select_instance(
                target,
                strategy=selection_strategy,
                preferred_instance_id=preferred_instance_id,
            )
            if not instance:
                raise ServiceUnavailableError(target)

            # For discovery-enabled calls, we keep the service name in the request
            # so the NATSAdapter can construct the correct RPC subject
            # The actual routing to the instance is handled by NATS

            if self._logger:
                self._logger.debug(
                    "Selected instance for RPC",
                    service=original_service_name,
                    instance=instance.instance_id,
                    method=request.method,
                )

        try:
            response = await self._bus.call_rpc(request)
            if not response.success:
                raise Exception(f"RPC failed: {response.error}")
            return response.result
        except Exception:
            # Invalidate cache on any failure if using discovery
            if (
                discovery_enabled
                and self._discovery
                and original_service_name
                and await self._is_service_name(original_service_name)
            ):
                await self._discovery.invalidate_cache(original_service_name)
            raise

    def create_rpc_request(
        self,
        service: str,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> RPCRequest:
        """Factory method to create an RPCRequest object.

        Args:
            service: Target service name or instance ID
            method: RPC method name
            params: Optional method parameters
            timeout: Request timeout in seconds (default: 5.0)

        Returns:
            RPCRequest: A properly constructed RPCRequest instance
        """
        return RPCRequest(
            method=method,
            params=params or {},
            source=self.instance_id,
            target=service,
            timeout=timeout,
        )

    async def _is_service_name(self, target: str) -> bool:
        """Check if target is a service name vs instance ID.

        This method checks:
        1. If the target is a valid service name format
        2. If service discovery is available, check if it's a registered service
        3. Otherwise, check if it matches our instance naming pattern

        Args:
            target: The target string to check

        Returns:
            bool: True if it's a service name, False if it's an instance ID
        """
        # First check if it's a valid service name format
        if not SubjectPatterns.is_valid_service_name(target):
            return False

        # If we have service discovery, check if it's a known service
        if self._discovery:
            try:
                instances = await self._discovery.discover_instances(target)
                if instances:
                    # It's a known service name
                    return True
            except Exception:
                # If discovery fails, fall back to pattern matching
                pass

        # Check if it matches an instance ID pattern
        # Instance IDs are typically: "{service_name}-{uuid_hex}"
        # Look for pattern: service-name followed by dash and hex chars
        parts = target.split("-")
        if len(parts) >= 2:
            # Get the last part after the last dash
            potential_uuid = parts[-1]
            # Check if it looks like a UUID hex (8+ hex chars)
            if len(potential_uuid) >= 8 and all(
                c in "0123456789abcdef" for c in potential_uuid.lower()
            ):
                return False  # Looks like an instance ID

        # Default to treating it as a service name
        return True

    # Event Methods
    def subscribe(
        self, pattern: str, mode: SubscriptionMode | str = SubscriptionMode.COMPETE
    ) -> Callable[[EventHandler], EventHandler]:
        """Decorator to subscribe to events.

        Args:
            pattern: Event pattern to subscribe to
            mode: "compete" (default) - load balanced, only one instance processes
                  "broadcast" - all instances receive the event

        Example:
            @service.subscribe("order.*")
            async def handle_order_event(event: Event):
                print(f"Order event: {event.event_type}")

            @service.subscribe("config.updated", mode="broadcast")
            async def handle_config_update(event: Event):
                print("Config updated on all instances")
        """
        # Validate event pattern
        if not SubjectPatterns.is_valid_event_pattern(pattern):
            raise ValueError(f"Invalid event pattern: {pattern}")

        # Validate mode
        if isinstance(mode, str):
            try:
                mode = SubscriptionMode(mode)
            except ValueError:
                valid_modes = [m.value for m in SubscriptionMode]
                raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}") from None

        def decorator(handler: EventHandler) -> EventHandler:
            with self._handler_lock:
                if pattern not in self._event_handlers:
                    self._event_handlers[pattern] = []
                self._event_handlers[pattern].append((handler, mode.value))

            return handler

        return decorator

    def unsubscribe(self, pattern: str, handler: EventHandler | None = None) -> bool:
        """Unsubscribe from event pattern.

        Args:
            pattern: Event pattern to unsubscribe from
            handler: Specific handler to remove. If None, removes all handlers for the pattern.

        Returns:
            bool: True if any handlers were removed, False otherwise

        Example:
            # Remove specific handler
            service.unsubscribe("order.*", handle_order_event)

            # Remove all handlers for a pattern
            service.unsubscribe("order.*")
        """
        with self._handler_lock:
            if pattern not in self._event_handlers:
                return False

            if handler is None:
                # Remove all handlers for this pattern
                del self._event_handlers[pattern]
                return True
            else:
                # Remove specific handler
                handlers = self._event_handlers[pattern]
                original_count = len(handlers)

                # Filter out the specific handler (comparing by function reference)
                self._event_handlers[pattern] = [(h, mode) for h, mode in handlers if h != handler]

                # If no handlers left, remove the pattern entry
                if not self._event_handlers[pattern]:
                    del self._event_handlers[pattern]

                # Return True if any handler was removed
                return len(self._event_handlers.get(pattern, [])) < original_count

    async def publish_event(self, event: Event) -> None:
        """Publish a domain event.

        Args:
            event: The Event object to publish. Must be a properly constructed Event instance.

        Raises:
            RuntimeError: If service is not in an operational state
        """
        if not self.is_operational():
            raise RuntimeError(
                f"Cannot publish events while service is in {self._lifecycle_state.value} state"
            )
        # Ensure the event has the correct source
        if event.source is None:
            event.source = self.instance_id

        await self._bus.publish_event(event)

    def create_event(
        self, domain: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> Event:
        """Factory method to create an Event object.

        Args:
            domain: The event domain
            event_type: The event type
            payload: Optional event payload

        Returns:
            Event: A properly constructed Event instance with source set to this instance
        """
        return Event(
            domain=domain,
            event_type=event_type,
            payload=payload or {},
            source=self.instance_id,
        )

    # Command Methods
    def command(self, command_name: str) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register command handler.

        Example:
            @service.command("process_batch")
            async def process_batch(cmd: Command, progress: Callable):
                for i in range(10):
                    await progress(i * 10, "Processing...")
                return {"processed": 10}
        """

        def decorator(handler: CommandHandler) -> CommandHandler:
            with self._handler_lock:
                self._command_handlers[command_name] = handler

            # Registration will happen in start()

            return handler

        return decorator

    def unregister_command(self, command_name: str) -> bool:
        """Unregister a command handler.

        Args:
            command_name: The command name to unregister

        Returns:
            bool: True if the handler was removed, False if not found
        """
        with self._handler_lock:
            if command_name in self._command_handlers:
                del self._command_handlers[command_name]
                return True
            return False

    async def send_command(
        self,
        command: Command,
        track_progress: bool = True,
    ) -> dict[str, Any]:
        """Send command to another service.

        Args:
            command: The Command object to send. Must be a properly constructed Command instance.
            track_progress: Whether to track command execution progress (default: True)

        Returns:
            dict: Command execution result
        """
        # Ensure command has source set
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
        """Factory method to create a Command object.

        Args:
            service: Target service name
            command_name: Command name
            payload: Optional command payload
            priority: Command priority (low, normal, high, critical)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Command timeout in seconds (default: 300.0)

        Returns:
            Command: A properly constructed Command instance
        """
        # Validate priority
        if isinstance(priority, str):
            try:
                priority = CommandPriority(priority)
            except ValueError:
                valid_priorities = [p.value for p in CommandPriority]
                raise ValueError(
                    f"Invalid priority: {priority}. Must be one of {valid_priorities}"
                ) from None

        # Validate max_retries
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if max_retries > 100:
            raise ValueError("max_retries cannot exceed 100")

        # Validate timeout
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if timeout > 3600:  # 1 hour
            raise ValueError("timeout cannot exceed 3600 seconds (1 hour)")

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
                    # Fallback for development/debugging
                    print(
                        f"❌ Heartbeat error ({consecutive_failures}/{max_consecutive_failures}): {e}"
                    )

                # If too many consecutive failures, mark service as unhealthy
                if consecutive_failures >= max_consecutive_failures:
                    self.set_status(ServiceStatus.UNHEALTHY)

                # Exponential backoff with jitter for retries
                base_backoff = min(2**consecutive_failures, 10)
                jitter = random.uniform(0, 1)
                backoff = base_backoff + jitter
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

    def is_healthy(self) -> bool:
        """Check if the service is healthy.

        A service is considered healthy if:
        1. It has started (has a start time)
        2. Its status is not UNHEALTHY or SHUTDOWN
        3. The shutdown event has not been set
        4. The lifecycle state is STARTED

        Returns:
            bool: True if service is healthy, False otherwise
        """
        if not self._start_time:
            return False

        if self._shutdown_event.is_set():
            return False

        if self._lifecycle_state != ServiceLifecycleState.STARTED:
            return False

        return self._info.status not in (
            ServiceStatus.UNHEALTHY.value,
            ServiceStatus.SHUTDOWN.value,
        )

    def set_status(self, status: ServiceStatus | str) -> None:
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
        # Validate status
        if isinstance(status, str):
            try:
                status = ServiceStatus(status)
            except ValueError:
                valid_statuses = [s.value for s in ServiceStatus]
                raise ValueError(
                    f"Invalid status: {status}. Must be one of {valid_statuses}"
                ) from None

        # Update local info
        self._info.status = status.value

        # Update domain model
        if self._service_instance:
            self._service_instance.status = status.value

        # Log status change
        if not self._logger and status == ServiceStatus.UNHEALTHY:
            # Fallback for development/debugging when marking unhealthy
            print(f"⚠️  Service marked as UNHEALTHY: {self.service_name}/{self.instance_id}")

        # Schedule registry update if enabled
        if self._enable_registration and self._registry and self._service_instance:
            # Create a tracked task for proper cleanup
            if hasattr(self, "_status_update_task") and self._status_update_task:
                self._status_update_task.cancel()

            self._status_update_task = asyncio.create_task(
                self._update_registry_status(status), name=f"status_update_{status}"
            )

    async def _update_registry_status(self, status: ServiceStatus) -> None:
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

    async def on_started(self) -> None:
        """Hook called after service has successfully started.

        Override this method to perform actions after the service is fully started.
        """
        pass

    async def on_stop(self) -> None:
        """Hook called before service begins stopping.

        Override this method to perform cleanup before the service stops.
        """
        pass

    async def on_stopped(self) -> None:
        """Hook called after service has successfully stopped.

        Override this method to perform final cleanup after the service stops.
        """
        pass

    async def register_rpc_method(self, method: str, handler: RPCHandler) -> None:
        """Register an RPC method handler.

        Args:
            method: The method name
            handler: The handler function
        """
        if not SubjectPatterns.is_valid_method_name(method):
            raise ValueError(f"Invalid method name: {method}")
        self._rpc_handlers[method] = handler

    async def register_command_handler(self, command_name: str, handler: CommandHandler) -> None:
        """Register a command handler.

        Args:
            command_name: The command name
            handler: The handler function
        """
        self._command_handlers[command_name] = handler

    async def subscribe_event(
        self,
        domain: str,
        event_type: str,
        handler: EventHandler,
        mode: SubscriptionMode | str = SubscriptionMode.COMPETE,
    ) -> None:
        """Subscribe to an event pattern.

        Args:
            domain: The event domain
            event_type: The event type (can include wildcards)
            handler: The handler function
            mode: Subscription mode - "compete" (load balanced) or "broadcast" (all instances)
        """
        # Validate mode
        if isinstance(mode, str):
            try:
                mode = SubscriptionMode(mode)
            except ValueError:
                valid_modes = [m.value for m in SubscriptionMode]
                raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}") from None

        # Use the full event pattern that matches SubjectPatterns.event()
        pattern = SubjectPatterns.event(domain, event_type)
        if pattern not in self._event_handlers:
            self._event_handlers[pattern] = []
        self._event_handlers[pattern].append((handler, mode.value))
