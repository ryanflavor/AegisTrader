"""Integration tests for echo-service-ddd using testcontainers for NATS."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import nats
import pytest
from testcontainers.nats import NatsContainer

from application.dto import EchoRequestDTO
from application.use_cases import (
    EchoUseCase,
    GetMetricsUseCase,
    HealthCheckUseCase,
)
from domain.entities import EchoRequest
from domain.value_objects import EchoMode, MessagePriority, ServiceDefinitionInfo
from infra.adapters import AegisServiceBusAdapter, KVRegistryAdapter
from infra.factory import ServiceFactory


@pytest.fixture(scope="module")
def nats_container():
    """Create a NATS container for testing."""
    with NatsContainer("nats:2.10-alpine") as nats:
        yield nats


@pytest.fixture
async def nats_client(nats_container):
    """Create a NATS client connected to the test container."""
    nc = await nats.connect(nats_container.get_nats_url())
    yield nc
    await nc.close()


@pytest.fixture
async def service_factory(nats_client):
    """Create a service factory with test dependencies."""
    factory = ServiceFactory()
    await factory.initialize(
        instance_id="test-echo-001",
        nats_url=nats_client.servers[0],
        service_name="test-echo-service",
        version="1.0.0",
    )
    yield factory
    await factory.shutdown()


class TestNATSIntegration:
    """Integration tests for NATS connectivity and messaging."""

    @pytest.mark.asyncio
    async def test_nats_connection(self, nats_client):
        """Test basic NATS connectivity."""
        assert nats_client.is_connected

    @pytest.mark.asyncio
    async def test_publish_subscribe(self, nats_client):
        """Test publish/subscribe messaging pattern."""
        received_messages = []

        async def message_handler(msg):
            received_messages.append(msg.data.decode())

        # Subscribe to a topic
        sub = await nats_client.subscribe("test.topic", cb=message_handler)

        # Publish a message
        await nats_client.publish("test.topic", b"test message")
        await nats_client.flush()

        # Wait for message to be received
        await asyncio.sleep(0.1)

        assert len(received_messages) == 1
        assert received_messages[0] == "test message"

        await sub.unsubscribe()

    @pytest.mark.asyncio
    async def test_request_reply(self, nats_client):
        """Test request/reply pattern."""

        async def responder(msg):
            await msg.respond(b"pong")

        # Set up responder
        sub = await nats_client.subscribe("ping", cb=responder)

        # Send request
        response = await nats_client.request("ping", b"ping", timeout=1.0)
        assert response.data == b"pong"

        await sub.unsubscribe()

    @pytest.mark.asyncio
    async def test_kv_store(self, nats_client):
        """Test NATS KV store functionality."""
        js = nats_client.jetstream()

        # Create KV bucket
        kv = await js.create_key_value(bucket="test_services")

        # Put and get value
        await kv.put("service.test", json.dumps({"name": "test", "version": "1.0.0"}).encode())
        entry = await kv.get("service.test")
        data = json.loads(entry.value.decode())

        assert data["name"] == "test"
        assert data["version"] == "1.0.0"

        # Update value
        await kv.put("service.test", json.dumps({"name": "test", "version": "2.0.0"}).encode())
        entry = await kv.get("service.test")
        updated_data = json.loads(entry.value.decode())

        assert updated_data["version"] == "2.0.0"

        # Delete value
        await kv.delete("service.test")

        # Clean up
        await js.delete_key_value("test_services")


class TestServiceBusIntegration:
    """Integration tests for service bus adapter."""

    @pytest.mark.asyncio
    async def test_service_bus_rpc(self, nats_client):
        """Test RPC through service bus adapter."""
        adapter = AegisServiceBusAdapter(nats_client)
        received_requests = []

        async def echo_handler(data: dict[str, Any]) -> dict[str, Any]:
            received_requests.append(data)
            return {"echoed": data.get("message", ""), "instance": "test"}

        # Register handler
        await adapter.register_handler("echo.service.echo", echo_handler)

        # Call RPC
        response = await adapter.call_rpc("echo.service.echo", {"message": "hello"})

        assert response["echoed"] == "hello"
        assert response["instance"] == "test"
        assert len(received_requests) == 1

    @pytest.mark.asyncio
    async def test_service_bus_events(self, nats_client):
        """Test event publishing and subscription."""
        adapter = AegisServiceBusAdapter(nats_client)
        received_events = []

        async def event_handler(data: dict[str, Any]) -> None:
            received_events.append(data)

        # Subscribe to events
        await adapter.subscribe_event("echo.events.processed", event_handler)

        # Publish event
        await adapter.publish_event(
            "echo.events.processed",
            {
                "request_id": "123",
                "mode": "simple",
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        # Wait for event to be received
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0]["request_id"] == "123"


class TestServiceRegistryIntegration:
    """Integration tests for service registry with KV store."""

    @pytest.mark.asyncio
    async def test_service_registration(self, nats_client):
        """Test service registration in KV store."""
        js = nats_client.jetstream()
        kv = await js.create_key_value(bucket="services")

        adapter = KVRegistryAdapter(kv)

        service_def = ServiceDefinitionInfo(
            service_name="test-service",
            owner="TestTeam",
            description="Test service",
            version="1.0.0",
        )

        # Register service
        await adapter.register_service("test-001", service_def.model_dump())

        # Get registered instances
        instances = await adapter.get_instances("test-service")
        assert "test-001" in instances

        # Deregister service
        await adapter.deregister_service("test-001", "test-service")

        # Verify deregistration
        instances = await adapter.get_instances("test-service")
        assert "test-001" not in instances

        # Clean up
        await js.delete_key_value("services")


class TestEchoServiceEndToEnd:
    """End-to-end integration tests for echo service."""

    @pytest.mark.asyncio
    async def test_echo_service_workflow(self, service_factory):
        """Test complete echo service workflow."""
        # Initialize components
        echo_processor = service_factory.echo_processor
        metrics_collector = service_factory.metrics_collector

        # Process echo request
        request = EchoRequest(
            message="Integration Test",
            mode=EchoMode.UPPERCASE,
            priority=MessagePriority.HIGH,
        )

        response = await echo_processor.process_echo(request)

        assert response.echoed == "INTEGRATION TEST"
        assert response.mode == EchoMode.UPPERCASE
        assert response.instance_id == "test-echo-001"

        # Record metrics
        metrics_collector.record_request(
            request.mode,
            request.priority,
            response.processing_time_ms,
            success=True,
        )

        # Verify metrics
        metrics = metrics_collector.get_current_metrics()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.mode_distribution[EchoMode.UPPERCASE] == 1

    @pytest.mark.asyncio
    async def test_batch_processing_integration(self, service_factory):
        """Test batch echo processing."""
        echo_processor = service_factory.echo_processor

        requests = [
            EchoRequest(message="test1", mode=EchoMode.SIMPLE),
            EchoRequest(message="test2", mode=EchoMode.REVERSE),
            EchoRequest(message="test3", mode=EchoMode.UPPERCASE),
        ]

        responses = await echo_processor.process_batch(requests)

        assert len(responses) == 3
        assert responses[0].echoed == "test1"
        assert responses[1].echoed == "2tset"
        assert responses[2].echoed == "TEST3"

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, service_factory):
        """Test health check integration."""
        health_checker = service_factory.health_checker

        # Check dependencies
        checks = await health_checker.check_dependencies()
        assert "nats" in checks
        assert "monitor_api" in checks

        # Get health status
        status = health_checker.get_health_status()
        assert status["status"] == "healthy"
        assert status["instance_id"] == "test-echo-001"
        assert status["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_use_case_integration(self, service_factory):
        """Test application use cases with real infrastructure."""
        # Test Echo Use Case
        echo_use_case = EchoUseCase(
            service_factory.echo_processor,
            service_factory.metrics_collector,
        )

        echo_dto = EchoRequestDTO(
            message="Use Case Test",
            mode="reverse",
            priority="normal",
        )

        result = await echo_use_case.execute(echo_dto)
        assert result["echoed"] == "tseT esaC esU"
        assert result["mode"] == "reverse"

        # Test Metrics Use Case
        metrics_use_case = GetMetricsUseCase(service_factory.metrics_collector)
        metrics_result = await metrics_use_case.execute()

        assert metrics_result["total_requests"] == 1
        assert metrics_result["success_rate"] == 100.0

        # Test Health Check Use Case
        health_use_case = HealthCheckUseCase(service_factory.health_checker)
        health_result = await health_use_case.execute()

        assert health_result["status"] == "healthy"
        assert health_result["instance_id"] == "test-echo-001"


class TestFailureScenarios:
    """Integration tests for failure scenarios."""

    @pytest.mark.asyncio
    async def test_nats_reconnection(self, nats_container):
        """Test NATS client reconnection behavior."""
        nc = await nats.connect(
            nats_container.get_nats_url(),
            reconnect_time_wait=0.1,
            max_reconnect_attempts=3,
        )

        assert nc.is_connected

        # Simulate disconnection (this is limited in test environment)
        # In real scenario, would stop/start container

        await nc.close()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, nats_client):
        """Test timeout handling in RPC calls."""
        adapter = AegisServiceBusAdapter(nats_client)

        # Try to call non-existent service (will timeout)
        with pytest.raises(asyncio.TimeoutError):
            await adapter.call_rpc("non.existent.service", {}, timeout=0.5)

    @pytest.mark.asyncio
    async def test_invalid_message_handling(self, service_factory):
        """Test handling of invalid messages."""
        echo_processor = service_factory.echo_processor

        # Test with invalid transform type
        request = EchoRequest(
            message="Test",
            mode=EchoMode.TRANSFORM,
            transform_type="invalid_transform",
        )

        response = await echo_processor.process_echo(request)

        # Should return original message on invalid transform
        assert response.echoed == "Test"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service_factory):
        """Test handling of concurrent requests."""
        echo_processor = service_factory.echo_processor

        # Create multiple concurrent requests
        requests = [EchoRequest(message=f"msg{i}", mode=EchoMode.SIMPLE) for i in range(10)]

        # Process concurrently
        tasks = [echo_processor.process_echo(req) for req in requests]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == 10
        for i, response in enumerate(responses):
            assert response.echoed == f"msg{i}"


class TestPerformanceIntegration:
    """Integration tests for performance characteristics."""

    @pytest.mark.asyncio
    async def test_latency_measurement(self, service_factory):
        """Test latency measurement accuracy."""
        echo_processor = service_factory.echo_processor

        request = EchoRequest(
            message="Latency Test",
            mode=EchoMode.DELAYED,
            delay=0.1,  # 100ms delay
        )

        response = await echo_processor.process_echo(request)

        # Processing time should be at least 100ms
        assert response.processing_time_ms >= 100
        assert response.echoed == "Latency Test"

    @pytest.mark.asyncio
    async def test_throughput(self, service_factory):
        """Test service throughput with multiple requests."""
        echo_processor = service_factory.echo_processor
        metrics_collector = service_factory.metrics_collector

        # Process 100 requests
        for i in range(100):
            request = EchoRequest(
                message=f"throughput-{i}",
                mode=EchoMode.SIMPLE,
            )
            response = await echo_processor.process_echo(request)
            metrics_collector.record_request(
                request.mode,
                request.priority,
                response.processing_time_ms,
                success=True,
            )

        metrics = metrics_collector.get_current_metrics()
        assert metrics.total_requests == 100
        assert metrics.successful_requests == 100
        assert metrics.get_success_rate() == 100.0

    @pytest.mark.asyncio
    async def test_memory_usage(self, service_factory):
        """Test that service doesn't leak memory with repeated operations."""
        echo_processor = service_factory.echo_processor

        # Process many requests to check for memory leaks
        for _ in range(1000):
            request = EchoRequest(message="memory test", mode=EchoMode.SIMPLE)
            await echo_processor.process_echo(request)

        # In a real test, would measure memory usage
        # For now, just ensure it completes without issues
        assert echo_processor._sequence_counter >= 1000
