"""Tests for pricing domain models."""

from datetime import datetime

import pytest
from pricing_service.domain_models import Price, PriceQuote


class TestPrice:
    """Test cases for Price model."""

    def test_price_creation(self):
        """Test creating a valid price."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)
        price = Price(
            symbol="AAPL",
            price=150.25,
            bid=150.20,
            ask=150.30,
            timestamp=timestamp,
            instance_id="pricing-01",
        )

        assert price.symbol == "AAPL"
        assert price.price == 150.25
        assert price.bid == 150.20
        assert price.ask == 150.30
        assert price.timestamp == timestamp
        assert price.instance_id == "pricing-01"

    def test_price_without_instance_id(self):
        """Test creating price without instance_id."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)
        price = Price(
            symbol="AAPL",
            price=150.25,
            bid=150.20,
            ask=150.30,
            timestamp=timestamp,
        )

        assert price.instance_id is None

    def test_price_invalid_values(self):
        """Test price validation."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)

        # Test negative price
        with pytest.raises(ValueError):
            Price(
                symbol="AAPL",
                price=-10.0,
                bid=150.20,
                ask=150.30,
                timestamp=timestamp,
            )

        # Test negative bid
        with pytest.raises(ValueError):
            Price(
                symbol="AAPL",
                price=150.25,
                bid=-10.0,
                ask=150.30,
                timestamp=timestamp,
            )

        # Test negative ask
        with pytest.raises(ValueError):
            Price(
                symbol="AAPL",
                price=150.25,
                bid=150.20,
                ask=-10.0,
                timestamp=timestamp,
            )


class TestPriceQuote:
    """Test cases for PriceQuote model."""

    def test_price_quote_creation(self):
        """Test creating a valid price quote."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)
        quote = PriceQuote(
            order_id="ORDER-001",
            symbol="AAPL",
            price=150.25,
            bid=150.20,
            ask=150.30,
            timestamp=timestamp,
            instance_id="pricing-01",
        )

        assert quote.order_id == "ORDER-001"
        assert quote.symbol == "AAPL"
        assert quote.price == 150.25
        assert quote.bid == 150.20
        assert quote.ask == 150.30
        assert quote.timestamp == timestamp
        assert quote.instance_id == "pricing-01"

    def test_price_quote_model_dump(self):
        """Test model serialization."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)
        quote = PriceQuote(
            order_id="ORDER-002",
            symbol="TSLA",
            price=250.50,
            bid=250.45,
            ask=250.55,
            timestamp=timestamp,
            instance_id="pricing-02",
        )

        data = quote.model_dump()

        assert data == {
            "order_id": "ORDER-002",
            "symbol": "TSLA",
            "price": 250.50,
            "bid": 250.45,
            "ask": 250.55,
            "timestamp": timestamp,
            "instance_id": "pricing-02",
        }

    def test_price_quote_timestamp_string(self):
        """Test price quote with timestamp as string."""
        quote = PriceQuote(
            order_id="ORDER-003",
            symbol="GOOGL",
            price=100.0,
            bid=99.95,
            ask=100.05,
            timestamp="2024-01-01T00:00:00Z",
            instance_id="pricing-03",
        )

        assert quote.order_id == "ORDER-003"
        assert isinstance(quote.timestamp, datetime)

    def test_price_quote_validation(self):
        """Test price quote validation."""
        timestamp = datetime(2024, 1, 1, 0, 0, 0)

        # Test missing required fields
        with pytest.raises(ValueError):
            PriceQuote(
                symbol="AAPL",
                price=150.25,
                bid=150.20,
                ask=150.30,
                timestamp=timestamp,
                instance_id="pricing-01",
                # Missing order_id
            )

        # Test invalid price values
        with pytest.raises(ValueError):
            PriceQuote(
                order_id="ORDER-001",
                symbol="AAPL",
                price=-10.0,  # Invalid negative price
                bid=150.20,
                ask=150.30,
                timestamp=timestamp,
                instance_id="pricing-01",
            )
