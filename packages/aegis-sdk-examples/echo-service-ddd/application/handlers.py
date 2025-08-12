"""Command and Query handlers for Echo Service application layer.

Handlers orchestrate the execution of commands and queries.
"""

from __future__ import annotations

import logging
from typing import Any

from .commands import (
    ProcessBatchEchoCommand,
    ProcessEchoCommand,
    RefreshRegistrationCommand,
    RegisterServiceCommand,
    ResetMetricsCommand,
    UpdateHealthStatusCommand,
)
from .queries import (
    GetHealthQuery,
    GetLatencyStatsQuery,
    GetMetricsQuery,
    GetModeDistributionQuery,
    GetPriorityDistributionQuery,
    GetServiceInfoQuery,
    PingQuery,
)
from .use_cases import (
    EchoUseCase,
    GetMetricsUseCase,
    HealthCheckUseCase,
    PingUseCase,
    ServiceRegistrationUseCase,
)

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handler for processing commands.

    Routes commands to appropriate use cases.
    """

    def __init__(
        self,
        echo_use_case: EchoUseCase,
        registration_use_case: ServiceRegistrationUseCase | None = None,
        metrics_use_case: GetMetricsUseCase | None = None,
        health_use_case: HealthCheckUseCase | None = None,
    ):
        """Initialize the command handler.

        Args:
            echo_use_case: Use case for echo processing
            registration_use_case: Optional use case for service registration
            metrics_use_case: Optional use case for metrics
            health_use_case: Optional use case for health checks
        """
        self.echo_use_case = echo_use_case
        self.registration_use_case = registration_use_case
        self.metrics_use_case = metrics_use_case
        self.health_use_case = health_use_case

    async def handle_process_echo(self, command: ProcessEchoCommand) -> dict[str, Any]:
        """Handle echo processing command.

        Args:
            command: Process echo command

        Returns:
            Echo response data
        """
        request_data = command.model_dump(exclude={"correlation_id"})
        response = await self.echo_use_case.execute(request_data)

        # Add correlation ID if present
        if command.correlation_id:
            response["correlation_id"] = command.correlation_id

        return response

    async def handle_process_batch_echo(
        self, command: ProcessBatchEchoCommand
    ) -> list[dict[str, Any]]:
        """Handle batch echo processing command.

        Args:
            command: Process batch echo command

        Returns:
            List of echo responses
        """
        # Convert commands to request data
        requests_data = [cmd.model_dump(exclude={"correlation_id"}) for cmd in command.requests]

        batch_data = {
            "requests": requests_data,
            "batch_id": command.batch_id,
            "priority": command.priority,
        }

        responses = await self.echo_use_case.execute_batch(batch_data)

        # Add correlation ID to all responses if present
        if command.correlation_id:
            for response in responses:
                response["correlation_id"] = command.correlation_id

        return responses

    async def handle_register_service(self, command: RegisterServiceCommand) -> dict[str, Any]:
        """Handle service registration command.

        Args:
            command: Register service command

        Returns:
            Registration confirmation
        """
        if not self.registration_use_case:
            raise ValueError("Registration use case not available")

        registration_data = {
            "definition": {
                "service_name": command.service_name,
                "owner": command.owner,
                "description": command.description,
                "version": command.version,
            },
            "instance_id": command.instance_id,
            "nats_url": command.nats_url,
        }

        return await self.registration_use_case.register_service(registration_data)

    async def handle_refresh_registration(
        self, command: RefreshRegistrationCommand
    ) -> dict[str, Any]:
        """Handle registration refresh command.

        Args:
            command: Refresh registration command

        Returns:
            Refresh confirmation
        """
        if not self.registration_use_case:
            raise ValueError("Registration use case not available")

        return await self.registration_use_case.refresh_registration(command.instance_id)

    async def handle_reset_metrics(self, command: ResetMetricsCommand) -> dict[str, str]:
        """Handle metrics reset command.

        Args:
            command: Reset metrics command

        Returns:
            Reset confirmation
        """
        if not self.metrics_use_case:
            raise ValueError("Metrics use case not available")

        if not command.confirm:
            raise ValueError("Reset confirmation required")

        self.metrics_use_case.metrics_collector.reset_metrics()
        return {"status": "metrics_reset", "message": "All metrics have been reset"}

    async def handle_update_health_status(
        self, command: UpdateHealthStatusCommand
    ) -> dict[str, str]:
        """Handle health status update command.

        Args:
            command: Update health status command

        Returns:
            Update confirmation
        """
        if not self.health_use_case:
            raise ValueError("Health use case not available")

        self.health_use_case.health_checker.add_check(command.component, command.status)

        return {
            "status": "health_updated",
            "component": command.component,
            "healthy": command.status,
        }


class QueryHandler:
    """Handler for processing queries.

    Routes queries to appropriate use cases or services.
    """

    def __init__(
        self,
        metrics_use_case: GetMetricsUseCase,
        health_use_case: HealthCheckUseCase,
        ping_use_case: PingUseCase,
        service_info: dict[str, Any] | None = None,
    ):
        """Initialize the query handler.

        Args:
            metrics_use_case: Use case for metrics retrieval
            health_use_case: Use case for health checks
            ping_use_case: Use case for ping responses
            service_info: Optional service information
        """
        self.metrics_use_case = metrics_use_case
        self.health_use_case = health_use_case
        self.ping_use_case = ping_use_case
        self.service_info = service_info or {}

    async def handle_get_metrics(self, query: GetMetricsQuery) -> dict[str, Any]:
        """Handle get metrics query.

        Args:
            query: Get metrics query

        Returns:
            Metrics data
        """
        if query.detailed:
            metrics = await self.metrics_use_case.get_detailed_metrics()
            return metrics.model_dump()
        else:
            return await self.metrics_use_case.execute()

    async def handle_get_health(self, query: GetHealthQuery) -> dict[str, Any]:
        """Handle get health query.

        Args:
            query: Get health query

        Returns:
            Health status data
        """
        # Temporarily disable components if requested
        original_metrics = self.health_use_case.metrics_collector
        if not query.include_metrics:
            self.health_use_case.metrics_collector = None

        try:
            health_status = await self.health_use_case.execute()
        finally:
            # Restore original configuration
            self.health_use_case.metrics_collector = original_metrics

        return health_status

    async def handle_get_service_info(self, query: GetServiceInfoQuery) -> dict[str, Any]:
        """Handle get service info query.

        Args:
            query: Get service info query

        Returns:
            Service information
        """
        info = self.service_info.copy()

        if not query.include_version and "version" in info:
            del info["version"]

        if query.include_registration and self.health_use_case.registration_repository:
            try:
                registrations = (
                    await self.health_use_case.registration_repository.find_active_instances()
                )
                if registrations:
                    # Find registration for current instance
                    instance_id = self.ping_use_case.instance_id
                    registration = next(
                        (r for r in registrations if r.instance_id == instance_id), None
                    )
                    if registration:
                        info["registration"] = {
                            "registered": True,
                            "instance_id": registration.instance_id,
                            "registered_at": registration.created_at.isoformat(),
                        }
                    else:
                        info["registration"] = {"registered": False}
                else:
                    info["registration"] = {"registered": False}
            except Exception:
                info["registration"] = {"registered": False, "error": "Unable to check"}

        return info

    async def handle_get_mode_distribution(self, query: GetModeDistributionQuery) -> dict[str, Any]:
        """Handle get mode distribution query.

        Args:
            query: Get mode distribution query

        Returns:
            Mode distribution data
        """
        metrics = await self.metrics_use_case.get_detailed_metrics()
        distribution = {mode.value: count for mode, count in metrics.mode_distribution.items()}

        return {
            "distribution": distribution,
            "total_requests": metrics.total_requests,
            "time_window": query.time_window_seconds,
        }

    async def handle_get_priority_distribution(
        self, query: GetPriorityDistributionQuery
    ) -> dict[str, Any]:
        """Handle get priority distribution query.

        Args:
            query: Get priority distribution query

        Returns:
            Priority distribution data
        """
        metrics = await self.metrics_use_case.get_detailed_metrics()
        distribution = {
            priority.value: count for priority, count in metrics.priority_distribution.items()
        }

        return {
            "distribution": distribution,
            "total_requests": metrics.total_requests,
            "time_window": query.time_window_seconds,
        }

    async def handle_get_latency_stats(self, query: GetLatencyStatsQuery) -> dict[str, Any]:
        """Handle get latency statistics query.

        Args:
            query: Get latency stats query

        Returns:
            Latency statistics
        """
        metrics = await self.metrics_use_case.get_detailed_metrics()

        # For now, return average latency
        # In a full implementation, would track percentiles
        return {
            "average_ms": metrics.average_latency_ms,
            "total_requests": metrics.total_requests,
            "percentiles_requested": query.percentiles,
            "note": "Percentile calculation not yet implemented",
        }

    async def handle_ping(self, query: PingQuery) -> dict[str, str]:
        """Handle ping query.

        Args:
            query: Ping query

        Returns:
            Ping response
        """
        response = await self.ping_use_case.execute()

        if query.echo_message:
            response["echo"] = query.echo_message

        return response
