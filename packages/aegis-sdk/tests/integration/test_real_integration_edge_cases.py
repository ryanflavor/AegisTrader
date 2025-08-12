"""Real integration tests for edge cases without any mocks."""

import asyncio

import pytest

from aegis_sdk.domain.models import Command, Event, RPCRequest
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


class TestRealIntegrationEdgeCases:
    """Test edge cases with real NATS connections."""

    @pytest.mark.asyncio
    async def test_connection_pool_multiple_urls(self, nats_container):
        """Test connecting to multiple NATS URLs with real connections."""
        config = NATSConnectionConfig(pool_size=3)
        adapter = NATSAdapter(config=config)
        # Connect to same server multiple times (simulating multiple servers)
        await adapter.connect([nats_container, nats_container, nats_container])

        assert await adapter.is_connected()
        assert len(adapter._connections) == 3

        # Verify all connections work
        for _i in range(3):
            conn = adapter._get_connection()
            assert conn.is_connected

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_rpc_timeout_real(self, nats_adapter):
        """Test RPC timeout with real NATS (no handler registered)."""
        request = RPCRequest(
            target="nonexistent_service",
            method="test_method",
            timeout=0.5,  # Short timeout
        )

        response = await nats_adapter.call_rpc(request)
        assert not response.success
        assert "no responders" in response.error.lower()

    @pytest.mark.asyncio
    async def test_event_publishing_with_large_payload(self, nats_adapter):
        """Test publishing events with large payloads."""
        # Create a large payload
        large_data = {"data": "x" * 10000, "items": list(range(1000))}
        event = Event(domain="test", event_type="large_payload", payload=large_data)

        # Should handle large payload
        await nats_adapter.publish_event(event)

        # Verify by subscribing and receiving
        received = []

        async def handler(evt):
            received.append(evt)

        await nats_adapter.subscribe_event("events.test.large_payload", handler)
        await asyncio.sleep(0.1)

        # Publish again
        await nats_adapter.publish_event(event)
        await asyncio.sleep(0.1)

        assert len(received) >= 1
        assert received[0].payload["data"] == large_data["data"]

    @pytest.mark.asyncio
    async def test_command_without_jetstream(self):
        """Test command operations when JetStream is not available."""
        # Create adapter without connecting (no JetStream)
        config = NATSConnectionConfig()

        adapter = NATSAdapter(config=config)

        command = Command(target="test", command="test_cmd", payload={"test": True})

        with pytest.raises(Exception, match="JetStream not initialized"):
            await adapter.send_command(command)

    @pytest.mark.asyncio
    async def test_concurrent_rpc_calls(self, nats_adapter):
        """Test multiple concurrent RPC calls."""

        # Register a simple RPC handler
        async def echo_handler(params):
            await asyncio.sleep(0.01)  # Simulate work
            return {"echo": params.get("message", "")}

        await nats_adapter.register_rpc_handler("test_service", "echo", echo_handler)
        await asyncio.sleep(0.1)  # Let handler register

        # Make multiple concurrent calls
        tasks = []
        for i in range(10):
            request = RPCRequest(
                target="test_service",
                method="echo",
                params={"message": f"test_{i}"},
                timeout=2.0,
            )
            tasks.append(nats_adapter.call_rpc(request))

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for i, response in enumerate(responses):
            assert response.success
            assert response.result["echo"] == f"test_{i}"

    @pytest.mark.asyncio
    async def test_service_registration_and_heartbeat(self, nats_adapter):
        """Test service registration and heartbeat functionality."""
        service_name = "test_heartbeat_service"
        instance_id = "instance_123"

        # Register service
        await nats_adapter.register_service(service_name, instance_id)

        # Send heartbeats
        for _ in range(3):
            await nats_adapter.send_heartbeat(service_name, instance_id)
            await asyncio.sleep(0.1)

        # Unregister
        await nats_adapter.unregister_service(service_name, instance_id)

    @pytest.mark.asyncio
    async def test_wildcard_event_patterns(self, nats_adapter):
        """Test wildcard event subscription patterns with real NATS."""
        received_events = []

        async def handler(event):
            received_events.append(event)

        # Subscribe to all events in test domain
        await nats_adapter.subscribe_event("events.test.*", handler)
        await asyncio.sleep(0.1)

        # Publish different event types
        events = [
            Event(domain="test", event_type="created", payload={"id": 1}),
            Event(domain="test", event_type="updated", payload={"id": 2}),
            Event(domain="test", event_type="deleted", payload={"id": 3}),
        ]

        for event in events:
            await nats_adapter.publish_event(event)

        await asyncio.sleep(0.2)

        # Should receive all events
        assert len(received_events) >= 3
        event_types = {e.event_type for e in received_events}
        assert "created" in event_types
        assert "updated" in event_types
        assert "deleted" in event_types

    @pytest.mark.asyncio
    async def test_invalid_method_name_validation(self, nats_adapter):
        """Test RPC method name validation."""
        from aegis_sdk.application.service import Service

        service = Service("test_service", nats_adapter)

        # Invalid method name should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await service.register_rpc_method("invalid-method-name", lambda x: x)
        assert "Invalid method name" in str(exc_info.value)
