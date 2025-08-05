"""Runner for sticky service in K8s testing."""

import asyncio
import os
import signal
from datetime import datetime

from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class TestStickyService(SingleActiveService):
    """Test service for sticky active pattern."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.process_count = 0
        self.last_processed = None

    async def on_start(self):
        """Register RPC handlers."""

        @self.exclusive_rpc("process_request")
        async def process_request(params: dict) -> dict:
            """Process request - only active instance should handle this."""
            self.process_count += 1
            self.last_processed = datetime.utcnow()

            return {
                "success": True,
                "instance_id": self.instance_id,
                "process_count": self.process_count,
                "timestamp": self.last_processed.isoformat(),
                "request_id": params.get("request_id", "unknown"),
            }

        @self.rpc("get_status")
        async def get_status(params: dict) -> dict:
            """Get instance status - all instances can handle this."""
            return {
                "instance_id": self.instance_id,
                "is_active": self.is_active,
                "process_count": self.process_count,
                "last_processed": self.last_processed.isoformat() if self.last_processed else None,
                "group_id": self.group_id,
            }

        # Subscribe to test events
        @self.subscribe("test.failover", mode="broadcast")
        async def handle_failover_test(event):
            """Handle failover test events."""
            if event.payload.get("target_instance") == self.instance_id:
                self._logger.info(f"Simulating failure for instance {self.instance_id}")
                # Simulate failure by stopping the service
                asyncio.create_task(self.stop())


async def main():
    """Main entry point for K8s sticky service."""
    # Configuration from environment
    instance_id = os.environ.get("INSTANCE_ID", f"sticky-service-{os.getpid()}")
    service_name = os.environ.get("SERVICE_NAME", "sticky-test-service")
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    group_id = os.environ.get("GROUP_ID", "default")
    leader_ttl = int(os.environ.get("LEADER_TTL", "5"))

    # Setup logger
    logger = SimpleLogger(f"sticky-service-{instance_id}")
    logger.info(f"Starting sticky service instance: {instance_id}")

    # Create NATS adapter
    config = NATSConnectionConfig()
    nats_adapter = NATSAdapter(config=config)
    await nats_adapter.connect(nats_url)

    # Create KV store and registry
    kv_store = NATSKVStore(nats_adapter=nats_adapter)
    service_registry = KVServiceRegistry(kv_store=kv_store, logger=logger)

    # Create metrics
    metrics = InMemoryMetrics()

    # Create and start service
    service = TestStickyService(
        service_name=service_name,
        instance_id=instance_id,
        message_bus=nats_adapter,
        service_registry=service_registry,
        logger=logger,
        metrics=metrics,
        group_id=group_id,
        leader_ttl_seconds=leader_ttl,
        registry_ttl=30,
        heartbeat_interval=2,
    )

    # Setup signal handlers
    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await service.start()
        logger.info(f"Service started successfully. Active: {service.is_active}")

        # Wait for shutdown signal
        await stop_event.wait()

    except Exception as e:
        logger.error(f"Service error: {e}")
        raise
    finally:
        logger.info("Shutting down service...")
        await service.stop()
        await nats_adapter.disconnect()
        logger.info("Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
