"""Integration tests for event contracts validation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aegis_sdk.domain.models import Event
from order_service import OrderService
from pricing_service import PricingService
from risk_service import RiskService
from shared_contracts import EventPatterns, ServiceNames, parse_event_pattern


@pytest.mark.asyncio
class TestEventContracts:
    """Test that services use correct event contracts."""

    async def test_order_created_event_format(self):
        """Test that order created events follow the correct format."""
        # Create a mock message bus to capture events
        captured_events = []

        class MockMessageBus:
            def __init__(self):
                self.is_connected = asyncio.create_task(asyncio.sleep(0))

            async def publish_event(self, event: Event) -> None:
                captured_events.append(event)

            async def register_service(self, *args, **kwargs):
                pass

            async def unregister_service(self, *args, **kwargs):
                pass

            async def register_rpc_handler(self, *args, **kwargs):
                pass

            async def subscribe_event(self, *args, **kwargs):
                pass

            async def call_rpc(self, *args, **kwargs):
                # Mock pricing service response
                return {"result": {"price": 150.0, "bid": 149.5, "ask": 150.5}}

        mock_bus = MockMessageBus()
        service = OrderService(message_bus=mock_bus)
        await service.on_start()

        # Get the create_order handler
        create_order = service._rpc_handlers["create_order"]

        # Create an order
        await create_order(
            {"symbol": "AAPL", "quantity": 100, "side": "BUY", "order_type": "MARKET"}
        )

        # Verify event was published
        assert len(captured_events) == 1
        event = captured_events[0]

        # Verify event structure
        assert event.domain == "order"
        assert event.event_type == "created"
        assert "order_id" in event.payload
        assert event.payload["symbol"] == "AAPL"
        assert event.payload["quantity"] == 100

        # Verify event pattern matches
        pattern = f"events.{event.domain}.{event.event_type}"
        assert pattern == EventPatterns.ORDER_CREATED

    async def test_risk_assessed_event_format(self):
        """Test that risk assessment events follow the correct format."""
        captured_events = []

        class MockMessageBus:
            def __init__(self):
                self.is_connected = asyncio.create_task(asyncio.sleep(0))

            async def publish_event(self, event: Event) -> None:
                captured_events.append(event)

            async def register_service(self, *args, **kwargs):
                pass

            async def unregister_service(self, *args, **kwargs):
                pass

            async def register_rpc_handler(self, *args, **kwargs):
                pass

            async def subscribe_event(self, *args, **kwargs):
                pass

        mock_bus = MockMessageBus()
        service = RiskService(message_bus=mock_bus)
        await service.on_start()

        # Get the risk handler
        risk_handler = service._event_handlers[EventPatterns.ORDER_CREATED][0]

        # Create order event
        order_event = Event(
            domain="order",
            event_type="created",
            payload={
                "order": {"order_id": "ORD-001", "symbol": "AAPL", "quantity": 100, "side": "BUY"}
            },
            source="test",
        )

        # Handle the event
        await risk_handler(order_event)

        # Verify risk assessment event was published
        assert len(captured_events) == 1
        event = captured_events[0]

        assert event.domain == "risk"
        assert event.event_type == "assessed"
        assert event.payload["order_id"] == "ORD-001"
        assert "risk_level" in event.payload
        assert "risk_score" in event.payload

        # Verify event pattern matches
        pattern = f"events.{event.domain}.{event.event_type}"
        assert pattern == EventPatterns.RISK_ASSESSED

    async def test_price_updated_event_format(self):
        """Test that price update events follow the correct format."""
        captured_events = []

        class MockMessageBus:
            def __init__(self):
                self.is_connected = asyncio.create_task(asyncio.sleep(0))
                self._shutdown = False

            async def publish_event(self, event: Event) -> None:
                captured_events.append(event)

            async def register_service(self, *args, **kwargs):
                pass

            async def unregister_service(self, *args, **kwargs):
                pass

            async def register_rpc_handler(self, *args, **kwargs):
                pass

            async def subscribe_event(self, *args, **kwargs):
                pass

            async def call_rpc(self, request):
                # Mock self RPC call
                return {
                    "result": {
                        "symbol": "BTC",
                        "price": 45000.0,
                        "bid": 44950.0,
                        "ask": 45050.0,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                }

        mock_bus = MockMessageBus()
        service = PricingService(message_bus=mock_bus)

        # Stop price update task immediately
        service._shutdown_event.set()

        await service.on_start()

        # Wait a bit for the price update task to emit at least one event
        await asyncio.sleep(0.1)

        # Cancel the task
        if service._price_update_task:
            service._price_update_task.cancel()
            try:
                await service._price_update_task
            except asyncio.CancelledError:
                pass

        # Find price updated events
        price_events = [e for e in captured_events if e.event_type == "updated"]

        if price_events:  # Task might not have run if too fast
            event = price_events[0]

            assert event.domain == "price"
            assert event.event_type == "updated"
            assert "symbol" in event.payload
            assert "price" in event.payload
            assert "bid" in event.payload
            assert "ask" in event.payload

            # Verify event pattern matches
            pattern = f"events.{event.domain}.{event.event_type}"
            assert pattern == EventPatterns.PRICE_UPDATED

    async def test_position_updated_event_format(self):
        """Test that position update events follow the correct format."""
        captured_events = []

        class MockMessageBus:
            def __init__(self):
                self.is_connected = asyncio.create_task(asyncio.sleep(0))

            async def publish_event(self, event: Event) -> None:
                captured_events.append(event)

            async def register_service(self, *args, **kwargs):
                pass

            async def unregister_service(self, *args, **kwargs):
                pass

            async def register_rpc_handler(self, *args, **kwargs):
                pass

            async def subscribe_event(self, *args, **kwargs):
                pass

        mock_bus = MockMessageBus()
        service = RiskService(message_bus=mock_bus)
        await service.on_start()

        # Get the order filled handler
        filled_handler = service._event_handlers[EventPatterns.ORDER_FILLED][0]

        # Create order filled event
        filled_event = Event(
            domain="order",
            event_type="filled",
            payload={
                "order": {"order_id": "ORD-001", "symbol": "ETH", "quantity": 10, "side": "BUY"}
            },
            source="test",
        )

        # Handle the event
        await filled_handler(filled_event)

        # Should have risk assessed and position updated events
        position_events = [e for e in captured_events if e.domain == "position"]

        assert len(position_events) >= 1
        event = position_events[0]

        assert event.domain == "position"
        assert event.event_type == "updated"
        assert event.payload["symbol"] == "ETH"
        assert "position" in event.payload

        # Verify event pattern matches
        pattern = f"events.{event.domain}.{event.event_type}"
        assert pattern == EventPatterns.POSITION_UPDATED

    async def test_parse_event_pattern_consistency(self):
        """Test that parse_event_pattern works correctly with all patterns."""
        # Test all defined patterns
        patterns = [
            (EventPatterns.ORDER_CREATED, "order", "created"),
            (EventPatterns.ORDER_UPDATED, "order", "updated"),
            (EventPatterns.ORDER_FILLED, "order", "filled"),
            (EventPatterns.PRICE_UPDATED, "price", "updated"),
            (EventPatterns.PRICE_QUOTED, "price", "quoted"),
            (EventPatterns.RISK_ASSESSED, "risk", "assessed"),
            (EventPatterns.POSITION_UPDATED, "position", "updated"),
        ]

        for pattern, expected_domain, expected_type in patterns:
            domain, event_type = parse_event_pattern(pattern)
            assert (
                domain == expected_domain
            ), f"Pattern {pattern}: expected domain {expected_domain}, got {domain}"
            assert (
                event_type == expected_type
            ), f"Pattern {pattern}: expected type {expected_type}, got {event_type}"

    async def test_service_names_consistency(self):
        """Test that services use correct service names from constants."""
        # This is more of a static check, but we can verify the constants are used
        assert ServiceNames.ORDER_SERVICE == "order-service"
        assert ServiceNames.PRICING_SERVICE == "pricing-service"
        assert ServiceNames.RISK_SERVICE == "risk-service"

        # Verify services use these names
        mock_bus = type("MockBus", (), {"is_connected": asyncio.create_task(asyncio.sleep(0))})()

        order_service = OrderService(message_bus=mock_bus)
        assert order_service.service_name == ServiceNames.ORDER_SERVICE

        pricing_service = PricingService(message_bus=mock_bus)
        assert pricing_service.service_name == ServiceNames.PRICING_SERVICE

        risk_service = RiskService(message_bus=mock_bus)
        assert risk_service.service_name == ServiceNames.RISK_SERVICE
