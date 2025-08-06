"""Single active service implementation for exclusive RPC execution.

This service uses the sticky active pattern with KV Store-based leader election
to ensure only one instance processes exclusive RPC methods at a time.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from ..infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from ..infrastructure.nats_kv_store import NATSKVStore
from ..ports.election_repository import ElectionRepository
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from ..ports.service_discovery import ServiceDiscoveryPort
from ..ports.service_registry import ServiceRegistryPort
from .service import Service
from .sticky_active_use_cases import (
    StickyActiveHeartbeatRequest,
    StickyActiveHeartbeatUseCase,
    StickyActiveMonitoringUseCase,
    StickyActiveRegistrationRequest,
    StickyActiveRegistrationUseCase,
)


class SingleActiveService(Service):
    """Service with single active instance support using sticky active pattern.

    Only one instance can execute exclusive RPC methods at a time.
    Uses KV Store-based leader election for robust failover and consistency.
    """

    def __init__(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
        registry_ttl: int = 30,
        heartbeat_interval: int = 10,
        enable_registration: bool = True,
        group_id: str = "default",
        leader_ttl_seconds: int = 5,
        election_repository: ElectionRepository | None = None,
    ):
        """Initialize single active service.

        Args:
            service_name: Name of the service
            message_bus: Message bus implementation
            instance_id: Optional instance ID (auto-generated if not provided)
            version: Service version
            service_registry: Optional service registry implementation
            service_discovery: Optional service discovery implementation
            logger: Optional logger implementation
            metrics: Optional metrics implementation
            registry_ttl: TTL for registry entries in seconds (default: 30)
            heartbeat_interval: Heartbeat interval in seconds (default: 10)
            enable_registration: Whether to enable service registration (default: True)
            group_id: Sticky active group identifier (default: "default")
            leader_ttl_seconds: TTL for leader key in seconds (default: 5)
            election_repository: Optional election repository (creates default if not provided)
        """
        super().__init__(
            service_name=service_name,
            message_bus=message_bus,
            instance_id=instance_id,
            version=version,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
            registry_ttl=registry_ttl,
            heartbeat_interval=heartbeat_interval,
            enable_registration=enable_registration,
        )

        # Sticky active configuration
        self.group_id = group_id
        self.leader_ttl_seconds = leader_ttl_seconds
        self.is_active = False

        # Dependencies
        self._metrics = metrics
        self._election_repository = election_repository

        # Use cases
        self._registration_use_case: StickyActiveRegistrationUseCase | None = None
        self._heartbeat_use_case: StickyActiveHeartbeatUseCase | None = None
        self._monitoring_use_case: StickyActiveMonitoringUseCase | None = None

        # Election state
        self._monitoring_task: asyncio.Task | None = None

    def _update_active_status(self, is_active: bool) -> None:
        """Callback for status updates from monitoring use case.

        Args:
            is_active: True if this instance is the active leader
        """
        self.is_active = is_active

    async def start(self) -> None:
        """Start service and sticky active election process."""
        # Initialize election repository if not provided
        if self._election_repository is None:
            kv_store = NATSKVStore(nats_adapter=self._bus)
            # Connect to KV store with a unique bucket name for elections
            await kv_store.connect(f"election_{self.service_name}", enable_ttl=True)
            self._election_repository = NatsKvElectionRepository(
                kv_store=kv_store,
                logger=self._logger,
            )

        # Initialize use cases with default implementations if not already set
        if self._metrics is None:
            from ..infrastructure.in_memory_metrics import InMemoryMetrics

            self._metrics = InMemoryMetrics()

        self._registration_use_case = StickyActiveRegistrationUseCase(
            election_repository=self._election_repository,
            service_registry=self._registry,
            message_bus=self._bus,
            metrics=self._metrics,
            logger=self._logger,
        )

        self._heartbeat_use_case = StickyActiveHeartbeatUseCase(
            election_repository=self._election_repository,
            service_registry=self._registry,
            metrics=self._metrics,
            logger=self._logger,
        )

        self._monitoring_use_case = StickyActiveMonitoringUseCase(
            election_repository=self._election_repository,
            service_registry=self._registry,
            message_bus=self._bus,
            metrics=self._metrics,
            logger=self._logger,
            status_callback=self._update_active_status,
        )

        # Call parent start to register handlers
        await super().start()

        # Perform sticky active registration
        if self._enable_registration and self._registry:
            request = StickyActiveRegistrationRequest(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                group_id=self.group_id,
                ttl_seconds=self._registry_ttl,
                leader_ttl_seconds=self.leader_ttl_seconds,
                metadata=self._service_instance.metadata if self._service_instance else {},
            )

            try:
                response = await self._registration_use_case.execute(request)
                self.is_active = response.is_leader

                if self._logger:
                    self._logger.info(
                        "Sticky active registration completed",
                        service=self.service_name,
                        instance=self.instance_id,
                        is_leader=response.is_leader,
                        group_id=self.group_id,
                    )
                else:
                    print(
                        f"✓ {self.instance_id} sticky active status: "
                        f"{'ACTIVE' if self.is_active else 'STANDBY'}"
                    )

                # Start monitoring for leadership changes
                await self._monitoring_use_case.start_monitoring(
                    self.service_name,
                    self.instance_id,
                    self.group_id,
                )
            except Exception as e:
                if self._logger:
                    self._logger.exception(f"Failed to register for sticky active election: {e}")
                raise

    async def stop(self) -> None:
        """Stop service and release leadership if held."""
        # Stop monitoring
        if self._monitoring_use_case:
            await self._monitoring_use_case.stop_monitoring(
                self.service_name,
                self.instance_id,
                self.group_id,
            )

        # Release leadership if we are the leader
        if self.is_active and self._election_repository:
            try:
                from ..domain.value_objects import InstanceId, ServiceName

                released = await self._election_repository.release_leadership(
                    ServiceName(value=self.service_name),
                    InstanceId(value=self.instance_id),
                    self.group_id,
                )

                if released and self._logger:
                    self._logger.info(
                        "Released leadership",
                        service=self.service_name,
                        instance=self.instance_id,
                        group_id=self.group_id,
                    )
            except Exception as e:
                if self._logger:
                    self._logger.warning(f"Failed to release leadership: {e}")

        # Always set is_active to False when stopping
        self.is_active = False

        await super().stop()

    async def _update_registry_heartbeat(self) -> None:
        """Override parent heartbeat to include sticky active heartbeat."""
        # First update the regular service heartbeat
        await super()._update_registry_heartbeat()

        # Then update sticky active heartbeat if we have the use case
        if self._heartbeat_use_case and self._enable_registration:
            request = StickyActiveHeartbeatRequest(
                service_name=self.service_name,
                instance_id=self.instance_id,
                group_id=self.group_id,
                ttl_seconds=self._registry_ttl,
                leader_ttl_seconds=self.leader_ttl_seconds,
            )

            success = await self._heartbeat_use_case.execute(request)

            # Update our active status based on heartbeat result
            if not success and self.is_active:
                self.is_active = False
                if self._logger:
                    self._logger.warning(
                        "Lost leadership during heartbeat",
                        service=self.service_name,
                        instance=self.instance_id,
                        group_id=self.group_id,
                    )

    def exclusive_rpc(self, method: str):
        """Instance method decorator for exclusive RPC handlers.

        This ensures only the active leader instance processes the RPC call.
        """

        def decorator(handler: Callable):
            @wraps(handler)
            async def wrapper(params: dict) -> dict:
                if not self.is_active:
                    if self._metrics:
                        self._metrics.increment("sticky_active.rpc.not_active")

                    return {
                        "success": False,
                        "error": "NOT_ACTIVE",
                        "message": (
                            f"This instance is not active. Instance {self.instance_id} "
                            f"is in STANDBY mode for group {self.group_id}."
                        ),
                    }

                if self._metrics:
                    self._metrics.increment("sticky_active.rpc.processed")

                result = await handler(params)
                return cast(dict[Any, Any], result)

            # Register with parent class
            self._rpc_handlers[method] = wrapper
            return wrapper

        return decorator


def exclusive_rpc(method: str | Callable[..., Any] | None = None) -> Callable[..., Any]:
    """Decorator to mark RPC methods that require single active instance.

    Can be used as:
    - @exclusive_rpc
    - @exclusive_rpc("method_name")

    Args:
        method: Either a string method name or the decorated function

    Returns:
        Decorated function that checks active status before execution
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: SingleActiveService, params: dict) -> dict:
            if isinstance(self, SingleActiveService) and not self.is_active:
                if hasattr(self, "_metrics") and self._metrics:
                    self._metrics.increment("sticky_active.rpc.not_active")

                return {
                    "success": False,
                    "error": "NOT_ACTIVE",
                    "message": (
                        f"This instance is not active. "
                        f"Instance {self.instance_id} is in STANDBY mode."
                    ),
                }

            result = await func(self, params)
            return cast(dict[Any, Any], result)

        # Mark as exclusive for registration
        wrapper_with_attr = cast(Any, wrapper)
        wrapper_with_attr._exclusive = True
        return wrapper

    # Handle both @exclusive_rpc and @exclusive_rpc("method_name")
    if callable(method):
        return decorator(method)

    def outer_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        wrapped = decorator(func)
        wrapped_with_attr = cast(Any, wrapped)
        wrapped_with_attr._rpc_method = method if isinstance(method, str) else None
        return wrapped

    return outer_decorator
