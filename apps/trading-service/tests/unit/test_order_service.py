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
        assert service._order_repository is not None
        assert hasattr(service, "_pricing_service")

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
            "order_type": "MARKET",  # Changed to MARKET since we're not providing a price
        }

        result = await create_order_handler(params)

        assert "order" in result
        order = result["order"]
        assert order["order_id"] == "ORD-000001"
        assert order["symbol"] == "AAPL"
        assert order["quantity"] == 100
        assert order["side"] == "BUY"
        assert order["order_type"] == "MARKET"
        assert order["status"] == "PENDING"
        assert order["price"] == 150.0
        assert "created_at" in order

        # Verify order is stored in repository
        saved_order = await service._order_repository.get("ORD-000001")
        assert saved_order is not None
        assert saved_order.order_id == "ORD-000001"

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

        # Add test order to repository
        from datetime import UTC, datetime

        from order_service.domain_models import Order, OrderSide, OrderStatus, OrderType

        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            instance_id=service.instance_id,
        )
        await service._order_repository.save(order)

        await service.on_start()

        # Get the get_order handler
        get_order_handler = service._rpc_handlers["get_order"]

        # Test get existing order
        result = await get_order_handler({"order_id": "ORD-000001"})

        assert "order" in result
        assert result["order"]["order_id"] == "ORD-000001"
        assert result["order"]["symbol"] == "AAPL"

        # Test missing order_id
        result = await get_order_handler({})
        assert "error" in result
        assert result["error"] == "order_id is required"

        # Test non-existent order
        result = await get_order_handler({"order_id": "ORD-999999"})
        assert "error" in result
        assert "Order not found" in result["error"]

    async def test_list_orders_rpc(self, mock_message_bus, mock_metrics):
        """Test list_orders RPC method."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-123",
            metrics=mock_metrics,
        )

        # Add test orders to repository
        from datetime import UTC, datetime

        from order_service.domain_models import Order, OrderSide, OrderStatus, OrderType

        for i in range(5):
            order = Order(
                order_id=f"ORD-{i:06d}",
                symbol="AAPL",
                quantity=100,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                status=OrderStatus.PENDING,
                created_at=datetime.now(UTC),
                instance_id=service.instance_id,
            )
            await service._order_repository.save(order)

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

        # Add test order to repository
        from datetime import UTC, datetime

        from order_service.domain_models import Order, OrderSide, OrderStatus, OrderType

        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            instance_id=service.instance_id,
        )
        await service._order_repository.save(order)

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

        # Verify order updated in repository
        updated_order = await service._order_repository.get("ORD-000001")
        assert updated_order.risk_level.value == "LOW"
        assert updated_order.status == OrderStatus.APPROVED
        assert updated_order.risk_assessed_at is not None

        # Verify metrics
        mock_metrics.increment.assert_any_call("events.order_updated.published")
        mock_metrics.increment.assert_any_call("orders.risk_assessment.low")

        # Test high risk rejection
        order2 = Order(
            order_id="ORD-000002",
            symbol="TSLA",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            instance_id=service.instance_id,
        )
        await service._order_repository.save(order2)

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

        # Verify order rejected in repository
        rejected_order = await service._order_repository.get("ORD-000002")
        assert rejected_order.risk_level.value == "HIGH"
        assert rejected_order.status == OrderStatus.REJECTED

    async def test_simulate_work_rpc(self, mock_message_bus, mock_metrics):
        """Test simulate_work RPC handler."""
        service = OrderService(
            message_bus=mock_message_bus,
            instance_id="order-test-01",
            metrics=mock_metrics,
        )

        await service.on_start()

        # Get the handler
        simulate_work_handler = service._rpc_handlers["simulate_work"]

        # Test with default duration
        result = await simulate_work_handler({})
        assert result["work_completed"] is True
        assert result["duration"] == 1.0
        assert result["service"] == "order-service"
        assert result["instance"] == "order-test-01"

        # Test with custom duration
        result = await simulate_work_handler({"duration": 0.01})
        assert result["work_completed"] is True
        assert result["duration"] == 0.01

    async def test_create_order_validation_error(self, mock_message_bus, mock_metrics):
        """Test create order with validation error."""
        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        create_order_handler = service._rpc_handlers["create_order"]

        # Test with invalid quantity
        result = await create_order_handler(
            {
                "symbol": "AAPL",
                "quantity": -10,  # Invalid negative quantity
                "side": "BUY",
                "order_type": "MARKET",
            }
        )

        assert "error" in result
        assert result["error"] == "Invalid order parameters"
        assert "details" in result

    async def test_create_order_pricing_service_error(
        self, mock_message_bus, mock_metrics, mock_logger
    ):
        """Test create order when pricing service fails."""
        # Import AsyncMock
        from unittest.mock import AsyncMock, MagicMock

        # Create a mock pricing service that raises an error
        mock_pricing_service = MagicMock()
        mock_pricing_service.get_price = AsyncMock(side_effect=Exception("Pricing service error"))

        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            logger=mock_logger,
            pricing_service=mock_pricing_service,
        )

        await service.on_start()

        create_order_handler = service._rpc_handlers["create_order"]

        # Create order - should fallback to default price
        result = await create_order_handler(
            {"symbol": "AAPL", "quantity": 100, "side": "BUY", "order_type": "MARKET"}
        )

        # Order should be created with default price
        assert "order" in result
        assert result["order"]["price"] == 100.0

        # Verify metrics and logging
        mock_metrics.increment.assert_any_call("rpc.pricing_service.failures")
        mock_logger.warning.assert_called_with("Failed to get price", error="Pricing service error")

    async def test_handle_risk_event_invalid_risk_level(
        self, mock_message_bus, mock_metrics, mock_logger
    ):
        """Test handling risk event with invalid risk level."""
        service = OrderService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            logger=mock_logger,
        )

        # Create order in repository
        from order_service.domain_models import Order, OrderSide, OrderType

        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            created_at=datetime.now(UTC),
            instance_id="order-test-01",
        )
        await service._order_repository.save(order)

        await service.on_start()

        # Get the risk assessment handler
        risk_handler = service._event_handlers["events.risk.*"][0]

        # Create risk event with invalid risk level
        from aegis_sdk.domain.models import Event

        invalid_risk_event = Event(
            domain="risk",
            event_type="assessed",
            payload={
                "order_id": "ORD-000001",
                "risk_level": "INVALID_LEVEL",  # Invalid risk level
            },
            source="risk-service-123",
        )

        await risk_handler(invalid_risk_event)

        # Verify error was logged
        mock_logger.error.assert_called()
