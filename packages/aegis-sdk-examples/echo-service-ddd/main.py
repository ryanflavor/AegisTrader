#!/usr/bin/env python3
"""Echo Service DDD - Demonstrates Domain-Driven Design with AegisSDK.

This service showcases:
- Domain-Driven Design with hexagonal architecture
- Using AegisSDK Service class instead of reimplementing infrastructure
- Service discovery and registration via SDK
- Health monitoring and metrics collection via SDK
- Multiple echo processing modes with DDD business logic
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import UTC, datetime

import httpx
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Import domain and application layers (keep DDD for business logic)
from application.use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase
from domain.services import EchoProcessor, HealthChecker, MetricsCollector

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class EchoServiceDDD:
    """Echo service using SDK Service class with DDD business logic."""

    def __init__(self):
        """Initialize the echo service with domain services."""
        self.service = None
        self.nats = None

        # Configuration
        self.monitor_api_url = os.getenv("MONITOR_API_URL", "http://monitor-api:8000")
        self.service_name = os.getenv("SERVICE_NAME", "echo-service-ddd")
        self.instance_id = os.getenv(
            "SERVICE_INSTANCE_ID",
            f"{self.service_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        )

        # Initialize domain services (business logic) with instance_id
        self.version = os.getenv("SERVICE_VERSION", "1.0.0")
        self.echo_processor = EchoProcessor(instance_id=self.instance_id)
        self.metrics_collector = MetricsCollector(instance_id=self.instance_id)
        self.health_checker = HealthChecker(instance_id=self.instance_id, version=self.version)

        # Initialize use cases (application layer)
        self.echo_use_case = EchoUseCase(self.echo_processor, self.metrics_collector)
        self.metrics_use_case = GetMetricsUseCase(self.metrics_collector)
        self.health_use_case = HealthCheckUseCase(self.health_checker, self.metrics_collector)

    async def register_with_monitor_api(self, version: str) -> None:
        """Register service with monitor-api via HTTP POST."""
        if not self.monitor_api_url:
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.monitor_api_url}/register",
                    json={
                        "name": self.service_name,
                        "instance_id": self.instance_id,
                        "version": version,
                        "endpoints": ["echo", "batch_echo", "metrics", "health", "ping"],
                        "status": "running",
                    },
                    timeout=5.0,
                )
                if response.status_code == 200:
                    logger.info(f"Registered with monitor-api at {self.monitor_api_url}")
                else:
                    logger.warning(f"Monitor-api registration returned {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to register with monitor-api: {e}")

    async def deregister_from_monitor_api(self) -> None:
        """Deregister service from monitor-api."""
        if not self.monitor_api_url or not self.instance_id:
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self.monitor_api_url}/deregister",
                    json={
                        "name": self.service_name,
                        "instance_id": self.instance_id,
                    },
                    timeout=5.0,
                )
                logger.info("Deregistered from monitor-api")
        except Exception as e:
            logger.warning(f"Failed to deregister from monitor-api: {e}")

    async def setup_handlers(self, service: Service) -> None:
        """Register RPC handlers with the SDK service."""

        async def handle_echo(params: dict) -> dict:
            """Handle echo requests using DDD use case."""
            result = await self.echo_use_case.execute(params)
            # Add instance_id to response
            result["instance_id"] = self.instance_id
            return result

        async def handle_batch_echo(params: dict) -> dict:
            """Handle batch echo requests."""
            results = []
            for message in params.get("messages", []):
                result = await self.echo_use_case.execute(
                    {
                        "message": message,
                        "mode": params.get("mode", "simple"),
                        "delay": params.get("delay", 0),
                    }
                )
                results.append(result)
            return {
                "results": results,
                "count": len(results),
                "instance_id": self.instance_id,
            }

        async def handle_metrics(params: dict) -> dict:
            """Get service metrics."""
            metrics = await self.metrics_use_case.execute()
            metrics["instance_id"] = self.instance_id
            return metrics

        async def handle_health(params: dict) -> dict:
            """Get service health."""
            health = await self.health_use_case.execute()
            health["instance_id"] = self.instance_id
            return health

        async def handle_ping(params: dict) -> dict:
            """Handle ping requests."""
            return {
                "pong": True,
                "timestamp": params.get("timestamp"),
                "instance_id": self.instance_id,
            }

        # Register all handlers with SDK service
        await service.register_rpc_method("echo", handle_echo)
        await service.register_rpc_method("batch_echo", handle_batch_echo)
        await service.register_rpc_method("metrics", handle_metrics)
        await service.register_rpc_method("health", handle_health)
        await service.register_rpc_method("ping", handle_ping)

        logger.info(f"Registered 5 RPC handlers for {self.service_name}")

    async def run(self) -> None:
        """Run the echo service using SDK Service class."""
        try:
            # Load configuration
            nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
            version = os.getenv("SERVICE_VERSION", "1.0.0")
            self.instance_id = os.getenv(
                "SERVICE_INSTANCE_ID",
                f"{self.service_name}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            )

            logger.info(
                f"Starting {self.service_name} (instance: {self.instance_id}, version: {version})"
            )

            # Step 1: Connect to NATS
            self.nats = NATSAdapter()
            await self.nats.connect(nats_url)
            logger.info("Connected to NATS")

            # Step 2: Setup KV store for service registry
            kv_store = NATSKVStore(self.nats)
            await kv_store.connect("service_registry")
            registry = KVServiceRegistry(kv_store=kv_store)
            logger.info("Connected to service registry")

            # Step 3: Create SDK Service (handles all infrastructure)
            config = ServiceConfig(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=version,
                heartbeat_interval=10.0,  # SDK handles heartbeat automatically
                registry_ttl=30.0,
                enable_registration=True,  # SDK handles service registration
            )

            self.service = Service(
                service_name=config.service_name,
                message_bus=self.nats,
                instance_id=config.instance_id,
                version=config.version,
                service_registry=registry,
                logger=SimpleLogger(self.service_name),
                heartbeat_interval=config.heartbeat_interval,
                registry_ttl=config.registry_ttl,
                enable_registration=config.enable_registration,
            )

            # Step 4: Setup business logic handlers
            await self.setup_handlers(self.service)
            logger.info(
                f"Registered handlers: {list(self.service._handler_registry.rpc_handlers.keys())}"
            )

            # Step 5: Register with monitor-api (in addition to SDK registration)
            await self.register_with_monitor_api(version)

            # Step 6: Start service - SDK handles everything!
            # - Lifecycle management
            # - Signal handling (SIGTERM, SIGINT)
            # - Automatic heartbeats
            # - Service registration
            # - Error recovery
            await self.service.start()
            logger.info(
                f"{self.service_name} started successfully - all infrastructure handled by SDK"
            )

            # Keep running until shutdown
            # SDK handles shutdown signals internally
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Service failed: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Starting cleanup...")

        # Deregister from monitor-api
        await self.deregister_from_monitor_api()

        # Stop SDK service (handles all cleanup)
        if self.service:
            try:
                await self.service.stop()
                logger.info("SDK service stopped")
            except Exception as e:
                logger.error(f"Error stopping service: {e}")

        # Disconnect NATS
        if self.nats:
            try:
                await self.nats.disconnect()
                logger.info("NATS disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting NATS: {e}")

        logger.info("Cleanup complete")


async def main():
    """Main entry point."""
    service = EchoServiceDDD()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await service.run()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
