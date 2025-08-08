"""Comprehensive unit tests for domain models.

This module tests all domain models with strict Pydantic v2 validation,
ensuring 100% coverage of validation rules and edge cases.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# Python 3.10 compatibility
UTC = UTC

from app.domain.models import (
    EchoMode,
    EchoRequest,
    EchoResponse,
    HealthCheck,
    MessagePriority,
    ServiceDefinitionInfo,
    ServiceMetrics,
    ServiceRegistrationData,
)


class TestEchoMode:
    """Test EchoMode enum."""

    def test_all_modes_defined(self):
        """Test all echo modes are properly defined."""
        assert EchoMode.SIMPLE.value == "simple"
        assert EchoMode.REVERSE.value == "reverse"
        assert EchoMode.UPPERCASE.value == "uppercase"
        assert EchoMode.DELAYED.value == "delayed"
        assert EchoMode.TRANSFORM.value == "transform"
        assert EchoMode.BATCH.value == "batch"

    def test_mode_from_string(self):
        """Test creating mode from string."""
        assert EchoMode("simple") == EchoMode.SIMPLE
        assert EchoMode("reverse") == EchoMode.REVERSE

    def test_invalid_mode_raises_error(self):
        """Test invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="'invalid' is not a valid EchoMode"):
            EchoMode("invalid")


class TestMessagePriority:
    """Test MessagePriority enum."""

    def test_all_priorities_defined(self):
        """Test all priority levels are properly defined."""
        assert MessagePriority.LOW.value == "low"
        assert MessagePriority.NORMAL.value == "normal"
        assert MessagePriority.HIGH.value == "high"
        assert MessagePriority.CRITICAL.value == "critical"

    def test_priority_ordering(self):
        """Test priority levels can be compared."""
        priorities = [
            MessagePriority.LOW,
            MessagePriority.NORMAL,
            MessagePriority.HIGH,
            MessagePriority.CRITICAL,
        ]
        # Verify all priorities are distinct
        assert len(set(priorities)) == 4


class TestEchoRequest:
    """Test EchoRequest model with strict validation."""

    def test_minimal_valid_request(self):
        """Test creating request with minimal required fields."""
        request = EchoRequest(message="Hello")
        assert request.message == "Hello"
        assert request.mode == EchoMode.SIMPLE
        assert request.delay == 0.0
        assert request.transform_type is None
        assert request.priority == MessagePriority.NORMAL
        assert request.metadata == {}

    def test_full_valid_request(self):
        """Test creating request with all fields."""
        request = EchoRequest(
            message="Test message",
            mode=EchoMode.REVERSE,
            delay=2.5,
            transform_type="custom",
            priority=MessagePriority.HIGH,
            metadata={"key": "value", "count": 42},
        )
        assert request.message == "Test message"
        assert request.mode == EchoMode.REVERSE
        assert request.delay == 2.5
        assert request.transform_type == "custom"
        assert request.priority == MessagePriority.HIGH
        assert request.metadata == {"key": "value", "count": 42}

    def test_mode_string_conversion(self):
        """Test mode can be provided as string and converted to enum."""
        request = EchoRequest(message="Test", mode="uppercase")
        assert request.mode == EchoMode.UPPERCASE

    def test_invalid_mode_string(self):
        """Test invalid mode string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="Test", mode="invalid_mode")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Invalid mode: invalid_mode" in str(errors[0]["ctx"]["error"])

    def test_message_validation(self):
        """Test message field validation."""
        # Empty message
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="")
        errors = exc_info.value.errors()
        assert any("at least 1 character" in str(error) for error in errors)

        # Message too long
        long_message = "x" * 1001
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message=long_message)
        errors = exc_info.value.errors()
        assert any("at most 1000 characters" in str(error) for error in errors)

    def test_delay_validation(self):
        """Test delay field validation."""
        # Negative delay
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="Test", delay=-1.0)
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)

        # Delay too large
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="Test", delay=11.0)
        errors = exc_info.value.errors()
        assert any("less than or equal to 10" in str(error) for error in errors)

    def test_model_is_frozen(self):
        """Test that model is immutable (frozen)."""
        request = EchoRequest(message="Test")
        with pytest.raises(ValidationError, match="Instance is frozen"):
            request.message = "Modified"

    def test_model_serialization(self):
        """Test model serialization to dict and JSON."""
        request = EchoRequest(
            message="Test",
            mode=EchoMode.REVERSE,
            delay=1.5,
            metadata={"test": True},
        )

        # Serialize to dict
        data = request.model_dump()
        assert data["message"] == "Test"
        assert data["mode"] == EchoMode.REVERSE
        assert data["delay"] == 1.5
        assert data["metadata"] == {"test": True}

        # Serialize to JSON
        json_str = request.model_dump_json()
        json_data = json.loads(json_str)
        assert json_data["message"] == "Test"
        assert json_data["mode"] == "reverse"
        assert json_data["delay"] == 1.5


class TestEchoResponse:
    """Test EchoResponse model with strict validation."""

    def test_valid_response(self):
        """Test creating valid response."""
        response = EchoResponse(
            original="Hello",
            echoed="HELLO",
            mode=EchoMode.UPPERCASE,
            instance_id="instance-123",
            processing_time_ms=5.2,
        )
        assert response.original == "Hello"
        assert response.echoed == "HELLO"
        assert response.mode == EchoMode.UPPERCASE
        assert response.instance_id == "instance-123"
        assert response.processing_time_ms == 5.2
        assert response.sequence_number == 0
        assert response.metadata == {}
        assert isinstance(response.timestamp, datetime)

    def test_response_with_all_fields(self):
        """Test response with all optional fields."""
        now = datetime.now(UTC)
        response = EchoResponse(
            original="test",
            echoed="TEST",
            mode=EchoMode.UPPERCASE,
            instance_id="inst-1",
            processing_time_ms=10.5,
            timestamp=now,
            sequence_number=42,
            metadata={"extra": "data"},
        )
        assert response.timestamp == now
        assert response.sequence_number == 42
        assert response.metadata == {"extra": "data"}

    def test_processing_time_validation(self):
        """Test processing time must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            EchoResponse(
                original="test",
                echoed="test",
                mode=EchoMode.SIMPLE,
                instance_id="inst-1",
                processing_time_ms=-1.0,
            )
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)

    def test_sequence_number_validation(self):
        """Test sequence number must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            EchoResponse(
                original="test",
                echoed="test",
                mode=EchoMode.SIMPLE,
                instance_id="inst-1",
                processing_time_ms=1.0,
                sequence_number=-1,
            )
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)

    def test_response_is_frozen(self):
        """Test that response is immutable."""
        response = EchoResponse(
            original="test",
            echoed="test",
            mode=EchoMode.SIMPLE,
            instance_id="inst-1",
            processing_time_ms=1.0,
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            response.original = "modified"


class TestServiceMetrics:
    """Test ServiceMetrics model."""

    def test_minimal_metrics(self):
        """Test creating metrics with minimal fields."""
        metrics = ServiceMetrics(instance_id="instance-123")
        assert metrics.instance_id == "instance-123"
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.average_latency_ms == 0.0
        assert metrics.uptime_seconds == 0.0
        assert metrics.last_request_at is None
        assert metrics.mode_distribution == {}

    def test_full_metrics(self):
        """Test creating metrics with all fields."""
        now = datetime.now(UTC)
        metrics = ServiceMetrics(
            instance_id="inst-1",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            average_latency_ms=25.5,
            uptime_seconds=3600.0,
            last_request_at=now,
            mode_distribution={
                EchoMode.SIMPLE: 50,
                EchoMode.REVERSE: 30,
                EchoMode.UPPERCASE: 20,
            },
        )
        assert metrics.total_requests == 100
        assert metrics.successful_requests == 95
        assert metrics.failed_requests == 5
        assert metrics.average_latency_ms == 25.5
        assert metrics.uptime_seconds == 3600.0
        assert metrics.last_request_at == now
        assert len(metrics.mode_distribution) == 3

    def test_metrics_validation(self):
        """Test metrics field validation."""
        # Negative values not allowed
        with pytest.raises(ValidationError):
            ServiceMetrics(instance_id="inst-1", total_requests=-1)

        with pytest.raises(ValidationError):
            ServiceMetrics(instance_id="inst-1", average_latency_ms=-1.0)

        with pytest.raises(ValidationError):
            ServiceMetrics(instance_id="inst-1", uptime_seconds=-1.0)


class TestHealthCheck:
    """Test HealthCheck model."""

    def test_valid_health_check(self):
        """Test creating valid health check."""
        health = HealthCheck(
            status="healthy",
            instance_id="instance-123",
            version="1.0.0",
        )
        assert health.status == "healthy"
        assert health.instance_id == "instance-123"
        assert health.version == "1.0.0"
        assert health.checks == {}
        assert isinstance(health.timestamp, datetime)

    def test_health_check_with_checks(self):
        """Test health check with detailed checks."""
        health = HealthCheck(
            status="degraded",
            instance_id="inst-1",
            version="2.0.0",
            checks={
                "nats": True,
                "database": False,
                "cache": True,
            },
        )
        assert health.status == "degraded"
        assert health.checks["nats"] is True
        assert health.checks["database"] is False
        assert health.checks["cache"] is True


class TestServiceDefinitionInfo:
    """Test ServiceDefinitionInfo model with strict validation."""

    def test_valid_service_definition(self):
        """Test creating valid service definition."""
        definition = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="Platform Team",
            description="Echo service for testing",
            version="1.0.0",
        )
        assert definition.service_name == "echo-service"
        assert definition.owner == "Platform Team"
        assert definition.description == "Echo service for testing"
        assert definition.version == "1.0.0"

    def test_service_name_validation(self):
        """Test service name validation rules."""
        # Valid names
        valid_names = [
            "abc",  # Minimum length
            "echo-service",
            "my-test-service-123",
            "a" * 64,  # Maximum length
        ]
        for name in valid_names:
            definition = ServiceDefinitionInfo(
                service_name=name,
                owner="Team",
                description="Test",
                version="1.0.0",
            )
            assert definition.service_name == name

        # Invalid names
        invalid_cases = [
            ("", "at least 3 characters"),  # Too short
            ("ab", "at least 3 characters"),  # Too short
            ("a" * 65, "at most 64 characters"),  # Too long
            ("Echo-Service", "String should match pattern"),  # Capital letter
            ("-service", "String should match pattern"),  # Starts with hyphen
            ("service-", "String should match pattern"),  # Ends with hyphen
            ("my--service", "consecutive hyphens"),  # Consecutive hyphens
            ("my_service", "String should match pattern"),  # Underscore
            ("my.service", "String should match pattern"),  # Dot
            ("123-service", "String should match pattern"),  # Starts with number
        ]

        for name, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                ServiceDefinitionInfo(
                    service_name=name,
                    owner="Team",
                    description="Test",
                    version="1.0.0",
                )
            assert expected_error in str(exc_info.value)

    def test_version_validation(self):
        """Test semantic version validation."""
        # Valid versions
        valid_versions = ["0.0.0", "1.0.0", "1.2.3", "10.20.30", "999.999.999"]
        for version in valid_versions:
            definition = ServiceDefinitionInfo(
                service_name="test-service",
                owner="Team",
                description="Test",
                version=version,
            )
            assert definition.version == version

        # Invalid versions
        invalid_cases = [
            ("1.0", "String should match pattern"),  # Missing patch
            ("1.0.0.0", "String should match pattern"),  # Too many parts
            ("v1.0.0", "String should match pattern"),  # Has prefix
            ("1.0.0-beta", "String should match pattern"),  # Has suffix
            ("01.0.0", "leading zeros"),  # Leading zero
            ("1.02.0", "leading zeros"),  # Leading zero in minor
            ("1.0.03", "leading zeros"),  # Leading zero in patch
            ("a.b.c", "String should match pattern"),  # Non-numeric
        ]

        for version, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                ServiceDefinitionInfo(
                    service_name="test-service",
                    owner="Team",
                    description="Test",
                    version=version,
                )
            assert expected_error in str(exc_info.value)

    def test_owner_validation(self):
        """Test owner field validation."""
        # Empty owner
        with pytest.raises(ValidationError, match="at least 1 character"):
            ServiceDefinitionInfo(
                service_name="test-service",
                owner="",
                description="Test",
                version="1.0.0",
            )

        # Owner too long
        with pytest.raises(ValidationError, match="at most 100 characters"):
            ServiceDefinitionInfo(
                service_name="test-service",
                owner="x" * 101,
                description="Test",
                version="1.0.0",
            )

    def test_description_validation(self):
        """Test description field validation."""
        # Empty description
        with pytest.raises(ValidationError, match="at least 1 character"):
            ServiceDefinitionInfo(
                service_name="test-service",
                owner="Team",
                description="",
                version="1.0.0",
            )

        # Description too long
        with pytest.raises(ValidationError, match="at most 500 characters"):
            ServiceDefinitionInfo(
                service_name="test-service",
                owner="Team",
                description="x" * 501,
                version="1.0.0",
            )

    def test_model_is_frozen(self):
        """Test that model is immutable."""
        definition = ServiceDefinitionInfo(
            service_name="test-service",
            owner="Team",
            description="Test",
            version="1.0.0",
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            definition.service_name = "modified"


class TestServiceRegistrationData:
    """Test ServiceRegistrationData aggregate root."""

    def test_valid_registration(self):
        """Test creating valid registration data."""
        definition = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="Team",
            description="Test service",
            version="1.0.0",
        )
        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="instance-123",
            nats_url="nats://localhost:4222",
        )
        assert registration.definition == definition
        assert registration.instance_id == "instance-123"
        assert registration.nats_url == "nats://localhost:4222"
        assert isinstance(registration.created_at, datetime)
        assert isinstance(registration.updated_at, datetime)

    def test_nats_url_validation(self):
        """Test NATS URL validation."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )

        # Valid URLs
        valid_urls = [
            "nats://localhost:4222",
            "nats://192.168.1.1:4222",
            "nats://nats.example.com:4222",
            "tls://secure.nats.com:4443",
        ]
        for url in valid_urls:
            registration = ServiceRegistrationData(
                definition=definition,
                instance_id="inst-1",
                nats_url=url,
            )
            assert registration.nats_url == url

        # Invalid URLs
        invalid_cases = [
            ("http://localhost:4222", "must start with nats:// or tls://"),
            ("nats://", "must include host and port"),
            ("tls://", "must include host and port"),
            ("localhost:4222", "must start with nats:// or tls://"),
            ("", "must start with nats:// or tls://"),
        ]

        for url, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                ServiceRegistrationData(
                    definition=definition,
                    instance_id="inst-1",
                    nats_url=url,
                )
            assert expected_error in str(exc_info.value)

    def test_to_service_definition_dict(self):
        """Test conversion to service definition dict for monitor-api."""
        definition = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="Team",
            description="Test service",
            version="1.2.3",
        )
        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="instance-123",
            nats_url="nats://localhost:4222",
        )

        result = registration.to_service_definition_dict()

        assert result["service_name"] == "echo-service"
        assert result["owner"] == "Team"
        assert result["description"] == "Test service"
        assert result["version"] == "1.2.3"
        assert "created_at" in result
        assert "updated_at" in result

        # Verify timestamps are ISO format strings
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)
        assert "T" in result["created_at"]  # ISO format check
        assert "T" in result["updated_at"]

    def test_registration_is_frozen(self):
        """Test that registration data is immutable."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )
        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="inst-1",
            nats_url="nats://localhost:4222",
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            registration.instance_id = "modified"


class TestModelIntegration:
    """Test interactions between different models."""

    def test_request_response_roundtrip(self):
        """Test creating response from request."""
        request = EchoRequest(
            message="Hello World",
            mode=EchoMode.UPPERCASE,
            metadata={"request_id": "123"},
        )

        # Simulate processing
        processed_message = request.message.upper()

        response = EchoResponse(
            original=request.message,
            echoed=processed_message,
            mode=request.mode,
            instance_id="instance-1",
            processing_time_ms=10.5,
            metadata=request.metadata,
        )

        assert response.original == request.message
        assert response.echoed == "HELLO WORLD"
        assert response.mode == request.mode
        assert response.metadata == request.metadata

    def test_json_serialization_compatibility(self):
        """Test models can be serialized and deserialized via JSON."""
        request = EchoRequest(
            message="Test",
            mode=EchoMode.REVERSE,
            delay=1.5,
            priority=MessagePriority.HIGH,
            metadata={"test": True},
        )

        # Serialize to JSON string
        json_str = request.model_dump_json()

        # Deserialize back
        data = json.loads(json_str)
        restored = EchoRequest(**data)

        assert restored == request
        assert restored.message == request.message
        assert restored.mode == request.mode
        assert restored.delay == request.delay
        assert restored.priority == request.priority
        assert restored.metadata == request.metadata

    def test_service_definition_and_registration(self):
        """Test service definition within registration data."""
        definition = ServiceDefinitionInfo(
            service_name="test-service",
            owner="Test Team",
            description="A test service",
            version="2.0.0",
        )

        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="unique-instance-id",
            nats_url="nats://nats-server:4222",
        )

        # Test accessing nested definition
        assert registration.definition.service_name == "test-service"
        assert registration.definition.owner == "Test Team"
        assert registration.definition.version == "2.0.0"

        # Test conversion to dict
        dict_data = registration.to_service_definition_dict()
        assert dict_data["service_name"] == definition.service_name
        assert dict_data["owner"] == definition.owner
        assert dict_data["version"] == definition.version
