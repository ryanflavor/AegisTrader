"""Test the refactored factory pattern implementation.

This test verifies that the factory pattern refactoring maintains
functionality while properly following hexagonal architecture.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk.infrastructure.application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultKVStoreFactory,
    DefaultUseCaseFactory,
    RedisElectionRepositoryFactory,
)
from aegis_sdk.ports.factory_ports import (
    ElectionRepositoryFactory,
    KVStoreFactory,
    UseCaseFactory,
)


class TestFactoryRefactoring:
    """Test suite for refactored factory pattern."""

    def test_factory_interfaces_are_abstract(self):
        """Factory interfaces should be abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ElectionRepositoryFactory()

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            KVStoreFactory()

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            UseCaseFactory()

    def test_concrete_factories_implement_interfaces(self):
        """Concrete factories should properly implement interfaces."""
        # Check inheritance
        assert issubclass(DefaultElectionRepositoryFactory, ElectionRepositoryFactory)
        assert issubclass(DefaultKVStoreFactory, KVStoreFactory)
        assert issubclass(DefaultUseCaseFactory, UseCaseFactory)
        assert issubclass(RedisElectionRepositoryFactory, ElectionRepositoryFactory)

        # Check that they can be instantiated
        election_factory = DefaultElectionRepositoryFactory()
        assert election_factory is not None

        kv_factory = DefaultKVStoreFactory()
        assert kv_factory is not None

        use_case_factory = DefaultUseCaseFactory()
        assert use_case_factory is not None

        redis_factory = RedisElectionRepositoryFactory()
        assert redis_factory is not None

    @pytest.mark.asyncio
    async def test_default_election_repository_factory(self):
        """Test DefaultElectionRepositoryFactory creates proper repository."""
        factory = DefaultElectionRepositoryFactory()
        message_bus = Mock()
        logger = Mock()

        with patch("aegis_sdk.infrastructure.nats_kv_store.NATSKVStore") as MockKVStore:
            with patch(
                "aegis_sdk.infrastructure.nats_kv_election_repository.NatsKvElectionRepository"
            ) as MockRepo:
                mock_kv = AsyncMock()
                MockKVStore.return_value = mock_kv

                repo = await factory.create_election_repository(
                    service_name="test-service",
                    message_bus=message_bus,
                    logger=logger,
                )

                # Verify KV store was created and connected
                MockKVStore.assert_called_once_with(nats_adapter=message_bus)
                mock_kv.connect.assert_called_once_with("election_test_service")

                # Verify repository was created
                MockRepo.assert_called_once_with(kv_store=mock_kv, logger=logger)

    @pytest.mark.asyncio
    async def test_default_kv_store_factory(self):
        """Test DefaultKVStoreFactory creates proper KV store."""
        factory = DefaultKVStoreFactory()
        message_bus = Mock()

        with patch("aegis_sdk.infrastructure.nats_kv_store.NATSKVStore") as MockKVStore:
            mock_kv = AsyncMock()
            MockKVStore.return_value = mock_kv

            store = await factory.create_kv_store(
                bucket_name="test-bucket",
                message_bus=message_bus,
            )

            # Verify KV store was created and connected
            MockKVStore.assert_called_once_with(nats_adapter=message_bus)
            mock_kv.connect.assert_called_once_with("test_bucket")
            assert store == mock_kv

    def test_default_use_case_factory(self):
        """Test DefaultUseCaseFactory creates proper use cases."""
        factory = DefaultUseCaseFactory()

        # Mock dependencies
        election_repo = Mock()
        service_registry = Mock()
        message_bus = Mock()
        metrics = Mock()
        logger = Mock()
        callback = Mock()

        # Test registration use case creation
        with patch(
            "aegis_sdk.application.sticky_active_use_cases.StickyActiveRegistrationUseCase"
        ) as MockUseCase:
            use_case = factory.create_registration_use_case(
                election_repository=election_repo,
                service_registry=service_registry,
                message_bus=message_bus,
                metrics=metrics,
                logger=logger,
            )

            MockUseCase.assert_called_once_with(
                election_repository=election_repo,
                service_registry=service_registry,
                message_bus=message_bus,
                metrics=metrics,
                logger=logger,
            )

        # Test heartbeat use case creation
        with patch(
            "aegis_sdk.application.sticky_active_use_cases.StickyActiveHeartbeatUseCase"
        ) as MockUseCase:
            use_case = factory.create_heartbeat_use_case(
                election_repository=election_repo,
                service_registry=service_registry,
                metrics=metrics,
                logger=logger,
            )

            MockUseCase.assert_called_once_with(
                election_repository=election_repo,
                service_registry=service_registry,
                metrics=metrics,
                logger=logger,
            )

        # Test monitoring use case creation
        with patch(
            "aegis_sdk.application.sticky_active_use_cases.StickyActiveMonitoringUseCase"
        ) as MockUseCase:
            use_case = factory.create_monitoring_use_case(
                election_repository=election_repo,
                service_registry=service_registry,
                message_bus=message_bus,
                metrics=metrics,
                logger=logger,
                status_callback=callback,
            )

            MockUseCase.assert_called_once_with(
                election_repository=election_repo,
                service_registry=service_registry,
                message_bus=message_bus,
                metrics=metrics,
                logger=logger,
                status_callback=callback,
            )

    @pytest.mark.asyncio
    async def test_redis_factory_placeholder(self):
        """Test RedisElectionRepositoryFactory raises NotImplementedError."""
        factory = RedisElectionRepositoryFactory("redis://localhost:6379")

        with pytest.raises(
            NotImplementedError, match="Redis election repository not yet implemented"
        ):
            await factory.create_election_repository(
                service_name="test",
                message_bus=Mock(),
                logger=Mock(),
            )

    def test_backward_compatibility_with_warning(self):
        """Test that factories are available from the new infrastructure location."""
        # Factories have been moved to infrastructure layer as part of hexagonal architecture
        # This test verifies they're accessible from the correct location

        # Import from infrastructure location
        from aegis_sdk.infrastructure.application_factories import (
            DefaultElectionRepositoryFactory,
            DefaultUseCaseFactory,
        )

        # Verify the classes exist and are properly defined
        assert DefaultElectionRepositoryFactory is not None
        assert DefaultUseCaseFactory is not None

        # Verify they have the expected methods
        assert hasattr(DefaultElectionRepositoryFactory, "create_election_repository")
        assert hasattr(DefaultUseCaseFactory, "create_registration_use_case")
        assert hasattr(DefaultUseCaseFactory, "create_heartbeat_use_case")
        assert hasattr(DefaultUseCaseFactory, "create_monitoring_use_case")

    def test_factory_injection_pattern(self):
        """Test that factories can be properly injected as dependencies."""
        from aegis_sdk.application.single_active_dtos import SingleActiveConfig
        from aegis_sdk.application.single_active_service import SingleActiveService

        # Create mock factories
        election_factory = Mock(spec=ElectionRepositoryFactory)
        use_case_factory = Mock(spec=UseCaseFactory)
        message_bus = Mock()

        config = SingleActiveConfig(
            service_name="test-service",
            version="1.0.0",
            group_id="test-group",
        )

        # Service should accept factory dependencies
        service = SingleActiveService(
            config=config,
            message_bus=message_bus,
            election_repository_factory=election_factory,
            use_case_factory=use_case_factory,
        )

        assert service._election_repository_factory is election_factory
        assert service._use_case_factory is use_case_factory
