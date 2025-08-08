"""Additional tests for domain models to achieve comprehensive coverage.

These tests cover edge cases, validation errors, and serialization scenarios
following TDD principles and Pydantic v2 strict validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from app.domain.models import (
    DetailedHealthStatus,
    HealthStatus,
    ServiceConfiguration,
    ServiceDefinition,
    ServiceInstance,
    SystemStatus,
)
from pydantic import ValidationError

if TYPE_CHECKING:
    pass


class TestHealthStatusEdgeCases:
    """Test edge cases for HealthStatus model."""

    def test_health_status_with_tls_url(self) -> None:
        """Test HealthStatus accepts TLS URLs."""
        status = HealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            nats_url="tls://secure.nats:4222",
        )
        assert status.nats_url == "tls://secure.nats:4222"

    def test_health_status_invalid_url_rejected(self) -> None:
        """Test HealthStatus rejects invalid NATS URLs."""
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(
                status="healthy",
                service_name="test-service",
                version="1.0.0",
                nats_url="http://invalid:4222",
            )
        assert "NATS URL must start with nats:// or tls://" in str(exc_info.value)

    def test_health_status_frozen(self) -> None:
        """Test HealthStatus model is immutable."""
        status = HealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            nats_url="nats://localhost:4222",
        )
        with pytest.raises(ValidationError):
            status.status = "unhealthy"  # type: ignore


class TestSystemStatusValidation:
    """Test SystemStatus validation and edge cases."""

    def test_system_status_negative_uptime_rejected(self) -> None:
        """Test SystemStatus rejects negative uptime."""
        with pytest.raises(ValidationError) as exc_info:
            SystemStatus(
                timestamp=datetime.now(UTC),
                uptime_seconds=-1.0,
                environment="development",
                deployment_version="v1.0.0",
                start_time=datetime.now(UTC),
            )
        # Pydantic v2 uses different error message format
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_system_status_excessive_uptime_rejected(self) -> None:
        """Test SystemStatus rejects unrealistic uptime."""
        with pytest.raises(ValidationError) as exc_info:
            SystemStatus(
                timestamp=datetime.now(UTC),
                uptime_seconds=315576001.0,  # > 10 years
                environment="development",
                deployment_version="v1.0.0",
                start_time=datetime.now(UTC),
            )
        assert "Uptime exceeds reasonable limit" in str(exc_info.value)

    def test_system_status_valid_uptime(self) -> None:
        """Test SystemStatus accepts valid uptime."""
        status = SystemStatus(
            timestamp=datetime.now(UTC),
            uptime_seconds=3600.0,  # 1 hour
            environment="production",
            deployment_version="v2.1.0",
            start_time=datetime.now(UTC),
        )
        assert status.uptime_seconds == 3600.0


class TestServiceConfigurationValidation:
    """Test ServiceConfiguration validation."""

    def test_service_configuration_tls_url(self) -> None:
        """Test ServiceConfiguration accepts TLS NATS URLs."""
        config = ServiceConfiguration(
            nats_url="tls://secure.nats:4222",
            api_port=8080,
            log_level="INFO",
            environment="production",
        )
        assert config.nats_url == "tls://secure.nats:4222"

    def test_service_configuration_invalid_url(self) -> None:
        """Test ServiceConfiguration rejects invalid URLs."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(
                nats_url="invalid://url",
                api_port=8080,
                log_level="INFO",
                environment="development",
            )
        assert "NATS URL must start with nats:// or tls://" in str(exc_info.value)


class TestServiceDefinitionEdgeCases:
    """Test ServiceDefinition edge cases and validation."""

    def test_service_definition_semantic_version_with_leading_zeros(self) -> None:
        """Test version validation rejects leading zeros."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc_info:
            ServiceDefinition(
                service_name="test-service",
                owner="test-team",
                description="Test",
                version="01.0.0",  # Leading zero
                created_at=now,
                updated_at=now,
            )
        assert "Version parts must be numeric without leading zeros" in str(exc_info.value)

    def test_service_definition_invalid_timestamp_format(self) -> None:
        """Test timestamp validation for invalid formats."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceDefinition(
                service_name="test-service",
                owner="test-team",
                description="Test",
                version="1.0.0",
                created_at="2024-01-01",  # Missing time component
                updated_at=datetime.now(UTC),
            )
        assert "Must be ISO 8601 format with time" in str(exc_info.value)

    def test_service_definition_parse_timestamp_with_z(self) -> None:
        """Test parsing timestamps with Z timezone."""
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test",
            version="1.0.0",
            created_at="2024-01-01T12:00:00Z",
            updated_at="2024-01-01T13:00:00Z",
        )
        assert service.created_at.year == 2024
        assert service.updated_at.hour == 13

    def test_service_definition_serialization(self) -> None:
        """Test ServiceDefinition serialization to ISO format."""
        now = datetime.now(UTC)
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )

        # Test to_iso_dict method
        iso_dict = service.to_iso_dict()
        assert isinstance(iso_dict["created_at"], str)
        assert isinstance(iso_dict["updated_at"], str)
        assert "T" in iso_dict["created_at"]


class TestServiceInstanceValidation:
    """Test ServiceInstance validation and edge cases."""

    def test_service_instance_invalid_timestamp_format(self) -> None:
        """Test ServiceInstance rejects invalid timestamp formats."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="test-service",
                instance_id="test-123",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat="invalid-timestamp",
            )
        assert "Invalid timestamp format" in str(exc_info.value)

    def test_service_instance_timestamp_serialization(self) -> None:
        """Test ServiceInstance timestamp serialization."""
        now = datetime.now(UTC)
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-123",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=now,
        )

        # Serialize to dict
        data = instance.model_dump(mode="json")
        assert isinstance(data["last_heartbeat"], str)
        assert "T" in data["last_heartbeat"]

    def test_service_instance_with_aliases(self) -> None:
        """Test ServiceInstance works with field aliases."""
        now = datetime.now(UTC)
        # Using aliases
        instance = ServiceInstance(
            serviceName="test-service",  # alias
            instanceId="test-123",  # alias
            version="1.0.0",
            status="ACTIVE",
            lastHeartbeat=now,  # alias
            stickyActiveGroup="group-1",  # alias
        )
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-123"
        assert instance.sticky_active_group == "group-1"


class TestDetailedHealthStatus:
    """Test DetailedHealthStatus model."""

    def test_detailed_health_status_valid(self) -> None:
        """Test creating valid DetailedHealthStatus."""
        status = DetailedHealthStatus(
            status="healthy",
            service_name="test-service",
            version="1.0.0",
            cpu_percent=45.5,
            memory_percent=60.2,
            disk_usage_percent=75.0,
            nats_status="healthy",
            nats_latency_ms=1.5,
        )
        assert status.cpu_percent == 45.5
        assert status.nats_status == "healthy"

    def test_detailed_health_status_invalid_cpu_percent(self) -> None:
        """Test DetailedHealthStatus rejects invalid CPU percentage."""
        with pytest.raises(ValidationError):
            DetailedHealthStatus(
                status="healthy",
                service_name="test-service",
                version="1.0.0",
                cpu_percent=150.0,  # > 100
                memory_percent=60.2,
                disk_usage_percent=75.0,
                nats_status="healthy",
                nats_latency_ms=1.5,
            )

    def test_detailed_health_status_negative_latency(self) -> None:
        """Test DetailedHealthStatus rejects negative latency."""
        with pytest.raises(ValidationError):
            DetailedHealthStatus(
                status="healthy",
                service_name="test-service",
                version="1.0.0",
                cpu_percent=45.5,
                memory_percent=60.2,
                disk_usage_percent=75.0,
                nats_status="healthy",
                nats_latency_ms=-1.0,  # Negative
            )
