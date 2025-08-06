"""Tests for event subscription load balancing modes."""

import asyncio

import pytest

from aegis_sdk.application.service import Service


class TestEventSubscriptionModes:
    """Test cases for event subscription with compete/broadcast modes."""

    def test_subscribe_decorator_default_mode(self, mock_message_bus):
        """Test event subscription decorator defaults to compete mode."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("order.created")
        async def handle_order_created(event):
            pass

        assert "order.created" in service._handler_registry._event_handlers
        # Check handler is stored as tuple with mode
        handlers = service._handler_registry._event_handlers["order.created"]
        assert len(handlers) == 1
        assert handlers[0][0] == handle_order_created
        assert handlers[0][1] == "compete"  # Default mode

    def test_subscribe_decorator_compete_mode(self, mock_message_bus):
        """Test event subscription decorator with explicit compete mode."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("order.created", mode="compete")
        async def handle_order_created(event):
            pass

        assert "order.created" in service._handler_registry._event_handlers
        handlers = service._handler_registry._event_handlers["order.created"]
        assert len(handlers) == 1
        assert handlers[0][0] == handle_order_created
        assert handlers[0][1] == "compete"

    def test_subscribe_decorator_broadcast_mode(self, mock_message_bus):
        """Test event subscription decorator with broadcast mode."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("user.updated", mode="broadcast")
        async def handle_user_updated(event):
            pass

        assert "user.updated" in service._handler_registry._event_handlers
        handlers = service._handler_registry._event_handlers["user.updated"]
        assert len(handlers) == 1
        assert handlers[0][0] == handle_user_updated
        assert handlers[0][1] == "broadcast"

    def test_subscribe_decorator_invalid_mode(self, mock_message_bus):
        """Test event subscription decorator with invalid mode."""
        service = Service("test-service", mock_message_bus)

        with pytest.raises(ValueError) as exc_info:

            @service.subscribe("order.created", mode="invalid")
            async def handle_order_created(event):
                pass

        assert "not a valid SubscriptionMode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compete_mode_subscription(self, mock_message_bus):
        """Test compete mode creates proper durable name and uses deliver_group."""
        service = Service("test-service", mock_message_bus, instance_id="test-service-abc123")

        @service.subscribe("order.*", mode="compete")
        async def handle_order_event(event):
            pass

        await service.start()

        # Verify subscribe_event was called with proper parameters
        mock_message_bus.subscribe_event.assert_called_once()
        call_args = mock_message_bus.subscribe_event.call_args

        assert call_args[0][0] == "order.*"  # pattern
        assert call_args[0][1] == handle_order_event  # handler
        assert call_args[0][2] == "test-service-order-star"  # durable name
        assert call_args[1]["mode"] == "compete"

        await service.stop()

    @pytest.mark.asyncio
    async def test_broadcast_mode_subscription(self, mock_message_bus):
        """Test broadcast mode creates unique durable name per instance."""
        service = Service("test-service", mock_message_bus, instance_id="test-service-abc123")

        @service.subscribe("config.updated", mode="broadcast")
        async def handle_config_update(event):
            pass

        await service.start()

        # Verify subscribe_event was called with proper parameters
        mock_message_bus.subscribe_event.assert_called_once()
        call_args = mock_message_bus.subscribe_event.call_args

        assert call_args[0][0] == "config.updated"  # pattern
        assert call_args[0][1] == handle_config_update  # handler
        # In broadcast mode, durable name should be unique per instance
        assert call_args[0][2] == "test-service-config-updated"  # base durable name
        assert call_args[1]["mode"] == "broadcast"

        await service.stop()

    @pytest.mark.asyncio
    async def test_multiple_handlers_different_modes(self, mock_message_bus):
        """Test multiple handlers with different modes."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("order.*", mode="compete")
        async def handle_order_compete(event):
            pass

        @service.subscribe("order.*", mode="broadcast")
        async def handle_order_broadcast(event):
            pass

        @service.subscribe("user.*")  # default mode (compete)
        async def handle_user_default(event):
            pass

        await service.start()

        # Should have 3 subscribe calls
        assert mock_message_bus.subscribe_event.call_count == 3

        # Verify each call
        calls = mock_message_bus.subscribe_event.call_args_list

        # First handler - compete mode
        assert calls[0][0][0] == "order.*"
        assert calls[0][1]["mode"] == "compete"

        # Second handler - broadcast mode
        assert calls[1][0][0] == "order.*"
        assert calls[1][1]["mode"] == "broadcast"

        # Third handler - default (compete) mode
        assert calls[2][0][0] == "user.*"
        assert calls[2][1]["mode"] == "compete"

        await service.stop()

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, mock_message_bus):
        """Test that existing code without mode parameter still works."""
        service = Service("test-service", mock_message_bus)

        # Old-style decorator without mode parameter
        @service.subscribe("payment.processed")
        async def handle_payment(event):
            pass

        await service.start()

        # Should default to compete mode
        call_args = mock_message_bus.subscribe_event.call_args
        assert call_args[1]["mode"] == "compete"

        await service.stop()

    def test_subscribe_event_helper_with_mode(self, mock_message_bus):
        """Test subscribe_event helper method with mode parameter."""
        service = Service("test-service", mock_message_bus)

        async def handler(event):
            pass

        # This method needs to be updated to support mode
        asyncio.run(service.subscribe_event("order", "created", handler, mode="broadcast"))

        expected_pattern = "events.order.created"
        assert expected_pattern in service._handler_registry._event_handlers
        handlers = service._handler_registry._event_handlers[expected_pattern]
        assert len(handlers) == 1
        assert handlers[0][0] == handler
        assert handlers[0][1] == "broadcast"

    @pytest.mark.asyncio
    async def test_service_name_in_deliver_group(self, mock_message_bus):
        """Test that compete mode uses service_name for deliver_group."""
        service = Service("pricing-service", mock_message_bus, instance_id="pricing-service-xyz789")

        @service.subscribe("market.data", mode="compete")
        async def handle_market_data(event):
            pass

        await service.start()

        # The service name should be passed to the adapter for use as deliver_group
        call_args = mock_message_bus.subscribe_event.call_args
        assert call_args[0][0] == "market.data"
        assert call_args[0][2] == "pricing-service-market-data"  # durable name
        assert call_args[1]["mode"] == "compete"
        # The adapter will use the service_name for deliver_group

        await service.stop()

    @pytest.mark.asyncio
    async def test_instance_id_in_broadcast_durable(self, mock_message_bus):
        """Test that broadcast mode includes instance_id in durable name."""
        service = Service("monitor-service", mock_message_bus, instance_id="monitor-service-def456")

        @service.subscribe("system.alert", mode="broadcast")
        async def handle_system_alert(event):
            pass

        await service.start()

        # The instance_id should be passed to adapter for unique durable names
        call_args = mock_message_bus.subscribe_event.call_args
        assert call_args[0][0] == "system.alert"
        assert call_args[0][2] == "monitor-service-system-alert"  # base durable name
        assert call_args[1]["mode"] == "broadcast"
        # The adapter will append instance_id for broadcast mode

        await service.stop()

    @pytest.mark.asyncio
    async def test_wildcard_pattern_with_modes(self, mock_message_bus):
        """Test wildcard patterns work with both modes."""
        service = Service("analytics-service", mock_message_bus)

        @service.subscribe("trade.*", mode="compete")
        async def handle_trade_compete(event):
            pass

        @service.subscribe("log.*", mode="broadcast")
        async def handle_log_broadcast(event):
            pass

        await service.start()

        calls = mock_message_bus.subscribe_event.call_args_list

        # Trade events - compete mode
        assert calls[0][0][0] == "trade.*"
        assert calls[0][0][2] == "analytics-service-trade-star"
        assert calls[0][1]["mode"] == "compete"

        # Log events - broadcast mode
        assert calls[1][0][0] == "log.*"
        assert calls[1][0][2] == "analytics-service-log-star"
        assert calls[1][1]["mode"] == "broadcast"

        await service.stop()
