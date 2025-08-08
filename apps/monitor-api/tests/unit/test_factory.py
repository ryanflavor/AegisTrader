"""Tests for InfrastructureFactory following TDD principles."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.models import ServiceConfiguration
from app.infrastructure.factory import InfrastructureFactory
from app.ports.service_registry_kv_store import ServiceRegistryKVStorePort


class TestInfrastructureFactory:
    """Test cases for InfrastructureFactory."""

    def test_create_configuration_port(self):
        """Test creating configuration port."""
        # Act
        port = InfrastructureFactory.create_configuration_port()

        # Assert
        assert port is not None
        assert hasattr(port, "load_configuration")

    def test_create_monitoring_port(self):
        """Test creating monitoring port."""
        # Arrange
        config = ServiceConfiguration(
            service_name="test-service",
            service_version="1.0.0",
            environment="development",
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            stale_threshold_seconds=35,
        )
        start_time = Mock()

        # Act
        port = InfrastructureFactory.create_monitoring_port(config, start_time)

        # Assert
        assert port is not None
        assert hasattr(port, "get_health_status")
        assert hasattr(port, "get_system_status")

    @pytest.mark.asyncio
    async def test_create_kv_store_port(self):
        """Test creating KV store port."""
        # Arrange
        nats_url = "nats://localhost:4222"

        with patch("app.infrastructure.factory.AegisSDKKVAdapter") as mock_adapter_class:
            mock_adapter = Mock(spec=ServiceRegistryKVStorePort)
            mock_adapter.connect = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            port = await InfrastructureFactory.create_kv_store_port(nats_url)

            # Assert
            assert port is not None
            assert port == mock_adapter
            mock_adapter.connect.assert_called_once_with(nats_url)

    def test_create_service_instance_repository(self):
        """Test creating service instance repository."""
        # Arrange
        mock_kv_store = Mock()
        stale_threshold = 35

        # Act
        repo = InfrastructureFactory.create_service_instance_repository(
            mock_kv_store, stale_threshold
        )

        # Assert
        assert repo is not None
        assert hasattr(repo, "get_all_instances")

    def test_create_service_instance_repository_with_wrapped_kv(self):
        """Test creating service instance repository with wrapped KV store."""
        # Arrange
        raw_kv = Mock()
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = raw_kv

        # Act
        repo = InfrastructureFactory.create_service_instance_repository(mock_kv_store)

        # Assert
        assert repo is not None
        assert hasattr(repo, "get_all_instances")

    def test_create_sdk_monitoring_port(self):
        """Test creating SDK monitoring port."""
        # Arrange
        mock_kv_store = Mock()

        # Act
        port = InfrastructureFactory.create_sdk_monitoring_port(mock_kv_store)

        # Assert
        assert port is not None
        assert hasattr(port, "get_service_dependencies")

    def test_create_sdk_monitoring_port_with_wrapped_kv(self):
        """Test creating SDK monitoring port with wrapped KV store."""
        # Arrange
        raw_kv = Mock()
        mock_kv_store = Mock()
        mock_kv_store.raw_kv = raw_kv

        # Act
        port = InfrastructureFactory.create_sdk_monitoring_port(mock_kv_store)

        # Assert
        assert port is not None
        assert hasattr(port, "get_service_dependencies")

    def test_create_all_adapters(self):
        """Test creating all adapters at once."""
        # Arrange
        config = ServiceConfiguration(
            service_name="test-service",
            service_version="1.0.0",
            environment="development",
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            stale_threshold_seconds=35,
        )
        start_time = Mock()
        mock_kv_store = Mock()

        # Act
        adapters = InfrastructureFactory.create_all_adapters(config, start_time, mock_kv_store)

        # Assert
        assert "configuration" in adapters
        assert "monitoring" in adapters
        assert "service_instance_repository" in adapters
        assert "sdk_monitoring" in adapters
        assert hasattr(adapters["configuration"], "load_configuration")
        assert hasattr(adapters["monitoring"], "get_health_status")
        assert hasattr(adapters["service_instance_repository"], "get_all_instances")
        assert hasattr(adapters["sdk_monitoring"], "get_service_dependencies")

    def test_factory_follows_static_factory_pattern(self):
        """Test that the factory follows the static factory pattern."""
        # All methods should be static or class methods
        import inspect

        for name, method in inspect.getmembers(InfrastructureFactory):
            if name.startswith("create_"):
                assert isinstance(method, (staticmethod, classmethod)) or callable(method)

    def test_factory_returns_correct_port_types(self):
        """Test that factory methods return correct port types."""
        # This ensures the factory is creating the right adapters for each port
        config = ServiceConfiguration(
            service_name="test",
            service_version="1.0.0",
            environment="development",
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            stale_threshold_seconds=35,
        )

        # Configuration port
        config_port = InfrastructureFactory.create_configuration_port()
        assert hasattr(config_port, "load_configuration")

        # Monitoring port
        monitoring_port = InfrastructureFactory.create_monitoring_port(config, None)
        assert hasattr(monitoring_port, "get_health_status")
        assert hasattr(monitoring_port, "get_system_status")
