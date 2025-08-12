"""Application entry point for test-example."""

import asyncio
import logging
import os
import signal

# Import AegisSDK components
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


async def main() -> None:
    """Main entry point for the service using AegisSDK."""
    # Configure logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Service configuration
    service_name = os.getenv("SERVICE_NAME", "test-example")
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    instance_id = os.getenv("SERVICE_INSTANCE_ID")
    version = os.getenv("SERVICE_VERSION", "1.0.0")

    logger.info(f"Starting {service_name} using AegisSDK")
    logger.info(f"NATS URL: {nats_url}")

    # Initialize components
    nats = None
    service = None
    shutdown_event = asyncio.Event()

    # Signal handler that sets shutdown event
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Connect to NATS
        nats = NATSAdapter()
        await nats.connect(nats_url)
        logger.info("Connected to NATS")

        # Set up KV store for service registry
        kv_store = NATSKVStore(nats)
        await kv_store.connect("service_registry")

        # Create service registry
        registry = KVServiceRegistry(kv_store=kv_store)

        # Configure service using SDK
        config = ServiceConfig(
            service_name=service_name,
            instance_id=instance_id,
            version=version,
            heartbeat_interval=10.0,  # SDK handles heartbeat automatically
            registry_ttl=30.0,
            enable_registration=True,
        )

        # Create service with SDK's Service class
        service = Service(
            service_name=config.service_name,
            message_bus=nats,
            instance_id=config.instance_id,
            version=config.version,
            service_registry=registry,
            logger=SimpleLogger(service_name),
            heartbeat_interval=config.heartbeat_interval,
            registry_ttl=config.registry_ttl,
            enable_registration=config.enable_registration,
        )

        # Register basic RPC handlers
        async def handle_ping(params: dict) -> dict:
            return {"pong": True, "timestamp": params.get("timestamp")}

        async def handle_health(params: dict) -> dict:
            return {
                "status": "healthy",
                "service": service_name,
                "instance_id": service.instance_id,
                "version": version,
            }

        await service.register_rpc_method("ping", handle_ping)
        await service.register_rpc_method("health", handle_health)

        # Start service (includes automatic heartbeat and registration)
        await service.start()
        logger.info(f"{service_name} started successfully (instance: {service.instance_id})")

        # Keep the service running until shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
    finally:
        logger.info(f"Shutting down {service_name}...")
        if service:
            await service.stop()
        if nats:
            await nats.disconnect()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
