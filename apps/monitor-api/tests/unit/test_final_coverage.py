"""Final tests to reach 80% coverage target.

These tests focus on remaining uncovered areas.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.domain.models import ServiceConfiguration
from app.infrastructure.configuration_adapter import EnvironmentConfigurationAdapter

if TYPE_CHECKING:
    pass


class TestFinalCoverage:
    """Final tests to reach coverage target."""

    @pytest.mark.asyncio
    async def test_configuration_adapter_privileged_port(self) -> None:
        """Test configuration adapter with privileged ports."""
        # Test non-root user trying to use privileged port
        with patch.dict(os.environ, {"API_PORT": "80"}), patch("os.getuid", return_value=1000):
            adapter = EnvironmentConfigurationAdapter()
            from app.domain.exceptions import ConfigurationException

            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()
            assert "requires root privileges" in str(exc_info.value)

        # Test root user can use privileged port
        with (
            patch.dict(os.environ, {"API_PORT": "443", "ENVIRONMENT": "development"}),
            patch("os.getuid", return_value=0),
        ):
            adapter = EnvironmentConfigurationAdapter()
            config = adapter.load_configuration()
            assert config.api_port == 443

    def test_configuration_adapter_invalid_port(self) -> None:
        """Test invalid port configuration."""
        with patch.dict(os.environ, {"API_PORT": "not-a-number"}):
            adapter = EnvironmentConfigurationAdapter()
            from app.domain.exceptions import ConfigurationException

            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()
            assert "Failed to load configuration" in str(exc_info.value)

    def test_configuration_adapter_tls_nats(self) -> None:
        """Test TLS NATS URL configuration."""
        with patch.dict(os.environ, {"NATS_URL": "tls://secure-nats:4222"}):
            adapter = EnvironmentConfigurationAdapter()
            config = adapter.load_configuration()
            assert config.nats_url == "tls://secure-nats:4222"

    def test_configuration_adapter_production_validation(self) -> None:
        """Test production environment validation."""
        # Test production with localhost - should fail
        with patch.dict(
            os.environ, {"ENVIRONMENT": "production", "NATS_URL": "nats://localhost:4222"}
        ):
            adapter = EnvironmentConfigurationAdapter()
            from app.domain.exceptions import ConfigurationException

            with pytest.raises(ConfigurationException) as exc_info:
                adapter.load_configuration()
            assert "Production environment should not use localhost" in str(exc_info.value)

    def test_configuration_validation_method(self) -> None:
        """Test validate_configuration method."""
        adapter = EnvironmentConfigurationAdapter()

        # Valid config
        valid_config = ServiceConfiguration(
            nats_url="nats://prod-nats:4222",
            api_port=8080,
            log_level="INFO",
            environment="development",
        )
        adapter.validate_configuration(valid_config)  # Should not raise

        # Invalid production config
        invalid_config = ServiceConfiguration(
            nats_url="nats://localhost:4222",
            api_port=8080,
            log_level="INFO",
            environment="production",
        )
        from app.domain.exceptions import ConfigurationException

        with pytest.raises(ConfigurationException) as exc_info:
            adapter.validate_configuration(invalid_config)
        assert "Production environment should not use localhost" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_instance_repository_parse_key(self) -> None:
        """Test service instance repository key parsing."""
        from app.infrastructure.service_instance_repository_adapter import (
            ServiceInstanceRepositoryAdapter,
        )

        adapter = ServiceInstanceRepositoryAdapter(Mock())

        # Test valid key
        service_name, instance_id = adapter._parse_key("service-instances.my-service.instance-123")
        assert service_name == "my-service"
        assert instance_id == "instance-123"

        # Test invalid key
        service_name, instance_id = adapter._parse_key("invalid-key")
        assert service_name == ""
        assert instance_id == ""

    @pytest.mark.asyncio
    async def test_service_instance_repository_parse_instance_data(self) -> None:
        """Test service instance repository data parsing."""
        from app.domain.models import ServiceInstance
        from app.infrastructure.service_instance_repository_adapter import (
            ServiceInstanceRepositoryAdapter,
        )

        adapter = ServiceInstanceRepositoryAdapter(Mock())

        # Test valid data
        valid_data = {
            "service_name": "test-service",
            "instance_id": "test-123",
            "host": "localhost",
            "port": 8080,
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now().isoformat(),
            "metadata": {},
        }
        instance = adapter._parse_instance_data(json.dumps(valid_data))
        assert isinstance(instance, ServiceInstance)
        assert instance.service_name == "test-service"

        # Test invalid JSON
        instance = adapter._parse_instance_data("invalid json")
        assert instance is None

        # Test missing fields
        invalid_data = {"service_name": "test"}
        instance = adapter._parse_instance_data(json.dumps(invalid_data))
        assert instance is None

    @pytest.mark.asyncio
    async def test_service_registry_service_check_health(self) -> None:
        """Test service registry health check."""
        from app.application.service_registry_service import ServiceRegistryService

        mock_kv = Mock()
        service = ServiceRegistryService(mock_kv)

        # Test health check
        mock_kv.get = AsyncMock(return_value=Mock(value=b'{"status": "healthy"}'))
        result = await service.check_service_health("test-service")
        assert result == {"status": "healthy"}

        # Test health check with no data
        mock_kv.get = AsyncMock(return_value=None)
        result = await service.check_service_health("unknown-service")
        assert result == {"status": "unknown", "message": "No health data available"}

    @pytest.mark.asyncio
    async def test_service_registry_service_get_instances(self) -> None:
        """Test service registry get instances."""
        from app.application.service_registry_service import ServiceRegistryService
        from app.domain.models import ServiceInstance

        mock_kv = Mock()
        service = ServiceRegistryService(mock_kv)

        # Mock instance data
        instance_data = {
            "service_name": "test-service",
            "instance_id": "test-123",
            "host": "localhost",
            "port": 8080,
            "version": "1.0.0",
            "status": "ACTIVE",
            "last_heartbeat": datetime.now().isoformat(),
            "metadata": {},
        }

        mock_kv.ls = AsyncMock(return_value=["service-instances.test-service.test-123"])
        mock_kv.get = AsyncMock(return_value=Mock(value=json.dumps(instance_data).encode()))

        instances = await service.get_service_instances("test-service")
        assert len(instances) == 1
        assert isinstance(instances[0], ServiceInstance)

    @pytest.mark.asyncio
    async def test_service_registry_update_metadata_success(self) -> None:
        """Test successful metadata update."""
        from app.application.service_registry_service import ServiceRegistryService
        from app.domain.models import ServiceDefinition

        mock_kv = Mock()
        service = ServiceRegistryService(mock_kv)

        # Mock existing service
        existing_def = ServiceDefinition(
            service_name="test",
            description="Test service",
            version="1.0.0",
            endpoints=["test"],
            metadata={"old": "value"},
        )

        mock_kv.get = AsyncMock(
            return_value=Mock(value=json.dumps(existing_def.model_dump()).encode())
        )
        mock_kv.put = AsyncMock()

        result = await service.update_service_metadata("test", {"new": "value"})
        assert result is not None
        assert result.metadata == {"old": "value", "new": "value"}

    def test_model_json_serialization(self) -> None:
        """Test model JSON serialization."""
        from datetime import datetime

        from app.domain.models import ServiceDefinition, ServiceInstance

        # Test ServiceDefinition to/from JSON
        definition = ServiceDefinition(
            service_name="test",
            description="Test service",
            version="1.0.0",
            endpoints=["test"],
            metadata={"key": "value"},
        )
        json_str = definition.model_dump_json()
        assert "test" in json_str

        # Test ServiceInstance field_serializer
        instance = ServiceInstance(
            service_name="test",
            instance_id="123",
            host="localhost",
            port=8080,
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=datetime.now(),
            metadata={},
        )
        dumped = instance.model_dump(mode="json")
        assert isinstance(dumped["last_heartbeat"], str)

    def test_timezone_edge_cases(self) -> None:
        """Test timezone utility edge cases."""
        from app.utils.timezone import parse_iso_to_utc8

        # Test parsing ISO string with Z suffix
        parsed = parse_iso_to_utc8("2024-01-01T00:00:00Z")
        assert parsed.tzinfo is not None

        # Test parsing ISO string with offset
        parsed = parse_iso_to_utc8("2024-01-01T00:00:00+05:00")
        assert parsed.tzinfo is not None

    def test_exception_inheritance(self) -> None:
        """Test exception class inheritance."""
        from app.domain.exceptions import (
            ConcurrentUpdateException,
            DomainException,
            ServiceAlreadyExistsException,
        )

        # Test base exception
        base_exc = DomainException("Test error", "TEST_CODE")
        assert base_exc.message == "Test error"
        assert base_exc.error_code == "TEST_CODE"

        # Test ConcurrentUpdateException
        exc = ConcurrentUpdateException("test-service")
        assert exc.key == "test-service"
        assert "Concurrent update" in str(exc)

        # Test ServiceAlreadyExistsException
        exc = ServiceAlreadyExistsException("test-service")
        assert exc.key == "test-service"
        assert "already exists" in str(exc)
