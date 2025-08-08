"""Integration tests to improve code coverage.

These tests exercise the main application flow and
infrastructure components to increase overall coverage.
"""

from __future__ import annotations

import os
from datetime import UTC
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.models import ServiceConfiguration
from app.infrastructure.configuration_adapter import EnvironmentConfigurationAdapter
from app.utils.timezone import convert_to_utc8, now_utc8

if TYPE_CHECKING:
    pass


class TestIntegrationCoverage:
    """Integration tests to boost coverage."""

    @pytest.mark.asyncio
    async def test_configuration_adapter_integration(self) -> None:
        """Test configuration adapter with different environments."""
        # Test default configuration
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvironmentConfigurationAdapter()
            config = adapter.load_configuration()
            assert config.environment == "development"
            assert config.log_level == "INFO"
            assert config.api_port == 8100

        # Test production configuration
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "NATS_URL": "nats://prod-nats:4222",
                "API_PORT": "8080",
                "LOG_LEVEL": "WARNING",
            },
        ):
            adapter = EnvironmentConfigurationAdapter()
            config = adapter.load_configuration()
            assert config.environment == "production"
            assert config.nats_url == "nats://prod-nats:4222"
            assert config.api_port == 8080
            assert config.log_level == "WARNING"

        # Test staging configuration
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            adapter = EnvironmentConfigurationAdapter()
            config = adapter.load_configuration()
            assert config.environment == "staging"

    def test_timezone_utilities(self) -> None:
        """Test timezone utility functions."""
        # Test now_utc8
        beijing_time = now_utc8()
        assert beijing_time.tzinfo is not None
        assert beijing_time.tzinfo.utcoffset(None).total_seconds() == 28800  # UTC+8

        # Test convert_to_utc8
        from datetime import datetime

        utc_time = datetime.now(UTC)
        beijing_time = convert_to_utc8(utc_time)
        assert beijing_time.tzinfo is not None
        assert beijing_time.tzinfo.utcoffset(None).total_seconds() == 28800

        # Test parse_iso_to_utc8
        from app.utils.timezone import parse_iso_to_utc8

        parsed = parse_iso_to_utc8("2024-01-01T00:00:00Z")
        assert parsed.tzinfo is not None
        assert parsed.tzinfo.utcoffset(None).total_seconds() == 28800

    @pytest.mark.asyncio
    async def test_service_instance_repository_error_paths(self) -> None:
        """Test error handling in service instance repository."""
        from app.infrastructure.service_instance_repository_adapter import (
            ServiceInstanceRepositoryAdapter,
        )

        mock_kv = Mock()
        mock_kv.ls = AsyncMock(side_effect=Exception("KV error"))
        mock_kv.get = AsyncMock()

        repo = ServiceInstanceRepositoryAdapter(mock_kv)

        # Test error handling
        from app.domain.exceptions import KVStoreException

        with pytest.raises(KVStoreException):
            await repo.get_all_instances()

    def test_domain_model_properties(self) -> None:
        """Test domain model properties and methods."""
        from datetime import datetime

        from app.domain.models import DetailedHealthStatus, HealthStatus, SystemStatus

        # Test HealthStatus
        health = HealthStatus(
            status="healthy",
            service_name="test",
            version="1.0.0",
            nats_url="nats://localhost:4222",
            timestamp=datetime.now(),
        )
        assert health.status == "healthy"

        # Test SystemStatus
        system = SystemStatus(
            timestamp=datetime.now(),
            uptime_seconds=3600.0,
            environment="production",
            connected_services=5,
            deployment_version="v1.0.0",
            start_time=datetime.now(),
        )
        assert system.uptime_seconds == 3600.0

        # Test DetailedHealthStatus
        detailed = DetailedHealthStatus(
            status="healthy",
            service_name="test",
            version="1.0.0",
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_usage_percent=70.0,
            nats_status="healthy",
            nats_latency_ms=10.0,
            timestamp=datetime.now(),
        )
        assert detailed.cpu_percent == 50.0

    def test_exception_classes(self) -> None:
        """Test exception class instantiation."""
        from app.domain.exceptions import (
            ConfigurationException,
            HealthCheckFailedException,
            KVStoreException,
            ServiceNotFoundException,
            ServiceRegistryException,
            ServiceUnavailableException,
        )

        # Test each exception
        config_exc = ConfigurationException("Config error")
        assert str(config_exc) == "Config error"

        health_exc = HealthCheckFailedException("Health check failed")
        assert str(health_exc) == "Health check failed"

        not_found_exc = ServiceNotFoundException("test-service")
        assert str(not_found_exc) == "Service 'test-service' not found"
        assert not_found_exc.key == "test-service"

        unavail_exc = ServiceUnavailableException("Service unavailable")
        assert str(unavail_exc) == "Service unavailable"

        kv_exc = KVStoreException("KV store error")
        assert str(kv_exc) == "KV store error"

        registry_exc = ServiceRegistryException("Registry error")
        assert str(registry_exc) == "Registry error"

    @pytest.mark.asyncio
    async def test_monitoring_port_abstract_methods(self) -> None:
        """Test monitoring port interface."""
        from app.ports.monitoring import MonitoringPort

        # Create a concrete implementation for testing
        class TestMonitoringPort(MonitoringPort):
            async def check_health(self):
                return Mock()

            async def get_system_status(self):
                return Mock()

            async def get_start_time(self):
                from datetime import datetime

                return datetime.now()

            async def is_ready(self):
                return True

            async def get_detailed_health(self):
                return Mock()

        port = TestMonitoringPort()
        assert await port.is_ready() is True

    @pytest.mark.asyncio
    async def test_configuration_port_abstract_methods(self) -> None:
        """Test configuration port interface."""
        from app.ports.configuration import ConfigurationPort

        # Create a concrete implementation for testing
        class TestConfigurationPort(ConfigurationPort):
            def load_configuration(self):
                return Mock()

            def validate_configuration(self, config):
                pass

        port = TestConfigurationPort()
        config = port.load_configuration()
        assert config is not None

    @pytest.mark.asyncio
    async def test_service_instance_service_edge_cases(self) -> None:
        """Test edge cases in service instance service."""
        from datetime import datetime

        from app.application.service_instance_service import ServiceInstanceService
        from app.domain.models import ServiceInstance

        mock_repo = Mock()
        service = ServiceInstanceService(mock_repo)

        # Test stale instances with timezone-naive datetime
        naive_instance = ServiceInstance(
            service_name="test",
            instance_id="123",
            host="localhost",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(),  # Naive datetime
            metadata={},
        )

        mock_repo.get_all_instances = AsyncMock(return_value=[naive_instance])
        stale = await service.get_stale_instances(threshold_minutes=0)
        assert len(stale) == 1  # Should handle naive datetime

    @pytest.mark.asyncio
    async def test_service_registry_service_coverage(self) -> None:
        """Test service registry service methods."""
        from app.application.service_registry_service import ServiceRegistryService
        from app.domain.models import ServiceDefinition

        mock_kv = Mock()
        service = ServiceRegistryService(mock_kv)

        # Test create_or_update_service
        definition = ServiceDefinition(
            service_name="test-service",
            description="Test service",
            version="1.0.0",
            endpoints=["echo", "health"],
            metadata={"type": "rpc"},
        )

        mock_kv.put = AsyncMock()
        result = await service.create_or_update_service(definition)
        assert result == definition

        # Test delete_service
        mock_kv.delete = AsyncMock()
        deleted = await service.delete_service("test-service")
        assert deleted is True

        # Test delete non-existent service
        mock_kv.delete = AsyncMock(side_effect=Exception("Not found"))
        deleted = await service.delete_service("unknown-service")
        assert deleted is False

    def test_domain_model_edge_cases(self) -> None:
        """Test domain model edge cases for coverage."""
        from datetime import datetime

        from app.domain.models import ServiceDefinition, ServiceInstanceLog

        # Test ServiceConfiguration with all fields
        config = ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="DEBUG",
            environment="development",
        )
        assert config.api_port == 8080

        # Test ServiceDefinition model_dump
        definition = ServiceDefinition(
            service_name="test",
            description="Test service",
            version="1.0.0",
            endpoints=["test"],
            metadata={},
        )
        dumped = definition.model_dump()
        assert dumped["service_name"] == "test"

        # Test ServiceInstanceLog
        log = ServiceInstanceLog(
            service_name="test",
            instance_id="123",
            timestamp=datetime.now(),
            level="INFO",
            message="Test log",
            metadata={"key": "value"},
        )
        assert log.level == "INFO"

    @pytest.mark.asyncio
    async def test_service_routes_coverage(self) -> None:
        """Test service routes error paths."""
        from app.domain.exceptions import ServiceRegistryException
        from app.infrastructure.api.service_routes import (
            delete_service,
            get_service,
        )

        # Mock service registry
        mock_registry = Mock()

        # Test get_service not found
        mock_registry.get_service_definition = AsyncMock(return_value=None)

        with patch(
            "app.infrastructure.api.service_routes.get_service_registry", return_value=mock_registry
        ):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await get_service("unknown-service", service_registry=mock_registry)
            assert exc_info.value.status_code == 404

        # Test delete_service error
        mock_registry.delete_service = AsyncMock(
            side_effect=ServiceRegistryException("Delete failed")
        )

        with patch(
            "app.infrastructure.api.service_routes.get_service_registry", return_value=mock_registry
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_service("test-service", service_registry=mock_registry)
            assert exc_info.value.status_code == 500

    def test_model_validators(self) -> None:
        """Test Pydantic model validators."""
        from pydantic import ValidationError

        # Test invalid environment
        with pytest.raises(ValidationError):
            ServiceConfiguration(
                nats_url="nats://localhost:4222",
                api_port=8080,
                log_level="INFO",
                environment="invalid",
            )

        # Test invalid log level
        with pytest.raises(ValidationError):
            ServiceConfiguration(
                nats_url="nats://localhost:4222",
                api_port=8080,
                log_level="INVALID",
                environment="development",
            )
