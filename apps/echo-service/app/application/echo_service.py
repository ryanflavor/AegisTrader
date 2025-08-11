"""Application service for the Echo Service.

This service extends the SDK's Service base class to leverage built-in
heartbeat management, handler registration, and lifecycle management.
Fully integrated with aegis-sdk without any legacy code.
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_sdk.application.service import Service

from ..domain.models import (
    EchoMode,
    EchoRequest,
)
from ..domain.services import EchoProcessor, MetricsCollector
from .use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase

logger = logging.getLogger(__name__)


class EchoApplicationService(Service):
    """Application service that orchestrates echo service functionality.

    Fully integrated with SDK's Service base class for complete lifecycle management.
    """

    def __init__(self, *args, **kwargs):
        """Initialize echo service with SDK base class."""
        super().__init__(*args, **kwargs)

        # Initialize domain services
        self._processor = EchoProcessor(self.instance_id)
        self._metrics = MetricsCollector()

        # Initialize use cases
        self._echo_use_case = EchoUseCase(self._processor, self._metrics)
        self._metrics_use_case = GetMetricsUseCase(self.instance_id, self.version, self._metrics)
        self._health_use_case = HealthCheckUseCase(self.instance_id, self.version)

    async def on_start(self) -> None:
        """Called when service is starting.

        Registers handlers using SDK's handler registry.
        """
        # Register RPC handlers using SDK's handler registry
        await self.register_rpc_method("echo", self._handle_echo)
        await self.register_rpc_method("batch_echo", self._handle_batch_echo)
        await self.register_rpc_method("metrics", self._handle_metrics)
        await self.register_rpc_method("health", self._handle_health)
        await self.register_rpc_method("ping", self._handle_ping)

        # Update health status
        self._health_use_case.set_nats_status(True)

        logger.info(
            f"Echo Service started:\n"
            f"  Instance: {self.instance_id}\n"
            f"  Version: {self.version}\n"
            f"  Service Name: {self.service_name}\n"
            f"  Heartbeat Interval: {self._config.heartbeat_interval}s\n"
            f"  Registry TTL: {self._config.registry_ttl}s\n"
            f"  RPC Endpoints: echo, batch_echo, metrics, health, ping"
        )

    async def on_stop(self) -> None:
        """Called when service is stopping."""
        # Update health status
        self._health_use_case.set_nats_status(False)

        # Log final metrics
        final_metrics = await self._metrics_use_case.execute()
        total_requests = max(final_metrics.total_requests, 1)
        success_rate = (final_metrics.successful_requests / total_requests) * 100

        logger.info(
            f"Echo Service stopped - Final Metrics:\n"
            f"  Total Requests: {final_metrics.total_requests}\n"
            f"  Success Rate: {success_rate:.1f}%\n"
            f"  Average Latency: {final_metrics.average_latency_ms:.2f}ms\n"
            f"  Uptime: {final_metrics.uptime_seconds:.1f}s"
        )

    async def _handle_echo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle echo requests with multiple modes.

        Args:
            params: Request parameters

        Returns:
            Echo response
        """
        # Parse request
        mode = EchoMode(params.get("mode", EchoMode.SIMPLE.value))
        metadata = params.get("metadata")
        request = EchoRequest(
            message=params.get("message", ""),
            mode=mode,
            delay=params.get("delay", 0),
            metadata=metadata if metadata is not None else {},
        )

        # Process echo
        response = await self._echo_use_case.execute(request)

        # Return response
        return {
            "echo": response.echo,
            "timestamp": response.timestamp,
            "instance_id": response.instance_id,
            "mode": response.mode.value,
            "processing_time_ms": response.processing_time_ms,
        }

    async def _handle_batch_echo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle batch echo requests.

        Args:
            params: Request parameters with messages array

        Returns:
            Batch response
        """
        messages = params.get("messages", [])
        mode = EchoMode(params.get("mode", EchoMode.NORMAL.value))

        responses = []
        for message in messages:
            request = EchoRequest(message=message, mode=mode)
            response = await self._echo_use_case.execute(request)
            responses.append(
                {
                    "echo": response.echo,
                    "timestamp": response.timestamp,
                    "processing_time_ms": response.processing_time_ms,
                }
            )

        return {
            "responses": responses,
            "instance_id": self.instance_id,
            "total_messages": len(messages),
        }

    async def _handle_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle metrics requests.

        Args:
            params: Request parameters (unused)

        Returns:
            Service metrics
        """
        metrics = await self._metrics_use_case.execute()
        return {
            "instance_id": metrics.instance_id,
            "version": metrics.version,
            "uptime_seconds": metrics.uptime_seconds,
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "average_latency_ms": metrics.average_latency_ms,
        }

    async def _handle_health(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle health check requests.

        Args:
            params: Request parameters (unused)

        Returns:
            Health status
        """
        health = await self._health_use_case.execute()
        return {
            "status": health.status,
            "instance_id": health.instance_id,
            "version": health.version,
            "checks": health.checks,
        }

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ping requests for connectivity checks.

        Args:
            params: Request parameters

        Returns:
            Pong response
        """
        return {
            "pong": True,
            "instance_id": self.instance_id,
            "service": self.service_name,
            "timestamp": params.get("timestamp"),
        }
