"""Integration tests for K8s examples and developer tools.

These tests verify that all SDK examples work correctly with the local K8s environment.
They follow DDD testing principles with clear Given-When-Then structure.
"""

from __future__ import annotations

import asyncio
import subprocess
import time

import pytest

from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.developer import quick_setup
from aegis_sdk.developer.config_validator import ConfigurationSpec, ConfigurationValidator
from aegis_sdk.developer.environment import detect_environment
from aegis_sdk.developer.k8s_discovery import K8sNATSDiscovery
from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.value_objects import FailoverPolicy


@pytest.mark.integration
@pytest.mark.k8s
class TestK8sNATSDiscovery:
    """Test automatic NATS discovery from K8s services."""

    def test_discovers_nats_from_k8s(self):
        """Given K8s environment, When discovering NATS, Then return correct URL."""
        # Given
        discovery = K8sNATSDiscovery()

        # When
        nats_url = discovery.discover_nats()

        # Then
        assert nats_url is not None
        assert nats_url.startswith("nats://")
        assert "4222" in nats_url

    def test_detects_port_forwarding(self):
        """Given port-forwarding active, When checking, Then detect it."""
        # Given
        discovery = K8sNATSDiscovery()

        # When
        is_forwarded = discovery.is_port_forwarding_active()

        # Then
        # This should be true if setup_k8s_dev.sh was run
        if is_forwarded:
            assert discovery.discover_nats() == "nats://localhost:4222"

    def test_handles_missing_kubectl(self, monkeypatch):
        """Given kubectl not available, When discovering, Then return default."""
        # Given
        monkeypatch.setenv("PATH", "/tmp")  # Remove kubectl from path
        discovery = K8sNATSDiscovery()

        # When
        nats_url = discovery.discover_nats()

        # Then
        assert nats_url == "nats://localhost:4222"  # Falls back to default


@pytest.mark.integration
@pytest.mark.asyncio
class TestPortForwardingExamples:
    """Test that examples work with port-forwarding."""

    async def test_echo_service_with_port_forward(self):
        """Given port-forwarded NATS, When running echo service, Then it works."""
        # Given
        service = await quick_setup("test-echo")

        # When
        @service.rpc("echo")
        async def echo(params):
            return {"echo": params.get("message", "")}

        await service.start()

        # Then - Service should be registered
        assert service._registry is not None

        # Test RPC call
        client = await quick_setup("test-client")
        response = await client.call_rpc("test-echo", "echo", {"message": "Hello K8s"})
        assert response["echo"] == "Hello K8s"

        # Cleanup
        await service.stop()
        await client.stop()

    async def test_load_balanced_service_multiple_instances(self):
        """Given multiple instances, When calling RPC, Then load balances."""
        # Given
        services = []
        for i in range(3):
            service = await quick_setup("lb-test", instance_id=f"instance-{i}")

            @service.rpc("process")
            async def process(params):
                return {"instance": service.instance_id, "data": params}

            await service.start()
            services.append(service)

        await asyncio.sleep(1)  # Let services register

        # When - Make multiple calls
        client = await quick_setup("test-client")
        instances_hit = set()

        for i in range(10):
            response = await client.call_rpc("lb-test", "process", {"request": i})
            instances_hit.add(response["instance"])

        # Then - Should hit multiple instances
        assert len(instances_hit) > 1  # Load balanced

        # Cleanup
        for service in services:
            await service.stop()
        await client.stop()

    async def test_single_active_failover(self):
        """Given single-active services, When leader fails, Then failover occurs."""
        # Given
        leader = SingleActiveService(
            name="sa-test",
            instance_id="leader",
            nats_url="nats://localhost:4222",
            failover_policy=FailoverPolicy.aggressive(),
        )

        standby = SingleActiveService(
            name="sa-test",
            instance_id="standby",
            nats_url="nats://localhost:4222",
            failover_policy=FailoverPolicy.aggressive(),
        )

        await leader.start()
        await asyncio.sleep(1)
        await standby.start()
        await asyncio.sleep(2)

        # When
        initial_leader = leader.is_leader
        assert initial_leader is True
        assert standby.is_leader is False

        # Kill the leader
        await leader.stop()

        # Wait for failover
        await asyncio.sleep(3)

        # Then - Standby should become leader
        assert standby.is_leader is True

        # Cleanup
        await standby.stop()


@pytest.mark.integration
@pytest.mark.asyncio
class TestFailoverScenariosInK8s:
    """Test failover scenarios in K8s environment."""

    async def test_failover_timing_measurement(self):
        """Given leader failure, When measuring failover, Then < 2 seconds."""
        # Given
        services = []
        for i in range(2):
            service = SingleActiveService(
                name="failover-timing",
                instance_id=f"instance-{i}",
                nats_url="nats://localhost:4222",
                failover_policy=FailoverPolicy.aggressive(),
            )
            await service.start()
            services.append(service)

        await asyncio.sleep(2)  # Let election complete

        # Identify leader
        leader = next(s for s in services if s.is_leader)
        standby = next(s for s in services if not s.is_leader)

        # When - Kill leader and measure time
        start_time = time.time()
        await leader.stop()

        # Wait for standby to become leader
        while not standby.is_leader and time.time() - start_time < 5:
            await asyncio.sleep(0.1)

        failover_time = time.time() - start_time

        # Then
        assert standby.is_leader is True
        assert failover_time < 2.0  # Aggressive policy < 2s

        # Cleanup
        await standby.stop()

    async def test_multiple_rapid_failovers(self):
        """Given multiple instances, When rapid failures, Then handle gracefully."""
        # Given
        services = []
        for i in range(3):
            service = SingleActiveService(
                name="rapid-failover",
                instance_id=f"instance-{i}",
                nats_url="nats://localhost:4222",
                failover_policy=FailoverPolicy.aggressive(),
            )
            await service.start()
            services.append(service)

        await asyncio.sleep(2)

        # When - Kill leaders repeatedly
        for round in range(2):
            # Find and kill current leader
            leader = next((s for s in services if s.is_leader), None)
            if leader:
                await leader.stop()
                services.remove(leader)
                await asyncio.sleep(2)  # Wait for failover

        # Then - Should still have a leader
        remaining = services[0] if services else None
        if remaining:
            assert remaining.is_leader is True

        # Cleanup
        for service in services:
            try:
                await service.stop()
            except:
                pass


@pytest.mark.integration
@pytest.mark.asyncio
class TestServiceRegistrationPersistence:
    """Test service registration persistence in KV store."""

    async def test_registration_persists_in_kv(self):
        """Given service registration, When checking KV, Then entry exists."""
        # Given
        service = await quick_setup("persistence-test")
        await service.start()

        # When - Check KV store directly
        kv_store = service._kv_store
        await kv_store.connect("service_registry")

        key = f"services.persistence-test.{service.instance_id}"
        value = await kv_store.get(key)

        # Then
        assert value is not None
        assert "instance_id" in value
        assert value["status"] == ServiceStatus.ACTIVE

        # Cleanup
        await service.stop()

    async def test_deregistration_removes_from_kv(self):
        """Given registered service, When stopped, Then removed from KV."""
        # Given
        service = await quick_setup("deregister-test")
        await service.start()

        kv_store = service._kv_store
        await kv_store.connect("service_registry")
        key = f"services.deregister-test.{service.instance_id}"

        # Verify registered
        value = await kv_store.get(key)
        assert value is not None

        # When
        await service.stop()
        await asyncio.sleep(1)

        # Then
        value = await kv_store.get(key)
        assert value is None  # Should be removed

    async def test_ttl_expiry_removes_stale_services(self):
        """Given service with TTL, When heartbeat stops, Then expires."""
        # Given
        service = await quick_setup(
            "ttl-test",
            heartbeat_interval=1,
            ttl=3,  # 3 second TTL
        )
        await service.start()

        # When - Stop heartbeat but don't deregister
        service._heartbeat_task.cancel()

        # Wait for TTL to expire
        await asyncio.sleep(4)

        # Then - Should be removed from registry
        client = await quick_setup("test-client")
        services = await client.discover("ttl-test")
        assert len(services) == 0

        # Cleanup
        await service.stop()
        await client.stop()


@pytest.mark.integration
@pytest.mark.asyncio
class TestResourceCleanup:
    """Test cleanup of test resources."""

    async def test_service_cleanup_on_exception(self):
        """Given service with error, When exception, Then cleanup properly."""
        # Given
        service = await quick_setup("cleanup-test")

        @service.rpc("fail")
        async def fail_handler(params):
            raise Exception("Intentional failure")

        await service.start()

        # When - Force an error and stop
        try:
            client = await quick_setup("test-client")
            await client.call_rpc("cleanup-test", "fail", {})
        except:
            pass  # Expected

        await service.stop()

        # Then - Should be deregistered
        services = await client.discover("cleanup-test")
        assert len(services) == 0

        await client.stop()

    async def test_multiple_service_cleanup(self):
        """Given multiple services, When batch cleanup, Then all removed."""
        # Given
        services = []
        for i in range(5):
            service = await quick_setup(f"batch-cleanup-{i}")
            await service.start()
            services.append(service)

        # When - Stop all services
        await asyncio.gather(*[service.stop() for service in services], return_exceptions=True)

        # Then - All should be deregistered
        client = await quick_setup("test-client")
        for i in range(5):
            found = await client.discover(f"batch-cleanup-{i}")
            assert len(found) == 0

        await client.stop()

    async def test_cleanup_with_pending_operations(self):
        """Given service with pending ops, When stopping, Then handle gracefully."""
        # Given
        service = await quick_setup("pending-ops")

        @service.rpc("slow")
        async def slow_handler(params):
            await asyncio.sleep(10)  # Long operation
            return {"done": True}

        await service.start()

        # When - Start operation then stop
        client = await quick_setup("test-client")
        task = asyncio.create_task(client.call_rpc("pending-ops", "slow", {}, timeout=15))

        await asyncio.sleep(0.5)  # Let request start
        await service.stop()  # Stop while processing

        # Then - Should handle gracefully
        try:
            await asyncio.wait_for(task, timeout=1)
        except (asyncio.TimeoutError, Exception):
            pass  # Expected - request should fail

        # Service should be cleaned up
        services = await client.discover("pending-ops")
        assert len(services) == 0

        await client.stop()


@pytest.mark.integration
@pytest.mark.asyncio
class TestConfigurationValidator:
    """Test configuration validation in K8s environment."""

    async def test_validator_detects_k8s_environment(self):
        """Given K8s environment, When validating, Then detects correctly."""
        # Given
        validator = ConfigurationValidator()
        config = {
            "service_name": "test-service",
            "nats_url": "nats://localhost:4222",
            "environment": "local-k8s",
        }
        spec = ConfigurationSpec(
            service_name="test-service",
            nats_url="nats://localhost:4222",
            environment="local-k8s",
            require_k8s=True,
            require_port_forward=True,
        )

        # When
        result = await validator.validate_all(config, spec)

        # Then
        # Should have k8s diagnostics
        assert "k8s_available" in result.diagnostics

        # Should check NATS connectivity
        assert "nats_connected" in result.diagnostics

    async def test_validator_provides_troubleshooting(self):
        """Given validation errors, When checking, Then provide solutions."""
        # Given
        validator = ConfigurationValidator()
        config = {
            "service_name": "",  # Invalid
            "nats_url": "invalid://url",  # Invalid
            "environment": "unknown",  # Invalid
        }

        # When
        result = await validator.validate_all(config)

        # Then
        assert result.is_valid is False
        assert len(result.issues) > 0
        assert len(result.recommendations) > 0

        # Should have resolution suggestions
        errors = result.get_issues_by_level("ERROR")
        for error in errors:
            if error.resolution:
                assert len(error.resolution) > 0


@pytest.mark.integration
def test_environment_detection():
    """Test that environment detection works correctly."""
    # Given/When
    env = detect_environment()

    # Then
    assert env in ["local-k8s", "docker", "production", "development"]

    # If kubectl is available, should detect k8s
    try:
        subprocess.run(["kubectl", "version"], capture_output=True, check=True)
        assert env == "local-k8s"
    except:
        pass  # kubectl not available


@pytest.mark.integration
@pytest.mark.asyncio
async def test_quick_setup_integration():
    """Test that quick_setup provides fully functional service."""
    # Given/When
    service = await quick_setup("integration-test")

    # Then
    assert service is not None
    assert service._nats is not None
    assert service._registry is not None
    assert service._discovery is not None

    # Should be able to start and stop
    await service.start()
    assert service._started is True

    await service.stop()
    assert service._started is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_example_flow():
    """Test complete flow from setup to teardown."""
    # Given - Setup services
    echo_service = await quick_setup("e2e-echo")

    @echo_service.rpc("echo")
    async def echo(params):
        return {"echo": params.get("message", ""), "from": echo_service.instance_id}

    order_service = SingleActiveService(
        name="e2e-orders",
        instance_id="order-1",
        nats_url="nats://localhost:4222",
        failover_policy=FailoverPolicy.balanced(),
    )

    @order_service.rpc("create")
    async def create_order(params):
        if not order_service.is_leader:
            raise Exception("NOT_ACTIVE")
        return {"order_id": "ORD-001", "status": "created"}

    # Start services
    await echo_service.start()
    await order_service.start()
    await asyncio.sleep(1)

    # When - Client interacts with services
    client = await quick_setup("e2e-client")

    # Test echo service
    echo_response = await client.call_rpc("e2e-echo", "echo", {"message": "Hello E2E"})
    assert echo_response["echo"] == "Hello E2E"

    # Test order service with retry
    max_retries = 3
    for i in range(max_retries):
        try:
            order_response = await client.call_rpc("e2e-orders", "create", {"items": ["item1"]})
            assert order_response["order_id"] == "ORD-001"
            break
        except Exception as e:
            if "NOT_ACTIVE" in str(e) and i < max_retries - 1:
                await asyncio.sleep(0.5)
                continue
            raise

    # Test service discovery
    echo_instances = await client.discover("e2e-echo")
    assert len(echo_instances) > 0

    order_instances = await client.discover("e2e-orders")
    assert len(order_instances) > 0

    # Then - Cleanup
    await echo_service.stop()
    await order_service.stop()
    await client.stop()

    # Verify cleanup
    echo_instances = await client.discover("e2e-echo")
    assert len(echo_instances) == 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-k", "k8s"])
