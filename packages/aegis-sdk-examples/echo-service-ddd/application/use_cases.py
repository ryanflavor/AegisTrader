"""Use cases for Echo Service application layer.

This module contains the application-level use cases that orchestrate domain logic.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from domain.entities import BatchEchoRequest, EchoRequest, ServiceMetrics
from domain.repositories import ServiceRegistrationRepository
from domain.services import EchoProcessor, HealthChecker, MetricsCollector, PriorityManager
from domain.value_objects import EchoMode, MessagePriority

logger = logging.getLogger(__name__)


class EchoUseCase:
    """Use case for processing echo requests.

    Orchestrates the echo processing workflow including
    validation, processing, and metrics collection.
    """

    def __init__(
        self,
        echo_processor: EchoProcessor,
        metrics_collector: MetricsCollector,
        priority_manager: PriorityManager | None = None,
    ):
        """Initialize the echo use case.

        Args:
            echo_processor: Domain service for echo processing
            metrics_collector: Domain service for metrics collection
            priority_manager: Optional priority management service
        """
        self.echo_processor = echo_processor
        self.metrics_collector = metrics_collector
        self.priority_manager = priority_manager or PriorityManager()

    async def execute(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the echo use case.

        Args:
            request_data: Raw request data

        Returns:
            Response data dictionary
        """
        try:
            # Create domain entity from request data
            request = EchoRequest(**request_data)

            # Check if request should be prioritized
            if self.priority_manager.should_prioritize(request):
                logger.info(f"Processing high priority request: {request.request_id}")

            # Process the echo request
            response = await self.echo_processor.process_echo(request)

            # Record metrics
            self.metrics_collector.record_request(
                mode=request.mode,
                priority=request.priority,
                latency_ms=response.processing_time_ms,
                success=True,
            )

            # Convert response to dict
            return response.model_dump()

        except Exception as e:
            logger.error(f"Error processing echo request: {e}")

            # Record failed request in metrics
            if "request" in locals():
                self.metrics_collector.record_request(
                    mode=request.mode if hasattr(request, "mode") else EchoMode.SIMPLE,
                    priority=(
                        request.priority if hasattr(request, "priority") else MessagePriority.NORMAL
                    ),
                    latency_ms=0.0,
                    success=False,
                )

            raise

    async def execute_batch(self, batch_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute batch echo processing.

        Args:
            batch_data: Batch request data

        Returns:
            List of response dictionaries
        """
        try:
            # Convert string priority to enum if needed
            if "priority" in batch_data and isinstance(batch_data["priority"], str):
                batch_data["priority"] = MessagePriority(batch_data["priority"])

            # Convert request data to EchoRequest objects
            if "requests" in batch_data:
                requests = []
                for req_data in batch_data["requests"]:
                    requests.append(EchoRequest(**req_data))
                batch_data["requests"] = requests

            # Create batch entity
            batch_request = BatchEchoRequest(**batch_data)

            # Sort requests by priority if priority manager is available
            sorted_requests = self.priority_manager.sort_by_priority(batch_request.requests)

            # Process batch
            responses = await self.echo_processor.process_batch(sorted_requests)

            # Record metrics for each processed request
            for req, resp in zip(sorted_requests, responses):
                self.metrics_collector.record_request(
                    mode=req.mode,
                    priority=req.priority,
                    latency_ms=resp.processing_time_ms,
                    success=True,
                )

            # Convert responses to dicts
            return [resp.model_dump() for resp in responses]

        except Exception as e:
            logger.error(f"Error processing batch echo request: {e}")
            raise


class GetMetricsUseCase:
    """Use case for retrieving service metrics.

    Handles metrics retrieval and formatting for presentation.
    """

    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize the metrics use case.

        Args:
            metrics_collector: Domain service for metrics collection
        """
        self.metrics_collector = metrics_collector

    async def execute(self) -> dict[str, Any]:
        """Execute the get metrics use case.

        Returns:
            Metrics summary dictionary
        """
        try:
            # Get current metrics from collector
            metrics_summary = self.metrics_collector.get_metrics_summary()

            # Add additional computed metrics
            metrics = self.metrics_collector.get_current_metrics()
            metrics_summary.update(
                {
                    "failed_requests": metrics.failed_requests,
                    "last_request_at": (
                        metrics.last_request_at.isoformat() if metrics.last_request_at else None
                    ),
                }
            )

            return metrics_summary

        except Exception as e:
            logger.error(f"Error retrieving metrics: {e}")
            raise

    async def get_detailed_metrics(self) -> ServiceMetrics:
        """Get detailed metrics entity.

        Returns:
            ServiceMetrics entity with full details
        """
        return self.metrics_collector.get_current_metrics()


class HealthCheckUseCase:
    """Use case for health checking.

    Orchestrates health checks across all service components.
    """

    def __init__(
        self,
        health_checker: HealthChecker,
        metrics_collector: MetricsCollector | None = None,
        registration_repository: ServiceRegistrationRepository | None = None,
    ):
        """Initialize the health check use case.

        Args:
            health_checker: Domain service for health checking
            metrics_collector: Optional metrics collector for health assessment
            registration_repository: Optional registration repository for registration status
        """
        self.health_checker = health_checker
        self.metrics_collector = metrics_collector
        self.registration_repository = registration_repository

    async def execute(self) -> dict[str, Any]:
        """Execute the health check use case.

        Returns:
            Health status dictionary
        """
        try:
            # Check external dependencies
            await self.health_checker.check_dependencies()

            # Add metrics-based health check if available
            if self.metrics_collector:
                metrics = self.metrics_collector.get_current_metrics()
                success_rate = metrics.get_success_rate()

                # Consider unhealthy if success rate is below 50%
                self.health_checker.add_check("metrics", success_rate >= 50.0)

            # Check registration status if repository is available
            if self.registration_repository:
                try:
                    registrations = await self.registration_repository.find_active_instances()
                    is_registered = len(registrations) > 0
                    self.health_checker.add_check("registration", is_registered)
                except Exception:
                    self.health_checker.add_check("registration", False)

            # Get overall health status
            health_status = self.health_checker.get_health_status()

            # Add additional context
            if self.metrics_collector:
                health_status["metrics"] = {
                    "total_requests": self.metrics_collector.metrics.total_requests,
                    "success_rate": metrics.get_success_rate(),
                    "uptime_seconds": self.metrics_collector.metrics.uptime_seconds,
                }

            return health_status

        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            # Return unhealthy status on error
            return {
                "status": "unhealthy",
                "instance_id": self.health_checker.instance_id,
                "version": self.health_checker.version,
                "error": str(e),
            }


class ServiceRegistrationUseCase:
    """Use case for service registration.

    Handles registration with the monitor-api service.
    """

    def __init__(self, registration_repository: ServiceRegistrationRepository):
        """Initialize the registration use case.

        Args:
            registration_repository: Repository for managing registrations
        """
        self.registration_repository = registration_repository

    async def register_service(self, registration_data: dict[str, Any]) -> dict[str, Any]:
        """Register the service with monitor-api.

        Args:
            registration_data: Service registration data

        Returns:
            Registration confirmation
        """
        try:
            # Create registration entity
            from domain.entities import ServiceRegistration
            from domain.value_objects import ServiceDefinitionInfo

            definition = ServiceDefinitionInfo(**registration_data["definition"])
            registration = ServiceRegistration(
                definition=definition,
                instance_id=registration_data["instance_id"],
                nats_url=registration_data["nats_url"],
            )

            # Save registration
            await self.registration_repository.register(registration)

            # Return confirmation
            return {
                "status": "registered",
                "instance_id": registration.instance_id,
                "service_name": registration.definition.service_name,
                "registered_at": registration.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error registering service: {e}")
            raise

    async def refresh_registration(self, instance_id: str) -> dict[str, Any]:
        """Refresh existing service registration.

        Args:
            instance_id: Instance identifier to refresh

        Returns:
            Refresh confirmation
        """
        try:
            success = await self.registration_repository.update_heartbeat(instance_id)

            if success:
                return {
                    "status": "refreshed",
                    "instance_id": instance_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            else:
                raise ValueError(f"Registration not found for instance: {instance_id}")

        except Exception as e:
            logger.error(f"Error refreshing registration: {e}")
            raise


class PingUseCase:
    """Simple ping use case for connectivity testing."""

    def __init__(self, instance_id: str):
        """Initialize the ping use case.

        Args:
            instance_id: Service instance identifier
        """
        self.instance_id = instance_id

    async def execute(self) -> dict[str, str]:
        """Execute the ping use case.

        Returns:
            Ping response with instance ID
        """
        return {"status": "pong", "instance_id": self.instance_id}
