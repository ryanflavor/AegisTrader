"""Single active service implementation for exclusive RPC execution.

This service provides leader election to ensure only one instance
processes exclusive RPC methods at a time. Sticky behavior is achieved
through client-side retry configuration, not a separate service class.
Follows hexagonal architecture with dependency injection.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from ..domain.value_objects import ServiceName
from ..ports.election_repository import ElectionRepository
from ..ports.factory_ports import ElectionRepositoryFactory, UseCaseFactory
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from ..ports.service_discovery import ServiceDiscoveryPort
from ..ports.service_registry import ServiceRegistryPort
from .dependency_provider import DependencyProvider
from .service import Service
from .single_active_dtos import ExclusiveRPCResponse, SingleActiveConfig, SingleActiveStatus
from .sticky_active_use_cases import (
    StickyActiveHeartbeatRequest,
    StickyActiveHeartbeatUseCase,
    StickyActiveMonitoringUseCase,
    StickyActiveRegistrationRequest,
    StickyActiveRegistrationUseCase,
)

if TYPE_CHECKING:
    pass


class SingleActiveService(Service):
    """Service with single active instance support for exclusive processing.

    Only one instance (leader) can execute exclusive RPC methods at a time.
    Sticky behavior is achieved when clients configure retry policies for
    NOT_ACTIVE errors, not through a separate service type.
    Follows hexagonal architecture with proper dependency injection.
    """

    def __init__(
        self,
        config: SingleActiveConfig,
        message_bus: MessageBusPort,
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
        election_repository: ElectionRepository | None = None,
        election_repository_factory: ElectionRepositoryFactory | None = None,
        use_case_factory: UseCaseFactory | None = None,
    ):
        """Initialize single active service with dependency injection.

        Args:
            config: Configuration for the single active service
            message_bus: Message bus implementation
            service_registry: Optional service registry implementation
            service_discovery: Optional service discovery implementation
            logger: Optional logger implementation
            metrics: Optional metrics implementation
            election_repository: Optional election repository (uses factory if not provided)
            election_repository_factory: Factory for creating election repository
            use_case_factory: Factory for creating use cases
        """
        # Generate instance ID if not provided
        instance_id = config.instance_id or f"{config.service_name}-{uuid.uuid4().hex[:8]}"

        # Initialize parent service
        super().__init__(
            service_name=config.service_name,
            message_bus=message_bus,
            instance_id=instance_id,
            version=config.version,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
            registry_ttl=config.registry_ttl,
            heartbeat_interval=config.heartbeat_interval,
            enable_registration=config.enable_registration,
        )

        # Store configuration
        self._config = config
        self.group_id = config.group_id
        self.leader_ttl_seconds = config.leader_ttl_seconds
        self.is_active = False

        # Dependencies and factories
        self._metrics = metrics
        self._election_repository = election_repository
        self._election_repository_factory = election_repository_factory
        self._use_case_factory = use_case_factory

        # Use cases (initialized in start())
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
            if self._election_repository_factory is None:
                # Use default factory from DependencyProvider
                self._election_repository_factory = (
                    DependencyProvider.get_default_election_factory()
                )

            self._election_repository = (
                await self._election_repository_factory.create_election_repository(
                    service_name=self.service_name.replace(
                        "-", "_"
                    ),  # Replace hyphens for KV bucket name
                    message_bus=self._bus,
                    logger=self._logger,
                )
            )

        # Initialize metrics if not provided
        if self._metrics is None:
            self._metrics = DependencyProvider.get_default_metrics()

        # Initialize use case factory if not provided
        if self._use_case_factory is None:
            # Use default factory from DependencyProvider
            self._use_case_factory = DependencyProvider.get_default_use_case_factory()

        # Create use cases using factory
        # Note: The factory methods should handle None values for optional dependencies
        self._registration_use_case = self._use_case_factory.create_registration_use_case(
            election_repository=self._election_repository,
            service_registry=self._registry,  # type: ignore[arg-type]
            message_bus=self._bus,
            metrics=self._metrics,
            logger=self._logger,  # type: ignore[arg-type]
        )

        self._heartbeat_use_case = self._use_case_factory.create_heartbeat_use_case(
            election_repository=self._election_repository,
            service_registry=self._registry,  # type: ignore[arg-type]
            metrics=self._metrics,
            logger=self._logger,  # type: ignore[arg-type]
        )

        self._monitoring_use_case = self._use_case_factory.create_monitoring_use_case(
            election_repository=self._election_repository,
            service_registry=self._registry,  # type: ignore[arg-type]
            message_bus=self._bus,
            metrics=self._metrics,
            logger=self._logger,  # type: ignore[arg-type]
            status_callback=self._update_active_status,
        )

        # Call parent start to register handlers
        await super().start()

        # Perform sticky active registration
        if self._config.enable_registration and self._registry:
            request = StickyActiveRegistrationRequest(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self._config.version,
                group_id=self._config.group_id,
                ttl_seconds=self._config.registry_ttl,
                leader_ttl_seconds=self._config.leader_ttl_seconds,
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
                        group_id=self._config.group_id,
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
                    self._config.group_id,
                    self._config.leader_ttl_seconds,
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
                self._config.group_id,
            )

        # Release leadership if we are the leader
        if self.is_active and self._election_repository:
            try:
                from ..domain.value_objects import InstanceId, ServiceName

                released = await self._election_repository.release_leadership(
                    ServiceName(value=self.service_name),
                    InstanceId(value=self.instance_id),
                    self._config.group_id,
                )

                if released and self._logger:
                    self._logger.info(
                        "Released leadership",
                        service=self.service_name,
                        instance=self.instance_id,
                        group_id=self._config.group_id,
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
        if hasattr(super(), "_update_registry_heartbeat"):
            await super()._update_registry_heartbeat()  # type: ignore[misc]

        # Then update sticky active heartbeat if we have the use case
        if self._heartbeat_use_case and self._config.enable_registration:
            request = StickyActiveHeartbeatRequest(
                service_name=self.service_name,
                instance_id=self.instance_id,
                group_id=self._config.group_id,
                ttl_seconds=self._config.registry_ttl,
                leader_ttl_seconds=self._config.leader_ttl_seconds,
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
                        group_id=self._config.group_id,
                    )

    def exclusive_rpc(self, method: str) -> Callable:
        """Instance method decorator for exclusive RPC handlers.

        This ensures only the active leader instance processes the RPC call.
        Returns standardized ExclusiveRPCResponse.
        """

        def decorator(handler: Callable) -> Callable:
            @wraps(handler)
            async def wrapper(params: dict) -> dict:
                if not self.is_active:
                    if self._metrics:
                        self._metrics.increment("sticky_active.rpc.not_active")

                    response = ExclusiveRPCResponse(
                        success=False,
                        error="NOT_ACTIVE",
                        message=(
                            f"This instance is not active. Instance {self.instance_id} "
                            f"is in STANDBY mode for group {self._config.group_id}."
                        ),
                    )
                    return response.model_dump()  # type: ignore[no-any-return]

                if self._metrics:
                    self._metrics.increment("sticky_active.rpc.processed")

                try:
                    result = await handler(params)
                    response = ExclusiveRPCResponse(
                        success=True,
                        result=result if isinstance(result, dict) else {"data": result},
                    )
                    return response.model_dump()  # type: ignore[no-any-return]
                except Exception as e:
                    if self._logger:
                        self._logger.exception(f"Error in exclusive RPC {method}: {e}")
                    response = ExclusiveRPCResponse(
                        success=False,
                        error="EXECUTION_ERROR",
                        message=str(e),
                    )
                    return response.model_dump()  # type: ignore[no-any-return]

            # Register with parent class's handler registry
            # This ensures the handler is properly registered with the message bus
            self._handler_registry._rpc_handlers[method] = wrapper
            return wrapper

        return decorator

    async def get_status(self) -> SingleActiveStatus:
        """Get the current status of the single active service.

        Returns:
            SingleActiveStatus with current service state
        """
        leader_id = None
        if self._election_repository:
            try:
                leader_instance, _ = await self._election_repository.get_current_leader(
                    ServiceName(value=self.service_name),
                    self._config.group_id,
                )
                leader_id = str(leader_instance) if leader_instance else None
            except Exception as e:
                if self._logger:
                    self._logger.warning(f"Failed to get leader info: {e}")

        return SingleActiveStatus(
            service_name=self.service_name,
            instance_id=self.instance_id,
            group_id=self._config.group_id,
            is_active=self.is_active,
            is_leader=self.is_active,
            leader_instance_id=leader_id,
            last_heartbeat=None,  # Could track this if needed
            metadata={
                "version": self._config.version,
                "leader_ttl": self._config.leader_ttl_seconds,
                "heartbeat_interval": self._config.heartbeat_interval,
            },
        )


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

                response = ExclusiveRPCResponse(
                    success=False,
                    error="NOT_ACTIVE",
                    message=(
                        f"This instance is not active. "
                        f"Instance {self.instance_id} is in STANDBY mode."
                    ),
                )
                return response.model_dump()  # type: ignore[no-any-return]

            try:
                result = await func(self, params)
                if not isinstance(result, dict) or "success" not in result:
                    # Wrap non-standard responses
                    response = ExclusiveRPCResponse(
                        success=True,
                        result=result if isinstance(result, dict) else {"data": result},
                    )
                    return response.model_dump()  # type: ignore[no-any-return]
                return result
            except Exception as e:
                if hasattr(self, "_logger") and self._logger:
                    self._logger.exception(f"Error in exclusive RPC: {e}")
                response = ExclusiveRPCResponse(
                    success=False,
                    error="EXECUTION_ERROR",
                    message=str(e),
                )
                return response.model_dump()  # type: ignore[no-any-return]

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
