"""Comprehensive tests for InfrastructureFactory following TDD and hexagonal architecture.

These tests verify the factory pattern implementation with proper
mocking at architectural boundaries and comprehensive coverage.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.models import ServiceConfiguration
from app.infrastructure.factory import InfrastructureFactory
from app.ports.service_registry_kv_store import ServiceRegistryKVStorePort


class TestInfrastructureFactory:
    """Test cases for InfrastructureFactory following hexagonal architecture."""

    @pytest.fixture
    def sample_config(self) -> ServiceConfiguration:
        """Create sample service configuration."""
        return ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            environment="development",
            stale_threshold_seconds=30,
        )

    def test_create_configuration_port(self) -> None:
        """Test creating a configuration port adapter."""
        # Act
        port = InfrastructureFactory.create_configuration_port()

        # Assert - check that it's an adapter instance implementing the required methods
        assert port is not None
        assert hasattr(port, "load_configuration")
        assert hasattr(port, "validate_configuration")

    def test_create_monitoring_port(self, sample_config: ServiceConfiguration) -> None:
        """Test creating a monitoring port adapter."""
        # Arrange
        start_time = datetime.now()

        # Act
        port = InfrastructureFactory.create_monitoring_port(sample_config, start_time)

        # Assert - check that it's an adapter instance implementing the required methods
        assert port is not None
        assert hasattr(port, "get_health_status")

    @pytest.mark.asyncio
    async def test_create_kv_store_port(self) -> None:
        """Test creating a KV store port adapter."""
        # Arrange
        nats_url = "nats://localhost:4222"

        # Mock the AegisSDKKVAdapter
        with patch("app.infrastructure.factory.AegisSDKKVAdapter") as MockAdapter:
            mock_adapter = Mock(spec=ServiceRegistryKVStorePort)
            mock_adapter.connect = AsyncMock()
            MockAdapter.return_value = mock_adapter

            # Act
            port = await InfrastructureFactory.create_kv_store_port(nats_url)

            # Assert
            assert port is not None
            MockAdapter.assert_called_once()
            mock_adapter.connect.assert_called_once_with(nats_url)

    def test_create_service_instance_repository(self) -> None:
        """Test creating a service instance repository adapter."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = Mock()
        stale_threshold = 35

        # Act
        port = InfrastructureFactory.create_service_instance_repository(
            mock_kv_store, stale_threshold
        )

        # Assert
        assert port is not None
        assert hasattr(port, "get_all_instances")

    def test_create_service_instance_repository_without_raw_kv(self) -> None:
        """Test creating repository when KV store doesn't have raw_kv attribute."""
        # Arrange
        mock_kv_store = Mock(spec=["get", "put", "delete"])  # No raw_kv attribute
        stale_threshold = 35

        # Act
        port = InfrastructureFactory.create_service_instance_repository(
            mock_kv_store, stale_threshold
        )

        # Assert
        assert port is not None
        assert hasattr(port, "get_all_instances")

    def test_create_sdk_monitoring_port(self) -> None:
        """Test creating an SDK monitoring port adapter."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = Mock()

        # Act
        port = InfrastructureFactory.create_sdk_monitoring_port(mock_kv_store)

        # Assert
        assert port is not None
        assert hasattr(port, "run_tests")

    def test_create_sdk_monitoring_port_without_raw_kv(self) -> None:
        """Test creating SDK monitoring port when KV store doesn't have raw_kv."""
        # Arrange
        mock_kv_store = Mock(spec=["get", "put", "delete"])  # No raw_kv attribute

        # Act
        port = InfrastructureFactory.create_sdk_monitoring_port(mock_kv_store)

        # Assert
        assert port is not None
        assert hasattr(port, "run_tests")

    def test_create_all_adapters(self, sample_config: ServiceConfiguration) -> None:
        """Test creating all adapters at once."""
        # Arrange
        start_time = datetime.now()
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = Mock()

        # Act
        adapters = InfrastructureFactory.create_all_adapters(
            sample_config, start_time, mock_kv_store
        )

        # Assert
        assert "configuration" in adapters
        assert "monitoring" in adapters
        assert "service_instance_repository" in adapters
        assert "sdk_monitoring" in adapters
        assert hasattr(adapters["configuration"], "load_configuration")
        assert hasattr(adapters["monitoring"], "get_health_status")
        assert hasattr(adapters["service_instance_repository"], "get_all_instances")
        assert hasattr(adapters["sdk_monitoring"], "run_tests")

    def test_factory_methods_are_static(self) -> None:
        """Test that factory methods are properly static."""
        # Assert that methods can be called without instance
        assert callable(InfrastructureFactory.create_configuration_port)
        assert callable(InfrastructureFactory.create_monitoring_port)
        assert callable(InfrastructureFactory.create_kv_store_port)
        assert callable(InfrastructureFactory.create_service_instance_repository)
        assert callable(InfrastructureFactory.create_sdk_monitoring_port)
        assert callable(InfrastructureFactory.create_all_adapters)

    @pytest.mark.asyncio
    async def test_create_kv_store_port_connection_failure(self) -> None:
        """Test handling connection failure when creating KV store port."""
        # Arrange
        nats_url = "nats://localhost:4222"

        # Mock the AegisSDKKVAdapter to raise exception
        with patch("app.infrastructure.factory.AegisSDKKVAdapter") as MockAdapter:
            mock_adapter = Mock(spec=ServiceRegistryKVStorePort)
            mock_adapter.connect = AsyncMock(side_effect=Exception("Connection failed"))
            MockAdapter.return_value = mock_adapter

            # Act & Assert
            with pytest.raises(Exception, match="Connection failed"):
                await InfrastructureFactory.create_kv_store_port(nats_url)

    def test_create_all_adapters_with_minimal_config(self) -> None:
        """Test creating all adapters with minimal configuration."""
        # Arrange
        minimal_config = ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            environment="development",
            stale_threshold_seconds=30,
        )
        mock_kv_store = Mock()

        # Act
        adapters = InfrastructureFactory.create_all_adapters(minimal_config, None, mock_kv_store)

        # Assert
        assert len(adapters) == 4
        assert all(v is not None for v in adapters.values())

    def test_factory_adapters_follow_ports_interfaces(
        self, sample_config: ServiceConfiguration
    ) -> None:
        """Test that created adapters properly implement port interfaces."""
        # Arrange
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = Mock()

        # Act
        config_port = InfrastructureFactory.create_configuration_port()
        monitoring_port = InfrastructureFactory.create_monitoring_port(sample_config, None)
        instance_repo = InfrastructureFactory.create_service_instance_repository(mock_kv_store)
        sdk_monitoring = InfrastructureFactory.create_sdk_monitoring_port(mock_kv_store)

        # Assert - check that required methods exist
        assert hasattr(config_port, "load_configuration")
        assert hasattr(config_port, "validate_configuration")
        assert hasattr(monitoring_port, "get_health_status")
        assert hasattr(instance_repo, "get_all_instances")
        assert hasattr(sdk_monitoring, "run_tests")
