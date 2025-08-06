"""Kubernetes-based integration tests for automatic failover.

Tests the automatic failover functionality in an actual Kubernetes environment,
verifying sub-2-second failover recovery time using the local k8s cluster.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest
import pytest_asyncio
from nats import NATS
from nats.js import JetStreamContext

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy
from aegis_sdk.infrastructure.application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultUseCaseFactory,
)
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Register default dependencies at module level for all tests
bootstrap_defaults()


@pytest_asyncio.fixture
async def k8s_nats_url() -> str:
    """Get NATS URL from Kubernetes service.

    Uses port-forwarding or service IP based on environment.
    """
    # Check if we're running inside k8s (in a pod)
    if os.path.exists("/var/run/secrets/kubernetes.io"):
        # Inside k8s, use service DNS
        return "nats://aegis-trader-nats.aegis-trader.svc.cluster.local:4222"
    else:
        # Outside k8s, use port-forward (assumed to be running)
        return "nats://localhost:4222"


@pytest_asyncio.fixture
async def nats_client(k8s_nats_url: str) -> NATS:
    """Create a NATS client connected to k8s NATS."""
    nc = NATS()
    await nc.connect(servers=[k8s_nats_url])
    yield nc
    await nc.close()


@pytest_asyncio.fixture
async def js_context(nats_client: NATS) -> JetStreamContext:
    """Create JetStream context."""
    return nats_client.jetstream()


@pytest_asyncio.fixture
async def nats_adapter(k8s_nats_url: str) -> NATSAdapter:
    """Create NATS adapter connected to k8s NATS."""
    adapter = NATSAdapter()
    await adapter.connect(servers=[k8s_nats_url])
    yield adapter
    await adapter.disconnect()


@pytest_asyncio.fixture
async def service_registry(nats_adapter: NATSAdapter) -> KVServiceRegistry:
    """Create KV service registry."""
    from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

    kv_store = NATSKVStore(nats_adapter)
    await kv_store.connect("service_registry", enable_ttl=True)

    registry = KVServiceRegistry(kv_store)
    yield registry
    # No cleanup needed as connection is managed by nats_adapter


@pytest_asyncio.fixture
async def service_discovery(js_context: JetStreamContext) -> BasicServiceDiscovery:
    """Create service discovery."""
    discovery = BasicServiceDiscovery(js_context)
    yield discovery


async def create_single_active_service(
    service_name: str,
    instance_id: str,
    sticky_active_group: str,
    nats_adapter: NATSAdapter,
    service_registry: KVServiceRegistry,
    service_discovery: BasicServiceDiscovery,
    failover_policy: FailoverPolicy | None = None,
) -> SingleActiveService:
    """Helper to create a single active service instance."""
    config = SingleActiveConfig(
        service_name=service_name,
        instance_id=instance_id,
        group_id=sticky_active_group,
        registry_ttl=2,
        heartbeat_interval=1,  # Use 1 second instead of 0.5
    )

    logger = SimpleLogger()

    # Create factories
    election_factory = DefaultElectionRepositoryFactory()
    use_case_factory = DefaultUseCaseFactory()

    service = SingleActiveService(
        config=config,
        message_bus=nats_adapter,
        service_registry=service_registry,
        service_discovery=service_discovery,
        election_repository_factory=election_factory,
        use_case_factory=use_case_factory,
        logger=logger,
    )

    # Set failover policy if provided
    if failover_policy and hasattr(service, "_failover_use_case"):
        service._failover_use_case._failover_policy = failover_policy

    await service.start()
    return service


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_k8s_sub_two_second_failover(
    nats_adapter: NATSAdapter,
    service_registry: KVServiceRegistry,
    service_discovery: BasicServiceDiscovery,
    js_context: JetStreamContext,
):
    """Test that failover completes in under 2 seconds in k8s environment."""
    service_name = "test-failover-service"
    group_id = f"test-group-{int(time.time())}"

    # Clean up any stale leader keys from previous runs
    try:
        kv = await js_context.key_value(f"election_{service_name}")
        # Delete the old leader key if it exists
        leader_key = f"sticky-active.{service_name}.default.leader"
        await kv.delete(leader_key)
        # Also delete for our specific group
        leader_key = f"sticky-active.{service_name}.{group_id}.leader"
        await kv.delete(leader_key)
    except Exception:
        pass  # Ignore if bucket doesn't exist or key not found

    # Create three service instances
    instance1 = await create_single_active_service(
        service_name=service_name,
        instance_id=f"instance-1-{int(time.time())}",
        sticky_active_group=group_id,
        nats_adapter=nats_adapter,
        service_registry=service_registry,
        service_discovery=service_discovery,
        failover_policy=FailoverPolicy.aggressive(),
    )

    instance2 = await create_single_active_service(
        service_name=service_name,
        instance_id=f"instance-2-{int(time.time())}",
        sticky_active_group=group_id,
        nats_adapter=nats_adapter,
        service_registry=service_registry,
        service_discovery=service_discovery,
        failover_policy=FailoverPolicy.aggressive(),
    )

    instance3 = await create_single_active_service(
        service_name=service_name,
        instance_id=f"instance-3-{int(time.time())}",
        sticky_active_group=group_id,
        nats_adapter=nats_adapter,
        service_registry=service_registry,
        service_discovery=service_discovery,
        failover_policy=FailoverPolicy.aggressive(),
    )

    # Wait for initial election to stabilize
    await asyncio.sleep(1.0)

    # Verify instance1 is active
    status1 = await instance1.get_status()
    assert status1.is_active is True
    assert status1.is_leader is True

    # Verify others are standby
    status2 = await instance2.get_status()
    assert status2.is_active is False
    assert status2.is_leader is False

    status3 = await instance3.get_status()
    assert status3.is_active is False
    assert status3.is_leader is False

    # Record start time
    start_time = time.time()

    # Simulate active instance failure by stopping it
    await instance1.stop()

    # Wait for new leader to be elected
    new_leader_found = False
    max_wait = 2.0  # Maximum 2 seconds

    while time.time() - start_time < max_wait:
        status2 = await instance2.get_status()
        status3 = await instance3.get_status()

        if status2.is_active or status3.is_active:
            new_leader_found = True
            break

        await asyncio.sleep(0.1)

    # Calculate failover time
    failover_time = time.time() - start_time

    # Assert failover completed within 2 seconds
    assert new_leader_found, f"No new leader elected within {max_wait} seconds"
    assert failover_time < 2.0, f"Failover took {failover_time:.2f} seconds (> 2s limit)"

    print(f"✅ Failover completed in {failover_time:.2f} seconds")

    # Cleanup
    await instance2.stop()
    await instance3.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_k8s_concurrent_election_single_winner(
    nats_adapter: NATSAdapter,
    service_registry: KVServiceRegistry,
    service_discovery: BasicServiceDiscovery,
):
    """Test that only one instance wins during concurrent elections in k8s."""
    service_name = "test-concurrent-election"
    group_id = f"test-group-{int(time.time())}"

    # Create five service instances
    instances = []
    for i in range(5):
        instance = await create_single_active_service(
            service_name=service_name,
            instance_id=f"instance-{i}-{int(time.time())}",
            sticky_active_group=group_id,
            nats_adapter=nats_adapter,
            service_registry=service_registry,
            service_discovery=service_discovery,
            failover_policy=FailoverPolicy.aggressive(),
        )
        instances.append(instance)

    # Wait for initial election
    await asyncio.sleep(1.5)

    # Count active instances
    active_count = 0
    active_instance = None

    for instance in instances:
        status = await instance.get_status()
        if status.is_active:
            active_count += 1
            active_instance = instance

    assert active_count == 1, f"Expected 1 active instance, found {active_count}"

    # Stop the active instance to trigger concurrent election attempts
    await active_instance.stop()

    # Wait for new election
    await asyncio.sleep(2.0)

    # Count active instances again
    new_active_count = 0
    for instance in instances:
        if instance != active_instance:  # Skip the stopped instance
            status = await instance.get_status()
            if status.is_active:
                new_active_count += 1

    assert new_active_count == 1, f"Expected 1 new active instance, found {new_active_count}"

    print("✅ Concurrent election resulted in exactly 1 winner")

    # Cleanup
    for instance in instances:
        if instance != active_instance:
            await instance.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_k8s_rapid_failover_cycles(
    nats_adapter: NATSAdapter,
    service_registry: KVServiceRegistry,
    service_discovery: BasicServiceDiscovery,
):
    """Test system stability during rapid failover cycles in k8s."""
    service_name = "test-rapid-failover"
    group_id = f"test-group-{int(time.time())}"

    # Create three service instances
    instances = []
    for i in range(3):
        instance = await create_single_active_service(
            service_name=service_name,
            instance_id=f"instance-{i}-{int(time.time())}",
            sticky_active_group=group_id,
            nats_adapter=nats_adapter,
            service_registry=service_registry,
            service_discovery=service_discovery,
            failover_policy=FailoverPolicy.aggressive(),
        )
        instances.append(instance)

    # Wait for initial election
    await asyncio.sleep(1.0)

    # Perform 5 rapid failover cycles
    failover_times = []

    for cycle in range(5):
        # Find and stop the active instance
        active_instance = None
        for instance in instances:
            status = await instance.get_status()
            if status.is_active:
                active_instance = instance
                break

        assert active_instance is not None, f"No active instance found in cycle {cycle}"

        # Measure failover time
        start_time = time.time()
        await active_instance.stop()

        # Wait for new leader
        new_leader_found = False
        max_wait = 3.0

        while time.time() - start_time < max_wait:
            for instance in instances:
                if instance != active_instance:
                    status = await instance.get_status()
                    if status.is_active:
                        new_leader_found = True
                        break
            if new_leader_found:
                break
            await asyncio.sleep(0.1)

        failover_time = time.time() - start_time
        failover_times.append(failover_time)

        assert new_leader_found, f"No new leader in cycle {cycle}"

        # Restart the stopped instance for next cycle
        if cycle < 4:  # Don't restart on last cycle
            # Create a new instance to replace the stopped one
            new_instance = await create_single_active_service(
                service_name=service_name,
                instance_id=f"instance-new-{cycle}-{int(time.time())}",
                sticky_active_group=group_id,
                nats_adapter=nats_adapter,
                service_registry=service_registry,
                service_discovery=service_discovery,
                failover_policy=FailoverPolicy.aggressive(),
            )
            instances.remove(active_instance)
            instances.append(new_instance)
            await asyncio.sleep(0.5)  # Brief pause between cycles

    # All failovers should be under 2 seconds
    avg_failover_time = sum(failover_times) / len(failover_times)
    max_failover_time = max(failover_times)

    print("✅ Rapid failover cycles completed:")
    print(f"   Average failover time: {avg_failover_time:.2f}s")
    print(f"   Maximum failover time: {max_failover_time:.2f}s")
    print(f"   All times: {[f'{t:.2f}s' for t in failover_times]}")

    assert (
        max_failover_time < 2.0
    ), f"Maximum failover time {max_failover_time:.2f}s exceeds 2s limit"

    # Cleanup
    for instance in instances:
        try:
            await instance.stop()
        except:
            pass  # Instance might already be stopped


if __name__ == "__main__":
    # Run tests directly
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
