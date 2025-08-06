"""Example service demonstrating sticky active pattern with hexagonal architecture.

This example shows how to create a service that uses the sticky active pattern
to ensure only one instance processes requests at a time, with automatic failover.
Follows DDD principles and hexagonal architecture.
"""

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import Any, Protocol

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
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
class Order:
    """Domain entity representing an order."""

    order_id: str
    amount: float
    status: str = "pending"
    processed_by: str | None = None


@dataclass
class OrderStats:
    """Value object for order processing statistics."""

    instance_id: str
    orders_processed: int
    is_active: bool


# =======================
# Domain Ports (Interfaces)
# =======================


class OrderRepositoryPort(Protocol):
    """Port for order persistence."""

    async def save(self, order: Order) -> None:
        """Save an order."""
        ...

    async def get(self, order_id: str) -> Order | None:
        """Get an order by ID."""
        ...

    async def count_processed(self) -> int:
        """Count processed orders."""
        ...


class OrderEventPublisherPort(Protocol):
    """Port for publishing order events."""

    async def publish_order_processed(self, order: Order) -> None:
        """Publish order processed event."""
        ...


# =======================
# Application Layer
# =======================


class ProcessOrderUseCase:
    """Use case for processing orders."""

    def __init__(
        self,
        repository: OrderRepositoryPort,
        event_publisher: OrderEventPublisherPort,
        instance_id: str,
    ):
        """Initialize the use case with required dependencies."""
        self.repository = repository
        self.event_publisher = event_publisher
        self.instance_id = instance_id

    async def execute(self, order_id: str, amount: float) -> dict[str, Any]:
        """Process an order.

        Args:
            order_id: The order ID to process
            amount: The order amount

        Returns:
            Processing result including order details and status
        """
        # Create order domain entity
        order = Order(
            order_id=order_id,
            amount=amount,
            status="processing",
            processed_by=self.instance_id,
        )

        # Business logic - validate order
        if amount <= 0:
            raise ValueError(f"Invalid order amount: {amount}")

        # Simulate processing
        await asyncio.sleep(0.5)

        # Update order status
        order.status = "processed"

        # Persist order
        await self.repository.save(order)

        # Publish domain event
        await self.event_publisher.publish_order_processed(order)

        # Get statistics
        total_processed = await self.repository.count_processed()

        return {
            "order_id": order.order_id,
            "amount": order.amount,
            "status": order.status,
            "processed_by": order.processed_by,
            "total_processed": total_processed,
        }


class GetOrderStatsUseCase:
    """Use case for getting order processing statistics."""

    def __init__(
        self,
        repository: OrderRepositoryPort,
        instance_id: str,
        is_active_provider: "ActiveStatusProvider",
    ):
        """Initialize the use case."""
        self.repository = repository
        self.instance_id = instance_id
        self.is_active_provider = is_active_provider

    async def execute(self) -> OrderStats:
        """Get order processing statistics.

        Returns:
            Current statistics from this instance
        """
        orders_processed = await self.repository.count_processed()
        is_active = await self.is_active_provider.is_active()

        return OrderStats(
            instance_id=self.instance_id,
            orders_processed=orders_processed,
            is_active=is_active,
        )


class ActiveStatusProvider(Protocol):
    """Provider for active status information."""

    async def is_active(self) -> bool:
        """Check if this instance is active."""
        ...


# =======================
# Infrastructure Layer - Adapters
# =======================


class InMemoryOrderRepository:
    """In-memory implementation of OrderRepositoryPort."""

    def __init__(self):
        """Initialize the repository."""
        self.orders: dict[str, Order] = {}

    async def save(self, order: Order) -> None:
        """Save an order."""
        self.orders[order.order_id] = order

    async def get(self, order_id: str) -> Order | None:
        """Get an order by ID."""
        return self.orders.get(order_id)

    async def count_processed(self) -> int:
        """Count processed orders."""
        return sum(1 for o in self.orders.values() if o.status == "processed")


class NATSOrderEventPublisher:
    """NATS implementation of OrderEventPublisherPort."""

    def __init__(self, message_bus: NATSAdapter, logger: SimpleLogger):
        """Initialize the publisher."""
        self.message_bus = message_bus
        self.logger = logger

    async def publish_order_processed(self, order: Order) -> None:
        """Publish order processed event."""
        event = {
            "order_id": order.order_id,
            "amount": order.amount,
            "processed_by": order.processed_by,
            "status": order.status,
        }
        await self.message_bus.publish(
            subject=f"orders.processed.{order.order_id}",
            data=event,
        )
        self.logger.info(f"Published order processed event for {order.order_id}")


# =======================
# Application Service
# =======================


class OrderProcessingService(SingleActiveService):
    """Service that processes orders using sticky active pattern.

    Only one instance will actively process orders at a time, with automatic
    failover if the active instance fails.
    """

    def __init__(
        self,
        config: SingleActiveConfig,
        process_order_use_case: ProcessOrderUseCase,
        get_stats_use_case: GetOrderStatsUseCase,
        **kwargs,
    ):
        """Initialize the order processing service.

        Args:
            config: Service configuration
            process_order_use_case: Use case for processing orders
            get_stats_use_case: Use case for getting statistics
            **kwargs: Additional arguments for SingleActiveService
        """
        super().__init__(config=config, **kwargs)
        self.process_order_use_case = process_order_use_case
        self.get_stats_use_case = get_stats_use_case
        self._active = False

    async def on_start(self) -> None:
        """Register RPC handlers when service starts."""
        await super().on_start()

        # Register exclusive RPC for order processing
        @self.exclusive_rpc("process_order")
        async def process_order_handler(params: dict) -> dict:
            """Process an order - only active instance will execute this."""
            return await self.process_order_use_case.execute(
                order_id=params["order_id"],
                amount=params["amount"],
            )

        # Register exclusive RPC for statistics
        @self.exclusive_rpc("get_stats")
        async def get_stats_handler(params: dict) -> dict:
            """Get processing statistics - only active instance will respond."""
            stats = await self.get_stats_use_case.execute()
            return {
                "instance_id": stats.instance_id,
                "orders_processed": stats.orders_processed,
                "is_active": stats.is_active,
            }

        # Register regular RPC for health check
        @self.rpc("health_check")
        async def health_check_handler(params: dict) -> dict:
            """Health check endpoint - all instances respond."""
            return {
                "instance_id": self.instance_id,
                "status": "healthy",
                "is_active": self._active,
            }

    async def on_active(self) -> None:
        """Called when this instance becomes active."""
        self._active = True
        if self.logger:
            self.logger.info(f"Instance {self.instance_id} is now ACTIVE")

    async def on_standby(self) -> None:
        """Called when this instance becomes standby."""
        self._active = False
        if self.logger:
            self.logger.info(f"Instance {self.instance_id} is now STANDBY")

    async def is_active(self) -> bool:
        """Check if this instance is active."""
        return self._active


# =======================
# Dependency Injection Container
# =======================


class ServiceContainer:
    """Dependency injection container for the service."""

    def __init__(self):
        """Initialize the container."""
        self.nats_adapter: NATSAdapter | None = None
        self.logger: SimpleLogger | None = None
        self.metrics: InMemoryMetrics | None = None
        self.config: SingleActiveConfig | None = None

    async def initialize(
        self,
        service_name: str = "order-processor",
        instance_id: str | None = None,
        nats_url: str = "nats://localhost:4222",
        group_id: str = "main",
    ) -> "OrderProcessingService":
        """Initialize all dependencies and create the service.

        Args:
            service_name: Name of the service
            instance_id: Optional instance ID
            nats_url: NATS server URL
            group_id: Sticky active group ID

        Returns:
            Configured OrderProcessingService instance
        """
        # Bootstrap default dependencies
        bootstrap_defaults()

        # Create infrastructure components
        self.nats_adapter = NATSAdapter(config=NATSConnectionConfig())
        await self.nats_adapter.connect(nats_url)

        self.logger = SimpleLogger(instance_id or service_name)
        self.metrics = InMemoryMetrics()

        # Create KV stores for service registry and election
        kv_store_registry = NATSKVStore(nats_adapter=self.nats_adapter)
        await kv_store_registry.connect("service_instances")

        kv_store_election = NATSKVStore(nats_adapter=self.nats_adapter)
        await kv_store_election.connect("sticky_active")

        # Create repositories
        service_registry = KVServiceRegistry(
            kv_store=kv_store_registry,
            logger=self.logger,
        )
        election_repository = NatsKvElectionRepository(
            kv_store=kv_store_election,
            logger=self.logger,
        )

        # Create service configuration
        self.config = SingleActiveConfig(
            service_name=service_name,
            instance_id=instance_id,
            group_id=group_id,
            version="1.0.0",
            leader_ttl_seconds=10,
            registry_ttl=30,
            heartbeat_interval=5,
        )

        # Create domain repositories and adapters
        order_repository = InMemoryOrderRepository()
        event_publisher = NATSOrderEventPublisher(
            message_bus=self.nats_adapter,
            logger=self.logger,
        )

        # Create the service instance first to get the instance_id
        service = OrderProcessingService(
            config=self.config,
            process_order_use_case=None,  # Will set after creation
            get_stats_use_case=None,  # Will set after creation
            message_bus=self.nats_adapter,
            service_registry=service_registry,
            election_repository=election_repository,
            logger=self.logger,
            metrics=self.metrics,
        )

        # Create use cases with the service's instance_id
        process_order_use_case = ProcessOrderUseCase(
            repository=order_repository,
            event_publisher=event_publisher,
            instance_id=service.instance_id,
        )

        get_stats_use_case = GetOrderStatsUseCase(
            repository=order_repository,
            instance_id=service.instance_id,
            is_active_provider=service,
        )

        # Inject use cases into the service
        service.process_order_use_case = process_order_use_case
        service.get_stats_use_case = get_stats_use_case

        return service

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.nats_adapter:
            await self.nats_adapter.disconnect()


# =======================
# Main Entry Point
# =======================


async def main():
    """Main entry point for the order processing service."""
    container = ServiceContainer()
    service = None

    try:
        # Initialize service with dependency injection
        service = await container.initialize(
            service_name="order-processor",
            nats_url="nats://localhost:4222",
            group_id="main",
        )

        # Setup graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(_sig, _frame):
            logger.info("Received shutdown signal, stopping service...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start the service
        await service.start()
        logger.info(f"Order processing service started with instance ID: {service.instance_id}")

        # Wait for shutdown signal
        await shutdown_event.wait()

    finally:
        # Cleanup
        if service:
            await service.stop()
        await container.cleanup()
        logger.info("Order processing service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
        sys.exit(0)
