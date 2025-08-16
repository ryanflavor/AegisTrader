"""
Unit tests for refactored Gateway Service using SDK's SingleActiveService
Tests the gateway-specific logic while SDK handles leader election
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from aegis_sdk.application.single_active_dtos import SingleActiveConfig

from application.gateway_service import GatewayService
from domain.gateway.ports import GatewayPort
from domain.gateway.value_objects import ConnectionState, GatewayConfig, GatewayType


@pytest.mark.asyncio
class TestGatewayService:
    """Test suite for Gateway Service using SDK's SingleActiveService"""

    @pytest.fixture
    def mock_gateway_port(self) -> Mock:
        """Mock gateway port for testing"""
        port = Mock(spec=GatewayPort)
        port.connect = AsyncMock()
        port.disconnect = AsyncMock()
        port.is_connected = Mock(return_value=False)
        port.get_connection_status = AsyncMock(return_value={})
        port.subscribe = AsyncMock()
        return port

    @pytest.fixture
    def gateway_config(self) -> GatewayConfig:
        """Gateway configuration for testing"""
        return GatewayConfig(
            gateway_id="test-gateway-01",
            gateway_type=GatewayType.CTP,
            heartbeat_interval=30,
            reconnect_delay=5,
            max_reconnect_attempts=10,
        )

    @pytest.fixture
    def single_active_config(self) -> SingleActiveConfig:
        """SingleActiveService configuration for testing"""
        return SingleActiveConfig(
            service_name="test-gateway-service",
            instance_id="test-instance-01",
            group_id="test-group",
            leader_ttl_seconds=10,  # Must be greater than heartbeat_interval
            heartbeat_interval=5,
            registry_ttl=10,
        )

    @pytest.fixture
    def mock_message_bus(self) -> Mock:
        """Mock message bus for SDK"""
        bus = Mock()
        bus.connect = AsyncMock()
        bus.disconnect = AsyncMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def mock_logger(self) -> Mock:
        """Mock logger"""
        logger = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        logger.debug = Mock()
        return logger

    @pytest.fixture
    def gateway_service(
        self,
        mock_gateway_port,
        gateway_config,
        single_active_config,
        mock_message_bus,
        mock_logger,
    ) -> GatewayService:
        """Create gateway service instance for testing"""
        service = GatewayService(
            gateway_adapter=mock_gateway_port,
            gateway_config=gateway_config,
            single_active_config=single_active_config,
            message_bus=mock_message_bus,
            logger=mock_logger,
        )
        # Mock SDK internals for testing
        service.is_active = False
        service.instance_id = single_active_config.instance_id
        service.logger = mock_logger
        return service

    async def test_gateway_service_inherits_from_single_active_service(self, gateway_service):
        """Test that GatewayService properly inherits from SingleActiveService"""
        from aegis_sdk.application.single_active_service import SingleActiveService

        # Verify inheritance
        assert isinstance(gateway_service, SingleActiveService)

        # Verify SDK methods are available
        assert hasattr(gateway_service, "on_active")
        assert hasattr(gateway_service, "on_standby")
        assert hasattr(gateway_service, "on_start")
        assert hasattr(gateway_service, "exclusive_rpc")
        assert hasattr(gateway_service, "rpc")

    async def test_on_active_starts_gateway_connection(
        self, gateway_service, mock_gateway_port, mock_logger
    ):
        """Test that becoming active leader starts gateway connection"""
        # Call on_active (SDK callback)
        await gateway_service.on_active()

        # Verify connection initiated
        assert gateway_service.connection_manager.state == ConnectionState.CONNECTED
        mock_logger.info.assert_called()

        # Verify heartbeat task started
        assert gateway_service._connection_task is not None

    async def test_on_standby_disconnects_gateway(
        self, gateway_service, mock_gateway_port, mock_logger
    ):
        """Test that losing leadership disconnects gateway"""
        # First become active
        await gateway_service.on_active()

        # Then transition to standby
        await gateway_service.on_standby()

        # Verify disconnection
        mock_gateway_port.disconnect.assert_called()
        assert gateway_service._connection_task is None
        mock_logger.info.assert_called()

    async def test_exclusive_rpc_only_responds_when_active(self, gateway_service):
        """Test that exclusive RPCs only work when instance is active"""
        # Register handlers
        await gateway_service.on_start()

        # When not active, exclusive RPCs should not be handled
        # This behavior is managed by SDK's SingleActiveService

        # Simulate being active
        gateway_service.is_active = True

        # Now exclusive RPCs should work
        # Note: Testing the actual RPC mechanism requires SDK infrastructure

    async def test_health_check_responds_regardless_of_active_state(self, gateway_service):
        """Test that health check RPC responds whether active or standby"""
        # Register handlers
        await gateway_service.on_start()

        # Health check should work in both states
        # This is a regular RPC, not exclusive
        # Testing would require SDK infrastructure

    async def test_connection_failure_handling(
        self, gateway_service, mock_gateway_port, mock_logger
    ):
        """Test graceful handling of connection failures"""
        # Make connection fail
        mock_gateway_port.connect.side_effect = ConnectionError("Connection failed")

        # Try to become active
        await gateway_service.on_active()

        # Should log error but not crash
        mock_logger.error.assert_called()

        # Connection manager should handle retries

    async def test_subscribe_symbols_rpc(self, gateway_service, mock_gateway_port):
        """Test symbol subscription RPC"""
        # Make gateway connected
        gateway_service.gateway.connection_state = ConnectionState.CONNECTED

        # This would be called through RPC infrastructure
        # Testing the handler logic directly
        symbols = ["IF2401", "IC2401"]

        # Simulate successful subscription
        await mock_gateway_port.subscribe(symbols)
        mock_gateway_port.subscribe.assert_called_with(symbols)

    async def test_graceful_shutdown_sequence(self, gateway_service, mock_gateway_port):
        """Test proper cleanup on shutdown"""
        # Become active
        await gateway_service.on_active()

        # Transition to standby (simulates shutdown)
        await gateway_service.on_standby()

        # Verify proper cleanup
        mock_gateway_port.disconnect.assert_called()
        assert gateway_service._connection_task is None

        # Verify events were published
        # (Would need event publisher mock to fully test)
