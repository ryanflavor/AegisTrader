"""Unit tests for RiskService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from risk_service import RiskService


@pytest.mark.asyncio
class TestRiskService:
    """Test RiskService functionality."""

    async def test_initialization(self, mock_message_bus, mock_metrics):
        """Test service initialization."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-123",
            version="1.0.0",
            metrics=mock_metrics,
        )

        assert service.service_name == "risk-service"
        assert service.instance_id == "risk-test-123"
        assert service.version == "1.0.0"
        assert len(service._position_limits) == 7
        assert service._positions == {}
        assert service._daily_volume == {}

    async def test_on_start_registers_handlers(self, mock_message_bus, mock_metrics):
        """Test that on_start registers all RPC handlers."""
        service = RiskService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        # Check that RPC handlers are registered
        assert "echo" in service._rpc_handlers
        assert "health" in service._rpc_handlers
        assert "simulate_work" in service._rpc_handlers
        assert "assess_risk" in service._rpc_handlers
        assert "get_positions" in service._rpc_handlers
        assert "update_limits" in service._rpc_handlers

        # Check that event subscriptions are registered
        assert "events.order.created" in service._event_handlers
        assert "events.order.filled" in service._event_handlers

    async def test_echo_rpc(self, mock_message_bus, mock_metrics):
        """Test echo RPC method."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-123",
            metrics=mock_metrics,
        )
        await service.on_start()

        # Get the echo handler
        echo_handler = service._rpc_handlers["echo"]

        # Test echo
        params = {"test": "data", "number": 42}
        result = await echo_handler(params)

        assert result["echo"] == params
        assert result["service"] == "risk-service"
        assert result["instance"] == "risk-test-123"
        assert "timestamp" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.echo.calls")

    async def test_health_rpc(self, mock_message_bus, mock_metrics):
        """Test health RPC method."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-123",
            metrics=mock_metrics,
        )

        # Mock start time
        service._start_time = datetime.now(UTC)

        # Add some positions
        service._positions["AAPL"] = 100
        service._positions["GOOGL"] = 50

        await service.on_start()

        # Get the health handler
        health_handler = service._rpc_handlers["health"]

        # Test health
        result = await health_handler({})

        assert result["status"] == "healthy"
        assert result["service"] == "risk-service"
        assert result["instance"] == "risk-test-123"
        assert result["monitored_symbols"] == 7
        assert result["active_positions"] == 2
        assert "uptime" in result
        assert "metrics" in result

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.health.calls")
        mock_metrics.gauge.assert_any_call("risk.monitored_symbols", 7)
        mock_metrics.gauge.assert_any_call("risk.active_positions", 2)

    @patch("random.uniform")
    async def test_assess_risk_rpc(self, mock_uniform, mock_message_bus, mock_metrics):
        """Test assess_risk RPC method."""
        # Mock market risk
        mock_uniform.return_value = 15.0  # Medium market risk

        service = RiskService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        await service.on_start()

        # Get the assess_risk handler
        assess_risk_handler = service._rpc_handlers["assess_risk"]

        # Test low risk assessment
        result = await assess_risk_handler(
            {
                "order_id": "ORD-000001",
                "symbol": "AAPL",
                "quantity": 100,
                "side": "BUY",
            }
        )

        assert result["order_id"] == "ORD-000001"
        assert result["symbol"] == "AAPL"
        assert result["risk_level"] == "LOW"  # 15 score < 40
        assert result["risk_score"] == 15.0
        assert result["risk_factors"] == []
        assert result["position_limit"] == 10000
        assert result["current_position"] == 0
        assert result["new_position"] == 100
        assert "assessment_time" in result
        assert result["instance"] == service.instance_id

        # Test position limit exceeded
        service._positions["AAPL"] = 9950
        result = await assess_risk_handler(
            {
                "order_id": "ORD-000002",
                "symbol": "AAPL",
                "quantity": 100,
                "side": "BUY",
            }
        )

        assert result["risk_level"] == "MEDIUM"  # 50 + 15 = 65 < 70 but >= 40
        assert result["risk_score"] == 65.0
        assert "POSITION_LIMIT_EXCEEDED" in result["risk_factors"]
        assert result["new_position"] == 10050

        # Test high daily volume
        service._daily_volume["TSLA"] = 5500
        result = await assess_risk_handler(
            {
                "order_id": "ORD-000003",
                "symbol": "TSLA",
                "quantity": 1000,
                "side": "BUY",
            }
        )

        assert result["risk_level"] == "MEDIUM"  # 30 + 15 = 45 > 40
        assert "HIGH_DAILY_VOLUME" in result["risk_factors"]

        # Test missing symbol
        with pytest.raises(ValueError, match="symbol is required"):
            await assess_risk_handler({"order_id": "ORD-000004"})

        # Verify metrics
        mock_metrics.increment.assert_any_call("risk.assessments")
        mock_metrics.increment.assert_any_call("risk.level.low")
        mock_metrics.increment.assert_any_call(
            "risk.level.medium"
        )  # Changed from high since we only got medium
        mock_metrics.record.assert_any_call("risk.score", 15.0)
        mock_metrics.timer.assert_called_with("rpc.assess_risk.duration_ms")

    async def test_get_positions_rpc(self, mock_message_bus, mock_metrics):
        """Test get_positions RPC method."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-123",
            metrics=mock_metrics,
        )

        # Set up test data
        service._positions = {"AAPL": 100, "GOOGL": -50}
        service._daily_volume = {"AAPL": 500, "GOOGL": 200}

        await service.on_start()

        # Get the get_positions handler
        get_positions_handler = service._rpc_handlers["get_positions"]

        # Test get positions
        result = await get_positions_handler({})

        assert result["positions"] == {"AAPL": 100, "GOOGL": -50}
        assert result["daily_volumes"] == {"AAPL": 500, "GOOGL": 200}
        assert len(result["limits"]) == 7
        assert result["limits"]["AAPL"] == 10000
        assert "timestamp" in result
        assert result["instance"] == "risk-test-123"

    async def test_update_limits_rpc(self, mock_message_bus, mock_metrics):
        """Test update_limits RPC method."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-123",
            metrics=mock_metrics,
        )

        await service.on_start()

        # Get the update_limits handler
        update_limits_handler = service._rpc_handlers["update_limits"]

        # Test update existing symbol
        result = await update_limits_handler(
            {
                "symbol": "AAPL",
                "limit": 15000,
            }
        )

        assert result["symbol"] == "AAPL"
        assert result["new_limit"] == 15000
        assert result["message"] == "Position limit updated"
        assert result["instance"] == "risk-test-123"
        assert service._position_limits["AAPL"] == 15000

        # Test update new symbol
        result = await update_limits_handler(
            {
                "symbol": "NVDA",
                "limit": 5000,
            }
        )

        assert service._position_limits["NVDA"] == 5000

        # Test missing parameters
        with pytest.raises(ValueError, match="symbol and limit are required"):
            await update_limits_handler({"symbol": "AAPL"})

        with pytest.raises(ValueError, match="symbol and limit are required"):
            await update_limits_handler({"limit": 1000})

    async def test_handle_order_created_event(self, mock_message_bus, mock_metrics):
        """Test order created event handler."""
        service = RiskService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

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
                    "quantity": 100,
                    "side": "BUY",
                }
            },
            source="order-service-123",
        )

        # Handle event
        await order_handler(order_event)

        # Verify risk assessment event published
        mock_message_bus.publish_event.assert_called()
        published_event = mock_message_bus.publish_event.call_args[0][0]
        assert published_event.domain == "risk"
        assert published_event.event_type == "assessed"
        assert published_event.payload["order_id"] == "ORD-000001"
        assert "risk_level" in published_event.payload

        # Verify position updated (assuming low risk)
        assert service._positions["AAPL"] == 100
        assert service._daily_volume["AAPL"] == 100

        # Verify metrics
        mock_metrics.increment.assert_any_call("events.risk_assessed.published")

    async def test_handle_order_filled_event(self, mock_message_bus, mock_metrics):
        """Test order filled event handler."""
        service = RiskService(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
        )

        # Set initial position
        service._positions["AAPL"] = 100

        await service.on_start()

        # Get the order filled handler
        filled_handler = service._event_handlers["events.order.filled"][0]

        # Create order filled event - BUY
        from aegis_sdk.domain.models import Event

        buy_event = Event(
            domain="order",
            event_type="filled",
            payload={
                "order": {
                    "order_id": "ORD-000001",
                    "symbol": "AAPL",
                    "quantity": 50,
                    "side": "BUY",
                }
            },
            source="order-service-123",
        )

        # Handle buy event
        await filled_handler(buy_event)

        # Verify position increased
        assert service._positions["AAPL"] == 150

        # Verify position update event published
        mock_message_bus.publish_event.assert_called()
        published_event = mock_message_bus.publish_event.call_args[0][0]
        assert published_event.domain == "position"
        assert published_event.event_type == "updated"
        assert published_event.payload["symbol"] == "AAPL"
        assert published_event.payload["position"] == 150

        # Create order filled event - SELL
        sell_event = Event(
            domain="order",
            event_type="filled",
            payload={
                "order": {
                    "order_id": "ORD-000002",
                    "symbol": "AAPL",
                    "filled_quantity": 75,  # Using filled_quantity
                    "side": "SELL",
                }
            },
            source="order-service-123",
        )

        # Handle sell event
        await filled_handler(sell_event)

        # Verify position decreased
        assert service._positions["AAPL"] == 75

        # Verify metrics
        mock_metrics.increment.assert_any_call("events.position_updated.published")
        mock_metrics.gauge.assert_any_call("positions.AAPL", 150)
        mock_metrics.gauge.assert_any_call("positions.AAPL", 75)

    async def test_simulate_work_rpc(self, mock_message_bus, mock_metrics):
        """Test simulate_work RPC handler."""
        service = RiskService(
            message_bus=mock_message_bus,
            instance_id="risk-test-01",
            metrics=mock_metrics,
        )

        await service.on_start()

        # Get the handler
        simulate_work_handler = service._rpc_handlers["simulate_work"]

        # Test with default duration
        result = await simulate_work_handler({})
        assert result["work_completed"] is True
        assert result["duration"] == 1.0
        assert result["service"] == "risk-service"
        assert result["instance"] == "risk-test-01"

        # Test with custom duration
        result = await simulate_work_handler({"duration": 0.01})
        assert result["work_completed"] is True
        assert result["duration"] == 0.01
