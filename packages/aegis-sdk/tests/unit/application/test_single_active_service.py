"""Unit tests for SingleActiveService using sticky active pattern."""

from unittest.mock import AsyncMock, Mock

import pytest

from aegis_sdk.application.metrics import Metrics
from aegis_sdk.application.single_active_dtos import (
    SingleActiveConfig,
    SingleActiveStatus,
)
from aegis_sdk.application.single_active_service import SingleActiveService, exclusive_rpc
from aegis_sdk.application.sticky_active_use_cases import (
    StickyActiveRegistrationResponse,
)


class TestSingleActiveService:
    """Test SingleActiveService implementation."""

    def test_init_creates_components(self):
        """Test that initialization creates necessary components."""
        mock_bus = Mock()
        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
            group_id="default",
            leader_ttl_seconds=5,
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
        )

        assert service.is_active is False
        assert service._monitoring_task is None
        assert service.group_id == "default"
        assert service.leader_ttl_seconds == 5
        assert service._config == config

    @pytest.mark.asyncio
    async def test_start_initializes_use_cases(self):
        """Test that start method initializes use cases."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        mock_bus.is_connected = Mock(return_value=True)

        # Mock factory
        mock_factory = Mock()
        mock_factory.create_registration_use_case = Mock(return_value=Mock())
        mock_factory.create_heartbeat_use_case = Mock(return_value=Mock())
        mock_factory.create_monitoring_use_case = Mock(return_value=Mock())

        # Mock election repository
        mock_election_repo = Mock()

        # Mock metrics
        mock_metrics = Mock(spec=Metrics)

        config = SingleActiveConfig(
            service_name="test-service",
            enable_registration=False,  # Disable to simplify test
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            election_repository=mock_election_repo,
            use_case_factory=mock_factory,
            metrics=mock_metrics,  # Provide metrics to avoid DependencyProvider
        )

        await service.start()

        # Should initialize use cases
        assert service._registration_use_case is not None
        assert service._heartbeat_use_case is not None
        assert service._monitoring_use_case is not None

        # Factory methods should be called
        mock_factory.create_registration_use_case.assert_called_once()
        mock_factory.create_heartbeat_use_case.assert_called_once()
        mock_factory.create_monitoring_use_case.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_releases_leadership_when_active(self):
        """Test that stop method releases leadership if active."""
        mock_bus = Mock()
        mock_bus.deregister_service = AsyncMock()
        mock_bus.unregister_service = AsyncMock()
        mock_bus.is_connected = Mock(return_value=True)

        # Mock election repository
        mock_election_repo = Mock()
        mock_election_repo.release_leadership = AsyncMock(return_value=True)

        config = SingleActiveConfig(
            service_name="test-service",
            enable_registration=False,
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            election_repository=mock_election_repo,
        )
        service.is_active = True
        service._monitoring_use_case = Mock()
        service._monitoring_use_case.stop_monitoring = AsyncMock()
        # Mock the parent stop method
        service._shutdown_event = Mock()
        service._shutdown_event.set = Mock()
        service._heartbeat_task = None
        service._status_update_task = None

        await service.stop()

        # Should release leadership
        mock_election_repo.release_leadership.assert_called_once()
        assert service.is_active is False

    @pytest.mark.asyncio
    async def test_stop_does_not_release_when_not_active(self):
        """Test that stop method doesn't release leadership when not active."""
        mock_bus = Mock()
        mock_bus.deregister_service = AsyncMock()
        mock_bus.unregister_service = AsyncMock()
        mock_bus.is_connected = Mock(return_value=True)

        # Mock election repository
        mock_election_repo = Mock()
        mock_election_repo.release_leadership = AsyncMock()

        config = SingleActiveConfig(
            service_name="test-service",
            enable_registration=False,
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            election_repository=mock_election_repo,
        )
        service.is_active = False  # Not active
        # Mock the parent stop method
        service._shutdown_event = Mock()
        service._shutdown_event.set = Mock()
        service._heartbeat_task = None
        service._status_update_task = None

        await service.stop()

        # Should not release leadership
        mock_election_repo.release_leadership.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_registry_heartbeat_includes_sticky_active(self):
        """Test that heartbeat update includes sticky active heartbeat."""
        mock_bus = Mock()
        mock_bus.is_connected = Mock(return_value=True)

        # Mock heartbeat use case
        mock_heartbeat_use_case = Mock()
        mock_heartbeat_use_case.execute = AsyncMock(return_value=True)

        config = SingleActiveConfig(
            service_name="test-service",
            enable_registration=True,
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
        )
        service._heartbeat_use_case = mock_heartbeat_use_case
        service._registry = Mock()
        service._registry.update_heartbeat = AsyncMock()

        await service._update_registry_heartbeat()

        # Should call sticky active heartbeat
        mock_heartbeat_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_exclusive_rpc_decorator_instance_method(self):
        """Test that exclusive_rpc instance method decorator works correctly."""
        mock_bus = Mock()
        config = SingleActiveConfig(service_name="test-service")

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
        )

        # Create a mock handler
        handler = AsyncMock(return_value={"result": "success"})

        # Apply decorator
        decorated = service.exclusive_rpc("test_method")(handler)

        # Test when not active
        service.is_active = False
        result = await decorated({"param": "value"})

        assert result["success"] is False
        assert result["error"] == "NOT_ACTIVE"
        handler.assert_not_called()

        # Test when active
        service.is_active = True
        result = await decorated({"param": "value"})

        assert result["success"] is True
        assert result["result"] == {"result": "success"}
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_exclusive_rpc_module_decorator_rejected_when_not_active(self):
        """Test that exclusive RPC module decorator rejects when not active."""
        # Create a mock service
        mock_service = Mock(spec=SingleActiveService)
        mock_service.is_active = False
        mock_service.instance_id = "test-instance"
        mock_service._metrics = Mock()

        # Create decorated function
        @exclusive_rpc
        async def test_handler(self, params: dict) -> dict:
            return {"result": "success"}

        # Call decorated function
        result = await test_handler(mock_service, {"param": "value"})

        assert result["success"] is False
        assert result["error"] == "NOT_ACTIVE"
        assert "not active" in result["message"]
        mock_service._metrics.increment.assert_called_with("sticky_active.rpc.not_active")

    @pytest.mark.asyncio
    async def test_exclusive_rpc_module_decorator_allowed_when_active(self):
        """Test that exclusive RPC module decorator allows when active."""
        # Create a mock service
        mock_service = Mock(spec=SingleActiveService)
        mock_service.is_active = True
        mock_service.instance_id = "test-instance"

        # Create decorated function
        @exclusive_rpc
        async def test_handler(self, params: dict) -> dict:
            return {"result": params["value"] * 2}

        # Call decorated function
        result = await test_handler(mock_service, {"value": 5})

        assert result["success"] is True
        assert result["result"] == {"result": 10}

    def test_status_callback_updates_active_status(self):
        """Test that status callback updates active status."""
        mock_bus = Mock()
        config = SingleActiveConfig(service_name="test-service")
        service = SingleActiveService(config=config, message_bus=mock_bus)

        # Test becoming active
        service._update_active_status(True)
        assert service.is_active is True

        # Test becoming inactive
        service._update_active_status(False)
        assert service.is_active is False

    @pytest.mark.asyncio
    async def test_start_with_service_registry(self):
        """Test start with service registry performs registration."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        mock_bus.is_connected = Mock(return_value=True)

        mock_registry = Mock()
        mock_registry.register = AsyncMock()

        # Mock registration response
        mock_response = StickyActiveRegistrationResponse(
            service_name="test-service",
            instance_id="test-instance",
            is_leader=True,
            sticky_active_status="ACTIVE",
            group_id="default",
        )

        # Mock use case factory
        mock_factory = Mock()
        mock_registration_use_case = Mock()
        mock_registration_use_case.execute = AsyncMock(return_value=mock_response)
        mock_factory.create_registration_use_case = Mock(return_value=mock_registration_use_case)
        mock_factory.create_heartbeat_use_case = Mock(return_value=Mock())

        mock_monitoring_use_case = Mock()
        mock_monitoring_use_case.start_monitoring = AsyncMock()
        mock_factory.create_monitoring_use_case = Mock(return_value=mock_monitoring_use_case)

        config = SingleActiveConfig(
            service_name="test-service",
            enable_registration=True,
        )

        # Mock election repository to avoid NATS connection
        mock_election_repo = Mock()

        # Mock metrics to avoid DependencyProvider
        mock_metrics = Mock(spec=Metrics)

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            service_registry=mock_registry,
            election_repository=mock_election_repo,
            use_case_factory=mock_factory,
            metrics=mock_metrics,
        )

        # Mock service instance
        service._service_instance = Mock()
        service._service_instance.metadata = {"key": "value"}

        await service.start()

        # Should perform registration
        mock_registration_use_case.execute.assert_called_once()
        assert service.is_active is True

        # Should start monitoring
        mock_monitoring_use_case.start_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test get_status method returns correct status."""
        mock_bus = Mock()
        mock_election_repo = Mock()

        from aegis_sdk.domain.value_objects import InstanceId

        mock_election_repo.get_current_leader = AsyncMock(
            return_value=(InstanceId(value="leader-instance"), {})
        )

        config = SingleActiveConfig(
            service_name="test-service",
            version="2.0.0",
            group_id="production",
            leader_ttl_seconds=3,  # Must be <= heartbeat_interval
            heartbeat_interval=5,
        )

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            election_repository=mock_election_repo,
        )
        service.is_active = True

        status = await service.get_status()

        assert isinstance(status, SingleActiveStatus)
        assert status.service_name == "test-service"
        assert status.group_id == "production"
        assert status.is_active is True
        assert status.is_leader is True
        assert status.leader_instance_id == "leader-instance"
        assert status.metadata["version"] == "2.0.0"
        assert status.metadata["leader_ttl"] == 3
        assert status.metadata["heartbeat_interval"] == 5

    @pytest.mark.asyncio
    async def test_exclusive_rpc_with_exception(self):
        """Test exclusive RPC handles exceptions properly."""
        mock_bus = Mock()
        mock_logger = Mock()

        config = SingleActiveConfig(service_name="test-service")

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            logger=mock_logger,
        )
        service.is_active = True

        # Create a handler that raises exception
        async def failing_handler(params: dict) -> dict:
            raise ValueError("Test error")

        # Apply decorator
        decorated = service.exclusive_rpc("failing_method")(failing_handler)

        # Call decorated function
        result = await decorated({"param": "value"})

        assert result["success"] is False
        assert result["error"] == "EXECUTION_ERROR"
        assert "Test error" in result["message"]
        mock_logger.exception.assert_called_once()

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = SingleActiveConfig(
            service_name="valid-service",
            version="1.2.3",
            heartbeat_interval=5,
            registry_ttl=30,
            leader_ttl_seconds=3,
        )
        assert config.service_name == "valid-service"

        # Invalid service name
        with pytest.raises(ValueError, match="Invalid service name"):
            SingleActiveConfig(
                service_name="-invalid",  # Can't start with hyphen
                version="1.0.0",
            )

        # Invalid version
        with pytest.raises(ValueError, match="String should match pattern"):
            SingleActiveConfig(
                service_name="test",
                version="invalid",
            )

        # Invalid heartbeat interval (must be less than TTL)
        with pytest.raises(ValueError, match="must be less than"):
            SingleActiveConfig(
                service_name="test",
                heartbeat_interval=30,
                registry_ttl=20,
            )
