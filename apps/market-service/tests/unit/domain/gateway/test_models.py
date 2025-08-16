"""
Comprehensive unit tests for Gateway domain model
Achieving 80%+ test coverage with edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from domain.gateway.events import (
    GatewayConnected,
    GatewayDisconnected,
    HeartbeatReceived,
    LeadershipAcquired,
    LeadershipLost,
)
from domain.gateway.models import Gateway
from domain.gateway.value_objects import (
    ConnectionState,
    GatewayConfig,
    GatewayId,
    GatewayType,
    HeartbeatConfig,
)


class TestGatewayModel:
    """Test suite for Gateway aggregate root"""

    @pytest.fixture
    def gateway_config(self) -> GatewayConfig:
        """Create a test gateway configuration"""
        return GatewayConfig(
            gateway_id="test-gateway-01",
            gateway_type=GatewayType.CTP,
            heartbeat_interval=30,
            reconnect_delay=5,
            max_reconnect_attempts=10,
        )

    @pytest.fixture
    def gateway(self, gateway_config) -> Gateway:
        """Create a test gateway instance"""
        return Gateway(
            gateway_id=GatewayId(value="gateway-01"),
            gateway_type=GatewayType.CTP,
            config=gateway_config,
        )

    def test_gateway_initialization(self, gateway):
        """Test gateway initialization with default values"""
        assert str(gateway.gateway_id) == "gateway-01"
        assert gateway.gateway_type == GatewayType.CTP
        assert gateway.connection_state == ConnectionState.DISCONNECTED
        assert gateway.last_heartbeat is None
        assert gateway.is_leader is False
        assert gateway.connection_attempts == 0
        assert gateway.last_connection_attempt is None
        assert gateway.events == []

    def test_connect_from_disconnected(self, gateway):
        """Test connecting from disconnected state"""
        events = gateway.connect()

        assert len(events) == 1
        assert isinstance(events[0], GatewayConnected)
        assert gateway.connection_state == ConnectionState.CONNECTING
        assert gateway.connection_attempts == 1
        assert gateway.last_connection_attempt is not None

    def test_connect_when_already_connected(self, gateway):
        """Test connecting when already connected - should be idempotent"""
        gateway.connection_state = ConnectionState.CONNECTED
        events = gateway.connect()

        assert len(events) == 0
        assert gateway.connection_state == ConnectionState.CONNECTED
        assert gateway.connection_attempts == 0

    def test_connect_when_already_connecting(self, gateway):
        """Test connecting when already in connecting state"""
        gateway.connection_state = ConnectionState.CONNECTING
        events = gateway.connect()

        assert len(events) == 0
        assert gateway.connection_state == ConnectionState.CONNECTING

    def test_connect_from_reconnecting_state(self, gateway):
        """Test connecting from reconnecting state"""
        gateway.connection_state = ConnectionState.RECONNECTING
        events = gateway.connect()

        assert len(events) == 1
        assert isinstance(events[0], GatewayConnected)
        assert gateway.connection_state == ConnectionState.CONNECTING
        assert gateway.connection_attempts == 1

    def test_disconnect_when_connected(self, gateway):
        """Test disconnecting from connected state"""
        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = datetime.now()

        events = gateway.disconnect()

        assert len(events) == 1
        assert isinstance(events[0], GatewayDisconnected)
        assert events[0].reason == "Graceful disconnection"
        assert gateway.connection_state == ConnectionState.DISCONNECTED
        assert gateway.last_heartbeat is None

    def test_disconnect_when_already_disconnected(self, gateway):
        """Test disconnecting when already disconnected - should be idempotent"""
        events = gateway.disconnect()

        assert len(events) == 0
        assert gateway.connection_state == ConnectionState.DISCONNECTED

    def test_disconnect_from_various_states(self, gateway):
        """Test disconnecting from various connection states"""
        states = [ConnectionState.CONNECTING, ConnectionState.RECONNECTING]

        for state in states:
            gateway.connection_state = state
            events = gateway.disconnect()

            assert len(events) == 1
            assert isinstance(events[0], GatewayDisconnected)
            assert gateway.connection_state == ConnectionState.DISCONNECTED

    def test_handle_heartbeat_when_connected(self, gateway):
        """Test handling heartbeat when connected"""
        gateway.connection_state = ConnectionState.CONNECTED

        with patch("domain.gateway.models.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.now.return_value = mock_now

            events = gateway.handle_heartbeat()

            assert len(events) == 1
            assert isinstance(events[0], HeartbeatReceived)
            assert gateway.last_heartbeat == mock_now

    def test_handle_heartbeat_when_not_connected(self, gateway):
        """Test handling heartbeat when not connected - should be ignored"""
        states = [
            ConnectionState.DISCONNECTED,
            ConnectionState.CONNECTING,
            ConnectionState.RECONNECTING,
        ]

        for state in states:
            gateway.connection_state = state
            events = gateway.handle_heartbeat()

            assert len(events) == 0
            assert gateway.last_heartbeat is None

    def test_acquire_leadership_when_not_leader(self, gateway):
        """Test acquiring leadership when not already leader"""
        events = gateway.acquire_leadership()

        assert len(events) == 1
        assert isinstance(events[0], LeadershipAcquired)
        assert gateway.is_leader is True

    def test_acquire_leadership_when_already_leader(self, gateway):
        """Test acquiring leadership when already leader - should be idempotent"""
        gateway.is_leader = True
        events = gateway.acquire_leadership()

        assert len(events) == 0
        assert gateway.is_leader is True

    def test_lose_leadership_when_leader_and_connected(self, gateway):
        """Test losing leadership when leader and connected"""
        gateway.is_leader = True
        gateway.connection_state = ConnectionState.CONNECTED

        events = gateway.lose_leadership()

        assert len(events) == 2
        assert isinstance(events[0], LeadershipLost)
        assert isinstance(events[1], GatewayDisconnected)
        assert gateway.is_leader is False
        assert gateway.connection_state == ConnectionState.DISCONNECTED

    def test_lose_leadership_when_leader_but_disconnected(self, gateway):
        """Test losing leadership when leader but already disconnected"""
        gateway.is_leader = True
        gateway.connection_state = ConnectionState.DISCONNECTED

        events = gateway.lose_leadership()

        assert len(events) == 1
        assert isinstance(events[0], LeadershipLost)
        assert gateway.is_leader is False

    def test_lose_leadership_when_not_leader(self, gateway):
        """Test losing leadership when not leader - should be idempotent"""
        gateway.is_leader = False
        events = gateway.lose_leadership()

        assert len(events) == 0
        assert gateway.is_leader is False

    def test_mark_connected(self, gateway):
        """Test marking gateway as connected"""
        gateway.mark_connected()
        assert gateway.connection_state == ConnectionState.CONNECTED

    def test_mark_reconnecting(self, gateway):
        """Test marking gateway as reconnecting"""
        gateway.mark_reconnecting()
        assert gateway.connection_state == ConnectionState.RECONNECTING

    def test_is_connected(self, gateway):
        """Test is_connected method"""
        assert gateway.is_connected() is False

        gateway.connection_state = ConnectionState.CONNECTED
        assert gateway.is_connected() is True

        gateway.connection_state = ConnectionState.CONNECTING
        assert gateway.is_connected() is False

        gateway.connection_state = ConnectionState.RECONNECTING
        assert gateway.is_connected() is False

    def test_is_healthy_when_connected_with_fresh_heartbeat(self, gateway):
        """Test is_healthy when connected with fresh heartbeat"""
        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = datetime.now()

        assert gateway.is_healthy() is True

    def test_is_healthy_when_not_connected(self, gateway):
        """Test is_healthy when not connected"""
        gateway.connection_state = ConnectionState.DISCONNECTED
        assert gateway.is_healthy() is False

        gateway.connection_state = ConnectionState.CONNECTING
        assert gateway.is_healthy() is False

    def test_is_healthy_when_connected_but_no_heartbeat(self, gateway):
        """Test is_healthy when connected but no heartbeat received"""
        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = None

        assert gateway.is_healthy() is False

    def test_is_healthy_with_stale_heartbeat(self, gateway):
        """Test is_healthy when heartbeat is stale"""
        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = datetime.now() - timedelta(seconds=65)

        assert gateway.is_healthy() is False

    def test_is_healthy_with_custom_heartbeat_timeout(self, gateway):
        """Test is_healthy with custom heartbeat timeout configuration"""
        # Create config with heartbeat config
        heartbeat_config = HeartbeatConfig(
            interval=30,
            timeout=120,  # 2 minutes
            max_failures=3,
        )
        gateway.config.heartbeat_config = heartbeat_config

        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = datetime.now() - timedelta(seconds=90)

        # 90 seconds ago, but timeout is 120 seconds, so still healthy
        assert gateway.is_healthy() is True

        # Now make it stale
        gateway.last_heartbeat = datetime.now() - timedelta(seconds=130)
        assert gateway.is_healthy() is False

    def test_is_healthy_without_heartbeat_config(self, gateway):
        """Test is_healthy falls back to default timeout when no heartbeat config"""
        # Remove heartbeat_config if it exists
        if hasattr(gateway.config, "heartbeat_config"):
            delattr(gateway.config, "heartbeat_config")

        gateway.connection_state = ConnectionState.CONNECTED
        gateway.last_heartbeat = datetime.now() - timedelta(seconds=55)

        # Default timeout is 60 seconds, so 55 seconds ago is still healthy
        assert gateway.is_healthy() is True

        gateway.last_heartbeat = datetime.now() - timedelta(seconds=65)
        # Now it's unhealthy
        assert gateway.is_healthy() is False

    def test_get_events(self, gateway):
        """Test getting and clearing domain events"""
        # Generate some events
        gateway.connect()
        gateway.mark_connected()
        gateway.handle_heartbeat()
        gateway.acquire_leadership()

        # Get events
        events = gateway.get_events()

        # Should have events from connect, heartbeat, and leadership
        assert len(events) == 3
        assert isinstance(events[0], GatewayConnected)
        assert isinstance(events[1], HeartbeatReceived)
        assert isinstance(events[2], LeadershipAcquired)

        # Events should be cleared
        assert gateway.events == []

        # Getting events again should return empty list
        assert gateway.get_events() == []

    def test_event_accumulation(self, gateway):
        """Test that events accumulate properly"""
        gateway.connect()
        assert len(gateway.events) == 1

        gateway.mark_connected()
        gateway.handle_heartbeat()
        assert len(gateway.events) == 2

        gateway.acquire_leadership()
        assert len(gateway.events) == 3

    def test_gateway_type_serialization(self, gateway):
        """Test that gateway type is properly serialized in events"""
        # Test with enum type
        events = gateway.connect()
        assert events[0].gateway_type == "CTP"

        # Test with string type (edge case)
        gateway.gateway_type = "CUSTOM"
        events = gateway.disconnect()
        assert events[0].gateway_type == "CUSTOM"

    def test_connection_attempts_tracking(self, gateway):
        """Test that connection attempts are properly tracked"""
        assert gateway.connection_attempts == 0

        gateway.connect()
        assert gateway.connection_attempts == 1
        assert gateway.last_connection_attempt is not None

        # Reset state and try again
        gateway.connection_state = ConnectionState.DISCONNECTED
        gateway.connect()
        assert gateway.connection_attempts == 2

    def test_concurrent_state_transitions(self, gateway):
        """Test handling of concurrent state transitions"""
        # Connect
        gateway.connect()
        assert gateway.connection_state == ConnectionState.CONNECTING

        # Mark as connected
        gateway.mark_connected()
        assert gateway.connection_state == ConnectionState.CONNECTED

        # Try to connect again - should be no-op
        events = gateway.connect()
        assert len(events) == 0

        # Mark as reconnecting
        gateway.mark_reconnecting()
        assert gateway.connection_state == ConnectionState.RECONNECTING

        # Disconnect
        gateway.disconnect()
        assert gateway.connection_state == ConnectionState.DISCONNECTED

    def test_model_validation_with_invalid_data(self):
        """Test model validation with invalid data"""
        with pytest.raises(ValidationError):
            Gateway(
                gateway_id=None,  # Invalid - required field
                gateway_type=GatewayType.CTP,
                config=None,  # Invalid - required field
            )

    def test_model_serialization(self, gateway):
        """Test model can be serialized to dict"""
        data = gateway.model_dump(exclude={"events"})

        assert data["gateway_id"] == "gateway-01"
        assert data["gateway_type"] == GatewayType.CTP
        assert data["connection_state"] == ConnectionState.DISCONNECTED
        assert data["is_leader"] is False
        assert data["connection_attempts"] == 0

    def test_edge_case_rapid_connect_disconnect(self, gateway):
        """Test rapid connect/disconnect cycles"""
        for _ in range(5):
            gateway.connect()
            gateway.mark_connected()
            gateway.disconnect()

        # Should handle rapid cycles without issues
        assert gateway.connection_state == ConnectionState.DISCONNECTED
        assert gateway.connection_attempts == 5

    def test_edge_case_leadership_changes_during_connection(self, gateway):
        """Test leadership changes during various connection states"""
        # Acquire leadership while disconnected
        gateway.acquire_leadership()
        assert gateway.is_leader is True

        # Connect as leader
        gateway.connect()
        gateway.mark_connected()

        # Lose leadership while connected - should disconnect
        events = gateway.lose_leadership()
        assert len(events) == 2  # LeadershipLost + GatewayDisconnected
        assert gateway.connection_state == ConnectionState.DISCONNECTED
        assert gateway.is_leader is False
