"""Unit tests for Order domain models following TDD principles."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from order_service.domain_models import Order, OrderSide, OrderStatus, OrderType, RiskLevel
from pydantic import ValidationError


class TestOrderModel:
    """Test Order domain model validation and behavior."""

    def test_create_valid_market_order(self):
        """Test creating a valid market order."""
        order = Order(
            order_id="ORD-000001",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
        )

        assert order.order_id == "ORD-000001"
        assert order.symbol == "AAPL"
        assert order.quantity == 100.0
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING
        assert order.price is None
        assert order.filled_quantity == 0
        assert order.risk_level is None

    def test_create_valid_limit_order(self):
        """Test creating a valid limit order with price."""
        order = Order(
            order_id="ORD-000002",
            symbol="GOOGL",
            quantity=50.0,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
            price=150.50,
        )

        assert order.order_type == OrderType.LIMIT
        assert order.price == 150.50

    def test_symbol_normalization(self):
        """Test that symbols are normalized to uppercase."""
        order = Order(
            order_id="ORD-000003",
            symbol=" aapl ",
            quantity=100.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
        )

        assert order.symbol == "AAPL"

    def test_invalid_order_id_format(self):
        """Test that invalid order ID format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="INVALID-ID",
                symbol="AAPL",
                quantity=100.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("order_id",) for error in errors)

    def test_invalid_quantity(self):
        """Test that invalid quantities are rejected."""
        # Negative quantity
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="ORD-000004",
                symbol="AAPL",
                quantity=-10.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

        # Zero quantity
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="ORD-000005",
                symbol="AAPL",
                quantity=0.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
            )

        # Excessive quantity
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="ORD-000006",
                symbol="AAPL",
                quantity=2_000_000.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
            )

    def test_filled_quantity_validation(self):
        """Test that filled quantity cannot exceed order quantity."""
        order = Order(
            order_id="ORD-000007",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
        )

        # Valid filled quantity
        order.filled_quantity = 50.0
        assert order.filled_quantity == 50.0

        # Try to exceed order quantity
        with pytest.raises(ValidationError) as exc_info:
            order.filled_quantity = 150.0

        errors = exc_info.value.errors()
        assert any("filled quantity cannot exceed" in str(error["msg"]).lower() for error in errors)

    def test_limit_order_requires_price(self):
        """Test that limit orders require a price."""
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="ORD-000008",
                symbol="AAPL",
                quantity=100.0,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
                # price missing
            )

        errors = exc_info.value.errors()
        assert any("price is required for limit" in str(error["msg"]).lower() for error in errors)

    def test_risk_assessment_update(self):
        """Test updating order with risk assessment."""
        order = Order(
            order_id="ORD-000009",
            symbol="TSLA",
            quantity=1000.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
        )

        # Initial state
        assert order.risk_level is None
        assert order.risk_assessed_at is None

        # Update with risk assessment
        order.risk_level = RiskLevel.HIGH
        order.risk_assessed_at = datetime.now(UTC)

        assert order.risk_level == RiskLevel.HIGH
        assert order.risk_assessed_at is not None

    def test_strict_mode_rejects_extra_fields(self):
        """Test that strict mode rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            Order(
                order_id="ORD-000010",
                symbol="AAPL",
                quantity=100.0,
                side=OrderSide.BUY,
                created_at=datetime.now(UTC),
                instance_id="order-service-01",
                extra_field="not allowed",  # This should be rejected
            )

        errors = exc_info.value.errors()
        assert any("extra" in str(error).lower() for error in errors)

    def test_model_dump_serialization(self):
        """Test model serialization for API responses."""
        order = Order(
            order_id="ORD-000011",
            symbol="AAPL",
            quantity=100.0,
            side=OrderSide.BUY,
            created_at=datetime.now(UTC),
            instance_id="order-service-01",
            metadata={"client": "web", "ip": "127.0.0.1"},
        )

        dumped = order.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["order_id"] == "ORD-000011"
        assert dumped["symbol"] == "AAPL"
        assert dumped["side"] == "BUY"
        assert dumped["metadata"] == {"client": "web", "ip": "127.0.0.1"}
