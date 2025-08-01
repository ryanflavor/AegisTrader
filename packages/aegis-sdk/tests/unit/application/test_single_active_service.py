"""Unit tests for SingleActiveService implementation."""

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk.application.single_active_service import (
    SingleActiveService,
    exclusive_rpc,
)
from aegis_sdk.domain.models import Event


class TestSingleActiveService:
    """Tests for SingleActiveService class."""

    def test_init_creates_components(self):
        """Test that initialization creates necessary components."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        assert service.is_active is False
        assert service.last_active_heartbeat == 0
        assert service._election_task is None

    @pytest.mark.asyncio
    async def test_start_creates_election_task(self):
        """Test that start method creates election task."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Mock parent start and election
        service._run_election = AsyncMock()

        await service.start()

        # Verify election task was created
        assert service._election_task is not None
        mock_bus.register_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cancels_election_task(self):
        """Test that stop method cancels election task."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        mock_bus.unregister_service = AsyncMock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Create a mock task
        mock_task = Mock()
        mock_task.cancel = Mock()
        service._election_task = mock_task

        await service.stop()

        # Verify task was cancelled
        mock_task.cancel.assert_called_once()
        mock_bus.unregister_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_election_becomes_active(self):
        """Test election process when no other instance is active."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Set initial state
        service.last_active_heartbeat = time.time() - 10  # Old heartbeat
        service.is_active = False
        service.publish_event = AsyncMock()

        # Run one iteration of election
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = (
                asyncio.CancelledError()
            )  # Stop after first iteration
            with contextlib.suppress(asyncio.CancelledError):
                await service._run_election()

        # Should become active
        assert service.is_active is True

    @pytest.mark.asyncio
    async def test_run_election_sends_heartbeat(self):
        """Test that active instance sends heartbeats."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Set as active
        service.is_active = True
        service.publish_event = AsyncMock()

        # Run one iteration
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError()
            with contextlib.suppress(asyncio.CancelledError):
                await service._run_election()

        # Should have published heartbeat
        service.publish_event.assert_called_once_with(
            "service.test-service.election",
            "heartbeat",
            {"instance_id": service.instance_id},
        )

    @pytest.mark.asyncio
    async def test_handle_election_event(self):
        """Test handling election events from other instances."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Capture the handler registered by the subscribe decorator
        election_handler = None

        # Mock the subscribe decorator to capture the handler
        def mock_subscribe(pattern, durable=True):
            def decorator(handler):
                nonlocal election_handler
                if "election" in pattern:
                    election_handler = handler
                # Add the handler to event_handlers as the real decorator does
                if pattern not in service._event_handlers:
                    service._event_handlers[pattern] = []
                service._event_handlers[pattern].append(handler)
                return handler

            return decorator

        service.subscribe = mock_subscribe

        # Mock register_rpc_handler and subscribe_event to prevent errors
        mock_bus.register_rpc_handler = AsyncMock()
        mock_bus.subscribe_event = AsyncMock()
        mock_bus.register_command_handler = AsyncMock()

        # Don't actually run election
        service._run_election = AsyncMock()

        # Start service to register handlers
        await service.start()

        # Verify election handler was registered
        assert election_handler is not None

        # Simulate receiving election event from another instance
        service.is_active = True
        event = Event(
            domain="service",
            event_type="test-service.election",
            payload={"instance_id": "other-instance"},
        )

        await election_handler(event)

        # Should become inactive
        assert service.is_active is False
        assert service.last_active_heartbeat > 0

    def test_exclusive_rpc_decorator_on_inactive(self):
        """Test exclusive RPC decorator when instance is not active."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Define a method with exclusive decorator
        @service.exclusive_rpc("test_method")
        async def test_handler(params):
            return {"result": "success"}

        # Service is not active
        service.is_active = False

        # Try to call the method
        result = asyncio.run(service._rpc_handlers["test_method"]({}))

        # Should return NOT_ACTIVE error
        assert result["success"] is False
        assert result["error"] == "NOT_ACTIVE"

    def test_exclusive_rpc_decorator_on_active(self):
        """Test exclusive RPC decorator when instance is active."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Define a method with exclusive decorator
        @service.exclusive_rpc("test_method")
        async def test_handler(params):
            return {"result": "success"}

        # Service is active
        service.is_active = True

        # Call the method
        result = asyncio.run(service._rpc_handlers["test_method"]({"key": "value"}))

        # Should execute normally
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_election_error_handling(self):
        """Test error handling in election process."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        # Make publish_event raise an error
        service.publish_event = AsyncMock(side_effect=Exception("Network error"))
        service.is_active = True

        # Run one iteration - should handle error gracefully
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [
                None,
                asyncio.CancelledError(),
            ]  # Sleep once then cancel
            with contextlib.suppress(asyncio.CancelledError):
                await service._run_election()

        # Should have tried to publish and handled the error

    def test_module_level_exclusive_rpc_decorator(self):
        """Test the module-level exclusive_rpc decorator."""

        class TestService(SingleActiveService):
            @exclusive_rpc
            async def test_method(self, params):
                return {"result": "success"}

            @exclusive_rpc("custom_name")
            async def another_method(self, params):
                return {"result": "another"}

        mock_bus = Mock()
        service = TestService(service_name="test-service", message_bus=mock_bus)

        # Test when not active
        service.is_active = False
        result = asyncio.run(service.test_method({}))
        assert result["success"] is False
        assert result["error"] == "NOT_ACTIVE"

        # Test when active
        service.is_active = True
        result = asyncio.run(service.test_method({}))
        assert result == {"result": "success"}

        # Test method with custom name
        result = asyncio.run(service.another_method({}))
        assert result == {"result": "another"}

    def test_module_level_exclusive_rpc_with_regular_service(self):
        """Test that exclusive_rpc decorator works with regular Service class."""
        from aegis_sdk.application.service import Service

        class RegularService(Service):
            @exclusive_rpc
            async def test_method(self, params):
                return {"result": "success"}

        mock_bus = Mock()
        service = RegularService(service_name="test-service", message_bus=mock_bus)

        # Should work normally (no is_active check)
        result = asyncio.run(service.test_method({}))
        assert result == {"result": "success"}
