"""Tests for NATSAdapter event subscription modes."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.domain.models import Event
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


class TestNATSAdapterEventModes:
    """Test cases for NATSAdapter event subscription modes."""

    @pytest.fixture
    def nats_adapter(self):
        """Create a NATSAdapter instance with mocked connections."""
        adapter = NATSAdapter()
        adapter._instance_id = "test-service-abc123"
        adapter._service_name = "test-service"
        return adapter

    @pytest.fixture
    def mock_jetstream(self):
        """Create a mock JetStream context."""
        js = MagicMock()
        js.subscribe = AsyncMock()
        return js

    @pytest.fixture
    def mock_nats_client(self):
        """Create a mock NATS client."""
        client = MagicMock()
        client.is_connected = True
        client.subscribe = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_compete_mode_uses_queue(self, nats_adapter, mock_jetstream):
        """Test compete mode subscription uses queue."""
        nats_adapter._js = mock_jetstream
        nats_adapter._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Subscribe with compete mode
        await nats_adapter.subscribe_event(
            "order.created", handler, "test-service-order-created", mode="compete"
        )

        # Verify JetStream subscribe was called with queue
        mock_jetstream.subscribe.assert_called_once()
        call_kwargs = mock_jetstream.subscribe.call_args.kwargs

        assert call_kwargs["subject"] == "order.created"
        assert call_kwargs["manual_ack"] is True
        assert call_kwargs["queue"] == "test-service"  # service name as queue
        assert "durable" not in call_kwargs  # No durable when using queue

    @pytest.mark.asyncio
    async def test_broadcast_mode_unique_durable(self, nats_adapter, mock_jetstream):
        """Test broadcast mode creates unique durable name per instance."""
        nats_adapter._js = mock_jetstream
        nats_adapter._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Subscribe with broadcast mode
        await nats_adapter.subscribe_event(
            "config.updated", handler, "test-service-config-updated", mode="broadcast"
        )

        # Verify JetStream subscribe was called with unique durable
        mock_jetstream.subscribe.assert_called_once()
        call_kwargs = mock_jetstream.subscribe.call_args.kwargs

        assert call_kwargs["subject"] == "config.updated"
        # Durable name should include instance ID for broadcast
        assert call_kwargs["durable"] == "test-service-config-updated-test-service-abc123"
        assert call_kwargs["manual_ack"] is True
        assert "queue" not in call_kwargs  # No queue for broadcast

    @pytest.mark.asyncio
    async def test_default_mode_is_compete(self, nats_adapter, mock_jetstream):
        """Test default mode is compete when not specified."""
        nats_adapter._js = mock_jetstream
        nats_adapter._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Subscribe without specifying mode
        await nats_adapter.subscribe_event(
            "user.registered", handler, "test-service-user-registered"
        )

        # Should use compete mode behavior
        call_kwargs = mock_jetstream.subscribe.call_args.kwargs
        assert call_kwargs["queue"] == "test-service"

    @pytest.mark.asyncio
    async def test_wildcard_pattern_compete_mode(self, nats_adapter, mock_nats_client):
        """Test wildcard patterns with compete mode use core NATS."""
        nats_adapter._js = MagicMock()
        nats_adapter._connections = [mock_nats_client]

        async def handler(event: Event):
            pass

        # Subscribe with wildcard and compete mode
        await nats_adapter.subscribe_event(
            "trade.*", handler, "test-service-trade-star", mode="compete"
        )

        # Should use core NATS for wildcards (current implementation)
        mock_nats_client.subscribe.assert_called_once()
        call_args = mock_nats_client.subscribe.call_args

        assert call_args[0][0] == "trade.*"  # pattern
        # Core NATS doesn't support queue directly

    @pytest.mark.asyncio
    async def test_wildcard_pattern_broadcast_mode(self, nats_adapter, mock_nats_client):
        """Test wildcard patterns with broadcast mode use core NATS."""
        nats_adapter._js = MagicMock()
        nats_adapter._connections = [mock_nats_client]

        async def handler(event: Event):
            pass

        # Subscribe with wildcard and broadcast mode
        await nats_adapter.subscribe_event(
            "log.*", handler, "test-service-log-star", mode="broadcast"
        )

        # Should use core NATS for wildcards
        mock_nats_client.subscribe.assert_called_once()
        call_args = mock_nats_client.subscribe.call_args

        assert call_args[0][0] == "log.*"  # pattern

    @pytest.mark.asyncio
    async def test_invalid_mode_raises_error(self, nats_adapter, mock_jetstream):
        """Test invalid mode raises ValueError."""
        nats_adapter._js = mock_jetstream
        nats_adapter._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Subscribe with invalid mode
        with pytest.raises(ValueError) as exc_info:
            await nats_adapter.subscribe_event(
                "order.created", handler, "test-service-order-created", mode="invalid"
            )

        assert "Invalid mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_instances_compete_mode(self, mock_jetstream):
        """Test multiple instances with compete mode share same queue."""
        # Create two adapter instances for same service
        adapter1 = NATSAdapter()
        adapter1._instance_id = "pricing-service-abc123"
        adapter1._service_name = "pricing-service"
        adapter1._js = mock_jetstream
        adapter1._connections = [MagicMock()]

        adapter2 = NATSAdapter()
        adapter2._instance_id = "pricing-service-def456"
        adapter2._service_name = "pricing-service"
        adapter2._js = mock_jetstream
        adapter2._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Both instances subscribe with compete mode
        await adapter1.subscribe_event(
            "market.data", handler, "pricing-service-market-data", mode="compete"
        )

        await adapter2.subscribe_event(
            "market.data", handler, "pricing-service-market-data", mode="compete"
        )

        # Both should use same queue
        calls = mock_jetstream.subscribe.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["queue"] == "pricing-service"
        assert calls[1].kwargs["queue"] == "pricing-service"
        # No durable when using queue
        assert "durable" not in calls[0].kwargs
        assert "durable" not in calls[1].kwargs

    @pytest.mark.asyncio
    async def test_multiple_instances_broadcast_mode(self, mock_jetstream):
        """Test multiple instances with broadcast mode have unique durables."""
        # Create two adapter instances for same service
        adapter1 = NATSAdapter()
        adapter1._instance_id = "monitor-service-abc123"
        adapter1._service_name = "monitor-service"
        adapter1._js = mock_jetstream
        adapter1._connections = [MagicMock()]

        adapter2 = NATSAdapter()
        adapter2._instance_id = "monitor-service-def456"
        adapter2._service_name = "monitor-service"
        adapter2._js = mock_jetstream
        adapter2._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Both instances subscribe with broadcast mode
        await adapter1.subscribe_event(
            "system.alert", handler, "monitor-service-system-alert", mode="broadcast"
        )

        await adapter2.subscribe_event(
            "system.alert", handler, "monitor-service-system-alert", mode="broadcast"
        )

        # Should have unique durable names
        calls = mock_jetstream.subscribe.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["durable"] == "monitor-service-system-alert-monitor-service-abc123"
        assert calls[1].kwargs["durable"] == "monitor-service-system-alert-monitor-service-def456"
        # No queue for broadcast
        assert "queue" not in calls[0].kwargs
        assert "queue" not in calls[1].kwargs

    @pytest.mark.asyncio
    async def test_service_name_and_instance_id_required(self):
        """Test that service_name and instance_id are set when needed."""
        adapter = NATSAdapter()
        adapter._js = MagicMock()
        adapter._js.subscribe = AsyncMock()  # Make it async
        adapter._connections = [MagicMock()]

        async def handler(event: Event):
            pass

        # Without service_name and instance_id, compete mode should work but use durable
        await adapter.subscribe_event("order.created", handler, "durable-name", mode="compete")

        call_kwargs = adapter._js.subscribe.call_args.kwargs
        assert "queue" not in call_kwargs  # No queue without service_name
        assert call_kwargs["durable"] == "durable-name"  # Uses durable instead

        # For broadcast mode without instance_id, should use base durable name
        adapter._js.subscribe.reset_mock()
        await adapter.subscribe_event("config.updated", handler, "durable-name", mode="broadcast")

        call_kwargs = adapter._js.subscribe.call_args.kwargs
        assert call_kwargs["durable"] == "durable-name"  # Uses base name without instance_id
