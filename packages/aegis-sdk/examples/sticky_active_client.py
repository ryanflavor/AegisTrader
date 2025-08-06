"""Example client demonstrating sticky active pattern with DDD and hexagonal architecture.

This example shows how clients automatically handle NOT_ACTIVE errors
with exponential backoff and retry logic during failovers.
Follows DDD principles and hexagonal architecture.
"""

import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Protocol

from aegis_sdk.application.use_cases import RPCCallRequest, RPCCallUseCase
from aegis_sdk.domain.services import MessageRoutingService, MetricsNamingService
from aegis_sdk.domain.value_objects import RetryPolicy
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.config import NATSConnectionConfig, StickyActiveConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =======================
# Domain Layer
# =======================


@dataclass
class OrderRequest:
    """Value object representing an order request."""

    order_id: str
    amount: float

    def __post_init__(self):
        """Validate order request."""
        if not self.order_id:
            raise ValueError("Order ID is required")
        if self.amount <= 0:
            raise ValueError(f"Invalid order amount: {self.amount}")


@dataclass
class OrderResult:
    """Value object representing the result of an order processing."""

    order_id: str
    amount: float
    status: str
    processed_by: str
    total_processed: int
    processing_time: float


@dataclass
class ServiceStats:
    """Value object for service statistics."""

    instance_id: str
    orders_processed: int
    is_active: bool


@dataclass
class HealthStatus:
    """Value object for health check status."""

    instance_id: str
    status: str
    is_active: bool


# =======================
# Domain Ports
# =======================


class OrderServicePort(Protocol):
    """Port for interacting with the order processing service."""

    async def process_order(self, request: OrderRequest) -> OrderResult:
        """Process an order."""
        ...

    async def get_stats(self) -> ServiceStats:
        """Get service statistics."""
        ...

    async def health_check(self) -> list[HealthStatus]:
        """Check health of service instances."""
        ...


# =======================
# Application Layer - Use Cases
# =======================


class ProcessOrderClientUseCase:
    """Use case for processing orders from the client side."""

    def __init__(
        self,
        order_service: OrderServicePort,
        logger: Any,
        enable_metrics: bool = True,
    ):
        """Initialize the use case."""
        self.order_service = order_service
        self.logger = logger
        self.enable_metrics = enable_metrics

    async def execute(self, order_id: str, amount: float) -> OrderResult:
        """Process an order with retry logic.

        Args:
            order_id: The order ID to process
            amount: The order amount

        Returns:
            Processing result from the active service instance
        """
        start_time = time.time()

        try:
            # Create order request
            request = OrderRequest(order_id=order_id, amount=amount)

            # Process order through the service port
            result = await self.order_service.process_order(request)

            elapsed = time.time() - start_time
            self.logger.info(
                f"Order {order_id} processed successfully in {elapsed:.2f}s: "
                f"status={result.status}, processed_by={result.processed_by}"
            )

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"Failed to process order {order_id} after {elapsed:.2f}s: {e}")
            raise


class GetServiceStatsUseCase:
    """Use case for getting service statistics."""

    def __init__(self, order_service: OrderServicePort, logger: Any):
        """Initialize the use case."""
        self.order_service = order_service
        self.logger = logger

    async def execute(self) -> ServiceStats:
        """Get service statistics.

        Returns:
            Current statistics from the active instance
        """
        try:
            stats = await self.order_service.get_stats()
            self.logger.info(
                f"Stats from {stats.instance_id}: "
                f"orders_processed={stats.orders_processed}, "
                f"is_active={stats.is_active}"
            )
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            raise


class HealthCheckUseCase:
    """Use case for checking service health."""

    def __init__(self, order_service: OrderServicePort, logger: Any):
        """Initialize the use case."""
        self.order_service = order_service
        self.logger = logger

    async def execute(self) -> list[HealthStatus]:
        """Check health of all service instances.

        Returns:
            Health status from all available instances
        """
        try:
            statuses = await self.order_service.health_check()
            for status in statuses:
                self.logger.info(
                    f"Health check - Instance: {status.instance_id}, "
                    f"Status: {status.status}, Active: {status.is_active}"
                )
            return statuses
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return []


# =======================
# Infrastructure Layer - Adapters
# =======================


class RPCOrderServiceAdapter:
    """RPC adapter implementing OrderServicePort."""

    def __init__(
        self,
        rpc_use_case: RPCCallUseCase,
        retry_policy: RetryPolicy,
        caller_service: str = "order-client",
        caller_instance: str | None = None,
    ):
        """Initialize the adapter.

        Args:
            rpc_use_case: The RPC call use case
            retry_policy: Retry policy for handling NOT_ACTIVE errors
            caller_service: Name of the calling service
            caller_instance: Instance ID of the caller
        """
        self.rpc_use_case = rpc_use_case
        self.retry_policy = retry_policy
        self.caller_service = caller_service
        self.caller_instance = caller_instance or f"{caller_service}-{time.time()}"

    async def process_order(self, request: OrderRequest) -> OrderResult:
        """Process an order via RPC."""
        start_time = time.time()

        result = await self.rpc_use_case.execute(
            RPCCallRequest(
                target_service="order-processor",
                method="process_order",
                params={"order_id": request.order_id, "amount": request.amount},
                timeout=10.0,
                caller_service=self.caller_service,
                caller_instance=self.caller_instance,
                retry_policy=self.retry_policy,
            )
        )

        processing_time = time.time() - start_time

        return OrderResult(
            order_id=result["order_id"],
            amount=result["amount"],
            status=result["status"],
            processed_by=result["processed_by"],
            total_processed=result["total_processed"],
            processing_time=processing_time,
        )

    async def get_stats(self) -> ServiceStats:
        """Get service statistics via RPC."""
        result = await self.rpc_use_case.execute(
            RPCCallRequest(
                target_service="order-processor",
                method="get_stats",
                params={},
                timeout=5.0,
                caller_service=self.caller_service,
                caller_instance=self.caller_instance,
                retry_policy=self.retry_policy,
            )
        )

        return ServiceStats(
            instance_id=result["instance_id"],
            orders_processed=result["orders_processed"],
            is_active=result["is_active"],
        )

    async def health_check(self) -> list[HealthStatus]:
        """Check health of service instances via RPC."""
        # For health check, we don't use retry policy as all instances respond
        try:
            result = await self.rpc_use_case.execute(
                RPCCallRequest(
                    target_service="order-processor",
                    method="health_check",
                    params={},
                    timeout=5.0,
                    caller_service=self.caller_service,
                    caller_instance=self.caller_instance,
                    retry_policy=None,  # No retry for health check
                )
            )

            return [
                HealthStatus(
                    instance_id=result["instance_id"],
                    status=result["status"],
                    is_active=result["is_active"],
                )
            ]
        except Exception:
            return []


# =======================
# Application Orchestration
# =======================


class OrderClientOrchestrator:
    """Orchestrates order processing scenarios."""

    def __init__(
        self,
        process_order_use_case: ProcessOrderClientUseCase,
        get_stats_use_case: GetServiceStatsUseCase,
        health_check_use_case: HealthCheckUseCase,
        logger: Any,
    ):
        """Initialize the orchestrator."""
        self.process_order_use_case = process_order_use_case
        self.get_stats_use_case = get_stats_use_case
        self.health_check_use_case = health_check_use_case
        self.logger = logger

    async def simulate_orders(self, count: int = 10) -> None:
        """Simulate processing multiple orders.

        Args:
            count: Number of orders to process
        """
        self.logger.info(f"Starting to process {count} orders...")

        successful = 0
        failed = 0

        for i in range(count):
            order_id = f"ORD-{i + 1:04d}"
            amount = 100.0 + (i * 10)

            try:
                result = await self.process_order_use_case.execute(order_id, amount)
                self.logger.info(
                    f"Order {order_id} processed by {result.processed_by} "
                    f"in {result.processing_time:.2f}s"
                )
                successful += 1
            except Exception:
                failed += 1

            # Small delay between orders
            await asyncio.sleep(0.5)

        self.logger.info(f"Order processing complete: {successful} successful, {failed} failed")

        # Get final stats
        try:
            stats = await self.get_stats_use_case.execute()
            self.logger.info(
                f"Final stats - Instance: {stats.instance_id}, "
                f"Orders processed: {stats.orders_processed}"
            )
        except Exception:
            self.logger.error("Could not retrieve final stats")

    async def demonstrate_failover(self) -> None:
        """Demonstrate behavior during failover.

        This simulates what happens when the active instance fails
        and requests are automatically retried until a new active is elected.
        """
        self.logger.info("Demonstrating failover behavior...")
        self.logger.info("(Simulate by stopping the active service instance)")

        # Process orders continuously to see failover in action
        order_num = 1
        while order_num <= 20:
            order_id = f"FAIL-{order_num:04d}"

            try:
                self.logger.info(f"Processing order {order_id}...")
                result = await self.process_order_use_case.execute(order_id, 250.0)
                self.logger.info(f"Order processed by instance: {result.processed_by}")
            except Exception as e:
                self.logger.error(f"Order {order_id} failed completely: {e}")

            order_num += 1
            await asyncio.sleep(1)  # Process one order per second


# =======================
# Dependency Injection Container
# =======================


class ClientContainer:
    """Dependency injection container for the client application."""

    def __init__(self):
        """Initialize the container."""
        self.nats_adapter: NATSAdapter | None = None
        self.logger: SimpleLogger | None = None
        self.metrics: InMemoryMetrics | None = None
        self.orchestrator: OrderClientOrchestrator | None = None

    async def initialize(
        self,
        service_name: str = "order-client",
        nats_url: str = "nats://localhost:4222",
        sticky_config: StickyActiveConfig | None = None,
    ) -> OrderClientOrchestrator:
        """Initialize all dependencies and create the orchestrator.

        Args:
            service_name: Name of the client service
            nats_url: NATS server URL
            sticky_config: Configuration for sticky active retry behavior

        Returns:
            Configured OrderClientOrchestrator instance
        """
        # Bootstrap default dependencies
        bootstrap_defaults()

        # Use provided config or create default
        if sticky_config is None:
            sticky_config = StickyActiveConfig(
                max_retries=5,
                initial_retry_delay_ms=100,
                backoff_multiplier=2.0,
                max_retry_delay_ms=5000,
                jitter_factor=0.1,
                enable_debug_logging=True,
                enable_metrics=True,
            )

        # Create infrastructure components
        self.nats_adapter = NATSAdapter(config=NATSConnectionConfig())
        await self.nats_adapter.connect(nats_url)

        instance_id = f"{service_name}-{int(time.time())}"
        self.logger = SimpleLogger(instance_id)
        self.metrics = InMemoryMetrics()

        # Create domain services
        routing_service = MessageRoutingService()
        naming_service = MetricsNamingService()

        # Create RPC use case
        rpc_use_case = RPCCallUseCase(
            message_bus=self.nats_adapter,
            metrics=self.metrics,
            routing_service=routing_service,
            naming_service=naming_service,
            logger=self.logger,
        )

        # Convert config to retry policy
        retry_policy = sticky_config.to_retry_policy()

        # Create infrastructure adapter
        order_service_adapter = RPCOrderServiceAdapter(
            rpc_use_case=rpc_use_case,
            retry_policy=retry_policy,
            caller_service=service_name,
            caller_instance=instance_id,
        )

        # Create application use cases
        process_order_use_case = ProcessOrderClientUseCase(
            order_service=order_service_adapter,
            logger=self.logger,
            enable_metrics=sticky_config.enable_metrics,
        )

        get_stats_use_case = GetServiceStatsUseCase(
            order_service=order_service_adapter,
            logger=self.logger,
        )

        health_check_use_case = HealthCheckUseCase(
            order_service=order_service_adapter,
            logger=self.logger,
        )

        # Create orchestrator
        self.orchestrator = OrderClientOrchestrator(
            process_order_use_case=process_order_use_case,
            get_stats_use_case=get_stats_use_case,
            health_check_use_case=health_check_use_case,
            logger=self.logger,
        )

        return self.orchestrator

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.nats_adapter:
            await self.nats_adapter.disconnect()


# =======================
# Main Entry Point
# =======================


async def main():
    """Main entry point for the client application."""
    container = ClientContainer()
    orchestrator = None

    try:
        # Configure sticky active behavior
        sticky_config = StickyActiveConfig(
            max_retries=5,  # Retry up to 5 times
            initial_retry_delay_ms=100,  # Start with 100ms delay
            backoff_multiplier=2.0,  # Double the delay each time
            max_retry_delay_ms=5000,  # Cap at 5 seconds
            jitter_factor=0.1,  # Add 10% jitter
            enable_debug_logging=True,  # Enable debug logs
            enable_metrics=True,  # Track retry metrics
        )

        # Initialize client with dependency injection
        orchestrator = await container.initialize(
            service_name="order-client",
            nats_url="nats://localhost:4222",
            sticky_config=sticky_config,
        )

        logger.info("Order client started")

        # Check health of order processing service
        logger.info("Checking health of order processing service...")
        await orchestrator.health_check_use_case.execute()

        # Demonstrate different scenarios
        choice = input(
            "\nSelect demonstration:\n"
            "1. Process orders normally\n"
            "2. Demonstrate failover behavior\n"
            "3. Both\n"
            "Enter choice (1-3): "
        ).strip()

        if choice == "1":
            await orchestrator.simulate_orders(count=10)
        elif choice == "2":
            await orchestrator.demonstrate_failover()
        elif choice == "3":
            await orchestrator.simulate_orders(count=5)
            logger.info("\n--- Now demonstrating failover ---\n")
            await orchestrator.demonstrate_failover()
        else:
            logger.info("Invalid choice, processing orders normally...")
            await orchestrator.simulate_orders(count=5)

    finally:
        # Cleanup
        await container.cleanup()
        logger.info("Order client stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Client interrupted by user")
        sys.exit(0)
