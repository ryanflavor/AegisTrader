"""Additional unit tests for SingleActiveService to improve coverage to 90%+."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService


class TestSingleActiveServiceCoverage:
    """Additional tests to improve coverage for SingleActiveService."""

    @pytest.mark.asyncio
    async def test_init_with_none_metrics(self):
        """Test initialization when metrics is None (line 140-141 in start)."""
        mock_bus = Mock()
        mock_bus.is_connected = Mock(return_value=True)
        mock_bus.register_service = AsyncMock()

        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
        )

        with patch(
            "aegis_sdk.application.single_active_service.DependencyProvider"
        ) as mock_provider:
            mock_metrics = Mock()
            mock_provider.get_default_metrics.return_value = mock_metrics

            # Mock election factory
            mock_election_factory = Mock()
            mock_election_factory.create_election_repository = AsyncMock(return_value=Mock())
            mock_provider.get_default_election_factory.return_value = mock_election_factory

            # Mock use case factory
            mock_use_case_factory = Mock()
            mock_use_case_factory.create_registration_use_case.return_value = Mock()
            mock_use_case_factory.create_heartbeat_use_case.return_value = Mock()
            mock_use_case_factory.create_monitoring_use_case.return_value = Mock()
            mock_provider.get_default_use_case_factory.return_value = mock_use_case_factory

            service = SingleActiveService(
                config=config,
                message_bus=mock_bus,
                metrics=None,  # Test None metrics
            )

            # Metrics should still be None after init
            assert service._metrics is None

            # Mock the parent's start method
            with patch.object(Service, "start", new=AsyncMock()):
                await service.start()

            # Now get_default_metrics should have been called
            mock_provider.get_default_metrics.assert_called_once()
            assert service._metrics == mock_metrics

    @pytest.mark.asyncio
    async def test_init_with_none_use_case_factory(self):
        """Test initialization when use_case_factory is None (lines 144-146 in start)."""
        mock_bus = Mock()
        mock_bus.is_connected = Mock(return_value=True)
        mock_bus.register_service = AsyncMock()

        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
        )

        with patch(
            "aegis_sdk.application.single_active_service.DependencyProvider"
        ) as mock_provider:
            # Mock use case factory
            mock_factory = Mock()
            mock_factory.create_registration_use_case.return_value = Mock()
            mock_factory.create_heartbeat_use_case.return_value = Mock()
            mock_factory.create_monitoring_use_case.return_value = Mock()
            mock_provider.get_default_use_case_factory.return_value = mock_factory

            # Mock election factory
            mock_election_factory = Mock()
            mock_election_factory.create_election_repository = AsyncMock(return_value=Mock())
            mock_provider.get_default_election_factory.return_value = mock_election_factory

            mock_provider.get_default_metrics.return_value = Mock()

            service = SingleActiveService(
                config=config,
                message_bus=mock_bus,
                use_case_factory=None,  # Test None factory
            )

            # Factory should still be None after init
            assert service._use_case_factory is None

            # Mock the parent's start method
            with patch.object(Service, "start", new=AsyncMock()):
                await service.start()

            # Verify get_default_use_case_factory was called
            mock_provider.get_default_use_case_factory.assert_called_once()
            assert service._use_case_factory == mock_factory

    @pytest.mark.asyncio
    async def test_start_with_registration_failure(self):
        """Test start method when registration fails (lines 215-218)."""
        mock_bus = Mock()
        mock_bus.is_connected = Mock(return_value=True)
        mock_bus.register_service = AsyncMock()

        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
            enable_registration=True,
        )

        mock_logger = Mock()

        with patch(
            "aegis_sdk.application.single_active_service.DependencyProvider"
        ) as mock_provider:
            # Mock the dependencies
            mock_metrics = Mock()
            mock_provider.get_default_metrics.return_value = mock_metrics

            # Mock election factory
            mock_election_factory = Mock()
            mock_election_repo = Mock()
            mock_election_factory.create_election_repository = AsyncMock(
                return_value=mock_election_repo
            )
            mock_provider.get_default_election_factory.return_value = mock_election_factory

            # Mock use case factory
            mock_use_case_factory = Mock()

            # Mock registration use case to throw exception
            mock_registration_use_case = Mock()
            mock_registration_use_case.execute = AsyncMock(
                side_effect=Exception("Registration failed")
            )
            mock_use_case_factory.create_registration_use_case.return_value = (
                mock_registration_use_case
            )

            # Mock heartbeat use case
            mock_heartbeat_use_case = Mock()
            mock_use_case_factory.create_heartbeat_use_case.return_value = mock_heartbeat_use_case

            # Mock monitoring use case to throw exception
            mock_monitoring_use_case = Mock()
            mock_monitoring_use_case.start_monitoring = AsyncMock(
                side_effect=Exception("Monitoring failed")
            )
            mock_use_case_factory.create_monitoring_use_case.return_value = mock_monitoring_use_case

            mock_provider.get_default_use_case_factory.return_value = mock_use_case_factory

            # Mock service registry
            mock_registry = Mock()

            service = SingleActiveService(
                config=config,
                message_bus=mock_bus,
                logger=mock_logger,
                service_registry=mock_registry,
            )

            # Mock the parent's start method
            with (
                patch.object(Service, "start", new=AsyncMock()),
                pytest.raises(Exception, match="Registration failed"),
            ):
                await service.start()

            # Logger should have logged the exception
            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_leadership_release_failure(self):
        """Test stop method when leadership release fails (lines 248-250)."""
        mock_bus = Mock()
        mock_bus.is_connected = Mock(return_value=True)
        mock_bus.unregister_service = AsyncMock()  # Use unregister_service

        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
        )

        # Mock election repository to fail release
        mock_election_repo = Mock()
        mock_election_repo.release_leadership = AsyncMock(side_effect=Exception("Release failed"))

        mock_logger = Mock()

        service = SingleActiveService(
            config=config,
            message_bus=mock_bus,
            logger=mock_logger,
        )
        service._election_repository = mock_election_repo
        service.is_active = True  # Set as active leader

        # Call stop
        await service.stop()

        # Logger should have logged the warning
        mock_logger.warning.assert_called_once()
        assert "Failed to release leadership" in str(mock_logger.warning.call_args)

        # Service should no longer be active
        assert service.is_active is False

    @pytest.mark.asyncio
    async def test_exclusive_rpc_decorator_when_not_active(self):
        """Test exclusive_rpc decorator when service is not active."""

        class TestService(SingleActiveService):
            async def test_method(self, request):
                """Test method decorated with exclusive_rpc."""
                return {"result": "success"}

        mock_bus = Mock()
        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
        )

        # Mock handler registry
        mock_handler_registry = Mock()
        mock_handler_registry._rpc_handlers = {}

        service = TestService(
            config=config,
            message_bus=mock_bus,
        )
        service.is_active = False  # Not active
        service._handler_registry = mock_handler_registry  # Set the handler registry

        # Use the instance method exclusive_rpc decorator
        decorated_method = service.exclusive_rpc("test_method")(service.test_method)

        # Should return error response
        result = await decorated_method({"data": "test"})
        assert result["success"] is False
        assert result["error"] == "NOT_ACTIVE"

    @pytest.mark.asyncio
    async def test_exclusive_rpc_decorator_when_active(self):
        """Test exclusive_rpc decorator when service is active."""

        class TestService(SingleActiveService):
            async def test_method(self, request):
                """Test method decorated with exclusive_rpc."""
                return {"result": "success"}

        mock_bus = Mock()
        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
        )

        # Mock handler registry
        mock_handler_registry = Mock()
        mock_handler_registry._rpc_handlers = {}

        service = TestService(
            config=config,
            message_bus=mock_bus,
        )
        service.is_active = True  # Active
        service._handler_registry = mock_handler_registry  # Set the handler registry

        # Use the instance method exclusive_rpc decorator
        decorated_method = service.exclusive_rpc("test_method")(service.test_method)

        # Should execute normally and return success response
        result = await decorated_method({"data": "test"})
        assert result["success"] is True
        assert result["result"]["result"] == "success"
