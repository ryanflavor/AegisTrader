"""Integration tests for service patterns (RPC, Events, Commands)."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from aegis_sdk.application.service import Service
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.models import Command
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


@pytest_asyncio.fixture
async def mock_message_bus():
    """Create a mock message bus for testing."""
    with patch("aegis_sdk.infrastructure.nats_adapter.nats") as mock_nats:
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_nats.connect = AsyncMock(return_value=mock_client)

        mock_js = AsyncMock()
        mock_client.jetstream.return_value = mock_js
        mock_js.stream_info.side_effect = Exception("Stream not found")
        mock_js.add_stream = AsyncMock()

        adapter = NATSAdapter()
        await adapter.connect(["nats://localhost:4222"])

        yield adapter

        await adapter.disconnect()


class TestRPCPatterns:
    """Integration tests for RPC patterns."""

    @pytest.mark.asyncio
    async def test_service_rpc_registration(self, mock_message_bus):
        """Test service RPC method registration and handling."""

        class TestService(Service):
            def __init__(self, message_bus):
                super().__init__(
                    service_name="test_service", version="1.0.0", message_bus=message_bus
                )
                self.calculation_count = 0

            async def on_start(self):
                await super().on_start()
                # Register RPC methods
                await self.register_rpc_method("calculate", self.handle_calculate)
                await self.register_rpc_method("status", self.handle_status)

            async def handle_calculate(self, params):
                self.calculation_count += 1
                a = params.get("a", 0)
                b = params.get("b", 0)
                operation = params.get("operation", "add")

                if operation == "add":
                    result = a + b
                elif operation == "multiply":
                    result = a * b
                else:
                    raise ValueError(f"Unknown operation: {operation}")

                return {"result": result, "count": self.calculation_count}

            async def handle_status(self, params):
                return {
                    "service": self.service_name,
                    "version": self.version,
                    "calculations": self.calculation_count,
                    "uptime": (datetime.now() - self._start_time).total_seconds(),
                }

        # Create and start service
        service = TestService(mock_message_bus)
        await service.start()

        # Verify RPC methods were registered
        assert mock_message_bus.register_rpc_handler.call_count == 2

        # Test calculation RPC
        calc_handler = None
        for call in mock_message_bus.register_rpc_handler.call_args_list:
            if call[0][1] == "calculate":
                calc_handler = call[0][2]
                break

        assert calc_handler is not None
        result = await calc_handler({"a": 5, "b": 3, "operation": "add"})
        assert result["result"] == 8
        assert result["count"] == 1

        # Test status RPC
        status_handler = None
        for call in mock_message_bus.register_rpc_handler.call_args_list:
            if call[0][1] == "status":
                status_handler = call[0][2]
                break

        assert status_handler is not None
        status = await status_handler({})
        assert status["service"] == "test_service"
        assert status["calculations"] == 1

        await service.stop()

    @pytest.mark.asyncio
    async def test_rpc_error_handling(self, mock_message_bus):
        """Test RPC error handling and propagation."""

        class ErrorService(Service):
            async def on_start(self):
                await super().on_start()
                await self.register_rpc_method("divide", self.handle_divide)

            async def handle_divide(self, params):
                a = params.get("a", 0)
                b = params.get("b", 1)
                if b == 0:
                    raise ValueError("Division by zero")
                return {"result": a / b}

        service = ErrorService("error_service", "1.0.0", mock_message_bus)
        await service.start()

        # Get the registered handler
        handler = mock_message_bus.register_rpc_handler.call_args[0][2]

        # Test normal operation
        result = await handler({"a": 10, "b": 2})
        assert result["result"] == 5.0

        # Test error case
        with pytest.raises(ValueError, match="Division by zero"):
            await handler({"a": 10, "b": 0})

        await service.stop()


class TestEventPatterns:
    """Integration tests for event patterns."""

    @pytest.mark.asyncio
    async def test_event_emission_and_subscription(self, mock_message_bus):
        """Test event emission and subscription patterns."""

        received_events = []

        class EventEmitter(Service):
            async def on_start(self):
                await super().on_start()
                await self.register_command_handler("create_user", self.handle_create_user)

            async def handle_create_user(self, command, progress):
                user_id = command.payload.get("user_id")
                username = command.payload.get("username")

                # Emit user created event
                await self.emit_event(
                    "user",
                    "created",
                    {
                        "user_id": user_id,
                        "username": username,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                return {"success": True, "user_id": user_id}

        class EventSubscriber(Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.received_events = []

            async def on_start(self):
                await super().on_start()
                await self.subscribe_event("user", "created", self.handle_user_created)

            async def handle_user_created(self, event):
                self.received_events.append(event)
                received_events.append(event)

        # Create services
        emitter = EventEmitter("emitter", "1.0.0", mock_message_bus)
        subscriber = EventSubscriber("subscriber", "1.0.0", mock_message_bus)

        await emitter.start()
        await subscriber.start()

        # Verify event subscription
        assert mock_message_bus.subscribe_event.called
        event_handler = mock_message_bus.subscribe_event.call_args[0][2]

        # Simulate command that triggers event
        cmd_handler = mock_message_bus.register_command_handler.call_args[0][2]
        command = Command(
            target="emitter",
            command="create_user",
            payload={"user_id": "123", "username": "testuser"},
        )

        await cmd_handler(command, AsyncMock())

        # Verify event was published
        assert mock_message_bus.publish_event.called
        published_event = mock_message_bus.publish_event.call_args[0][0]
        assert published_event.domain == "user"
        assert published_event.event_type == "created"

        # Simulate event delivery
        await event_handler(published_event)

        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].payload["user_id"] == "123"

        await emitter.stop()
        await subscriber.stop()

    @pytest.mark.asyncio
    async def test_wildcard_event_subscription(self, mock_message_bus):
        """Test wildcard event subscription patterns."""

        class WildcardSubscriber(Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.all_user_events = []
                self.all_events = []

            async def on_start(self):
                await super().on_start()
                # Subscribe to all user events
                await self.message_bus.subscribe_event("user.*", self.handle_user_event)
                # Subscribe to all events
                await self.message_bus.subscribe_event("*.*", self.handle_any_event)

            async def handle_user_event(self, event):
                self.all_user_events.append(event)

            async def handle_any_event(self, event):
                self.all_events.append(event)

        subscriber = WildcardSubscriber("wildcard_sub", "1.0.0", mock_message_bus)
        await subscriber.start()

        # Verify wildcard subscriptions
        assert mock_message_bus.subscribe_event.call_count == 2

        wildcard_calls = [
            call for call in mock_message_bus.subscribe_event.call_args_list if "*" in call[0][0]
        ]
        assert len(wildcard_calls) == 2

        await subscriber.stop()


class TestCommandPatterns:
    """Integration tests for command patterns."""

    @pytest.mark.asyncio
    async def test_command_with_progress_reporting(self, mock_message_bus):
        """Test command execution with progress reporting."""

        progress_updates = []

        class WorkerService(Service):
            async def on_start(self):
                await super().on_start()
                await self.register_command_handler("process_batch", self.handle_process_batch)

            async def handle_process_batch(self, command, progress_reporter):
                batch_size = command.payload.get("size", 100)

                # Simulate batch processing with progress
                for i in range(0, batch_size, 10):
                    await progress_reporter(
                        percent=(i / batch_size) * 100, status=f"Processing item {i}/{batch_size}"
                    )
                    await asyncio.sleep(0.01)  # Simulate work

                await progress_reporter(100, "Batch processing complete")

                return {
                    "processed": batch_size,
                    "status": "completed",
                    "duration": 0.1 * (batch_size / 10),
                }

        service = WorkerService("worker", "1.0.0", mock_message_bus)
        await service.start()

        # Get command handler
        cmd_handler = mock_message_bus.register_command_handler.call_args[0][2]

        # Create progress reporter that captures updates
        async def capture_progress(percent, status):
            progress_updates.append({"percent": percent, "status": status})

        # Execute command
        command = Command(target="worker", command="process_batch", payload={"size": 50})

        result = await cmd_handler(command, capture_progress)

        # Verify progress updates
        assert len(progress_updates) > 0
        assert progress_updates[0]["percent"] == 0
        assert progress_updates[-1]["percent"] == 100
        assert "complete" in progress_updates[-1]["status"]

        # Verify result
        assert result["processed"] == 50
        assert result["status"] == "completed"

        await service.stop()

    @pytest.mark.asyncio
    async def test_command_retry_on_failure(self, mock_message_bus):
        """Test command retry logic on failure."""

        attempt_count = 0

        class RetryService(Service):
            async def on_start(self):
                await super().on_start()
                await self.register_command_handler("flaky_operation", self.handle_flaky)

            async def handle_flaky(self, command, progress):
                nonlocal attempt_count
                attempt_count += 1

                max_attempts = command.payload.get("max_attempts", 3)
                if attempt_count < max_attempts:
                    raise Exception(f"Attempt {attempt_count} failed")

                return {"success": True, "attempts": attempt_count}

        service = RetryService("retry_service", "1.0.0", mock_message_bus)
        await service.start()

        # Get command handler
        cmd_handler = mock_message_bus.register_command_handler.call_args[0][2]

        # Test command that fails initially
        command = Command(
            target="retry_service",
            command="flaky_operation",
            payload={"max_attempts": 3},
            max_retries=3,
        )

        # First two attempts should fail
        with pytest.raises(Exception, match="Attempt 1 failed"):
            await cmd_handler(command, AsyncMock())

        with pytest.raises(Exception, match="Attempt 2 failed"):
            await cmd_handler(command, AsyncMock())

        # Third attempt should succeed
        result = await cmd_handler(command, AsyncMock())
        assert result["success"] is True
        assert result["attempts"] == 3

        await service.stop()


class TestSingleActiveServicePattern:
    """Integration tests for single active service pattern."""

    @pytest.mark.asyncio
    async def test_single_active_coordination(self, mock_message_bus):
        """Test single active service coordination."""

        # Mock KV store for leadership
        mock_kv = AsyncMock()
        mock_kv.get.return_value = None  # No current leader
        mock_kv.create.return_value = 1  # Revision 1
        mock_kv.update.return_value = 2  # Updated revision

        with patch.object(mock_message_bus, "_js") as mock_js:
            mock_js.key_value.return_value = mock_kv

            # Create multiple service instances
            services = []
            for i in range(3):
                service = SingleActiveService(
                    service_name="single_active_test",
                    version="1.0.0",
                    message_bus=mock_message_bus,
                    instance_id=f"instance_{i}",
                )
                services.append(service)

            # Start all services
            for service in services:
                await service.start()

            # One should become active (the first one that acquires leadership)
            active_count = sum(1 for s in services if s.is_active)
            assert active_count <= 1  # At most one active

            # Stop all services
            for service in services:
                await service.stop()

    @pytest.mark.asyncio
    async def test_single_active_failover(self, mock_message_bus):
        """Test failover in single active pattern."""

        # Mock KV store
        mock_kv = AsyncMock()
        current_leader = None

        async def mock_get(key):
            if current_leader:
                return Mock(value=current_leader.encode())
            return None

        async def mock_create(key, value):
            nonlocal current_leader
            if current_leader is None:
                current_leader = value.decode()
                return 1
            raise Exception("Key already exists")

        async def mock_update(key, value, revision):
            nonlocal current_leader
            current_leader = value.decode()
            return revision + 1

        mock_kv.get = mock_get
        mock_kv.create = mock_create
        mock_kv.update = mock_update
        mock_kv.delete = AsyncMock()

        with patch.object(mock_message_bus, "_js") as mock_js:
            mock_js.key_value.return_value = mock_kv

            # Create primary service
            primary = SingleActiveService(
                service_name="failover_test",
                version="1.0.0",
                message_bus=mock_message_bus,
                instance_id="primary",
            )

            # Create standby service
            standby = SingleActiveService(
                service_name="failover_test",
                version="1.0.0",
                message_bus=mock_message_bus,
                instance_id="standby",
            )

            # Start primary first
            await primary.start()
            await asyncio.sleep(0.1)
            assert primary.is_active

            # Start standby
            await standby.start()
            await asyncio.sleep(0.1)
            assert not standby.is_active

            # Simulate primary failure
            current_leader = None
            await primary.stop()

            # Standby should take over (in a real system)
            # Here we simulate by manually triggering leadership check
            await standby._acquire_leadership()
            assert standby.is_active

            await standby.stop()
