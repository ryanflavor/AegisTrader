"""Comprehensive unit tests for Service Bus adapter.

Testing all RPC functionality, event handling, and error scenarios
following TDD principles.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from app.infrastructure.service_bus_adapter import (
    RPCRequest,
    RPCResponse,
    ServiceBusAdapter,
)


@pytest.fixture
def mock_nats_adapter():
    """Create mock NATS adapter."""
    adapter = AsyncMock()
    adapter.is_connected = True
    adapter.subscribe = AsyncMock(return_value="sub_123")
    adapter.unsubscribe = AsyncMock()
    adapter.request = AsyncMock()
    adapter.publish = AsyncMock()
    return adapter


@pytest.fixture
def service_bus(mock_nats_adapter):
    """Create service bus adapter instance."""
    return ServiceBusAdapter(mock_nats_adapter, "test-service")


class TestRPCModels:
    """Test RPC request and response models."""

    def test_rpc_request_creation(self):
        """Test creating RPC request."""
        request = RPCRequest(
            method="echo",
            params={"message": "test"},
            id="req_123",
        )
        assert request.method == "echo"
        assert request.params == {"message": "test"}
        assert request.id == "req_123"

    def test_rpc_request_optional_fields(self):
        """Test RPC request with optional fields."""
        request = RPCRequest(method="ping")
        assert request.method == "ping"
        assert request.params is None
        assert request.id is None

    def test_rpc_response_success(self):
        """Test creating successful RPC response."""
        response = RPCResponse(
            result={"echo": "test"},
            id="req_123",
        )
        assert response.result == {"echo": "test"}
        assert response.error is None
        assert response.id == "req_123"

    def test_rpc_response_error(self):
        """Test creating error RPC response."""
        response = RPCResponse(
            error={"code": -32601, "message": "Method not found"},
            id="req_123",
        )
        assert response.result is None
        assert response.error["code"] == -32601
        assert response.id == "req_123"


class TestServiceBusAdapter:
    """Test service bus adapter functionality."""

    @pytest.mark.asyncio
    async def test_start_success(self, service_bus, mock_nats_adapter):
        """Test starting the service bus."""
        await service_bus.start()

        assert service_bus._is_started

        # Verify subscriptions were created
        calls = mock_nats_adapter.subscribe.call_args_list
        assert len(calls) == 2

        # Check RPC subscription with queue group
        rpc_call = calls[0]
        assert rpc_call[0][0] == "rpc.test-service"
        assert rpc_call[1]["queue"] == "test-service"

        # Check broadcast subscription without queue group
        broadcast_call = calls[1]
        assert broadcast_call[0][0] == "broadcast.test-service"
        assert "queue" not in broadcast_call[1]

    @pytest.mark.asyncio
    async def test_start_already_started(self, service_bus, mock_nats_adapter):
        """Test starting when already started."""
        service_bus._is_started = True

        await service_bus.start()

        # Should not subscribe again
        mock_nats_adapter.subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_error(self, service_bus, mock_nats_adapter):
        """Test error during start."""
        mock_nats_adapter.subscribe.side_effect = Exception("Subscribe failed")

        with pytest.raises(Exception) as exc_info:
            await service_bus.start()

        assert "Subscribe failed" in str(exc_info.value)
        assert not service_bus._is_started

    @pytest.mark.asyncio
    async def test_stop_success(self, service_bus, mock_nats_adapter):
        """Test stopping the service bus."""
        service_bus._is_started = True
        service_bus._subscriptions = ["sub1", "sub2", "sub3"]

        await service_bus.stop()

        assert not service_bus._is_started
        assert len(service_bus._subscriptions) == 0

        # Verify all subscriptions were unsubscribed
        assert mock_nats_adapter.unsubscribe.call_count == 3

    @pytest.mark.asyncio
    async def test_stop_not_started(self, service_bus, mock_nats_adapter):
        """Test stopping when not started."""
        service_bus._is_started = False

        await service_bus.stop()

        mock_nats_adapter.unsubscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_error_handling(self, service_bus, mock_nats_adapter):
        """Test error handling during stop."""
        service_bus._is_started = True
        service_bus._subscriptions = ["sub1"]
        mock_nats_adapter.unsubscribe.side_effect = Exception("Unsubscribe failed")

        # Should handle error gracefully
        await service_bus.stop()

        assert not service_bus._is_started

    def test_register_handler(self, service_bus):
        """Test registering an RPC handler."""

        async def test_handler(params):
            return {"result": "ok"}

        service_bus.register_handler("test_method", test_handler)

        assert "test_method" in service_bus._handlers
        assert service_bus._handlers["test_method"] == test_handler

    def test_register_rpc_handler_alias(self, service_bus):
        """Test register_rpc_handler as alias."""

        async def test_handler(params):
            return {"result": "ok"}

        service_bus.register_rpc_handler("test_method", test_handler)

        assert "test_method" in service_bus._handlers

    @pytest.mark.asyncio
    async def test_call_remote_success(self, service_bus, mock_nats_adapter):
        """Test successful remote RPC call."""
        mock_nats_adapter.request.return_value = {
            "result": {"echo": "test"},
            "id": "req_123",
        }

        result = await service_bus.call_remote(
            "echo-service",
            "echo",
            {"message": "test"},
            timeout=5.0,
        )

        assert result == {"echo": "test"}

        # Verify request was sent
        mock_nats_adapter.request.assert_called_once()
        call_args = mock_nats_adapter.request.call_args
        assert call_args[0][0] == "rpc.echo-service"
        assert call_args[0][1]["method"] == "echo"
        assert call_args[0][1]["params"] == {"message": "test"}

    @pytest.mark.asyncio
    async def test_call_remote_with_error_response(self, service_bus, mock_nats_adapter):
        """Test remote call with error response."""
        mock_nats_adapter.request.return_value = {
            "error": {"code": -32601, "message": "Method not found"},
            "id": "req_123",
        }

        with pytest.raises(RuntimeError) as exc_info:
            await service_bus.call_remote("echo-service", "unknown", {})

        assert "RPC error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_remote_timeout(self, service_bus, mock_nats_adapter):
        """Test remote call timeout."""
        mock_nats_adapter.request.side_effect = TimeoutError("Request timeout")

        with pytest.raises(TimeoutError) as exc_info:
            await service_bus.call_remote("echo-service", "echo", {}, timeout=1.0)

        assert "RPC call to echo-service.echo timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_remote_general_error(self, service_bus, mock_nats_adapter):
        """Test remote call with general error."""
        mock_nats_adapter.request.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError) as exc_info:
            await service_bus.call_remote("echo-service", "echo", {})

        assert "RPC call failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_remote_non_dict_response(self, service_bus, mock_nats_adapter):
        """Test remote call with non-dict response."""
        mock_nats_adapter.request.return_value = "simple string response"

        result = await service_bus.call_remote("echo-service", "ping", {})

        assert result == "simple string response"

    @pytest.mark.asyncio
    async def test_call_rpc_alias(self, service_bus, mock_nats_adapter):
        """Test call_rpc as alias for call_remote."""
        mock_nats_adapter.request.return_value = {
            "result": {"pong": True},
            "id": "req_123",
        }

        result = await service_bus.call_rpc(
            "echo-service",
            "ping",
            {},
            timeout=3.0,
        )

        assert result == {"result": {"pong": True}}

    @pytest.mark.asyncio
    async def test_call_rpc_wraps_non_dict(self, service_bus, mock_nats_adapter):
        """Test call_rpc wraps non-dict results."""
        mock_nats_adapter.request.return_value = "simple response"

        result = await service_bus.call_rpc("echo-service", "ping", {})

        assert result == {"result": "simple response"}

    @pytest.mark.asyncio
    async def test_publish_event(self, service_bus, mock_nats_adapter):
        """Test publishing an event."""
        event_data = {"user": "test", "action": "login"}

        await service_bus.publish_event("user.login", event_data)

        mock_nats_adapter.publish.assert_called_once_with(
            "events.test-service.user.login",
            event_data,
        )

    @pytest.mark.asyncio
    async def test_subscribe_to_events(self, service_bus, mock_nats_adapter):
        """Test subscribing to events from another service."""

        async def event_handler(data):
            print(f"Event: {data}")

        sub_id = await service_bus.subscribe_to_events(
            "user-service",
            "login",
            event_handler,
        )

        assert sub_id == "sub_123"
        assert sub_id in service_bus._subscriptions

        mock_nats_adapter.subscribe.assert_called_once_with(
            "events.user-service.login",
            event_handler,
        )

    @pytest.mark.asyncio
    async def test_handle_rpc_request_success(self, service_bus):
        """Test handling incoming RPC request."""

        # Register handler
        async def echo_handler(params):
            return {"echo": params["message"]}

        service_bus._handlers["echo"] = echo_handler

        # Create request
        request_data = {
            "method": "echo",
            "params": {"message": "test"},
            "id": "req_123",
        }

        response = await service_bus._handle_rpc_request(request_data)

        assert response["result"] == {"echo": "test"}
        assert response["id"] == "req_123"
        assert response.get("error") is None

    @pytest.mark.asyncio
    async def test_handle_rpc_request_method_not_found(self, service_bus):
        """Test handling request for unknown method."""
        request_data = {
            "method": "unknown_method",
            "params": {},
            "id": "req_123",
        }

        response = await service_bus._handle_rpc_request(request_data)

        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]
        assert response["id"] == "req_123"

    @pytest.mark.asyncio
    async def test_handle_rpc_request_handler_error(self, service_bus):
        """Test handling request when handler raises error."""

        async def failing_handler(params):
            raise ValueError("Handler failed")

        service_bus._handlers["fail"] = failing_handler

        request_data = {
            "method": "fail",
            "params": {},
            "id": "req_123",
        }

        response = await service_bus._handle_rpc_request(request_data)

        assert response["error"]["code"] == -32603
        assert "Handler failed" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handle_rpc_request_invalid_data(self, service_bus):
        """Test handling invalid request data."""
        # Non-dict data
        response = await service_bus._handle_rpc_request("invalid")

        # Should create a default request
        assert response["error"]["code"] == -32601
        assert "Method not found: unknown" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handle_rpc_request_parse_error(self, service_bus):
        """Test handling parse error in request."""
        # Create request that will cause parse error
        with pytest.raises(ValueError):
            # This would normally not happen but tests error path
            request_data = {"method": 123}  # Invalid type for method
            RPCRequest(**request_data)

    @pytest.mark.asyncio
    async def test_handle_rpc_request_no_params(self, service_bus):
        """Test handling request without params."""

        async def handler(params):
            return {"received": params}

        service_bus._handlers["test"] = handler

        request_data = {
            "method": "test",
            "id": "req_123",
        }

        response = await service_bus._handle_rpc_request(request_data)

        assert response["result"] == {"received": {}}

    @pytest.mark.asyncio
    async def test_handle_broadcast_message(self, service_bus):
        """Test handling broadcast message."""
        # Should just log, not respond
        await service_bus._handle_broadcast_message({"type": "broadcast", "data": "test"})

        # No assertions needed - just ensure no errors

    @pytest.mark.asyncio
    async def test_health_check(self, service_bus, mock_nats_adapter):
        """Test health check functionality."""
        service_bus._is_started = True
        service_bus._handlers = {"echo": Mock(), "ping": Mock()}
        service_bus._subscriptions = ["sub1", "sub2"]

        health = await service_bus.health_check()

        assert health["status"] == "healthy"
        assert health["service_name"] == "test-service"
        assert health["handlers_registered"] == 2
        assert health["active_subscriptions"] == 2
        assert health["nats_connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_stopped(self, service_bus, mock_nats_adapter):
        """Test health check when stopped."""
        service_bus._is_started = False
        mock_nats_adapter.is_connected = False

        health = await service_bus.health_check()

        assert health["status"] == "stopped"
        assert health["nats_connected"] is False

    def test_get_instance_id(self, service_bus):
        """Test getting instance ID."""
        instance_id = service_bus.get_instance_id()

        assert instance_id.startswith("test-service-")
        assert str(id(service_bus)) in instance_id

    def test_is_connected(self, service_bus, mock_nats_adapter):
        """Test checking connection status."""
        # Not started
        service_bus._is_started = False
        assert not service_bus.is_connected()

        # Started but NATS not connected
        service_bus._is_started = True
        mock_nats_adapter.is_connected = False
        assert not service_bus.is_connected()

        # Both conditions met
        mock_nats_adapter.is_connected = True
        assert service_bus.is_connected()

    @pytest.mark.asyncio
    async def test_full_rpc_flow(self, service_bus, mock_nats_adapter):
        """Test complete RPC flow from request to response."""

        # Register handler
        async def multiply_handler(params):
            return {"result": params["a"] * params["b"]}

        service_bus.register_handler("multiply", multiply_handler)

        # Simulate incoming request
        request = RPCRequest(
            method="multiply",
            params={"a": 5, "b": 3},
            id="calc_123",
        )

        response = await service_bus._handle_rpc_request(request.model_dump())

        assert response["result"] == {"result": 15}
        assert response["id"] == "calc_123"
        assert "error" not in response or response["error"] is None

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service_bus):
        """Test handling multiple concurrent requests."""
        call_count = 0

        async def slow_handler(params):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate work
            return {"count": call_count, "data": params}

        service_bus._handlers["slow"] = slow_handler

        # Create multiple concurrent requests
        requests = [
            service_bus._handle_rpc_request(
                {
                    "method": "slow",
                    "params": {"id": i},
                    "id": f"req_{i}",
                }
            )
            for i in range(5)
        ]

        responses = await asyncio.gather(*requests)

        assert len(responses) == 5
        assert call_count == 5

        # Each should have unique response
        for i, response in enumerate(responses):
            assert response["id"] == f"req_{i}"
            assert response["result"]["data"] == {"id": i}
