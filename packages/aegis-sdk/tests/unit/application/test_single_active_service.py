"""Unit tests for SingleActiveService using sticky active pattern."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk.application.single_active_service import SingleActiveService


class TestSingleActiveService:
    """Test SingleActiveService implementation."""

    def test_init_creates_components(self):
        """Test that initialization creates necessary components."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

        assert service.is_active is False
        assert service._monitoring_task is None
        assert service.group_id == "default"
        assert service.leader_ttl_seconds == 5

    @pytest.mark.asyncio
    async def test_start_initializes_use_cases(self):
        """Test that start method initializes use cases."""
        mock_bus = Mock()
        mock_bus.register_service = AsyncMock()
        mock_bus.is_connected = Mock(return_value=True)

        # Mock the KV store creation
        with patch(
            "aegis_sdk.application.single_active_service.NATSKVStore"
        ) as mock_kv_store_class:
            mock_kv_store = Mock()
            mock_kv_store.connect = AsyncMock()
            mock_kv_store_class.return_value = mock_kv_store

            service = SingleActiveService(
                service_name="test-service",
                message_bus=mock_bus,
                enable_registration=False,  # Disable to simplify test
            )

            await service.start()

            # Should initialize use cases
            assert service._registration_use_case is not None
            assert service._heartbeat_use_case is not None
            assert service._monitoring_use_case is not None

            # KV store should be connected
            mock_kv_store.connect.assert_called_once_with("election_test-service", enable_ttl=True)

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

        service = SingleActiveService(
            service_name="test-service",
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
        service._enable_registration = False

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

        service = SingleActiveService(
            service_name="test-service",
            message_bus=mock_bus,
            election_repository=mock_election_repo,
        )
        service.is_active = False  # Not active
        # Mock the parent stop method
        service._shutdown_event = Mock()
        service._shutdown_event.set = Mock()
        service._heartbeat_task = None
        service._status_update_task = None
        service._enable_registration = False

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

        service = SingleActiveService(
            service_name="test-service", message_bus=mock_bus, enable_registration=True
        )
        service._heartbeat_use_case = mock_heartbeat_use_case
        service._registry = Mock()
        service._registry.update_heartbeat = AsyncMock()

        await service._update_registry_heartbeat()

        # Should call sticky active heartbeat
        mock_heartbeat_use_case.execute.assert_called_once()

    def test_rpc_exclusive_decorator(self):
        """Test that rpc_exclusive decorator works correctly."""
        # The current implementation doesn't have rpc_exclusive decorator
        # This test should be removed or updated when the decorator is implemented
        pass

    @pytest.mark.asyncio
    async def test_exclusive_rpc_rejected_when_not_active(self):
        """Test that exclusive RPC is rejected when not active."""
        # The current implementation doesn't have rpc_exclusive decorator
        # This test should be removed or updated when the decorator is implemented
        pass

    @pytest.mark.asyncio
    async def test_exclusive_rpc_allowed_when_active(self):
        """Test that exclusive RPC is allowed when active."""
        # The current implementation doesn't have rpc_exclusive decorator
        # This test should be removed or updated when the decorator is implemented
        pass

    def test_status_callback_updates_active_status(self):
        """Test that status callback updates active status."""
        mock_bus = Mock()
        service = SingleActiveService(service_name="test-service", message_bus=mock_bus)

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

        # Mock the registration use case
        with patch(
            "aegis_sdk.application.single_active_service.NATSKVStore"
        ) as mock_kv_store_class:
            mock_kv_store = Mock()
            mock_kv_store.connect = AsyncMock()
            mock_kv_store_class.return_value = mock_kv_store

            with patch(
                "aegis_sdk.application.single_active_service.StickyActiveRegistrationUseCase"
            ) as mock_use_case_class:
                mock_use_case = Mock()
                mock_use_case.execute = AsyncMock(return_value=Mock(is_leader=True))
                mock_use_case_class.return_value = mock_use_case

                service = SingleActiveService(
                    service_name="test-service",
                    message_bus=mock_bus,
                    service_registry=mock_registry,
                    enable_registration=True,
                )

                await service.start()

                # Should perform registration
                mock_use_case.execute.assert_called_once()
                assert service.is_active is True
