#!/usr/bin/env python3
"""
Pattern Comparison - Service vs External Client Patterns.

This example demonstrates the fundamental difference between:
1. SERVICE PATTERN: Services that provide business functionality (data plane)
2. EXTERNAL CLIENT PATTERN: Tools that observe/manage the system (management plane)

Key Differences:
- Services register themselves and handle requests
- External clients discover services and make requests
- Services are part of the system
- External clients observe/manage the system

Run this example to see both patterns in action:
    python pattern_comparison.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from aegis_sdk.application.services import Service
from aegis_sdk.developer.bootstrap import quick_setup
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("PatternComparison")


# ============================================================================
# PATTERN 1: SERVICE PATTERN (Data Plane)
# Services that provide business functionality
# ============================================================================


class CalculatorService(Service):
    """
    Example SERVICE: Provides calculation functionality.

    This is a SERVICE because it:
    - Registers itself in the service registry
    - Responds to RPC requests
    - Provides business functionality
    - Is discoverable by other services and clients
    - Has a lifecycle (startup, shutdown, health checks)
    """

    def __init__(self, instance_id: int = 1):
        self.instance_id = str(instance_id)
        self.request_count = 0

        super().__init__(
            name=f"calculator-service-{instance_id}",
            service_type="calculator",
            instance_id=self.instance_id,
        )

    async def on_startup(self) -> None:
        """Service lifecycle - startup."""
        await super().on_startup()
        logger.info(f"🧮 Calculator Service {self.instance_id} started - I AM A SERVICE")
        logger.info("  ✅ Registered in service registry")
        logger.info("  ✅ Heartbeats active")
        logger.info("  ✅ Ready to handle requests")

    async def add(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC handler for addition."""
        self.request_count += 1
        a = params.get("a", 0)
        b = params.get("b", 0)
        result = a + b

        logger.info(f"🧮 Service {self.instance_id} processed: {a} + {b} = {result}")

        return {
            "result": result,
            "processed_by": self.instance_id,
            "request_count": self.request_count,
        }

    async def multiply(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC handler for multiplication."""
        self.request_count += 1
        a = params.get("a", 0)
        b = params.get("b", 0)
        result = a * b

        logger.info(f"🧮 Service {self.instance_id} processed: {a} × {b} = {result}")

        return {
            "result": result,
            "processed_by": self.instance_id,
            "request_count": self.request_count,
        }


# ============================================================================
# PATTERN 2: EXTERNAL CLIENT PATTERN (Management Plane)
# Tools that observe and manage the system
# ============================================================================


class SystemMonitor:
    """
    Example EXTERNAL CLIENT: Monitors and manages services.

    This is an EXTERNAL CLIENT because it:
    - Does NOT register as a service
    - Does NOT handle RPC requests
    - Observes the system from outside
    - Uses infrastructure components directly
    - Is a management/monitoring tool

    Similar to monitor-api in the AegisTrader system.
    """

    def __init__(self):
        self.nats = None
        self.kv_store = None
        self.registry = None
        self.discovery = None

    async def connect(self) -> None:
        """Connect to NATS and setup infrastructure components."""
        logger.info("🔍 System Monitor starting - I AM AN EXTERNAL CLIENT")
        logger.info("  ❌ NOT registering as a service")
        logger.info("  ❌ NOT handling requests")
        logger.info("  ✅ Observing the system")
        logger.info("  ✅ Using infrastructure directly")

        # External clients use infrastructure components directly
        # They don't use the Service class
        self.nats = NATSAdapter()
        await self.nats.connect("nats://localhost:4222")

        self.kv_store = NATSKVStore(self.nats)
        await self.kv_store.connect("service_registry")

        self.registry = KVServiceRegistry(self.kv_store)
        self.discovery = BasicServiceDiscovery(self.registry)

        logger.info("🔍 Monitor connected to infrastructure")

    async def list_all_services(self) -> None:
        """List all registered services - READ ONLY operation."""
        logger.info("\n📋 EXTERNAL CLIENT: Listing all services...")

        services = await self.discovery.discover("calculator")

        if not services:
            logger.info("  No services found")
        else:
            for service in services:
                logger.info(f"  Found service: {service.instance_id}")
                logger.info(f"    - Status: {service.health_status}")
                logger.info(f"    - Last heartbeat: {service.last_heartbeat}")

    async def check_service_health(self) -> None:
        """Check health of all services - OBSERVATION only."""
        logger.info("\n🏥 EXTERNAL CLIENT: Checking service health...")

        services = await self.discovery.discover("calculator")

        for service in services:
            age = (datetime.utcnow() - service.last_heartbeat).total_seconds()
            if age < 5:
                status = "✅ Healthy"
            elif age < 10:
                status = "⚠️ Warning"
            else:
                status = "❌ Unhealthy"

            logger.info(f"  Service {service.instance_id}: {status} (last seen {age:.1f}s ago)")

    async def call_service(self, a: int, b: int) -> None:
        """External client can call services but doesn't provide services."""
        logger.info("\n📞 EXTERNAL CLIENT: Calling calculator service...")

        # External clients can make RPC calls
        request = {"jsonrpc": "2.0", "method": "add", "params": {"a": a, "b": b}, "id": "monitor-1"}

        # Find a service to call
        services = await self.discovery.discover("calculator")
        if services:
            service = services[0]
            subject = f"rpc.calculator.{service.instance_id}"

            response = await self.nats.request(subject, request, timeout=5.0)

            if response and "result" in response:
                logger.info(f"  Response: {response['result']['result']}")
                logger.info(f"  Processed by: {response['result']['processed_by']}")
            else:
                logger.info("  No response or error")
        else:
            logger.info("  No calculator services available")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.nats:
            await self.nats.disconnect()


# ============================================================================
# PATTERN DEMONSTRATION
# ============================================================================


async def demonstrate_patterns():
    """Demonstrate both patterns side by side."""

    print("\n" + "=" * 70)
    print("PATTERN COMPARISON: Service vs External Client")
    print("=" * 70)

    print("\n📚 KEY CONCEPTS:")
    print("  SERVICE PATTERN (Data Plane):")
    print("    - Provides business functionality")
    print("    - Registers in service registry")
    print("    - Handles RPC requests")
    print("    - Has heartbeats and health checks")
    print("    - Examples: calculator, order-processor, payment-service")

    print("\n  EXTERNAL CLIENT PATTERN (Management Plane):")
    print("    - Observes and manages the system")
    print("    - Does NOT register as a service")
    print("    - Makes requests but doesn't handle them")
    print("    - Uses infrastructure directly")
    print("    - Examples: monitor-api, admin-tools, metrics-aggregator")

    print("\n" + "-" * 70)

    # ========================================
    # Start a SERVICE
    # ========================================
    print("\n🚀 STARTING SERVICE PATTERN EXAMPLE...")

    service = CalculatorService(instance_id=1)
    configured_service = await quick_setup("calculator-service-1", service_instance=service)

    # Register RPC handlers
    configured_service.register_rpc_handler("add", service.add)
    configured_service.register_rpc_handler("multiply", service.multiply)

    await configured_service.start()

    # Give service time to register
    await asyncio.sleep(2)

    # ========================================
    # Start an EXTERNAL CLIENT
    # ========================================
    print("\n🚀 STARTING EXTERNAL CLIENT PATTERN EXAMPLE...")

    monitor = SystemMonitor()
    await monitor.connect()

    # Give time to connect
    await asyncio.sleep(1)

    # ========================================
    # Demonstrate the differences
    # ========================================
    print("\n" + "-" * 70)
    print("DEMONSTRATION:")
    print("-" * 70)

    # External client observes the system
    await monitor.list_all_services()
    await monitor.check_service_health()

    # External client can call services
    await monitor.call_service(10, 20)

    # Service continues to handle requests
    print("\n📊 SERVICE STATISTICS:")
    print(f"  Service {service.instance_id} handled {service.request_count} requests")
    print("  Service is registered: ✅")
    print("  Service has heartbeat: ✅")

    print("\n📊 EXTERNAL CLIENT STATISTICS:")
    print("  Monitor is registered: ❌ (not a service)")
    print("  Monitor has heartbeat: ❌ (not a service)")
    print("  Monitor observes system: ✅")

    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print("\n✅ SERVICE (calculator-service):")
    print("  - Registered in service registry")
    print("  - Handling RPC requests")
    print("  - Sending heartbeats")
    print("  - Part of the data plane")

    print("\n✅ EXTERNAL CLIENT (system-monitor):")
    print("  - NOT in service registry")
    print("  - Observing services")
    print("  - Making RPC calls")
    print("  - Part of the management plane")

    print("\n💡 WHEN TO USE EACH PATTERN:")
    print("\n  Use SERVICE pattern for:")
    print("    ✓ Business logic (orders, payments, inventory)")
    print("    ✓ Data processing (analytics, ML models)")
    print("    ✓ Integration services (APIs, adapters)")

    print("\n  Use EXTERNAL CLIENT pattern for:")
    print("    ✓ Monitoring tools (metrics, health checks)")
    print("    ✓ Admin tools (configuration, deployment)")
    print("    ✓ Testing tools (load tests, chaos engineering)")
    print("    ✓ One-off scripts (migrations, reports)")

    # Cleanup
    await configured_service.stop()
    await monitor.cleanup()


async def main():
    """Main entry point."""
    try:
        await demonstrate_patterns()
    except KeyboardInterrupt:
        print("\n⏹️ Demonstration stopped")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
