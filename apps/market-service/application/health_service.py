"""
Extended Health Service for Market Service.

This service extends the SDK's health management capabilities with domain-specific
health checks, following hexagonal architecture and the Single Source of Truth principle.
It leverages SDK's infrastructure health management rather than duplicating it.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from aegis_sdk.application.service import Service
    from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

    from domain.ports import MarketDataGatewayRepository, MarketDataSource, TickDataRepository


class HealthCheckRequest(BaseModel):
    """Request model for health check."""

    model_config = ConfigDict(strict=True)
    timestamp: datetime | None = None


class InfrastructureHealth(BaseModel):
    """Infrastructure health status from SDK."""

    model_config = ConfigDict(strict=True)

    sdk_available: bool = Field(default=False, description="Whether SDK service is available")
    sdk_health_status: bool = Field(default=False, description="SDK's health manager status")
    message_bus_connected: bool = Field(default=False, description="NATS connection status")
    service_registry_connected: bool = Field(default=False, description="Registry connection")
    heartbeat_active: bool = Field(default=False, description="Heartbeat task active")
    consecutive_failures: int = Field(default=0, description="Consecutive heartbeat failures")


class DomainHealth(BaseModel):
    """Domain-specific health indicators."""

    model_config = ConfigDict(strict=True)

    active_gateways: int = Field(default=0, description="Number of active gateways")
    gateway_status: str = Field(default="unknown", description="Overall gateway status")
    market_source_connected: bool = Field(default=False, description="Market data source status")
    tick_repository_available: bool = Field(
        default=False, description="Tick repository availability"
    )


class HealthCheckResponse(BaseModel):
    """Extended health check response combining SDK and domain health."""

    model_config = ConfigDict(strict=True)

    status: str = Field(description="Overall health status: healthy, degraded, unhealthy")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    service_name: str
    version: str
    instance_id: str

    # Separated health concerns
    infrastructure_health: InfrastructureHealth
    domain_health: DomainHealth

    # Optional custom checks
    custom_checks: dict[str, Any] = Field(default_factory=dict)


class DomainHealthService:
    """
    Extended health service that leverages SDK's health management.

    This service extends rather than duplicates SDK functionality by:
    1. Using SDK's HealthManager for infrastructure health
    2. Adding domain-specific health checks
    3. Aggregating both for comprehensive health status
    """

    def __init__(
        self,
        service: Service | None = None,
        gateway_repo: MarketDataGatewayRepository | None = None,
        tick_repo: TickDataRepository | None = None,
        market_source: MarketDataSource | None = None,
        nats_adapter: NATSAdapter | None = None,
    ) -> None:
        """
        Initialize extended health service.

        Args:
            service: SDK Service instance (provides infrastructure health)
            gateway_repo: Repository for gateway health checks
            tick_repo: Repository for tick data health checks
            market_source: Market data source for connectivity checks
            nats_adapter: NATS adapter for message bus health
        """
        self._service = service
        self._gateway_repo = gateway_repo
        self._tick_repo = tick_repo
        self._market_source = market_source
        self._nats = nats_adapter
        self._custom_checks: dict[str, Callable[[], Coroutine[Any, Any, dict]]] = {}

    def add_custom_check(
        self, name: str, check_func: Callable[[], Coroutine[Any, Any, dict]]
    ) -> None:
        """
        Add a custom health check function.

        Args:
            name: Name of the health check
            check_func: Async function that returns health check result
        """
        self._custom_checks[name] = check_func

    async def health_check(self, request: HealthCheckRequest) -> HealthCheckResponse:
        """
        Perform comprehensive health check.

        This method:
        1. Retrieves infrastructure health from SDK's HealthManager
        2. Performs domain-specific health checks
        3. Runs any custom health checks
        4. Aggregates all health indicators

        Args:
            request: Health check request

        Returns:
            Extended health check response
        """
        # Get infrastructure health from SDK
        infrastructure_health = await self._get_infrastructure_health()

        # Perform domain-specific health checks
        domain_health = await self._get_domain_health()

        # Run custom checks
        custom_results = await self._run_custom_checks()

        # Aggregate health status
        overall_status = self._calculate_overall_status(infrastructure_health, domain_health)

        # Get service metadata from SDK or defaults
        service_name = self._service.service_name if self._service else "market-service"
        version = self._service.version if self._service else "unknown"
        instance_id = self._service.instance_id if self._service else "unknown"

        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.now(UTC),
            service_name=service_name,
            version=version,
            instance_id=instance_id,
            infrastructure_health=infrastructure_health,
            domain_health=domain_health,
            custom_checks=custom_results,
        )

    async def _get_infrastructure_health(self) -> InfrastructureHealth:
        """
        Get infrastructure health from SDK's health manager.

        Returns:
            Infrastructure health status
        """
        if not self._service:
            return InfrastructureHealth(sdk_available=False)

        # Leverage SDK's health manager
        sdk_health = False
        heartbeat_active = False
        consecutive_failures = 0

        if hasattr(self._service, "_health_manager"):
            health_manager = self._service._health_manager
            sdk_health = health_manager.is_healthy() if health_manager else False
            heartbeat_active = (
                hasattr(health_manager, "_heartbeat_task")
                and health_manager._heartbeat_task is not None
            )
            consecutive_failures = getattr(health_manager, "_consecutive_failures", 0)

        # Check message bus connection
        message_bus_connected = False
        if self._nats:
            try:
                message_bus_connected = self._nats.is_connected()
            except Exception:
                pass

        # Check service registry
        registry_connected = (
            hasattr(self._service, "_registry") and self._service._registry is not None
        )

        return InfrastructureHealth(
            sdk_available=True,
            sdk_health_status=sdk_health,
            message_bus_connected=message_bus_connected,
            service_registry_connected=registry_connected,
            heartbeat_active=heartbeat_active,
            consecutive_failures=consecutive_failures,
        )

    async def _get_domain_health(self) -> DomainHealth:
        """
        Perform domain-specific health checks.

        Returns:
            Domain health status
        """
        # Check gateway health
        active_gateways = 0
        gateway_status = "unknown"
        if self._gateway_repo:
            try:
                gateways = await self._gateway_repo.list_active()
                active_gateways = len(gateways)
                if active_gateways == 0:
                    gateway_status = "no_gateways"
                elif active_gateways == 1:
                    gateway_status = "single_gateway"
                else:
                    gateway_status = "multiple_gateways"
            except Exception:
                gateway_status = "error"

        # Check market source
        market_source_connected = False
        if self._market_source:
            try:
                market_source_connected = self._market_source.is_connected
            except Exception:
                pass

        # Check tick repository
        tick_repo_available = False
        if self._tick_repo:
            try:
                from domain.market_data import Symbol, TimeRange

                # Perform a simple health check query
                symbol = Symbol(value="HEALTHCHECK", exchange="TEST")
                time_range = TimeRange(
                    start=datetime.now(UTC),
                    end=datetime.now(UTC),
                )
                await self._tick_repo.count_ticks(symbol=symbol, time_range=time_range)
                tick_repo_available = True
            except Exception:
                pass

        return DomainHealth(
            active_gateways=active_gateways,
            gateway_status=gateway_status,
            market_source_connected=market_source_connected,
            tick_repository_available=tick_repo_available,
        )

    async def _run_custom_checks(self) -> dict[str, Any]:
        """
        Run all registered custom health checks.

        Returns:
            Dictionary of custom check results
        """
        results = {}
        for name, check_func in self._custom_checks.items():
            try:
                results[name] = await check_func()
            except Exception as e:
                results[name] = {"error": str(e)}
        return results

    def _calculate_overall_status(
        self, infrastructure: InfrastructureHealth, domain: DomainHealth
    ) -> str:
        """
        Calculate overall health status based on all indicators.

        Priority:
        1. If SDK is unavailable or unhealthy -> unhealthy
        2. If message bus is down -> unhealthy
        3. If domain components are degraded -> degraded
        4. Otherwise -> healthy

        Args:
            infrastructure: Infrastructure health status
            domain: Domain health status

        Returns:
            Overall status: "healthy", "degraded", or "unhealthy"
        """
        # Critical: SDK must be healthy
        if not infrastructure.sdk_available or not infrastructure.sdk_health_status:
            return "unhealthy"

        # Critical: Message bus must be connected
        if not infrastructure.message_bus_connected:
            return "unhealthy"

        # Degraded: Domain components not fully operational
        if not domain.tick_repository_available or not domain.market_source_connected:
            return "degraded"

        # Degraded: No active gateways
        if domain.active_gateways == 0:
            return "degraded"

        return "healthy"

    async def get_domain_metrics(self) -> dict[str, Any]:
        """
        Get domain-specific metrics.

        Returns:
            Dictionary of domain metrics
        """
        domain_health = await self._get_domain_health()
        return {
            "gateways": {
                "active_count": domain_health.active_gateways,
                "status": domain_health.gateway_status,
            },
            "market_source": {
                "connected": domain_health.market_source_connected,
            },
            "tick_repository": {
                "available": domain_health.tick_repository_available,
            },
        }

    async def get_infrastructure_metrics(self) -> dict[str, Any]:
        """
        Get infrastructure metrics from SDK.

        Returns:
            Dictionary of infrastructure metrics
        """
        metrics: dict[str, Any] = {}

        # Get SDK metrics if available
        if self._service and hasattr(self._service, "get_metrics"):
            metrics["sdk_metrics"] = self._service.get_metrics()

        # Get heartbeat metrics
        if self._service and hasattr(self._service, "_health_manager"):
            health_manager = self._service._health_manager
            metrics["heartbeat"] = {
                "active": health_manager._heartbeat_task is not None if health_manager else False,
                "consecutive_failures": getattr(health_manager, "_consecutive_failures", 0),
            }

        return metrics
