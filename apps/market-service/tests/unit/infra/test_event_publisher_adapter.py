"""
Unit tests for SDK Event Publisher Adapter.

Tests the adapter that bridges domain events to SDK event publishing.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from aegis_sdk.domain.models import Event as SDKEvent

from domain.shared.events import (
    DomainEvent,
    GatewayConnectedEvent,
    GatewayDisconnectedEvent,
    MarketDataReceivedEvent,
    SubscriptionCreatedEvent,
)
from infra.event_publisher_adapter import SDKEventPublisherAdapter


class TestSDKEventPublisherAdapter:
    """Test suite for SDK Event Publisher Adapter."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock SDK Service."""
        service = MagicMock()
        service.instance_id = "test-instance-123"
        service.publish_event = AsyncMock()
        return service

    @pytest.fixture
    def event_publisher(self, mock_service):
        """Create the event publisher adapter with mock service."""
        return SDKEventPublisherAdapter(mock_service)

    @pytest.mark.asyncio
    async def test_publish_single_event(self, event_publisher, mock_service):
        """Test publishing a single domain event."""
        # Arrange
        domain_event = DomainEvent(
            event_id=UUID("12345678-1234-5678-1234-567812345678"),
            occurred_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            aggregate_id="gateway-1",
            event_type="TestEvent",
        )

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        mock_service.publish_event.assert_called_once()
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert isinstance(sdk_event, SDKEvent)
        assert sdk_event.domain == "market-service"
        assert sdk_event.event_type == "TestEvent"
        assert sdk_event.source == "test-instance-123"
        assert sdk_event.payload["event_id"] == "12345678-1234-5678-1234-567812345678"
        assert sdk_event.payload["aggregate_id"] == "gateway-1"

    @pytest.mark.asyncio
    async def test_publish_batch_events(self, event_publisher, mock_service):
        """Test publishing multiple domain events."""
        # Arrange
        events = [
            DomainEvent(aggregate_id="gateway-1", event_type="Event1"),
            DomainEvent(aggregate_id="gateway-2", event_type="Event2"),
            DomainEvent(aggregate_id="gateway-3", event_type="Event3"),
        ]

        # Act
        await event_publisher.publish_batch(events)

        # Assert
        assert mock_service.publish_event.call_count == 3
        for i, call in enumerate(mock_service.publish_event.call_args_list):
            sdk_event = call[0][0]
            assert sdk_event.event_type == f"Event{i + 1}"
            assert sdk_event.payload["aggregate_id"] == f"gateway-{i + 1}"

    @pytest.mark.asyncio
    async def test_translate_gateway_connected_event(self, event_publisher, mock_service):
        """Test translating a GatewayConnectedEvent."""
        # Arrange
        session_id = UUID("98765432-1234-5678-1234-567812345678")
        domain_event = GatewayConnectedEvent(
            aggregate_id="gateway-1",
            gateway_id="ctp-gateway",
            gateway_type="CTP",
            session_id=session_id,
        )

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        mock_service.publish_event.assert_called_once()
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert sdk_event.event_type == "GatewayConnectedEvent"
        assert sdk_event.payload["gateway_id"] == "ctp-gateway"
        assert sdk_event.payload["gateway_type"] == "CTP"
        assert sdk_event.payload["session_id"] == str(session_id)

    @pytest.mark.asyncio
    async def test_translate_gateway_disconnected_event(self, event_publisher, mock_service):
        """Test translating a GatewayDisconnectedEvent."""
        # Arrange
        domain_event = GatewayDisconnectedEvent(
            aggregate_id="gateway-1",
            gateway_id="ctp-gateway",
            reason="Network error",
        )

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        mock_service.publish_event.assert_called_once()
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert sdk_event.event_type == "GatewayDisconnectedEvent"
        assert sdk_event.payload["gateway_id"] == "ctp-gateway"
        assert sdk_event.payload["reason"] == "Network error"

    @pytest.mark.asyncio
    async def test_translate_market_data_received_event(self, event_publisher, mock_service):
        """Test translating a MarketDataReceivedEvent."""
        # Arrange
        timestamp = datetime(2024, 1, 1, 13, 30, 0, tzinfo=UTC)
        domain_event = MarketDataReceivedEvent(
            aggregate_id="tick-1",
            symbol="AAPL",
            exchange="NASDAQ",
            price=150.25,
            volume=1000,
            timestamp=timestamp,
        )

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        mock_service.publish_event.assert_called_once()
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert sdk_event.event_type == "MarketDataReceivedEvent"
        assert sdk_event.payload["symbol"] == "AAPL"
        assert sdk_event.payload["exchange"] == "NASDAQ"
        assert sdk_event.payload["price"] == 150.25
        assert sdk_event.payload["volume"] == 1000
        assert sdk_event.payload["timestamp"] == timestamp.isoformat()

    @pytest.mark.asyncio
    async def test_translate_subscription_created_event(self, event_publisher, mock_service):
        """Test translating a SubscriptionCreatedEvent."""
        # Arrange
        subscription_id = UUID("11111111-2222-3333-4444-555555555555")
        domain_event = SubscriptionCreatedEvent(
            aggregate_id="sub-1",
            subscription_id=subscription_id,
            symbol="TSLA",
            exchange="NASDAQ",
            subscriber_id="trader-1",
        )

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        mock_service.publish_event.assert_called_once()
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert sdk_event.event_type == "SubscriptionCreatedEvent"
        assert sdk_event.payload["subscription_id"] == str(subscription_id)
        assert sdk_event.payload["symbol"] == "TSLA"
        assert sdk_event.payload["exchange"] == "NASDAQ"
        assert sdk_event.payload["subscriber_id"] == "trader-1"

    @pytest.mark.asyncio
    async def test_event_source_is_set_correctly(self, event_publisher, mock_service):
        """Test that event source is set to the service instance ID."""
        # Arrange
        domain_event = DomainEvent(aggregate_id="test", event_type="TestEvent")

        # Act
        await event_publisher.publish(domain_event)

        # Assert
        sdk_event = mock_service.publish_event.call_args[0][0]
        assert sdk_event.source == "test-instance-123"

    @pytest.mark.asyncio
    async def test_event_domain_is_always_market_service(self, event_publisher, mock_service):
        """Test that all events have domain set to 'market-service'."""
        # Arrange
        events = [
            GatewayConnectedEvent(gateway_id="g1", gateway_type="CTP"),
            GatewayDisconnectedEvent(gateway_id="g1", reason="test"),
            MarketDataReceivedEvent(symbol="AAPL", exchange="NASDAQ", price=100.0, volume=100),
            SubscriptionCreatedEvent(symbol="AAPL", exchange="NASDAQ", subscriber_id="s1"),
        ]

        # Act
        for event in events:
            await event_publisher.publish(event)

        # Assert
        for call in mock_service.publish_event.call_args_list:
            sdk_event = call[0][0]
            assert sdk_event.domain == "market-service"
