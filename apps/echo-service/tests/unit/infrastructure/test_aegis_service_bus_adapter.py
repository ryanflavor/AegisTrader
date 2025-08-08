"""Unit tests for AegisServiceBusAdapter following TDD and hexagonal architecture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from aegis_sdk.domain.models import RPCRequest, RPCResponse
from app.infrastructure.aegis_service_bus_adapter import AegisServiceBusAdapter


class TestAegisServiceBusAdapter:
    """Test suite for AegisServiceBusAdapter."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock Aegis SDK service."""
        service = MagicMock()
        service.instance_id = "test-instance-123"
        service.start = AsyncMock()
        service.stop = AsyncMock()
        service.rpc = Mock(return_value=lambda x: x)  # Decorator mock
        service._bus = MagicMock()
        service._bus.call_rpc = AsyncMock()
        return service

    @pytest.fixture
    def adapter(self, mock_service):
        """Create an adapter with mocked service."""
        return AegisServiceBusAdapter(mock_service)

    # Test Initialization
    def test_initialization(self, mock_service):
        """Test adapter initialization with service."""
        adapter = AegisServiceBusAdapter(mock_service)
        assert adapter._service == mock_service
        assert adapter._handlers == {}
        assert adapter._is_connected is False

    # Test Start Method
    @pytest.mark.asyncio
    async def test_start_success(self, adapter, mock_service):
        """Test successful service bus start."""
        # Register some handlers first
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        adapter.register_rpc_handler("method1", handler1)
        adapter.register_rpc_handler("method2", handler2)

        # Start the service
        await adapter.start()

        # Verify service was started
        mock_service.start.assert_called_once()
        assert adapter._is_connected is True

        # Verify handlers were registered
        assert mock_service.rpc.call_count == 2
        mock_service.rpc.assert_any_call("method1")
        mock_service.rpc.assert_any_call("method2")

    @pytest.mark.asyncio
    async def test_start_failure(self, adapter, mock_service):
        """Test service bus start failure."""
        mock_service.start.side_effect = Exception("Connection failed")

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.start()

        assert "Unable to connect to service bus" in str(exc_info.value)
        assert adapter._is_connected is False

    # Test Stop Method
    @pytest.mark.asyncio
    async def test_stop_when_connected(self, adapter, mock_service):
        """Test stopping connected service bus."""
        adapter._is_connected = True

        await adapter.stop()

        mock_service.stop.assert_called_once()
        assert adapter._is_connected is False

    @pytest.mark.asyncio
    async def test_stop_when_not_connected(self, adapter, mock_service):
        """Test stopping when not connected."""
        adapter._is_connected = False

        await adapter.stop()

        mock_service.stop.assert_not_called()
        assert adapter._is_connected is False

    @pytest.mark.asyncio
    async def test_stop_with_error(self, adapter, mock_service):
        """Test graceful handling of stop errors."""
        adapter._is_connected = True
        mock_service.stop.side_effect = Exception("Stop failed")

        # Should not raise exception
        await adapter.stop()

        mock_service.stop.assert_called_once()
        # Connection status should still be updated
        assert adapter._is_connected is False

    # Test RPC Handler Registration
    def test_register_rpc_handler_success(self, adapter):
        """Test successful RPC handler registration."""
        handler = AsyncMock()

        adapter.register_rpc_handler("test_method", handler)

        assert "test_method" in adapter._handlers
        assert adapter._handlers["test_method"] == handler

    def test_register_rpc_handler_duplicate(self, adapter):
        """Test duplicate RPC handler registration raises error."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        adapter.register_rpc_handler("test_method", handler1)

        with pytest.raises(ValueError) as exc_info:
            adapter.register_rpc_handler("test_method", handler2)

        assert "already registered" in str(exc_info.value)

    def test_register_rpc_handler_when_connected(self, adapter, mock_service):
        """Test registering handler when already connected."""
        adapter._is_connected = True
        handler = AsyncMock()

        adapter.register_rpc_handler("test_method", handler)

        # Should register immediately with service
        mock_service.rpc.assert_called_with("test_method")

    # Test RPC Call Method
    @pytest.mark.asyncio
    async def test_call_rpc_success(self, adapter, mock_service):
        """Test successful RPC call."""
        adapter._is_connected = True

        # Mock successful response
        mock_response = MagicMock(spec=RPCResponse)
        mock_response.result = {"echo": "test", "processed": True}
        mock_response.error = None
        mock_service._bus.call_rpc.return_value = mock_response

        result = await adapter.call_rpc(
            target="target-service",
            method="echo",
            params={"message": "test"},
            timeout=5.0,
        )

        assert result == {"echo": "test", "processed": True}

        # Verify RPC request was created correctly
        call_args = mock_service._bus.call_rpc.call_args[0][0]
        assert isinstance(call_args, RPCRequest)
        assert call_args.target == "target-service"
        assert call_args.method == "echo"
        assert call_args.params == {"message": "test"}
        assert call_args.timeout == 5.0

    @pytest.mark.asyncio
    async def test_call_rpc_with_error_response(self, adapter, mock_service):
        """Test RPC call with error in response."""
        adapter._is_connected = True

        # Mock error response
        mock_response = MagicMock(spec=RPCResponse)
        mock_response.result = None
        mock_response.error = "Method not found"
        mock_service._bus.call_rpc.return_value = mock_response

        result = await adapter.call_rpc(
            target="target-service",
            method="unknown",
            params={},
        )

        assert result == {"error": "Method not found"}

    @pytest.mark.asyncio
    async def test_call_rpc_when_not_connected(self, adapter):
        """Test RPC call when not connected."""
        adapter._is_connected = False

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.call_rpc(
                target="target-service",
                method="echo",
                params={},
            )

        assert "Service bus is not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_rpc_timeout(self, adapter, mock_service):
        """Test RPC call timeout."""
        adapter._is_connected = True
        mock_service._bus.call_rpc.side_effect = TimeoutError("Request timed out")

        with pytest.raises(TimeoutError):
            await adapter.call_rpc(
                target="target-service",
                method="echo",
                params={},
                timeout=1.0,
            )

    @pytest.mark.asyncio
    async def test_call_rpc_connection_error(self, adapter, mock_service):
        """Test RPC call with connection error."""
        adapter._is_connected = True
        mock_service._bus.call_rpc.side_effect = Exception("Network error")

        with pytest.raises(ConnectionError) as exc_info:
            await adapter.call_rpc(
                target="target-service",
                method="echo",
                params={},
            )

        assert "Failed to call RPC" in str(exc_info.value)

    # Test Helper Methods
    def test_get_instance_id(self, adapter, mock_service):
        """Test getting instance ID from service."""
        instance_id = adapter.get_instance_id()
        assert instance_id == "test-instance-123"

    def test_is_connected_true(self, adapter):
        """Test is_connected when connected."""
        adapter._is_connected = True
        assert adapter.is_connected() is True

    def test_is_connected_false(self, adapter):
        """Test is_connected when not connected."""
        adapter._is_connected = False
        assert adapter.is_connected() is False
