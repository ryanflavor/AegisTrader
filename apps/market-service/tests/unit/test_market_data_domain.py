"""
Comprehensive unit tests for Market Data domain.

Tests follow TDD principles with AAA pattern (Arrange-Act-Assert).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.market_data import (
    InstrumentType,
    MarketDataGateway,
    MarketDataSession,
    MarketDataSubscription,
    MarketDepth,
    Price,
    Symbol,
    Tick,
    TimeRange,
    Volume,
)


class TestValueObjects:
    """Test suite for value objects."""

    def test_symbol_creation_valid(self):
        """Test creating a valid symbol."""
        # Arrange & Act
        symbol = Symbol(value="AAPL", exchange="NASDAQ")

        # Assert
        assert symbol.value == "AAPL"
        assert symbol.exchange == "NASDAQ"
        assert str(symbol) == "AAPL.NASDAQ"

    def test_symbol_immutable(self):
        """Test that symbol is immutable."""
        # Arrange
        symbol = Symbol(value="AAPL", exchange="NASDAQ")

        # Act & Assert
        with pytest.raises(ValidationError):
            symbol.value = "GOOGL"  # type: ignore

    def test_symbol_validation(self):
        """Test symbol validation rules."""
        # Empty value
        with pytest.raises(ValidationError):
            Symbol(value="", exchange="NYSE")

        # Empty exchange
        with pytest.raises(ValidationError):
            Symbol(value="AAPL", exchange="")

        # Invalid characters
        with pytest.raises(ValidationError):
            Symbol(value="AAPL@#", exchange="NYSE")

    def test_price_creation_valid(self):
        """Test creating a valid price."""
        # Arrange & Act
        price = Price(value=Decimal("100.5678"))

        # Assert
        assert price.value == Decimal("100.5678")
        assert price.currency == "USD"
        assert str(price) == "USD 100.5678"

    def test_price_operations(self):
        """Test price arithmetic operations."""
        # Arrange
        price1 = Price(value=Decimal("100.50"))
        price2 = Price(value=Decimal("50.25"))

        # Act
        result = price1.add(price2)
        multiplied = price1.multiply(Decimal("2"))

        # Assert
        assert result.value == Decimal("150.75")
        assert multiplied.value == Decimal("201.00")

    def test_price_different_currencies_cannot_add(self):
        """Test that prices with different currencies cannot be added."""
        # Arrange
        price1 = Price(value=Decimal("100"), currency="USD")
        price2 = Price(value=Decimal("100"), currency="EUR")

        # Act & Assert
        with pytest.raises(ValueError, match="different currencies"):
            price1.add(price2)

    def test_volume_operations(self):
        """Test volume operations."""
        # Arrange
        vol1 = Volume(value=1000)
        vol2 = Volume(value=500)

        # Act
        result = vol1.add(vol2)

        # Assert
        assert result.value == 1500
        assert str(vol1) == "1,000"

    def test_market_depth_calculations(self):
        """Test market depth calculations."""
        # Arrange
        depth = MarketDepth(
            bid_price=Price(value=Decimal("100.00")),
            bid_volume=Volume(value=1000),
            ask_price=Price(value=Decimal("100.10")),
            ask_volume=Volume(value=1500),
            timestamp=datetime.now(UTC),
        )

        # Act
        spread = depth.spread
        mid = depth.mid_price

        # Assert
        assert spread == Decimal("0.10")
        assert mid.value == Decimal("100.05")

    def test_tick_creation(self):
        """Test tick creation and validation."""
        # Arrange
        symbol = Symbol(value="AAPL", exchange="NASDAQ")
        price = Price(value=Decimal("150.50"))
        volume = Volume(value=1000)
        timestamp = datetime.now(UTC)

        # Act
        tick = Tick(
            symbol=symbol,
            price=price,
            volume=volume,
            timestamp=timestamp,
            sequence_number=1,
        )

        # Assert
        assert tick.symbol == symbol
        assert tick.price == price
        assert tick.volume == volume
        assert tick.sequence_number == 1

    def test_time_range_validation(self):
        """Test time range validation."""
        # Valid range
        start = datetime.now(UTC)
        end = start + timedelta(hours=1)
        time_range = TimeRange(start=start, end=end)
        assert time_range.duration_seconds == 3600

        # End before start
        with pytest.raises(ValidationError, match="End time must be after start time"):
            TimeRange(start=end, end=start)

        # No timezone
        with pytest.raises(ValidationError, match="timezone-aware"):
            TimeRange(start=datetime.now(), end=datetime.now())


class TestEntities:
    """Test suite for domain entities."""

    def test_subscription_lifecycle(self):
        """Test subscription entity lifecycle."""
        # Arrange
        symbol = Symbol(value="AAPL", exchange="NASDAQ")
        subscription = MarketDataSubscription(
            symbol=symbol,
            subscriber_id="user123",
            instrument_type=InstrumentType.STOCK,
        )

        # Assert initial state
        assert subscription.is_active
        assert subscription.tick_count == 0
        assert subscription.last_tick_at is None

        # Act - Process tick
        tick = Tick(
            symbol=symbol,
            price=Price(value=Decimal("150.50")),
            volume=Volume(value=1000),
            timestamp=datetime.now(UTC),
            sequence_number=1,
        )
        subscription.process_tick(tick)

        # Assert after tick
        assert subscription.tick_count == 1
        assert subscription.last_tick_at == tick.timestamp

        # Act - Unsubscribe
        subscription.unsubscribe()

        # Assert after unsubscribe
        assert not subscription.is_active

        # Cannot process tick when inactive
        with pytest.raises(ValueError, match="inactive subscription"):
            subscription.process_tick(tick)

    def test_subscription_events(self):
        """Test that subscription raises proper domain events."""
        # Arrange
        symbol = Symbol(value="AAPL", exchange="NASDAQ")
        subscription = MarketDataSubscription(
            symbol=symbol,
            subscriber_id="user123",
            instrument_type=InstrumentType.STOCK,
        )

        # Act - Unsubscribe
        subscription.unsubscribe()

        # Assert - Check events
        events = subscription.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "MarketDataUnsubscribed"

    def test_session_lifecycle(self):
        """Test market data session lifecycle."""
        # Arrange
        session = MarketDataSession(gateway_id="gateway1")

        # Assert initial state
        assert not session.is_connected
        assert session.active_subscription_count == 0

        # Act - Connect
        session.connect({"host": "localhost", "port": "8080"})

        # Assert after connect
        assert session.is_connected
        assert session.last_heartbeat_at is not None
        assert session.connection_params == {"host": "localhost", "port": "8080"}

        # Act - Add subscription
        subscription = MarketDataSubscription(
            symbol=Symbol(value="AAPL", exchange="NASDAQ"),
            subscriber_id="user123",
            instrument_type=InstrumentType.STOCK,
        )
        session.add_subscription(subscription)

        # Assert after subscription
        assert session.active_subscription_count == 1
        assert "AAPL.NASDAQ" in session.subscriptions

        # Act - Disconnect
        session.disconnect()

        # Assert after disconnect
        assert not session.is_connected
        assert session.session_ended_at is not None

    def test_session_cannot_add_subscription_when_disconnected(self):
        """Test that subscriptions cannot be added to disconnected session."""
        # Arrange
        session = MarketDataSession(gateway_id="gateway1")
        subscription = MarketDataSubscription(
            symbol=Symbol(value="AAPL", exchange="NASDAQ"),
            subscriber_id="user123",
            instrument_type=InstrumentType.STOCK,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="disconnected session"):
            session.add_subscription(subscription)

    def test_session_health_check(self):
        """Test session health monitoring."""
        # Arrange
        session = MarketDataSession(gateway_id="gateway1")

        # Not healthy when disconnected
        assert not session.is_healthy

        # Connect
        session.connect()
        assert session.is_healthy

        # Simulate stale heartbeat
        session.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=31)
        assert not session.is_healthy


class TestAggregates:
    """Test suite for aggregate roots."""

    def test_gateway_lifecycle(self):
        """Test gateway aggregate lifecycle."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="ctp_gateway",
            gateway_type="CTP",
            max_subscriptions=50,
        )

        # Assert initial state
        assert not gateway.is_connected
        assert gateway.active_subscription_count == 0

        # Act - Connect
        gateway.connect({"server": "ctp.example.com"})

        # Assert after connect
        assert gateway.is_connected
        assert gateway.current_session is not None
        assert gateway.total_sessions == 1

        # Collect events
        events = gateway.collect_events()
        assert len(events) == 2  # GatewayConnected, MarketSessionStarted

        # Act - Subscribe
        subscription = gateway.subscribe(
            symbol=Symbol(value="IF2312", exchange="CFFEX"),
            subscriber_id="trader1",
            instrument_type=InstrumentType.FUTURE,
        )

        # Assert after subscribe
        assert gateway.active_subscription_count == 1
        assert subscription.is_active

        # Act - Disconnect
        gateway.disconnect("End of trading day")

        # Assert after disconnect
        assert not gateway.is_connected
        assert gateway.current_session is None

    def test_gateway_subscription_limit(self):
        """Test gateway subscription limit enforcement."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="test_gateway",
            gateway_type="TEST",
            max_subscriptions=2,
        )
        gateway.connect()

        # Act - Add subscriptions up to limit
        gateway.subscribe(
            Symbol(value="AAPL", exchange="NASDAQ"),
            "user1",
            InstrumentType.STOCK,
        )
        gateway.subscribe(
            Symbol(value="GOOGL", exchange="NASDAQ"),
            "user1",
            InstrumentType.STOCK,
        )

        # Assert - Cannot exceed limit
        with pytest.raises(ValueError, match="Subscription limit reached"):
            gateway.subscribe(
                Symbol(value="MSFT", exchange="NASDAQ"),
                "user1",
                InstrumentType.STOCK,
            )

    def test_gateway_process_tick(self):
        """Test processing ticks through gateway."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="test_gateway",
            gateway_type="TEST",
        )
        gateway.connect()

        symbol = Symbol(value="AAPL", exchange="NASDAQ")
        gateway.subscribe(symbol, "user1", InstrumentType.STOCK)

        # Act - Process tick
        tick = Tick(
            symbol=symbol,
            price=Price(value=Decimal("150.50")),
            volume=Volume(value=1000),
            timestamp=datetime.now(UTC),
            sequence_number=1,
        )
        gateway.process_tick(tick)

        # Assert
        assert gateway.total_ticks_processed == 1
        assert gateway.current_session.total_ticks_received == 1

    def test_gateway_cannot_process_tick_without_subscription(self):
        """Test that ticks cannot be processed without subscription."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="test_gateway",
            gateway_type="TEST",
        )
        gateway.connect()

        # Act & Assert
        tick = Tick(
            symbol=Symbol(value="AAPL", exchange="NASDAQ"),
            price=Price(value=Decimal("150.50")),
            volume=Volume(value=1000),
            timestamp=datetime.now(UTC),
            sequence_number=1,
        )

        with pytest.raises(ValueError, match="No subscription found"):
            gateway.process_tick(tick)

    def test_gateway_health_monitoring(self):
        """Test gateway health monitoring."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="test_gateway",
            gateway_type="TEST",
            heartbeat_timeout_seconds=10,
        )

        # Not healthy when disconnected
        assert not gateway.is_healthy()

        # Connect
        gateway.connect()
        assert gateway.is_healthy()

        # Simulate stale heartbeat
        gateway.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=11)
        assert not gateway.is_healthy()

    def test_gateway_event_collection(self):
        """Test collecting events from gateway and nested entities."""
        # Arrange
        gateway = MarketDataGateway(
            gateway_id="test_gateway",
            gateway_type="TEST",
        )

        # Act - Multiple operations
        gateway.connect()
        symbol = Symbol(value="AAPL", exchange="NASDAQ")
        gateway.subscribe(symbol, "user1", InstrumentType.STOCK)

        tick = Tick(
            symbol=symbol,
            price=Price(value=Decimal("150.50")),
            volume=Volume(value=1000),
            timestamp=datetime.now(UTC),
            sequence_number=1,
        )
        gateway.process_tick(tick)

        # Collect all events
        events = gateway.collect_events()

        # Assert - Should have events from gateway and subscription
        event_types = [e.__class__.__name__ for e in events]
        assert "GatewayConnected" in event_types
        assert "MarketSessionStarted" in event_types
        assert "MarketDataSubscribed" in event_types
        assert "TickProcessed" in event_types
