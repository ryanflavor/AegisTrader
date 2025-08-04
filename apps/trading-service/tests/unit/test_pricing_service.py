"""Unit tests for PricingService."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pricing_service import PricingService


@pytest.mark.asyncio
class TestPricingService:
    """Test PricingService functionality."""

    async def test_initialization(self, mock_message_bus, mock_metrics):
        """Test service initialization."""
        service = PricingService(
            message_bus=mock_message_bus,
            instance_id="pricing-test-123",
            version="1.0.0",
            metrics=mock_metrics,
        )

        assert service.service_name == "pricing-service"
        assert service.instance_id == "pricing-test-123"
        assert service.version == "1.0.0"
        assert len(service._base_prices) == 7  # AAPL, GOOGL, MSFT, AMZN, TSLA, BTC, ETH
        assert service._price_update_task is None

    async def test_on_start_registers_handlers(self, mock_message_bus, mock_metrics):
        """Test that on_start registers all RPC handlers."""
        service = PricingService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        # Check that RPC handlers are registered
        assert "echo" in service._rpc_handlers
        assert "health" in service._rpc_handlers
        assert "simulate_work" in service._rpc_handlers
        assert "get_price" in service._rpc_handlers
        assert "get_prices" in service._rpc_handlers
        assert "subscribe_price_updates" in service._rpc_handlers

        # Check that event subscriptions are registered
        assert "events.order.created" in service._event_handlers

        # Check that price update task is started
        assert service._price_update_task is not None
        assert not service._price_update_task.done()

        # Clean up
        service._shutdown_event.set()
        service._price_update_task.cancel()
        try:
            await service._price_update_task
        except asyncio.CancelledError:
            pass

    async def test_echo_rpc(self, mock_message_bus, mock_metrics):
        """Test echo RPC method."""
        service = PricingService(
            message_bus=mock_message_bus,
            instance_id="pricing-test-123",
            metrics=mock_metrics,
        )

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the echo handler
        echo_handler = service._rpc_handlers["echo"]

        # Test echo
        params = {"test": "data", "number": 42}
        result = await echo_handler(params)

        assert result["echo"] == params
        assert result["service"] == "pricing-service"
        assert result["instance"] == "pricing-test-123"
        assert "timestamp" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.echo.calls")

    async def test_health_rpc(self, mock_message_bus, mock_metrics):
        """Test health RPC method."""
        service = PricingService(
            message_bus=mock_message_bus,
            instance_id="pricing-test-123",
            metrics=mock_metrics,
        )

        # Mock start time
        service._start_time = datetime.now(UTC)

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the health handler
        health_handler = service._rpc_handlers["health"]

        # Test health
        result = await health_handler({})

        assert result["status"] == "healthy"
        assert result["service"] == "pricing-service"
        assert result["instance"] == "pricing-test-123"
        assert result["price_symbols"] == 7
        assert "uptime" in result
        assert "metrics" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.health.calls")
        mock_metrics.gauge.assert_called_with("prices.symbols_tracked", 7)

    @patch("random.uniform")
    async def test_get_price_rpc(self, mock_uniform, mock_message_bus, mock_metrics):
        """Test get_price RPC method."""
        # Mock random variation
        mock_uniform.return_value = 1.01  # 1% increase

        service = PricingService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the get_price handler
        get_price_handler = service._rpc_handlers["get_price"]

        # Test get price for known symbol
        result = await get_price_handler({"symbol": "AAPL"})

        assert result["symbol"] == "AAPL"
        assert result["price"] == 176.75  # 175 * 1.01
        assert result["bid"] == 176.57  # price * 0.999
        assert result["ask"] == 176.93  # price * 1.001
        assert "timestamp" in result
        assert result["instance"] == service.instance_id

        # Test unknown symbol (should use default price)
        result = await get_price_handler({"symbol": "UNKNOWN"})
        assert result["price"] == 101.0  # 100 * 1.01

        # Test missing symbol
        with pytest.raises(ValueError, match="symbol is required"):
            await get_price_handler({})

        # Verify metrics
        mock_metrics.increment.assert_any_call("prices.requests")
        mock_metrics.timer.assert_called_with("rpc.get_price.duration_ms")

    async def test_get_prices_rpc(self, mock_message_bus, mock_metrics):
        """Test get_prices RPC method."""
        service = PricingService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the get_prices handler
        get_prices_handler = service._rpc_handlers["get_prices"]

        # Test get prices for specific symbols
        result = await get_prices_handler({"symbols": ["AAPL", "GOOGL"]})

        assert "prices" in result
        assert len(result["prices"]) == 2
        assert "AAPL" in result["prices"]
        assert "GOOGL" in result["prices"]
        assert "price" in result["prices"]["AAPL"]
        assert "bid" in result["prices"]["AAPL"]
        assert "ask" in result["prices"]["AAPL"]
        assert "timestamp" in result
        assert result["instance"] == service.instance_id

        # Test get all prices (no symbols specified)
        result = await get_prices_handler({})
        assert len(result["prices"]) == 7  # All base prices

    async def test_subscribe_price_updates_rpc(self, mock_message_bus, mock_metrics):
        """Test subscribe_price_updates RPC method."""
        service = PricingService(
            message_bus=mock_message_bus,
            instance_id="pricing-test-123",
            metrics=mock_metrics,
        )

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the subscribe handler
        subscribe_handler = service._rpc_handlers["subscribe_price_updates"]

        # Test subscribe
        result = await subscribe_handler({"symbols": ["AAPL", "GOOGL"]})

        assert result["subscribed"] is True
        assert result["symbols"] == ["AAPL", "GOOGL"]
        assert "message" in result
        assert result["instance"] == "pricing-test-123"

        # Test missing symbols
        with pytest.raises(ValueError, match="symbols are required"):
            await subscribe_handler({})

    async def test_handle_order_created_event(self, mock_message_bus, mock_metrics):
        """Test order created event handler."""
        service = PricingService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Set shutdown event to prevent price update task from running
        service._shutdown_event.set()

        await service.on_start()

        # Get the order created handler
        order_handler = service._event_handlers["events.order.created"][0]

        # Create order created event
        from aegis_sdk.domain.models import Event

        order_event = Event(
            domain="order",
            event_type="created",
            payload={
                "order": {
                    "order_id": "ORD-000001",
                    "symbol": "AAPL",
                }
            },
            source="order-service-123",
        )

        # Handle event
        await order_handler(order_event)

        # Verify price quote event published
        mock_message_bus.publish_event.assert_called_once()
        published_event = mock_message_bus.publish_event.call_args[0][0]
        assert published_event.domain == "price"
        assert published_event.event_type == "quoted"
        assert published_event.payload["order_id"] == "ORD-000001"
        assert published_event.payload["symbol"] == "AAPL"
        assert "price" in published_event.payload
        assert "bid" in published_event.payload
        assert "ask" in published_event.payload

        # Verify metrics
        mock_metrics.increment.assert_any_call("events.price_quoted.published")

    async def test_stop_cancels_price_update_task(self, mock_message_bus, mock_metrics):
        """Test that stop properly cancels the price update task."""
        service = PricingService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        # Verify task is running
        assert service._price_update_task is not None
        assert not service._price_update_task.done()

        # Stop service
        await service.stop()

        # Verify task is cancelled
        assert service._price_update_task.cancelled()

        # Verify parent stop was called
        mock_message_bus.unregister_service.assert_called_once_with(
            service.service_name, service.instance_id
        )
