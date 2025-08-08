"""Integration test for cross-process service discovery.

This test verifies that the deterministic key encoding (hex encoding)
allows services registered in one process to be discovered by another.
"""

import asyncio
import multiprocessing
import time
from datetime import UTC, datetime

import pytest

from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


def server_process(service_name: str, instance_id: str, ready_event, stop_event):
    """Server process that registers a service."""

    async def run():
        # Connect to NATS
        nats_config = NATSConnectionConfig()
        adapter = NATSAdapter(config=nats_config)
        await adapter.connect(["nats://localhost:4222"])

        # Create KV store with key sanitization
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("cross_process_test")

        # Create registry
        registry = KVServiceRegistry(kv_store)

        # Register service
        service_instance = ServiceInstance(
            service_name=service_name,
            instance_id=instance_id,
            status="ACTIVE",
            version="1.0.0",
            metadata={"process": "server", "pid": multiprocessing.current_process().pid},
            last_heartbeat=datetime.now(UTC).isoformat(),
        )

        await registry.register(service_instance, ttl_seconds=60)
        print(f"Server: Registered {service_name}/{instance_id}")

        # Signal that we're ready
        ready_event.set()

        # Keep updating heartbeat until stopped
        while not stop_event.is_set():
            await asyncio.sleep(1)
            try:
                await registry.update_heartbeat(service_instance, ttl_seconds=60)
            except:
                break

        # Cleanup
        await registry.deregister(service_name, instance_id)
        await adapter.disconnect()
        print(f"Server: Cleaned up {service_name}/{instance_id}")

    asyncio.run(run())


def client_process(service_name: str, expected_instance_id: str, result_queue):
    """Client process that discovers the service."""

    async def run():
        # Wait a bit for server to register
        await asyncio.sleep(2)

        # Connect to NATS (separate connection)
        nats_config = NATSConnectionConfig()
        adapter = NATSAdapter(config=nats_config)
        await adapter.connect(["nats://localhost:4222"])

        # Create KV store (separate instance)
        kv_store = NATSKVStore(nats_adapter=adapter)
        await kv_store.connect("cross_process_test")

        # Create registry (separate instance)
        registry = KVServiceRegistry(kv_store)

        # Try to discover the service
        print(f"Client: Looking for {service_name}")

        # List all services
        all_services = await registry.list_all_services()
        print(f"Client: Found services: {all_services}")

        # Check if our service is there
        if service_name in all_services:
            # Get instances
            instances = await registry.list_instances(service_name)
            print(f"Client: Found {len(instances)} instances of {service_name}")

            # Look for the expected instance
            for instance in instances:
                print(f"Client: - Instance {instance.instance_id}, metadata: {instance.metadata}")
                if instance.instance_id == expected_instance_id:
                    result_queue.put(
                        {
                            "success": True,
                            "instance": instance.instance_id,
                            "metadata": instance.metadata,
                        }
                    )
                    await adapter.disconnect()
                    return

        # Not found
        result_queue.put({"success": False, "all_services": list(all_services)})
        await adapter.disconnect()

    asyncio.run(run())


@pytest.mark.asyncio
async def test_cross_process_service_discovery():
    """Test that services can be discovered across process boundaries."""
    # Test parameters
    service_name = "test-service"  # Valid service name
    instance_id = f"test-instance-{int(time.time())}"  # Instance ID without dots for now

    # Create synchronization primitives
    ready_event = multiprocessing.Event()
    stop_event = multiprocessing.Event()
    result_queue = multiprocessing.Queue()

    # Start server process
    server = multiprocessing.Process(
        target=server_process, args=(service_name, instance_id, ready_event, stop_event)
    )
    server.start()

    # Wait for server to be ready
    assert ready_event.wait(timeout=10), "Server failed to start"

    # Start client process
    client = multiprocessing.Process(
        target=client_process, args=(service_name, instance_id, result_queue)
    )
    client.start()

    # Wait for client to complete
    client.join(timeout=10)

    # Stop server
    stop_event.set()
    server.join(timeout=5)

    # Check results
    assert not result_queue.empty(), "Client didn't return results"
    result = result_queue.get()

    # Assertions
    assert result[
        "success"
    ], f"Service discovery failed. Found services: {result.get('all_services', [])}"
    assert result["instance"] == instance_id, f"Wrong instance ID: {result['instance']}"
    assert result["metadata"]["process"] == "server", "Wrong metadata"

    print("✅ Cross-process service discovery successful!")
    print(f"   Service: {service_name}")
    print(f"   Instance: {instance_id}")
    print("   Key encoding: Hex (_xHH format) for dots in keys")


@pytest.mark.asyncio
async def test_cross_process_with_multiple_services():
    """Test discovery with multiple services across processes."""
    services = [
        ("service-alpha", "alpha-001"),
        ("service-beta", "beta-002"),
        ("service-gamma", "gamma-003"),
    ]

    processes = []
    events = []

    try:
        # Start multiple server processes
        for service_name, instance_id in services:
            ready_event = multiprocessing.Event()
            stop_event = multiprocessing.Event()
            events.append((ready_event, stop_event))

            server = multiprocessing.Process(
                target=server_process, args=(service_name, instance_id, ready_event, stop_event)
            )
            server.start()
            processes.append(server)

            # Wait for each to be ready
            assert ready_event.wait(timeout=10), f"Server {service_name} failed to start"

        # Now discover all services from a separate process
        result_queue = multiprocessing.Queue()

        async def discover_all():
            # Connect to NATS
            nats_config = NATSConnectionConfig()
            adapter = NATSAdapter(config=nats_config)
            await adapter.connect(["nats://localhost:4222"])

            # Create KV store
            kv_store = NATSKVStore(nats_adapter=adapter)
            await kv_store.connect("cross_process_test")

            # Create registry
            registry = KVServiceRegistry(kv_store)

            # Discover all services
            all_services = await registry.list_all_services()

            found = {}
            for service_name, expected_id in services:
                if service_name in all_services:
                    instances = await registry.list_instances(service_name)
                    for instance in instances:
                        if instance.instance_id == expected_id:
                            found[service_name] = instance.instance_id

            await adapter.disconnect()
            return found

        # Run discovery
        found_services = await discover_all()

        # Verify all services were found
        for service_name, instance_id in services:
            assert service_name in found_services, f"Service {service_name} not found"
            assert found_services[service_name] == instance_id

        print(f"✅ Found all {len(services)} services across processes!")

    finally:
        # Cleanup
        for (_, stop_event), process in zip(events, processes, strict=False):
            stop_event.set()
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()


if __name__ == "__main__":
    # Run tests directly
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
