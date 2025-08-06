"""Comprehensive unit tests for the refactored Service class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from aegis_sdk.application.service import (
    HandlerRegistry,
    HealthManager,
    LifecycleManager,
    Service,
    ServiceConfig,
    ServiceNameResolver,
)
from aegis_sdk.domain.enums import (
    ServiceLifecycleState,
    ServiceStatus,
    SubscriptionMode,
)
from aegis_sdk.domain.models import (
    RPCResponse,
    ServiceInstance,
)


class TestServiceConfig:
    """Test ServiceConfig DTO validation."""

    def test_valid_config(self):
        """Test valid service configuration."""
        config = ServiceConfig(
            service_name="test-service",
            instance_id="test-123",
            version="1.2.3",
            registry_ttl=60,
            heartbeat_interval=20,
            enable_registration=True,
        )
        assert config.service_name == "test-service"
        assert config.instance_id == "test-123"
        assert config.version == "1.2.3"
        assert config.registry_ttl == 60
        assert config.heartbeat_interval == 20
        assert config.enable_registration is True

    def test_invalid_service_name(self):
        """Test invalid service name validation."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfig(service_name="123-invalid")

        errors = exc_info.value.errors()
        assert any("Invalid service name" in str(e) for e in errors)

    def test_invalid_version_format(self):
        """Test invalid version format."""
        with pytest.raises(ValidationError):
            ServiceConfig(service_name="test", version="1.2")

    def test_boundary_values(self):
        """Test boundary values for numeric fields."""
        # Minimum values
        config = ServiceConfig(
            service_name="t",
            registry_ttl=0.001,
            heartbeat_interval=0.001,
        )
        assert config.registry_ttl == 0.001
        assert config.heartbeat_interval == 0.001

        # Maximum values
        config = ServiceConfig(
            service_name="test",
            registry_ttl=3600,
            heartbeat_interval=300,
        )
        assert config.registry_ttl == 3600
        assert config.heartbeat_interval == 300

    def test_float_heartbeat_interval(self):
        """Test that float heartbeat intervals are accepted."""
        config = ServiceConfig(
            service_name="test",
            heartbeat_interval=0.5,
        )
        assert config.heartbeat_interval == 0.5


class TestHandlerRegistry:
    """Test HandlerRegistry component."""

    @pytest.mark.asyncio
    async def test_register_rpc_handler(self):
        """Test registering RPC handler."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        await registry.register_rpc("test_method", handler)
        assert "test_method" in registry.rpc_handlers
        assert registry.rpc_handlers["test_method"] is handler

    @pytest.mark.asyncio
    async def test_register_rpc_invalid_method(self):
        """Test registering RPC with invalid method name."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await registry.register_rpc("123-invalid", handler)
        assert "Invalid method name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unregister_rpc(self):
        """Test unregistering RPC handler."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        await registry.register_rpc("test_method", handler)
        result = await registry.unregister_rpc("test_method")
        assert result is True
        assert "test_method" not in registry.rpc_handlers

    @pytest.mark.asyncio
    async def test_unregister_rpc_not_found(self):
        """Test unregistering non-existent RPC handler."""
        registry = HandlerRegistry()
        result = await registry.unregister_rpc("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_register_event_handler(self):
        """Test registering event handler."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        await registry.register_event("test.event", handler, SubscriptionMode.COMPETE)
        assert "test.event" in registry.event_handlers
        handlers = registry.event_handlers["test.event"]
        assert len(handlers) == 1
        assert handlers[0] == (handler, "compete")

    @pytest.mark.asyncio
    async def test_register_event_invalid_pattern(self):
        """Test registering event with invalid pattern."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await registry.register_event("invalid..pattern", handler, SubscriptionMode.COMPETE)
        assert "Invalid event pattern" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unregister_event_all_handlers(self):
        """Test unregistering all handlers for an event pattern."""
        registry = HandlerRegistry()
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await registry.register_event("test.*", handler1, SubscriptionMode.COMPETE)
        await registry.register_event("test.*", handler2, SubscriptionMode.BROADCAST)

        result = await registry.unregister_event("test.*")
        assert result is True
        assert "test.*" not in registry.event_handlers

    @pytest.mark.asyncio
    async def test_unregister_event_specific_handler(self):
        """Test unregistering specific event handler."""
        registry = HandlerRegistry()
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await registry.register_event("test.*", handler1, SubscriptionMode.COMPETE)
        await registry.register_event("test.*", handler2, SubscriptionMode.BROADCAST)

        result = await registry.unregister_event("test.*", handler1)
        assert result is True
        assert "test.*" in registry.event_handlers
        handlers = registry.event_handlers["test.*"]
        assert len(handlers) == 1
        assert handlers[0][0] is handler2

    @pytest.mark.asyncio
    async def test_unregister_event_not_found(self):
        """Test unregistering non-existent event pattern."""
        registry = HandlerRegistry()
        result = await registry.unregister_event("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_register_command_handler(self):
        """Test registering command handler."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        await registry.register_command("test_command", handler)
        assert "test_command" in registry.command_handlers
        assert registry.command_handlers["test_command"] is handler

    @pytest.mark.asyncio
    async def test_unregister_command(self):
        """Test unregistering command handler."""
        registry = HandlerRegistry()
        handler = AsyncMock()

        await registry.register_command("test_command", handler)
        result = await registry.unregister_command("test_command")
        assert result is True
        assert "test_command" not in registry.command_handlers

    @pytest.mark.asyncio
    async def test_unregister_command_not_found(self):
        """Test unregistering non-existent command handler."""
        registry = HandlerRegistry()
        result = await registry.unregister_command("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_thread_safety(self):
        """Test thread-safe handler registration."""
        registry = HandlerRegistry()
        handlers = []

        async def register_handler(i):
            handler = AsyncMock()
            handlers.append(handler)
            await registry.register_rpc(f"method_{i}", handler)
            await registry.register_event(f"event.{i}", handler, SubscriptionMode.COMPETE)
            await registry.register_command(f"command_{i}", handler)

        # Register handlers concurrently
        await asyncio.gather(*[register_handler(i) for i in range(10)])

        # Verify all handlers registered
        assert len(registry.rpc_handlers) == 10
        assert len(registry.event_handlers) == 10
        assert len(registry.command_handlers) == 10


class TestLifecycleManager:
    """Test LifecycleManager component."""

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """Test initial lifecycle state."""
        manager = LifecycleManager()
        assert manager.state == ServiceLifecycleState.INITIALIZING
        assert not manager.is_operational()

    @pytest.mark.asyncio
    async def test_valid_transition(self):
        """Test valid state transition."""
        manager = LifecycleManager()

        await manager.transition_to(
            ServiceLifecycleState.STARTING, [ServiceLifecycleState.INITIALIZING]
        )
        assert manager.state == ServiceLifecycleState.STARTING

    @pytest.mark.asyncio
    async def test_invalid_transition(self):
        """Test invalid state transition."""
        manager = LifecycleManager()

        with pytest.raises(RuntimeError) as exc_info:
            await manager.transition_to(
                ServiceLifecycleState.STOPPED, [ServiceLifecycleState.STARTED]
            )
        assert "Cannot transition from INITIALIZING to STOPPED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_is_operational(self):
        """Test operational state check."""
        manager = LifecycleManager()
        assert not manager.is_operational()

        manager._state = ServiceLifecycleState.STARTED
        assert manager.is_operational()

        manager._state = ServiceLifecycleState.STOPPING
        assert not manager.is_operational()

    @pytest.mark.asyncio
    async def test_transition_with_logger(self, mock_logger):
        """Test state transition with logging."""
        manager = LifecycleManager(logger=mock_logger)

        await manager.transition_to(
            ServiceLifecycleState.STARTING, [ServiceLifecycleState.INITIALIZING]
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Service lifecycle state changed" in call_args[0][0]


class TestHealthManager:
    """Test HealthManager component."""

    @pytest.mark.asyncio
    async def test_initial_state(self, mock_message_bus):
        """Test initial health manager state."""
        manager = HealthManager("test-service", "test-123", 10, 30, mock_message_bus)
        assert manager.service_name == "test-service"
        assert manager.instance_id == "test-123"
        assert manager.heartbeat_interval == 10
        assert manager.registry_ttl == 30
        assert manager.is_healthy()

    @pytest.mark.asyncio
    async def test_start_heartbeat(self, mock_message_bus):
        """Test starting heartbeat."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus)

        await manager.start_heartbeat(None)
        assert manager._heartbeat_task is not None
        assert not manager._heartbeat_task.done()

        await manager.stop_heartbeat()

    @pytest.mark.asyncio
    async def test_stop_heartbeat(self, mock_message_bus):
        """Test stopping heartbeat."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus)

        await manager.start_heartbeat(None)
        await manager.stop_heartbeat()

        assert manager._shutdown_event.is_set()
        assert manager._heartbeat_task.cancelled()

    @pytest.mark.asyncio
    async def test_heartbeat_sends_to_bus(self, mock_message_bus):
        """Test heartbeat sends to message bus."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus)

        await manager._send_heartbeat(None)
        mock_message_bus.send_heartbeat.assert_called_once_with("test-service", "test-123")

    @pytest.mark.asyncio
    async def test_heartbeat_updates_registry(self, mock_message_bus, mock_service_registry):
        """Test heartbeat updates registry."""
        manager = HealthManager(
            "test-service", "test-123", 0.01, 30, mock_message_bus, registry=mock_service_registry
        )

        instance = ServiceInstance(
            service_name="test-service", instance_id="test-123", version="1.0.0", status="ACTIVE"
        )

        await manager._send_heartbeat(instance)

        mock_message_bus.send_heartbeat.assert_called_once()
        mock_service_registry.update_heartbeat.assert_called_once_with(instance, 30)

    @pytest.mark.asyncio
    async def test_heartbeat_failure_handling(self, mock_message_bus, mock_logger):
        """Test heartbeat failure handling."""
        mock_message_bus.send_heartbeat.side_effect = Exception("Network error")

        manager = HealthManager(
            "test-service", "test-123", 0.01, 30, mock_message_bus, logger=mock_logger
        )

        await manager._handle_heartbeat_failure(Exception("Test error"))

        assert manager._consecutive_failures == 1
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_marks_unhealthy(self, mock_message_bus):
        """Test heartbeat marks service unhealthy after max failures."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus)

        manager._consecutive_failures = 3
        assert not manager.is_healthy()

    @pytest.mark.asyncio
    async def test_backoff_sleep(self, mock_message_bus):
        """Test exponential backoff calculation."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus)

        manager._consecutive_failures = 1

        with patch("asyncio.sleep") as mock_sleep:
            await manager._backoff_sleep()

            # Check that sleep was called with a value between 2 and 3 (2^1 + jitter)
            call_args = mock_sleep.call_args[0][0]
            assert 2 <= call_args <= 3

    @pytest.mark.asyncio
    async def test_heartbeat_failure_without_logger(self, mock_message_bus, capsys):
        """Test heartbeat failure handling without logger."""
        manager = HealthManager("test-service", "test-123", 0.01, 30, mock_message_bus, logger=None)

        await manager._handle_heartbeat_failure(Exception("Test error"))

        captured = capsys.readouterr()
        assert "❌ Heartbeat error (1/3): Test error" in captured.out


class TestServiceNameResolver:
    """Test ServiceNameResolver component."""

    @pytest.mark.asyncio
    async def test_valid_service_name(self):
        """Test valid service name detection."""
        resolver = ServiceNameResolver()
        assert await resolver.is_service_name("test-service") is True
        assert await resolver.is_service_name("user-service") is True

    @pytest.mark.asyncio
    async def test_invalid_service_name(self):
        """Test invalid service name detection."""
        resolver = ServiceNameResolver()
        assert await resolver.is_service_name("123-invalid") is False
        assert await resolver.is_service_name("test..service") is False

    @pytest.mark.asyncio
    async def test_instance_id_detection(self):
        """Test instance ID pattern detection."""
        resolver = ServiceNameResolver()
        assert await resolver.is_service_name("service-12345678") is False
        assert await resolver.is_service_name("service-deadbeef") is False
        assert await resolver.is_service_name("service-abc123def") is False

    @pytest.mark.asyncio
    async def test_with_discovery(self):
        """Test resolver with service discovery."""
        mock_discovery = MagicMock()
        mock_discovery.discover_instances = AsyncMock(return_value=["instance1"])

        resolver = ServiceNameResolver(discovery=mock_discovery)
        assert await resolver.is_service_name("known-service") is True

        mock_discovery.discover_instances.assert_called_once_with("known-service")

    @pytest.mark.asyncio
    async def test_discovery_failure_fallback(self):
        """Test fallback when discovery fails."""
        mock_discovery = MagicMock()
        mock_discovery.discover_instances = AsyncMock(side_effect=Exception("Discovery error"))

        resolver = ServiceNameResolver(discovery=mock_discovery)
        # Should fall back to pattern matching
        assert await resolver.is_service_name("test-service") is True
        assert await resolver.is_service_name("service-12345678") is False


class TestServiceIntegration:
    """Integration tests for Service class."""

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, mock_message_bus):
        """Test complete service lifecycle."""
        service = Service("test-service", mock_message_bus)

        # Initial state
        assert service.lifecycle_state == ServiceLifecycleState.INITIALIZING
        assert not service.is_operational()

        # Start service
        await service.start()
        assert service.lifecycle_state == ServiceLifecycleState.STARTED
        assert service.is_operational()

        # Stop service
        await service.stop()
        assert service.lifecycle_state == ServiceLifecycleState.STOPPED
        assert not service.is_operational()

    @pytest.mark.asyncio
    async def test_rpc_decorator(self, mock_message_bus):
        """Test RPC decorator registration."""
        service = Service("test-service", mock_message_bus)

        @service.rpc("test_method")
        async def handler(params):
            return {"result": "ok"}

        assert "test_method" in service._handler_registry._rpc_handlers

    @pytest.mark.asyncio
    async def test_event_decorator(self, mock_message_bus):
        """Test event decorator registration."""
        service = Service("test-service", mock_message_bus)

        @service.subscribe("test.event")
        async def handler(event):
            pass

        assert "test.event" in service._handler_registry._event_handlers

    @pytest.mark.asyncio
    async def test_command_decorator(self, mock_message_bus):
        """Test command decorator registration."""
        service = Service("test-service", mock_message_bus)

        @service.command("test_command")
        async def handler(cmd, progress):
            return {"result": "ok"}

        assert "test_command" in service._handler_registry._command_handlers

    @pytest.mark.asyncio
    async def test_call_rpc_with_discovery(self, mock_message_bus):
        """Test RPC call with service discovery."""
        mock_discovery = MagicMock()
        mock_discovery.select_instance = AsyncMock(
            return_value=ServiceInstance(
                service_name="target-service",
                instance_id="target-123",
                version="1.0.0",
                status="ACTIVE",
            )
        )

        service = Service("test-service", mock_message_bus, service_discovery=mock_discovery)

        mock_response = RPCResponse(success=True, result={"data": "test"})
        mock_message_bus.call_rpc.return_value = mock_response

        request = service.create_rpc_request("target-service", "method", {"param": 1})
        result = await service.call_rpc(request)

        assert result == {"data": "test"}
        mock_discovery.select_instance.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event(self, mock_message_bus):
        """Test event publishing."""
        service = Service("test-service", mock_message_bus)
        await service.start()

        event = service.create_event("test", "created", {"id": 123})
        await service.publish_event(event)

        mock_message_bus.publish_event.assert_called_once()
        published_event = mock_message_bus.publish_event.call_args[0][0]
        assert published_event.domain == "test"
        assert published_event.event_type == "created"

        await service.stop()

    @pytest.mark.asyncio
    async def test_send_command(self, mock_message_bus):
        """Test command sending."""
        service = Service("test-service", mock_message_bus)

        mock_message_bus.send_command.return_value = {"status": "completed"}

        command = service.create_command("worker", "process", {"data": "test"})
        result = await service.send_command(command)

        assert result == {"status": "completed"}
        mock_message_bus.send_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_status(self, mock_message_bus):
        """Test status setting."""
        service = Service("test-service", mock_message_bus)

        service.set_status(ServiceStatus.STANDBY)
        assert service._info.status == "STANDBY"

        service.set_status("UNHEALTHY")
        assert service._info.status == "UNHEALTHY"
        assert not service._health_manager.is_healthy()

    @pytest.mark.asyncio
    async def test_health_check(self, mock_message_bus):
        """Test health check logic."""
        service = Service("test-service", mock_message_bus)

        # Not healthy before start
        assert not service.is_healthy()

        await service.start()
        assert service.is_healthy()

        # Mark unhealthy
        service.set_status(ServiceStatus.UNHEALTHY)
        assert not service.is_healthy()

        await service.stop()

    @pytest.mark.asyncio
    async def test_create_command_validation(self, mock_message_bus):
        """Test command creation validation."""
        service = Service("test-service", mock_message_bus)

        # Valid command
        cmd = service.create_command("target", "action", max_retries=5, timeout=100)
        assert cmd.max_retries == 5
        assert cmd.timeout == 100

        # Invalid max_retries
        with pytest.raises(ValueError) as exc_info:
            service.create_command("target", "action", max_retries=101)
        assert "max_retries must be between 0 and 100" in str(exc_info.value)

        # Invalid timeout
        with pytest.raises(ValueError) as exc_info:
            service.create_command("target", "action", timeout=3601)
        assert "timeout must be between 0 and 3600 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, mock_message_bus):
        """Test backward compatibility methods."""
        service = Service("test-service", mock_message_bus)

        # Test helper methods
        handler = AsyncMock()
        await service.register_rpc_method("test_method", handler)
        assert "test_method" in service._handler_registry._rpc_handlers

        await service.register_command_handler("test_command", handler)
        assert "test_command" in service._handler_registry._command_handlers

        await service.subscribe_event("test", "event", handler)
        assert "events.test.event" in service._handler_registry._event_handlers

    @pytest.mark.asyncio
    async def test_lifecycle_hooks(self, mock_message_bus):
        """Test lifecycle hooks are called."""

        class TestService(Service):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.on_start_called = False
                self.on_started_called = False
                self.on_stop_called = False
                self.on_stopped_called = False

            async def on_start(self):
                self.on_start_called = True

            async def on_started(self):
                self.on_started_called = True

            async def on_stop(self):
                self.on_stop_called = True

            async def on_stopped(self):
                self.on_stopped_called = True

        service = TestService("test-service", mock_message_bus)

        await service.start()
        assert service.on_start_called
        assert service.on_started_called

        await service.stop()
        assert service.on_stop_called
        assert service.on_stopped_called

    @pytest.mark.asyncio
    async def test_error_handling_on_start(self, mock_message_bus):
        """Test error handling during service start."""
        mock_message_bus.register_service.side_effect = Exception("Registration failed")

        service = Service("test-service", mock_message_bus)

        with pytest.raises(Exception) as exc_info:
            await service.start()

        assert "Registration failed" in str(exc_info.value)
        assert service.lifecycle_state == ServiceLifecycleState.FAILED

    @pytest.mark.asyncio
    async def test_error_handling_on_stop(self, mock_message_bus, mock_logger):
        """Test error handling during service stop."""
        service = Service("test-service", mock_message_bus, logger=mock_logger)

        await service.start()

        # Make stop fail
        mock_message_bus.unregister_service.side_effect = Exception("Unregister failed")

        with pytest.raises(Exception):
            await service.stop()

        # Should still transition to STOPPED
        assert service.lifecycle_state == ServiceLifecycleState.STOPPED
        mock_logger.error.assert_called()
