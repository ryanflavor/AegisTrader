"""Migration tests for SingleActiveService refactoring.

These tests ensure backward compatibility and correct behavior
after migrating from event-based to KV Store-based election.
"""

from unittest.mock import AsyncMock, patch

import pytest

from aegis_sdk.application.single_active_service import SingleActiveService, exclusive_rpc
from aegis_sdk.application.sticky_active_use_cases import StickyActiveRegistrationResponse
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


@pytest.fixture
def mock_message_bus():
    """Create mock message bus."""
    bus = AsyncMock()
    bus.register_service = AsyncMock()
    bus.register_rpc_handler = AsyncMock()
    bus.send_heartbeat = AsyncMock()
    bus.unregister_service = AsyncMock()
    bus.publish_event = AsyncMock()
    bus.subscribe_event = AsyncMock()
    return bus


@pytest.fixture
def mock_service_registry():
    """Create mock service registry."""
    registry = AsyncMock()
    registry.register = AsyncMock()
    registry.deregister = AsyncMock()
    registry.update_heartbeat = AsyncMock()
    registry.get_instances = AsyncMock(return_value=[])
    return registry


@pytest.fixture
def mock_election_repository():
    """Create mock election repository."""
    repo = AsyncMock()
    repo.attempt_leadership = AsyncMock(return_value=True)
    repo.update_leadership = AsyncMock(return_value=True)
    repo.get_current_leader = AsyncMock(return_value=(None, {}))
    repo.release_leadership = AsyncMock(return_value=True)
    repo.save_election_state = AsyncMock()
    repo.get_election_state = AsyncMock(return_value=None)
    repo.watch_leadership = AsyncMock()
    return repo


class TestSingleActiveServiceMigration:
    """Test backward compatibility after refactoring."""

    @pytest.mark.asyncio
    async def test_service_initialization_compatibility(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that service initializes correctly with new components."""
        # Create service with all new dependencies
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            logger=SimpleLogger("test"),
            metrics=InMemoryMetrics(),
            election_repository=mock_election_repository,
        )

        assert service.service_name == "test-service"
        assert service.group_id == "default"
        assert service.leader_ttl_seconds == 5
        assert not service.is_active

    @pytest.mark.asyncio
    async def test_service_starts_with_election(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that service performs election on start."""
        # Setup mock to return successful election
        mock_election_repository.attempt_leadership.return_value = True

        # Create service with logger to avoid None errors
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
            logger=SimpleLogger("test"),
            metrics=InMemoryMetrics(),
        )

        # Setup mocks for watch_leadership
        async def mock_watch():
            # Return empty async generator
            return
            yield  # Make it an async generator

        mock_election_repository.watch_leadership.return_value = mock_watch()
        mock_election_repository.get_election_state.return_value = None
        mock_election_repository.save_election_state.return_value = None
        mock_election_repository.get_current_leader.return_value = (None, {})

        await service.start()

        # Verify service became active through election
        assert service.is_active
        # Verify election was attempted
        mock_election_repository.attempt_leadership.assert_called()

        await service.stop()

    @pytest.mark.asyncio
    async def test_exclusive_rpc_decorator_instance_method(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test exclusive_rpc decorator as instance method works correctly."""

        class TestService(SingleActiveService):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.processed_count = 0

            async def on_start(self):
                @self.exclusive_rpc("process")
                async def process_handler(params: dict) -> dict:
                    self.processed_count += 1
                    return {"result": "processed", "count": self.processed_count}

        # Test active instance
        active_service = TestService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
        )
        active_service.is_active = True

        await active_service.on_start()

        # Call the RPC method
        result = await active_service._rpc_handlers["process"]({"data": "test"})
        assert result["result"] == "processed"
        assert result["count"] == 1

        # Test standby instance
        standby_service = TestService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
        )
        standby_service.is_active = False

        await standby_service.on_start()

        # Call the RPC method on standby
        result = await standby_service._rpc_handlers["process"]({"data": "test"})
        assert not result["success"]
        assert result["error"] == "NOT_ACTIVE"
        assert "STANDBY mode" in result["message"]

    @pytest.mark.asyncio
    async def test_exclusive_rpc_decorator_class_level(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test exclusive_rpc decorator at class level works correctly."""

        class TestService(SingleActiveService):
            @exclusive_rpc
            async def process_exclusive(self, params: dict) -> dict:
                return {"result": "exclusive_processed"}

            @exclusive_rpc("custom_method")
            async def custom_exclusive(self, params: dict) -> dict:
                return {"result": "custom_processed"}

        # Test active instance
        active_service = TestService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
        )
        active_service.is_active = True

        # Test bare @exclusive_rpc
        result = await active_service.process_exclusive({"data": "test"})
        assert result["result"] == "exclusive_processed"

        # Test @exclusive_rpc("method_name")
        result = await active_service.custom_exclusive({"data": "test"})
        assert result["result"] == "custom_processed"

        # Test standby instance
        standby_service = TestService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
        )
        standby_service.is_active = False

        result = await standby_service.process_exclusive({"data": "test"})
        assert not result["success"]
        assert result["error"] == "NOT_ACTIVE"

    @pytest.mark.asyncio
    async def test_heartbeat_updates_leadership(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that heartbeat updates both service and leader heartbeat."""
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
        )
        service.is_active = True
        service._enable_registration = True

        # Initialize use cases
        service._heartbeat_use_case = AsyncMock()
        service._heartbeat_use_case.execute.return_value = True

        await service._update_registry_heartbeat()

        # Verify heartbeat use case was called
        service._heartbeat_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_leadership_loss_during_heartbeat(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that service handles leadership loss during heartbeat."""
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
            logger=SimpleLogger("test"),
        )
        service.is_active = True
        service._enable_registration = True

        # Initialize use cases
        service._heartbeat_use_case = AsyncMock()
        service._heartbeat_use_case.execute.return_value = False  # Heartbeat fails

        await service._update_registry_heartbeat()

        # Verify service is no longer active
        assert not service.is_active

    @pytest.mark.asyncio
    async def test_service_stop_releases_leadership(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that stopping service releases leadership."""
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
            logger=SimpleLogger("test"),
        )
        service.is_active = True
        service._monitoring_use_case = AsyncMock()

        await service.stop()

        # Verify leadership was released
        mock_election_repository.release_leadership.assert_called_once_with(
            ServiceName(value="test-service"),
            InstanceId(value=service.instance_id),
            "default",
        )

    @pytest.mark.asyncio
    async def test_backward_compatibility_without_registry(
        self,
        mock_message_bus,
    ):
        """Test that service works without registry (for testing)."""
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            enable_registration=False,
        )

        await service.start()

        # Service should start without errors
        assert service.service_name == "test-service"
        assert not service.is_active  # No election without registry

        await service.stop()

    @pytest.mark.asyncio
    async def test_metrics_tracking(
        self,
        mock_message_bus,
        mock_service_registry,
        mock_election_repository,
    ):
        """Test that metrics are properly tracked."""
        metrics = InMemoryMetrics()
        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=mock_election_repository,
            metrics=metrics,
        )

        # Initialize the service to set up handlers
        await service.on_start()

        # Test RPC on standby instance
        service.is_active = False

        @service.exclusive_rpc("test_method")
        async def test_handler(params: dict) -> dict:
            return {"result": "ok"}

        result = await service._rpc_handlers["test_method"]({"data": "test"})
        assert not result["success"]

        # Check metrics - InMemoryMetrics stores counters in a nested structure
        all_metrics = metrics.get_all()
        assert "counters" in all_metrics
        assert "sticky_active.rpc.not_active" in all_metrics["counters"]
        assert all_metrics["counters"]["sticky_active.rpc.not_active"] == 1

    @pytest.mark.asyncio
    async def test_multiple_instances_election(
        self,
        mock_message_bus,
        mock_service_registry,
    ):
        """Test that multiple instances properly handle election."""
        # Create two instances with mock election repositories
        election_repo1 = AsyncMock()
        election_repo1.attempt_leadership.return_value = True  # First wins
        election_repo1.get_election_state.return_value = None
        election_repo1.save_election_state.return_value = None
        election_repo1.get_current_leader.return_value = (None, {})
        election_repo1.release_leadership.return_value = True

        election_repo2 = AsyncMock()
        election_repo2.attempt_leadership.return_value = False  # Second loses
        election_repo2.get_election_state.return_value = None
        election_repo2.save_election_state.return_value = None
        election_repo2.get_current_leader.return_value = (InstanceId(value="instance-1"), {})
        election_repo2.release_leadership.return_value = False

        # Create services with logger and metrics
        service1 = SingleActiveService(
            service_name="test-service",
            instance_id="instance-1",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=election_repo1,
            logger=SimpleLogger("test"),
            metrics=InMemoryMetrics(),
        )

        service2 = SingleActiveService(
            service_name="test-service",
            instance_id="instance-2",
            message_bus=mock_message_bus,
            service_registry=mock_service_registry,
            election_repository=election_repo2,
            logger=SimpleLogger("test"),
            metrics=InMemoryMetrics(),
        )

        # Mock registration responses
        with (
            patch.object(service1, "_registration_use_case") as mock_reg1,
            patch.object(service2, "_registration_use_case") as mock_reg2,
            patch.object(service1, "_monitoring_use_case") as mock_mon1,
            patch.object(service2, "_monitoring_use_case") as mock_mon2,
        ):
            mock_reg1.execute.return_value = StickyActiveRegistrationResponse(
                service_name="test-service",
                instance_id="instance-1",
                is_leader=True,
                sticky_active_status="ACTIVE",
                group_id="default",
            )

            mock_reg2.execute.return_value = StickyActiveRegistrationResponse(
                service_name="test-service",
                instance_id="instance-2",
                is_leader=False,
                sticky_active_status="STANDBY",
                group_id="default",
            )

            mock_mon1.start_monitoring = AsyncMock()
            mock_mon2.start_monitoring = AsyncMock()

            await service1.start()
            await service2.start()

            # Verify election results
            assert service1.is_active
            assert not service2.is_active

            await service1.stop()
            await service2.stop()
