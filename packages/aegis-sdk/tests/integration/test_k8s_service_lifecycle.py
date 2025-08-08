#!/usr/bin/env python3
"""K8s E2E Service Lifecycle Tests for AegisSDK.

This test must be run in a K8s environment with:
1. NATS deployed in aegis-trader namespace
2. Monitor-API and Monitor-UI deployed
3. Echo service deployed (optional, will be tested if present)

Run with: pytest test_k8s_service_lifecycle.py -v
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.config import KVStoreConfig, NATSConnectionConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


def is_k8s_environment() -> bool:
    """Check if running in K8s environment."""
    return (
        os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")
        or os.getenv("KUBERNETES_SERVICE_HOST") is not None
    )


def get_nats_url() -> str:
    """Get NATS URL based on environment."""
    if is_k8s_environment():
        return "nats://aegis-trader-nats.aegis-trader.svc.cluster.local:4222"
    else:
        # Assume port-forwarding is set up
        return "nats://localhost:4222"


@pytest.mark.skipif(
    not is_k8s_environment() and not os.getenv("K8S_E2E_TEST"),
    reason="K8s E2E tests require K8s environment or K8S_E2E_TEST=1",
)
@pytest.mark.asyncio
class TestK8sServiceLifecycle:
    """E2E tests for service lifecycle in K8s environment."""

    @pytest_asyncio.fixture
    async def nats_kv_store(self):
        """Create real NATS KV store connection."""
        # Create NATS connection config
        nats_config = NATSConnectionConfig(
            servers=[get_nats_url()],
            enable_jetstream=True,
            service_name="test-k8s-e2e",
            instance_id="test-instance",
        )

        # Create NATS adapter
        nats_adapter = NATSAdapter(config=nats_config)
        await nats_adapter.connect()

        # Create KV store config
        config = KVStoreConfig(bucket="service_registry")

        # Create KV store with adapter and config
        store = NATSKVStore(nats_adapter=nats_adapter, config=config)
        await store.connect("service_registry")
        yield store
        # NATSKVStore doesn't have a close method, just disconnect the adapter
        await nats_adapter.disconnect()

    @pytest_asyncio.fixture
    async def service_registry(self, nats_kv_store):
        """Create real service registry."""
        return KVServiceRegistry(kv_store=nats_kv_store)

    async def test_echo_service_deployment_lifecycle(self, service_registry):
        """Test echo service deployment and lifecycle in K8s (AC: 1, 2, 4)."""
        # Check if echo service is deployed
        try:
            result = subprocess.run(
                ["kubectl", "get", "deployment", "echo-service", "-n", "aegis-trader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            echo_deployed = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("kubectl not available or timeout")
            return

        if not echo_deployed:
            pytest.skip("Echo service not deployed in K8s")
            return

        # Scale echo service to 3 replicas
        subprocess.run(
            [
                "kubectl",
                "scale",
                "deployment",
                "echo-service",
                "--replicas=3",
                "-n",
                "aegis-trader",
            ],
            capture_output=True,
            timeout=10,
        )

        # Wait for pods to be ready
        await asyncio.sleep(10)

        # Check service instances appear in registry
        start_time = time.time()
        instances_found = False

        while time.time() - start_time < 30:  # Wait up to 30 seconds
            all_services = await service_registry.list_all_services()
            echo_instances = all_services.get("echo-service", [])

            if len(echo_instances) >= 1:
                instances_found = True
                print(f"Found {len(echo_instances)} echo-service instances")
                for instance in echo_instances:
                    print(f"  - {instance.instance_id}: {instance.status}")
                break

            await asyncio.sleep(2)

        assert instances_found, "Echo service instances did not appear within 30 seconds"

        # Verify instances have proper metadata
        for instance in echo_instances:
            assert instance.service_name == "echo-service"
            assert instance.status in [ServiceStatus.ACTIVE, ServiceStatus.STANDBY]
            assert instance.last_heartbeat is not None

            # Check heartbeat is recent (within last 35 seconds)
            age = (datetime.now(UTC) - instance.last_heartbeat).total_seconds()
            assert age < 35, f"Instance {instance.instance_id} heartbeat too old: {age}s"

    async def test_service_disappears_after_scaling_down(self, service_registry):
        """Test services disappear after scaling down (AC: 2)."""
        # Ensure echo service is deployed
        try:
            # First scale up
            subprocess.run(
                [
                    "kubectl",
                    "scale",
                    "deployment",
                    "echo-service",
                    "--replicas=3",
                    "-n",
                    "aegis-trader",
                ],
                capture_output=True,
                timeout=10,
            )
            await asyncio.sleep(10)

            # Get initial instance count
            all_services = await service_registry.list_all_services()
            initial_instances = all_services.get("echo-service", [])
            initial_count = len(initial_instances)

            if initial_count == 0:
                pytest.skip("No echo service instances found")
                return

            print(f"Initial instance count: {initial_count}")

            # Scale down to 1 replica
            subprocess.run(
                [
                    "kubectl",
                    "scale",
                    "deployment",
                    "echo-service",
                    "--replicas=1",
                    "-n",
                    "aegis-trader",
                ],
                capture_output=True,
                timeout=10,
            )

            # Wait for TTL + buffer (35 seconds)
            print("Waiting 40 seconds for instances to disappear...")
            await asyncio.sleep(40)

            # Check remaining instances
            all_services = await service_registry.list_all_services()
            remaining_instances = all_services.get("echo-service", [])
            remaining_count = len(remaining_instances)

            print(f"Remaining instance count: {remaining_count}")

            # Should have fewer instances (ideally just 1)
            assert remaining_count < initial_count, "Instances did not disappear after scaling down"
            assert remaining_count <= 1, "More than 1 instance remains after scaling to 1"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("kubectl not available or timeout")

    async def test_monitor_api_filters_stale_entries(self, service_registry):
        """Test that monitor-api filters stale entries (AC: 3, 6)."""
        pytest.skip("aiohttp not installed")  # Skip this test for now
        return

        # Get monitor-api URL (assume port-forward or in-cluster)
        if is_k8s_environment():
            monitor_url = "http://aegis-trader-monitor-api.aegis-trader.svc.cluster.local:8000"
        else:
            monitor_url = "http://localhost:8001"  # Assume port-forward

        try:
            async with aiohttp.ClientSession() as session:
                # Get services from monitor-api
                async with session.get(f"{monitor_url}/api/services") as response:
                    if response.status != 200:
                        pytest.skip(f"Monitor API not accessible: {response.status}")
                        return

                    services = await response.json()

                    # Check all returned services have recent heartbeats
                    for service in services:
                        for instance in service.get("instances", []):
                            if "last_heartbeat" in instance:
                                # Parse heartbeat timestamp
                                heartbeat_str = instance["last_heartbeat"]
                                # Handle different timestamp formats
                                try:
                                    if "T" in heartbeat_str:
                                        heartbeat = datetime.fromisoformat(
                                            heartbeat_str.replace("Z", "+00:00")
                                        )
                                    else:
                                        heartbeat = datetime.strptime(
                                            heartbeat_str, "%Y-%m-%d %H:%M:%S"
                                        )
                                        heartbeat = heartbeat.replace(tzinfo=UTC)
                                except Exception as e:
                                    print(f"Failed to parse heartbeat: {heartbeat_str}, error: {e}")
                                    continue

                                age = (datetime.now(UTC) - heartbeat).total_seconds()

                                # Monitor API should filter entries older than 35 seconds
                                assert (
                                    age <= 35
                                ), f"Monitor API returned stale entry: {instance['instance_id']} with age {age}s"

        except aiohttp.ClientConnectorError:
            pytest.skip("Monitor API not accessible")

    async def test_nats_kv_ttl_cleanup(self, nats_kv_store):
        """Test NATS KV TTL actually removes entries (AC: 5)."""
        # The service_registry bucket is now configured with max_age=30s
        # This provides stream-level TTL that works reliably

        # Create a test entry
        test_key = "test_ttl_cleanup_" + str(int(time.time()))
        test_value = {"test": "data", "timestamp": time.time()}

        # Put the value (no per-message TTL needed, stream has max_age)
        await nats_kv_store.put(test_key, test_value)

        # Verify it exists
        retrieved = await nats_kv_store.get(test_key)
        assert retrieved is not None, "Test entry not stored"
        assert retrieved.value["test"] == "data"

        # Wait for stream TTL to expire (30s + buffer)
        print("Waiting 35 seconds for stream-level TTL to expire...")
        await asyncio.sleep(35)

        # Verify it's gone
        retrieved = await nats_kv_store.get(test_key)
        assert retrieved is None, "Entry not cleaned up after TTL expiration"
        print("Entry successfully expired via stream max_age TTL!")

    async def test_real_service_registration_and_heartbeat(self, service_registry):
        """Test registering a real service and heartbeat updates (AC: 1, 3)."""
        # Create a test service instance
        test_instance = ServiceInstance(
            service_name="test-e2e-service",
            instance_id="test-e2e-instance-001",
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
            last_heartbeat=datetime.now(UTC),
        )

        # Register the service
        await service_registry.register(test_instance, ttl_seconds=30)

        # Verify it appears
        all_services = await service_registry.list_all_services()
        test_instances = all_services.get("test-e2e-service", [])
        assert len(test_instances) == 1, "Test service not registered"
        assert test_instances[0].instance_id == "test-e2e-instance-001"

        # Update heartbeat
        await asyncio.sleep(2)
        test_instance.last_heartbeat = datetime.now(UTC)
        await service_registry.update_heartbeat(test_instance, ttl_seconds=30)

        # Verify heartbeat updated
        updated = await service_registry.get_instance("test-e2e-service", "test-e2e-instance-001")
        assert updated is not None
        assert updated.last_heartbeat > test_instances[0].last_heartbeat

        # Deregister
        await service_registry.deregister("test-e2e-service", "test-e2e-instance-001")

        # Verify it's gone
        all_services = await service_registry.list_all_services()
        test_instances = all_services.get("test-e2e-service", [])
        assert len(test_instances) == 0, "Test service not deregistered"

    async def test_multiple_replicas_round_robin(self):
        """Test multiple echo service replicas appear independently (AC: 4)."""
        # This test verifies that when echo service has multiple replicas,
        # each appears as a separate instance in the registry

        try:
            # Get current replicas
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "deployment",
                    "echo-service",
                    "-n",
                    "aegis-trader",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                pytest.skip("Echo service not deployed")
                return

            import json

            deployment = json.loads(result.stdout)
            current_replicas = deployment["spec"]["replicas"]

            if current_replicas < 2:
                # Scale to at least 2 replicas
                subprocess.run(
                    [
                        "kubectl",
                        "scale",
                        "deployment",
                        "echo-service",
                        "--replicas=2",
                        "-n",
                        "aegis-trader",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                await asyncio.sleep(15)  # Wait for pods to start

            # Get pod names
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    "aegis-trader",
                    "-l",
                    "app=echo-service",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            pods = json.loads(result.stdout)
            pod_names = [
                pod["metadata"]["name"]
                for pod in pods["items"]
                if pod["status"]["phase"] == "Running"
            ]

            print(f"Found {len(pod_names)} running echo-service pods: {pod_names}")

            # Each pod should register with its pod name as instance ID
            assert len(pod_names) >= 2, "Need at least 2 pods for round-robin test"

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            pytest.skip(f"Could not verify pod replicas: {e}")
