"""
Unit tests for CTP adapter interface
Following TDD RED phase - these tests should fail initially
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# These imports will fail initially (RED phase)
from domain.gateway.ports import GatewayPort
from infra.adapters.gateway.ctp_adapter import (
    CtpConfig,
    CtpGatewayAdapter,
)


class TestCtpAdapter:
    """Test suite for CTP adapter implementation"""

    @pytest.fixture
    def ctp_config(self) -> CtpConfig:
        """CTP configuration for testing"""
        return CtpConfig(
            user_id="test_user",
            password="test_password",
            broker_id="9999",
            app_id="simnow_client_test",
            auth_code="0000000000000000",
            td_address="tcp://180.168.146.187:10130",
            md_address="tcp://180.168.146.187:10131",
        )

    @pytest.fixture
    def mock_vnpy_gateway(self):
        """Mock vnpy CTP gateway"""
        with patch("infra.adapters.gateway.ctp_adapter.CtpGateway") as mock_gateway_class:
            mock_gateway = MagicMock()
            mock_gateway.connect = Mock()
            mock_gateway.close = Mock()
            mock_gateway.subscribe = Mock()
            mock_gateway.send_order = Mock(return_value="TEST_ORDER_ID")
            mock_gateway.cancel_order = Mock()
            mock_gateway_class.return_value = mock_gateway
            yield mock_gateway

    @pytest.fixture
    async def ctp_adapter(self, ctp_config, mock_vnpy_gateway) -> CtpGatewayAdapter:
        """Create CTP adapter instance for testing"""
        with patch("infra.adapters.gateway.ctp_adapter.EventEngine") as mock_event_engine:
            # Create mock event engine that doesn't hang
            mock_engine = MagicMock()
            mock_engine.start = Mock()
            mock_engine.stop = Mock()
            mock_engine.register = Mock()
            mock_engine.unregister = Mock()
            mock_event_engine.return_value = mock_engine

            adapter = CtpGatewayAdapter(config=ctp_config)
            adapter.gateway = mock_vnpy_gateway  # Inject mock
            adapter.event_engine = mock_engine  # Use mock engine

            yield adapter

            # Cleanup - ensure event engine is stopped
            try:
                mock_engine.stop()
                # Clear any registered callbacks
                adapter._tick_callbacks.clear()
                adapter._order_callbacks.clear()
                adapter._trade_callbacks.clear()
                adapter._position_callbacks.clear()
                adapter._account_callbacks.clear()
            except:
                pass  # Ignore cleanup errors

    async def test_adapter_implements_gateway_port_interface(self, ctp_adapter):
        """Test that CTP adapter properly implements the Gateway port interface"""
        # Verify adapter implements GatewayPort
        assert isinstance(ctp_adapter, GatewayPort)

        # Verify required methods exist
        assert hasattr(ctp_adapter, "connect")
        assert hasattr(ctp_adapter, "disconnect")
        assert hasattr(ctp_adapter, "subscribe")
        assert hasattr(ctp_adapter, "unsubscribe")
        assert hasattr(ctp_adapter, "is_connected")
        assert hasattr(ctp_adapter, "send_heartbeat")

    async def test_ctp_specific_authentication(self, ctp_adapter, ctp_config, mock_vnpy_gateway):
        """Test CTP-specific authentication with user/password/broker/app_id"""
        # Set status to simulate successful connection
        ctp_adapter.status.is_connected = True

        # Perform authentication
        await ctp_adapter.connect()

        # Verify CTP authentication parameters were passed correctly
        mock_vnpy_gateway.connect.assert_called_once()
        call_args = mock_vnpy_gateway.connect.call_args[0][0]

        assert call_args["用户名"] == ctp_config.user_id
        assert call_args["密码"] == ctp_config.password
        assert call_args["经纪商代码"] == ctp_config.broker_id
        assert call_args["交易服务器"] == ctp_config.td_address
        assert call_args["行情服务器"] == ctp_config.md_address
        assert call_args["产品名称"] == ctp_config.app_id
        assert call_args["授权编码"] == ctp_config.auth_code

    async def test_ctp_protocol_message_handling(self, ctp_adapter, mock_vnpy_gateway):
        """Test handling of CTP protocol messages"""
        from vnpy.event import Event
        from vnpy.trader.object import TickData

        # Setup mock tick data from CTP with all required fields
        mock_tick = Mock(spec=TickData)
        mock_tick.symbol = "IF2312"
        mock_tick.exchange = "CFFEX"
        mock_tick.last_price = 3456.8
        mock_tick.volume = 12345
        mock_tick.datetime = datetime.now()
        mock_tick.bid_price_1 = 3456.6
        mock_tick.ask_price_1 = 3457.0
        mock_tick.bid_volume_1 = 10
        mock_tick.ask_volume_1 = 15
        mock_tick.open_interest = 10000

        # Add fields that adapter checks for
        mock_tick.turnover = 1000000.0
        mock_tick.open_price = 3450.0
        mock_tick.high_price = 3460.0
        mock_tick.low_price = 3445.0
        mock_tick.pre_close = 3455.0
        mock_tick.limit_up = 3800.0
        mock_tick.limit_down = 3100.0

        # Don't add level 2-5 quotes attributes - hasattr will return False
        # Use spec to limit attributes to only those explicitly set
        delattr(mock_tick, "bid_price_2")
        delattr(mock_tick, "bid_price_3")
        delattr(mock_tick, "bid_price_4")
        delattr(mock_tick, "bid_price_5")
        delattr(mock_tick, "ask_price_2")
        delattr(mock_tick, "ask_price_3")
        delattr(mock_tick, "ask_price_4")
        delattr(mock_tick, "ask_price_5")

        # Create event
        event = Mock(spec=Event)
        event.data = mock_tick

        # Register a callback to capture tick
        received_tick = None

        def capture_tick(tick):
            nonlocal received_tick
            received_tick = tick

        ctp_adapter.register_tick_callback(capture_tick)

        # Simulate receiving tick data
        ctp_adapter._on_tick(event)

        # Verify tick was processed
        assert received_tick is not None

    async def test_adapter_data_transformation(self, ctp_adapter):
        """Test transformation from CTP data format to domain model"""
        from vnpy.event import Event
        from vnpy.trader.object import TickData

        from domain.market_data import Tick

        # Create CTP tick data with all required fields
        ctp_tick = Mock(spec=TickData)
        ctp_tick.symbol = "rb2405"
        ctp_tick.exchange = "SHFE"
        ctp_tick.last_price = 4128.0
        ctp_tick.volume = 98765
        ctp_tick.datetime = datetime.now()
        ctp_tick.bid_price_1 = 4127.0
        ctp_tick.ask_price_1 = 4129.0
        ctp_tick.bid_volume_1 = 10
        ctp_tick.ask_volume_1 = 20
        ctp_tick.open_interest = 50000

        # Add additional fields
        ctp_tick.turnover = 5000000.0
        ctp_tick.open_price = 4120.0
        ctp_tick.high_price = 4135.0
        ctp_tick.low_price = 4115.0
        ctp_tick.pre_close = 4125.0
        ctp_tick.limit_up = 4540.0
        ctp_tick.limit_down = 3710.0

        # Don't add level 2-5 quotes attributes - hasattr will return False
        delattr(ctp_tick, "bid_price_2")
        delattr(ctp_tick, "bid_price_3")
        delattr(ctp_tick, "bid_price_4")
        delattr(ctp_tick, "bid_price_5")
        delattr(ctp_tick, "ask_price_2")
        delattr(ctp_tick, "ask_price_3")
        delattr(ctp_tick, "ask_price_4")
        delattr(ctp_tick, "ask_price_5")

        # Create event
        event = Mock(spec=Event)
        event.data = ctp_tick

        # Register callback to capture transformed tick
        domain_tick = None

        def capture_tick(tick):
            nonlocal domain_tick
            domain_tick = tick

        ctp_adapter.register_tick_callback(capture_tick)

        # Process tick through adapter
        ctp_adapter._on_tick(event)

        # Verify transformation
        assert domain_tick is not None
        assert isinstance(domain_tick, Tick)

    async def test_ctp_specific_error_handling(self, ctp_adapter, mock_vnpy_gateway):
        """Test handling of CTP-specific errors"""
        # Test connection timeout
        ctp_adapter.status.is_connected = False
        ctp_adapter.status.last_error = "Connection timeout"

        with pytest.raises(ConnectionError) as exc_info:
            await ctp_adapter.connect()
        assert "Connection timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_string_parsing(self):
        """Test parsing of CTP front addresses"""
        # Test TCP address parsing
        tcp_string = "tcp://180.168.146.187:10130"
        connection = CtpConnectionString.parse(tcp_string)
        assert connection.protocol == "tcp"
        assert connection.host == "180.168.146.187"
        assert connection.port == 10130

        # Test multiple addresses
        addresses = [
            "tcp://180.168.146.187:10130",
            "tcp://180.168.146.187:10131",
            "tcp://218.202.237.33:10130",
        ]
        connections = [CtpConnectionString.parse(addr) for addr in addresses]
        assert len(connections) == 3
        assert all(c.protocol == "tcp" for c in connections)

    async def test_market_data_subscription(self, ctp_adapter, mock_vnpy_gateway):
        """Test subscribing to market data for specific symbols"""
        # Set connected status
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.md_connected = True

        symbols = ["IF2312", "IC2312", "IH2312"]

        # Subscribe to symbols
        await ctp_adapter.subscribe(symbols)

        # Verify subscription was called for each symbol
        assert mock_vnpy_gateway.subscribe.call_count == len(symbols)
        assert symbols[0] in ctp_adapter._subscribed_symbols

    async def test_unsubscribe_functionality(self, ctp_adapter, mock_vnpy_gateway):
        """Test unsubscribing from market data"""
        # Set connected status
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.md_connected = True

        symbols = ["rb2405", "au2406"]

        # Subscribe first
        await ctp_adapter.subscribe(symbols)

        # Then unsubscribe
        await ctp_adapter.unsubscribe(symbols)

        # Verify symbols were removed from tracking
        for symbol in symbols:
            assert symbol not in ctp_adapter._subscribed_symbols

    async def test_connection_status_tracking(self, ctp_adapter, mock_vnpy_gateway):
        """Test tracking of connection status"""
        # Initially disconnected
        assert not ctp_adapter.is_connected()

        # Simulate successful connection
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.td_connected = True
        await ctp_adapter.connect()
        assert ctp_adapter.is_connected()

        # Disconnect
        await ctp_adapter.disconnect()
        assert not ctp_adapter.is_connected()

    async def test_heartbeat_functionality(self, ctp_adapter, mock_vnpy_gateway):
        """Test heartbeat sending for connection maintenance"""
        # Set connected status
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.td_connected = True

        # Send heartbeat - should not raise
        await ctp_adapter.send_heartbeat()

        # Test heartbeat fails when disconnected
        ctp_adapter.status.is_connected = False
        with pytest.raises(ConnectionError):
            await ctp_adapter.send_heartbeat()

    async def test_adapter_cleanup_on_disconnect(self, ctp_adapter, mock_vnpy_gateway):
        """Test proper cleanup when disconnecting"""
        # Set connected status
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.td_connected = True
        ctp_adapter.status.md_connected = True

        # Subscribe to a symbol
        await ctp_adapter.subscribe(["IF2312"])

        # Disconnect
        await ctp_adapter.disconnect()

        # Verify cleanup
        mock_vnpy_gateway.close.assert_called_once()
        assert not ctp_adapter.is_connected()
        assert len(ctp_adapter._subscribed_symbols) == 0

    async def test_error_code_mapping(self, ctp_adapter):
        """Test handling of CTP error codes"""
        from vnpy.event import Event

        # Test error event handling
        error_event = Mock(spec=Event)
        error_event.data = "Authentication failed: Invalid password"

        # Process error
        ctp_adapter._on_error(error_event)

        # Verify error was captured
        assert ctp_adapter.status.last_error == str(error_event.data)

    async def test_reconnection_capability(self, ctp_adapter, mock_vnpy_gateway):
        """Test adapter's ability to reconnect after disconnection"""

        # Mock the wait methods to return immediately
        async def mock_wait(*args, **kwargs):
            pass

        ctp_adapter._wait_for_connection = mock_wait
        ctp_adapter._wait_for_authentication = mock_wait
        ctp_adapter._wait_for_settlement = mock_wait
        ctp_adapter._wait_for_contracts = mock_wait

        # Set all status flags to simulate successful connection
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.is_authenticated = True
        ctp_adapter.status.settlement_confirmed = True
        ctp_adapter.status.contracts_loaded = True

        # Initial connection
        await ctp_adapter.connect()

        # Simulate disconnection
        await ctp_adapter.disconnect()

        # Set status flags again for reconnection
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.is_authenticated = True
        ctp_adapter.status.settlement_confirmed = True
        ctp_adapter.status.contracts_loaded = True

        # Reconnect
        await ctp_adapter.connect()

        # Verify reconnection attempted
        assert mock_vnpy_gateway.connect.call_count == 2

    async def test_concurrent_subscription_handling(self, ctp_adapter, mock_vnpy_gateway):
        """Test handling of concurrent subscription requests"""
        # Set connected status
        ctp_adapter.status.is_connected = True
        ctp_adapter.status.md_connected = True

        # Multiple concurrent subscriptions
        symbols1 = ["IF2312", "IC2312"]
        symbols2 = ["IH2312", "IM2312"]

        # Subscribe concurrently
        await asyncio.gather(ctp_adapter.subscribe(symbols1), ctp_adapter.subscribe(symbols2))

        # Verify all symbols subscribed
        all_symbols = set(symbols1 + symbols2)
        subscribed = ctp_adapter._subscribed_symbols
        assert all_symbols == subscribed


class TestCtpConfig:
    """Test suite for CTP configuration validation"""

    def test_valid_ctp_config(self):
        """Test creation of valid CTP configuration"""
        config = CtpConfig(
            user_id="test_user",
            password="secure_password",
            broker_id="9999",
            app_id="test_app",
            auth_code="0000000000000000",
            td_address="tcp://180.168.146.187:10130",
            md_address="tcp://180.168.146.187:10131",
        )

        assert config.user_id == "test_user"
        assert config.broker_id == "9999"
        assert "tcp://" in config.td_address
        assert "tcp://" in config.md_address

    def test_invalid_address_format(self):
        """Test validation of invalid CTP addresses"""
        with pytest.raises(ValueError) as exc_info:
            CtpConfig(
                user_id="test",
                password="pass",
                broker_id="9999",
                app_id="app",
                auth_code="0000",
                td_address="invalid_address",  # Missing tcp://
                md_address="tcp://180.168.146.187:10131",
            )
        assert "Invalid TD address format" in str(exc_info.value)

    def test_config_from_environment(self, monkeypatch):
        """Test loading CTP config from environment variables"""
        # Set environment variables
        monkeypatch.setenv("CTP_USER_ID", "env_user")
        monkeypatch.setenv("CTP_PASSWORD", "env_password")
        monkeypatch.setenv("CTP_BROKER_ID", "9999")
        monkeypatch.setenv("CTP_APP_ID", "env_app")
        monkeypatch.setenv("CTP_AUTH_CODE", "0000000000000000")
        monkeypatch.setenv("CTP_TD_ADDRESS", "tcp://180.168.146.187:10130")
        monkeypatch.setenv("CTP_MD_ADDRESS", "tcp://180.168.146.187:10131")

        # Load from environment
        config = CtpConfig.from_env()

        assert config.user_id == "env_user"
        assert config.password == "env_password"
        assert config.broker_id == "9999"
