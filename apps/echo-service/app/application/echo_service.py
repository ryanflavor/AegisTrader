"""Application service for the Echo Service.

This service orchestrates the use cases and manages the application lifecycle,
decoupled from infrastructure concerns through dependency injection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..domain.models import EchoRequest
from ..domain.services import EchoProcessor, MetricsCollector
from ..ports.configuration import ConfigurationPort
from ..ports.service_bus import ServiceBusPort
from .use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase

logger = logging.getLogger(__name__)


class EchoApplicationService:
    """Application service that orchestrates echo service functionality."""

    def __init__(
        self,
        service_bus: ServiceBusPort,
        configuration: ConfigurationPort,
    ) -> None:
        """Initialize the echo application service.

        Args:
            service_bus: Port for service bus operations
            configuration: Port for configuration access
        """
        self._service_bus = service_bus
        self._configuration = configuration

        # Initialize domain services
        self._processor = EchoProcessor(configuration.get_instance_id())
        self._metrics = MetricsCollector()

        # Initialize use cases
        self._echo_use_case = EchoUseCase(self._processor, self._metrics)
        self._metrics_use_case = GetMetricsUseCase(
            configuration.get_instance_id(), configuration.get_service_version(), self._metrics
        )
        self._health_use_case = HealthCheckUseCase(
            configuration.get_instance_id(), configuration.get_service_version()
        )

        # Register RPC handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all RPC handlers with the service bus."""
        # Echo handler
        self._service_bus.register_rpc_handler("echo", self._handle_echo)

        # Batch echo handler
        self._service_bus.register_rpc_handler("batch_echo", self._handle_batch_echo)

        # Metrics handler
        self._service_bus.register_rpc_handler("metrics", self._handle_metrics)

        # Health handler
        self._service_bus.register_rpc_handler("health", self._handle_health)

        # Ping handler
        self._service_bus.register_rpc_handler("ping", self._handle_ping)

        logger.info("All RPC handlers registered")

    async def _handle_echo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle echo requests with multiple modes.

        Args:
            params: Request parameters

        Returns:
            Echo response
        """
        try:
            # Parse and validate request using Pydantic
            request = EchoRequest(**params)

            # Process through use case
            response = await self._echo_use_case.execute(request)

            # Update metrics
            self._metrics_use_case.update_last_request_time()

            # Return serialized response
            return response.model_dump()

        except ValueError as e:
            logger.error(f"Invalid echo request: {e}")
            return {
                "error": f"Invalid request: {str(e)}",
                "instance_id": self._configuration.get_instance_id(),
            }
        except Exception as e:
            logger.error(f"Error processing echo: {e}", exc_info=True)
            return {
                "error": str(e),
                "instance_id": self._configuration.get_instance_id(),
            }

    async def _handle_batch_echo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle batch echo requests.

        Args:
            params: Request parameters with messages list

        Returns:
            Batch processing results
        """
        messages = params.get("messages", [])
        results = []

        for msg in messages:
            try:
                request = EchoRequest(message=msg, mode="batch")
                response = await self._echo_use_case.execute(request)
                results.append(response.model_dump())
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                results.append({"error": str(e), "message": msg})

        return {
            "results": results,
            "count": len(results),
            "instance_id": self._configuration.get_instance_id(),
        }

    async def _handle_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get service metrics.

        Args:
            params: Request parameters (unused)

        Returns:
            Service metrics
        """
        try:
            metrics = await self._metrics_use_case.execute()
            return metrics.model_dump()
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {"error": str(e)}

    async def _handle_health(self, params: dict[str, Any]) -> dict[str, Any]:
        """Health check endpoint.

        Args:
            params: Request parameters (unused)

        Returns:
            Health status
        """
        try:
            health = await self._health_use_case.execute()
            return health.model_dump()
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return {
                "status": "error",
                "error": str(e),
                "instance_id": self._configuration.get_instance_id(),
            }

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Simple ping for connectivity check.

        Args:
            params: Request parameters

        Returns:
            Pong response
        """
        return {
            "pong": True,
            "instance_id": self._configuration.get_instance_id(),
            "timestamp": params.get("timestamp"),
        }

    async def start(self) -> None:
        """Start the application service."""
        logger.info(
            f"Starting Echo Application Service (Instance: {self._configuration.get_instance_id()})"
        )

        # Start the service bus
        await self._service_bus.start()

        # Update health status
        self._health_use_case.set_nats_status(self._service_bus.is_connected())

        logger.info(
            f"Echo Application Service started successfully:\n"
            f"  Instance: {self._configuration.get_instance_id()}\n"
            f"  Version: {self._configuration.get_service_version()}\n"
            f"  Service ID: {self._service_bus.get_instance_id()}\n"
            f"  Pattern: Load-Balanced (multiple active instances)\n"
            f"  RPC Endpoints:\n"
            f"    - echo: Process echo with multiple modes\n"
            f"    - batch_echo: Process multiple messages\n"
            f"    - metrics: Get service metrics\n"
            f"    - health: Health check\n"
            f"    - ping: Connectivity check"
        )

    async def stop(self) -> None:
        """Stop the application service."""
        logger.info(
            f"Stopping Echo Application Service (Instance: {self._configuration.get_instance_id()})"
        )

        # Update health status
        self._health_use_case.set_nats_status(False)

        # Stop the service bus
        await self._service_bus.stop()

        # Log final metrics
        final_metrics = await self._metrics_use_case.execute()
        total_requests = max(final_metrics.total_requests, 1)
        success_rate = (final_metrics.successful_requests / total_requests) * 100

        logger.info(
            f"Final Metrics:\n"
            f"  Total Requests: {final_metrics.total_requests}\n"
            f"  Success Rate: {success_rate:.1f}%\n"
            f"  Average Latency: {final_metrics.average_latency_ms:.2f}ms\n"
            f"  Uptime: {final_metrics.uptime_seconds:.1f}s"
        )
