"""Unit tests for OrderService."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from order_service import OrderService


@pytest.mark.asyncio
class TestOrderService:
    """Test OrderService functionality."""

    async def test_initialization(self, mock_message_bus, mock_metrics):
        """Test service initialization."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-123",
            version="1.0.0",
            metrics=mock_metrics,
        )

        assert service.service_name == "order-service"
        assert service.instance_id == "order-test-123"
        assert service.version == "1.0.0"
        assert service._orders == {}
        assert service._order_counter == 0

    async def test_on_start_registers_handlers(self, mock_message_bus, mock_metrics):
        """Test that on_start registers all RPC handlers."""
        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        # Check that RPC handlers are registered
        assert "echo" in service._rpc_handlers
        assert "health" in service._rpc_handlers
        assert "simulate_work" in service._rpc_handlers
        assert "create_order" in service._rpc_handlers
        assert "get_order" in service._rpc_handlers
        assert "list_orders" in service._rpc_handlers

        # Check that event subscriptions are registered
        assert "events.risk.*" in service._event_handlers

    async def test_echo_rpc(self, mock_message_bus, mock_metrics):
        """Test echo RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-123",
            metrics=mock_metrics,
        )
        await service.on_start()

        # Get the echo handler
        echo_handler = service._rpc_handlers["echo"]

        # Test echo
        params = {"test": "data", "number": 42}
        result = await echo_handler(params)

        assert result["echo"] == params
        assert result["service"] == "order-service"
        assert result["instance"] == "order-test-123"
        assert "timestamp" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.echo.calls")

    async def test_health_rpc(self, mock_message_bus, mock_metrics):
        """Test health RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-123",
            metrics=mock_metrics,
        )

        # Mock start time
        service._start_time = datetime.now(UTC)

        await service.on_start()

        # Get the health handler
        health_handler = service._rpc_handlers["health"]

        # Test health
        result = await health_handler({})

        assert result["status"] == "healthy"
        assert result["service"] == "order-service"
        assert result["instance"] == "order-test-123"
        assert result["order_count"] == 0
        assert "uptime" in result
        assert "metrics" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.health.calls")
        mock_metrics.gauge.assert_called_with("orders.active", 0)

    async def test_create_order_rpc(self, mock_message_bus, mock_service_discovery, mock_metrics):
        """Test create_order RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            service_discovery=mock_service_discovery,
            metrics=mock_metrics,
        )

        # Mock service discovery to return a pricing instance
        from aegis_sdk.domain.models import ServiceInstance

        mock_instance = ServiceInstance(
            service_name="pricing-service",
            instance_id="pricing-service-01",
            version="1.0.0",
            status="ACTIVE",
        )
        mock_service_discovery.select_instance.return_value = mock_instance

        # Mock RPC response for pricing
        from aegis_sdk.domain.models import RPCResponse

        mock_rpc_response = RPCResponse(
            success=True,
            result={"price": 150.0},
            error=None,
        )
        mock_message_bus.call_rpc.return_value = mock_rpc_response

        await service.on_start()

        # Get the create_order handler
        create_order_handler = service._rpc_handlers["create_order"]

        # Test create order
        params = {
            "symbol": "AAPL",
            "quantity": 100,
            "side": "BUY",
            "order_type": "LIMIT",
        }

        result = await create_order_handler(params)

        assert "order" in result
        order = result["order"]
        assert order["order_id"] == "ORD-000001"
        assert order["symbol"] == "AAPL"
        assert order["quantity"] == 100
        assert order["side"] == "BUY"
        assert order["order_type"] == "LIMIT"
        assert order["status"] == "PENDING"
        assert order["price"] == 150.0
        assert "created_at" in order

        # Verify order is stored
        assert len(service._orders) == 1
        assert "ORD-000001" in service._orders

        # Verify metrics
        mock_metrics.increment.assert_any_call("orders.created")
        mock_metrics.increment.assert_any_call("events.order_created.published")
        mock_metrics.timer.assert_called_with("rpc.create_order.duration_ms")

        # Verify event published
        mock_message_bus.publish_event.assert_called_once()

    async def test_create_order_pricing_failure(
        self, mock_message_bus, mock_service_discovery, mock_metrics, mock_logger
    ):
        """Test create_order with pricing service failure."""
        service = OrderService(
            message_bus=mock_message_bus,
            service_discovery=mock_service_discovery,
            logger=mock_logger,
            metrics=mock_metrics,
        )

        # Mock RPC failure
        mock_message_bus.call_rpc.side_effect = Exception("Pricing service unavailable")

        await service.on_start()

        # Get the create_order handler
        create_order_handler = service._rpc_handlers["create_order"]

        # Test create order
        params = {"symbol": "AAPL", "quantity": 100}

        result = await create_order_handler(params)

        # Should still create order with default price
        assert "order" in result
        order = result["order"]
        assert order["price"] == 100.0  # Default price

        # Verify metrics
        mock_metrics.increment.assert_any_call("rpc.pricing_service.failures")

    async def test_get_order_rpc(self, mock_message_bus, mock_metrics):
        """Test get_order RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Add test order
        service._orders["ORD-000001"] = {
            "order_id": "ORD-000001",
            "symbol": "AAPL",
            "quantity": 100,
        }

        await service.on_start()

        # Get the get_order handler
        get_order_handler = service._rpc_handlers["get_order"]

        # Test get existing order
        result = await get_order_handler({"order_id": "ORD-000001"})

        assert "order" in result
        assert result["order"]["order_id"] == "ORD-000001"
        assert result["order"]["symbol"] == "AAPL"

        # Test missing order_id
        with pytest.raises(ValueError, match="order_id is required"):
            await get_order_handler({})

        # Test non-existent order
        with pytest.raises(ValueError, match="Order not found"):
            await get_order_handler({"order_id": "ORD-999999"})

    async def test_list_orders_rpc(self, mock_message_bus, mock_metrics):
        """Test list_orders RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-123",
            metrics=mock_metrics,
        )

        # Add test orders
        for i in range(5):
            service._orders[f"ORD-{i:06d}"] = {
                "order_id": f"ORD-{i:06d}",
                "symbol": "AAPL",
            }

        await service.on_start()

        # Get the list_orders handler
        list_orders_handler = service._rpc_handlers["list_orders"]

        # Test list all orders
        result = await list_orders_handler({})

        assert "orders" in result
        assert len(result["orders"]) == 5
        assert result["total"] == 5
        assert result["instance"] == "order-test-123"

        # Test with limit
        result = await list_orders_handler({"limit": 3})
        assert len(result["orders"]) == 3
        assert result["total"] == 5

    async def test_handle_risk_event(self, mock_message_bus, mock_metrics):
        """Test risk event handler."""
        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Add test order
        service._orders["ORD-000001"] = {
            "order_id": "ORD-000001",
            "symbol": "AAPL",
            "status": "PENDING",
        }

        await service.on_start()

        # Get the risk event handler
        risk_handler = service._event_handlers["events.risk.*"][0]

        # Create risk assessment event
        from aegis_sdk.domain.models import Event

        risk_event = Event(
            domain="risk",
            event_type="assessed",
            payload={
                "order_id": "ORD-000001",
                "risk_level": "LOW",
            },
            source="risk-service-123",
        )

        # Handle event
        await risk_handler(risk_event)

        # Verify order updated
        order = service._orders["ORD-000001"]
        assert order["risk_level"] == "LOW"
        assert order["status"] == "APPROVED"
        assert "risk_assessed_at" in order

        # Verify metrics
        mock_metrics.increment.assert_any_call("events.order_updated.published")
        mock_metrics.increment.assert_any_call("orders.risk_assessment.low")

        # Test high risk rejection
        service._orders["ORD-000002"] = {
            "order_id": "ORD-000002",
            "symbol": "TSLA",
            "status": "PENDING",
        }

        high_risk_event = Event(
            domain="risk",
            event_type="assessed",
            payload={
                "order_id": "ORD-000002",
                "risk_level": "HIGH",
            },
            source="risk-service-123",
        )

        await risk_handler(high_risk_event)

        # Verify order rejected
        order = service._orders["ORD-000002"]
        assert order["risk_level"] == "HIGH"
        assert order["status"] == "REJECTED"
