"""Main entry point for running trading services."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from typing import Any

from aegis_sdk.infrastructure import (
    InMemoryMetrics,
    NATSAdapter,
    NATSKVStore,
    SimpleLogger,
)
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from order_service import OrderService
from order_service.adapters import RemotePricingServiceAdapter
from pricing_service import PricingService
from risk_service import RiskService


class ServiceRunner:
    """Manages running trading services."""

    def __init__(self):
        """Initialize service runner."""
        self.service = None
        self.nats_adapter = None
        self.kv_store = None
        self.running = False

    async def setup_infrastructure(self, nats_url: str) -> dict[str, Any]:
        """Set up infrastructure components."""
        # Create NATS adapter
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect([nats_url])

        # Create KV store
        self.kv_store = NATSKVStore(nats_adapter=self.nats_adapter)
        bucket_name = os.getenv("NATS_KV_BUCKET", "service-registry")
        await self.kv_store.connect(bucket_name)

        # Create registry and discovery
        logger = SimpleLogger()
        registry = KVServiceRegistry(kv_store=self.kv_store, logger=logger)

        # For now, use basic discovery without caching
        # TODO: Fix WatchableCachedServiceDiscovery initialization
        from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery

        discovery = BasicServiceDiscovery(registry, logger)

        # Create metrics
        metrics = InMemoryMetrics()

        return {
            "message_bus": self.nats_adapter,
            "service_registry": registry,
            "service_discovery": discovery,
            "logger": logger,
            "metrics": metrics,
        }

    async def run_service(
        self,
        service_type: str,
        instance_count: int,
        nats_url: str = "nats://localhost:4222",
    ) -> None:
        """Run the specified service type."""
        print(f"🚀 Starting {service_type} service(s)...")

        # Set up infrastructure
        infra = await self.setup_infrastructure(nats_url)

        # Create services based on type
        services = []
        ServiceClass = {
            "order": OrderService,
            "pricing": PricingService,
            "risk": RiskService,
        }.get(service_type)

        if not ServiceClass:
            raise ValueError(f"Unknown service type: {service_type}")

        # Create specified number of instances
        for i in range(instance_count):
            instance_id = f"{service_type}-service-{i + 1:02d}"

            # Create service with proper dependency injection
            if service_type == "order":
                # Create a temporary service instance first
                temp_service = ServiceClass(
                    instance_id=instance_id,
                    **infra,
                )
                # Create pricing adapter
                pricing_adapter = RemotePricingServiceAdapter(
                    temp_service, infra["service_discovery"]
                )
                # Create the real service with dependencies
                service = ServiceClass(
                    instance_id=instance_id,
                    pricing_service=pricing_adapter,
                    **infra,
                )
            else:
                service = ServiceClass(
                    instance_id=instance_id,
                    **infra,
                )
            services.append(service)

        # Start all services
        for service in services:
            await service.start()
            print(f"✅ Started {service.instance_id}")

        self.running = True
        self.services = services

        # Run until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down...")
        finally:
            # Stop all services
            for service in services:
                await service.stop()

            # Disconnect infrastructure
            await self.kv_store.disconnect()
            await self.nats_adapter.disconnect()

            print("👋 Services stopped")

    def stop(self):
        """Stop the service runner."""
        self.running = False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run trading services")
    parser.add_argument(
        "service",
        choices=["order", "pricing", "risk", "all"],
        help="Service type to run",
    )
    parser.add_argument(
        "--instances",
        type=int,
        default=2,
        help="Number of instances to run (default: 2)",
    )
    parser.add_argument(
        "--nats-url",
        default=os.getenv("NATS_URL", "nats://localhost:4222"),
        help="NATS server URL",
    )

    args = parser.parse_args()

    runner = ServiceRunner()

    # Handle signals
    def signal_handler(sig, frame):
        print("\n⚠️  Signal received, shutting down...")
        runner.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.service == "all":
            # Run all services with specified instances each
            tasks = []
            runners = []

            for service_type in ["order", "pricing", "risk"]:
                r = ServiceRunner()
                runners.append(r)
                task = asyncio.create_task(
                    r.run_service(service_type, args.instances, args.nats_url)
                )
                tasks.append(task)

            # Wait for all services
            await asyncio.gather(*tasks)
        else:
            # Run single service type
            await runner.run_service(args.service, args.instances, args.nats_url)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
