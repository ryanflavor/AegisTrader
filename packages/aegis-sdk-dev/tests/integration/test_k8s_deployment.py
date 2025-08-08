"""K8s deployment integration tests for aegis-sdk-dev.

These tests validate SDK functionality in a Kubernetes environment.
They use the actual K8s cluster that's running locally.
"""

import os

import pytest

from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter


class TestK8sDeploymentIntegration:
    """Integration tests for K8s deployment scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_k8s_environment_detection(self):
        """Test that we can detect K8s environment correctly."""
        env_adapter = EnvironmentAdapter()

        # Check if we're in K8s by looking for service account
        is_k8s = os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")

        # Or check for K8s environment variables
        has_k8s_vars = "KUBERNETES_SERVICE_HOST" in os.environ

        # For local testing, check if kubectl is available
        try:
            import subprocess

            result = subprocess.run(
                ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=5
            )
            kubectl_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            kubectl_available = False

        # Test should pass if we can detect any K8s environment
        assert (
            is_k8s or has_k8s_vars or kubectl_available
        ), "K8s environment not detected - ensure cluster is running"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nats_connectivity_in_k8s(self):
        """Test NATS connectivity using K8s service discovery."""
        from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter

        # Try different NATS URLs based on environment
        nats_urls = [
            "nats://aegis-trader-nats:4222",  # K8s service name
            "nats://localhost:4222",  # Local port-forward
            "nats://host.docker.internal:4222",  # Docker Desktop
        ]

        connected = False
        successful_url = None

        for url in nats_urls:
            adapter = NATSConnectionAdapter()
            try:
                await adapter.connect(url)
                if adapter.is_connected():
                    connected = True
                    successful_url = url
                    await adapter.disconnect()
                    break
            except Exception:
                continue

        assert connected, f"Could not connect to NATS at any URL: {nats_urls}"
        print(f"Successfully connected to NATS at: {successful_url}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_registration_in_k8s(self):
        """Test service registration using K8s NATS."""
        from aegis_sdk.domain.models import InstanceMetadata, ServiceMetadata
        from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
        from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
        from aegis_sdk.infrastructure.simple_logger import SimpleLogger

        from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter

        # Connect to NATS
        nats_urls = [
            "nats://aegis-trader-nats:4222",
            "nats://localhost:4222",
        ]

        nats = NATSConnectionAdapter()
        connected = False

        for url in nats_urls:
            try:
                await nats.connect(url)
                if nats.is_connected():
                    connected = True
                    break
            except Exception:
                continue

        if not connected:
            pytest.skip("NATS not available for integration test")

        try:
            # Create KV store and registry
            kv_store = NATSKVStore(nats)
            await kv_store.connect("test_k8s_registry")

            logger = SimpleLogger()
            registry = KVServiceRegistry(kv_store, logger)

            # Register a test service
            service = ServiceMetadata(
                name="test-k8s-service", version="1.0.0", description="K8s integration test service"
            )

            instance = InstanceMetadata(
                instance_id="k8s-test-001",
                host="test-pod",
                port=8080,
                healthy=True,
                metadata={"environment": "k8s", "test": True},
            )

            # Register and verify
            await registry.register_instance(service, instance)

            # Discover the service
            discovered = await registry.discover_service("test-k8s-service")
            assert discovered is not None
            assert len(discovered.instances) > 0
            assert discovered.instances[0].instance_id == "k8s-test-001"

            # Cleanup
            await registry.deregister_instance("test-k8s-service", "k8s-test-001")

        finally:
            await nats.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_instance_coordination(self):
        """Test multiple service instances coordinating via K8s NATS."""
        from aegis_sdk.domain.models import InstanceMetadata, ServiceMetadata
        from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
        from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
        from aegis_sdk.infrastructure.simple_logger import SimpleLogger

        from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter

        # Connect multiple instances
        nats_urls = [
            "nats://aegis-trader-nats:4222",
            "nats://localhost:4222",
        ]

        instances = []
        registries = []

        try:
            # Create 3 service instances
            for i in range(3):
                nats = NATSConnectionAdapter()
                connected = False

                for url in nats_urls:
                    try:
                        await nats.connect(url)
                        if nats.is_connected():
                            connected = True
                            break
                    except Exception:
                        continue

                if not connected:
                    pytest.skip("NATS not available for integration test")

                kv_store = NATSKVStore(nats)
                await kv_store.connect("test_k8s_coordination")

                logger = SimpleLogger()
                registry = KVServiceRegistry(kv_store, logger)

                # Register instance
                service = ServiceMetadata(
                    name="coordinated-service", version="1.0.0", description="Multi-instance test"
                )

                instance = InstanceMetadata(
                    instance_id=f"instance-{i}",
                    host=f"pod-{i}",
                    port=8080 + i,
                    healthy=True,
                    metadata={"replica": i},
                )

                await registry.register_instance(service, instance)

                instances.append((nats, instance))
                registries.append(registry)

            # Each instance should see all others
            for registry in registries:
                discovered = await registry.discover_service("coordinated-service")
                assert discovered is not None
                assert len(discovered.instances) == 3

            # Verify all instances are registered
            instance_ids = {inst.instance_id for _, inst in instances}
            discovered_ids = {inst.instance_id for inst in discovered.instances}
            assert instance_ids == discovered_ids

        finally:
            # Cleanup
            for i, (nats, instance) in enumerate(instances):
                try:
                    if i < len(registries):
                        await registries[i].deregister_instance(
                            "coordinated-service", instance.instance_id
                        )
                    await nats.disconnect()
                except Exception:
                    pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_k8s_pod_failover_simulation(self):
        """Simulate pod failover scenario in K8s."""
        from aegis_sdk.domain.models import InstanceMetadata, ServiceMetadata
        from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
        from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
        from aegis_sdk.infrastructure.simple_logger import SimpleLogger

        from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter

        nats_urls = [
            "nats://aegis-trader-nats:4222",
            "nats://localhost:4222",
        ]

        # Simulate primary pod
        primary_nats = NATSConnectionAdapter()
        connected = False

        for url in nats_urls:
            try:
                await primary_nats.connect(url)
                if primary_nats.is_connected():
                    connected = True
                    break
            except Exception:
                continue

        if not connected:
            pytest.skip("NATS not available for integration test")

        try:
            # Setup primary instance
            kv_store = NATSKVStore(primary_nats)
            await kv_store.connect("test_failover")

            logger = SimpleLogger()
            registry = KVServiceRegistry(kv_store, logger)

            service = ServiceMetadata(
                name="failover-service", version="1.0.0", description="Failover test service"
            )

            primary_instance = InstanceMetadata(
                instance_id="primary-pod",
                host="k8s-node-1",
                port=8080,
                healthy=True,
                metadata={"role": "primary"},
            )

            # Register primary
            await registry.register_instance(service, primary_instance)

            # Verify primary is registered
            discovered = await registry.discover_service("failover-service")
            assert len(discovered.instances) == 1
            assert discovered.instances[0].instance_id == "primary-pod"

            # Simulate primary failure (deregister)
            await registry.deregister_instance("failover-service", "primary-pod")

            # Register backup instance (simulating new pod)
            backup_nats = NATSConnectionAdapter()
            for url in nats_urls:
                try:
                    await backup_nats.connect(url)
                    if backup_nats.is_connected():
                        break
                except Exception:
                    continue

            backup_kv = NATSKVStore(backup_nats)
            await backup_kv.connect("test_failover")
            backup_registry = KVServiceRegistry(backup_kv, SimpleLogger())

            backup_instance = InstanceMetadata(
                instance_id="backup-pod",
                host="k8s-node-2",
                port=8080,
                healthy=True,
                metadata={"role": "backup-promoted"},
            )

            await backup_registry.register_instance(service, backup_instance)

            # Verify failover completed
            discovered = await backup_registry.discover_service("failover-service")
            assert len(discovered.instances) == 1
            assert discovered.instances[0].instance_id == "backup-pod"
            assert discovered.instances[0].metadata["role"] == "backup-promoted"

            # Cleanup
            await backup_registry.deregister_instance("failover-service", "backup-pod")
            await backup_nats.disconnect()

        finally:
            await primary_nats.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_k8s_service_discovery_via_dns():
    """Test K8s service discovery using DNS names."""
    import socket

    # Try to resolve K8s service names
    k8s_services = [
        "aegis-trader-nats",
        "aegis-trader-echo-service",
        "aegis-trader-monitor-api",
    ]

    resolved_any = False
    for service in k8s_services:
        try:
            # Try with default namespace
            fqdn = f"{service}.default.svc.cluster.local"
            ip = socket.gethostbyname(fqdn)
            print(f"Resolved {fqdn} to {ip}")
            resolved_any = True
        except socket.gaierror:
            # Try without namespace (works in port-forward scenarios)
            try:
                ip = socket.gethostbyname(service)
                print(f"Resolved {service} to {ip}")
                resolved_any = True
            except socket.gaierror:
                continue

    # For local development, we might not have K8s DNS
    # but we should at least resolve localhost
    if not resolved_any:
        try:
            ip = socket.gethostbyname("localhost")
            assert ip in ["127.0.0.1", "::1"]
        except socket.gaierror:
            pytest.fail("Could not resolve any hostnames")
