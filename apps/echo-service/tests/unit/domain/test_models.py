"""Unit tests for domain models.

Tests for domain entities, value objects, and business logic
following TDD principles.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.domain.models import (
    EchoMode,
    EchoRequest,
    EchoResponse,
    ServiceDefinitionInfo,
    ServiceRegistrationData,
)
from pydantic import ValidationError


class TestEchoRequest:
    """Test cases for EchoRequest value object."""

    def test_valid_request_creation(self):
        """Test creating a valid echo request."""
        request = EchoRequest(
            message="Hello World",
            mode="simple",
            delay=0.5,
        )
        assert request.message == "Hello World"
        assert request.mode == EchoMode.SIMPLE
        assert request.delay == 0.5

    def test_mode_enum_conversion(self):
        """Test that string mode is converted to enum."""
        request = EchoRequest(message="test", mode="reverse")
        assert request.mode == EchoMode.REVERSE
        assert isinstance(request.mode, EchoMode)

    def test_default_values(self):
        """Test default values for optional fields."""
        request = EchoRequest(message="test")
        assert request.mode == EchoMode.SIMPLE
        assert request.delay == 0

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="test", mode="invalid_mode")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "mode" in str(errors[0])

    def test_empty_message_raises_error(self):
        """Test that empty message raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "message" in str(errors[0])

    def test_negative_delay_raises_error(self):
        """Test that negative delay raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="test", delay=-1)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "delay" in str(errors[0])

    def test_excessive_delay_raises_error(self):
        """Test that delay over 10 seconds raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoRequest(message="test", delay=11)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "delay" in str(errors[0])

    def test_model_immutability(self):
        """Test that model is frozen and immutable."""
        request = EchoRequest(message="test")
        with pytest.raises(ValidationError):
            request.message = "modified"


class TestEchoResponse:
    """Test cases for EchoResponse value object."""

    def test_valid_response_creation(self):
        """Test creating a valid echo response."""
        response = EchoResponse(
            original="Hello",
            echoed="HELLO",
            mode=EchoMode.UPPERCASE,
            instance_id="echo-service-abc123",
            processing_time_ms=10.5,
        )
        assert response.original == "Hello"
        assert response.echoed == "HELLO"
        assert response.mode == EchoMode.UPPERCASE
        assert response.instance_id == "echo-service-abc123"
        assert response.processing_time_ms == 10.5

    def test_timestamp_auto_generation(self):
        """Test that timestamp is automatically generated."""
        response = EchoResponse(
            original="test",
            echoed="test",
            mode=EchoMode.SIMPLE,
            instance_id="test-123",
            processing_time_ms=1.0,
        )
        assert isinstance(response.timestamp, datetime)
        assert response.timestamp.tzinfo == UTC

    def test_custom_timestamp(self):
        """Test providing custom timestamp."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        response = EchoResponse(
            original="test",
            echoed="test",
            mode=EchoMode.SIMPLE,
            instance_id="test-123",
            processing_time_ms=1.0,
            timestamp=custom_time,
        )
        assert response.timestamp == custom_time

    def test_negative_processing_time_raises_error(self):
        """Test that negative processing time raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EchoResponse(
                original="test",
                echoed="test",
                mode=EchoMode.SIMPLE,
                instance_id="test-123",
                processing_time_ms=-1,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "processing_time_ms" in str(errors[0])

    def test_model_immutability(self):
        """Test that model is frozen and immutable."""
        response = EchoResponse(
            original="test",
            echoed="test",
            mode=EchoMode.SIMPLE,
            instance_id="test-123",
            processing_time_ms=1.0,
        )
        with pytest.raises(ValidationError):
            response.echoed = "modified"


class TestServiceDefinitionInfo:
    """Test cases for ServiceDefinitionInfo value object."""

    def test_valid_service_definition_creation(self):
        """Test creating a valid service definition."""
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
        """Test service name format validation."""
        # Valid names
        valid_names = [
            "echo-service",
            "test",
            "service123",
            "my-awesome-service",
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
        invalid_names = [
            "Echo-Service",  # uppercase
            "-service",  # starts with dash
            "service-",  # ends with dash
            "service--name",  # double dash
            "my_service",  # underscore
            "a",  # too short
            "a" * 65,  # too long
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ServiceDefinitionInfo(
                    service_name=name,
                    owner="Team",
                    description="Test",
                    version="1.0.0",
                )

    def test_version_validation(self):
        """Test semantic version validation."""
        # Valid versions
        valid_versions = ["1.0.0", "0.0.1", "10.20.30", "999.999.999"]
        for version in valid_versions:
            definition = ServiceDefinitionInfo(
                service_name="test",
                owner="Team",
                description="Test",
                version=version,
            )
            assert definition.version == version

        # Invalid versions
        invalid_versions = [
            "1.0",  # missing patch
            "1.0.0.0",  # too many parts
            "v1.0.0",  # prefix
            "1.0.0-beta",  # suffix
            "01.0.0",  # leading zero
        ]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                ServiceDefinitionInfo(
                    service_name="test",
                    owner="Team",
                    description="Test",
                    version=version,
                )

    def test_empty_fields_raise_error(self):
        """Test that empty required fields raise validation errors."""
        with pytest.raises(ValidationError):
            ServiceDefinitionInfo(
                service_name="test",
                owner="",  # empty owner
                description="Test",
                version="1.0.0",
            )

        with pytest.raises(ValidationError):
            ServiceDefinitionInfo(
                service_name="test",
                owner="Team",
                description="",  # empty description
                version="1.0.0",
            )

    def test_model_immutability(self):
        """Test that model is frozen and immutable."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )
        with pytest.raises(ValidationError):
            definition.service_name = "modified"


class TestServiceRegistrationData:
    """Test cases for ServiceRegistrationData aggregate."""

    def test_valid_registration_data_creation(self):
        """Test creating valid service registration data."""
        definition = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="Platform Team",
            description="Echo service",
            version="1.0.0",
        )

        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="echo-service-abc123",
            nats_url="nats://localhost:4222",
        )

        assert registration.definition == definition
        assert registration.instance_id == "echo-service-abc123"
        assert registration.nats_url == "nats://localhost:4222"

    def test_timestamps_auto_generation(self):
        """Test that timestamps are automatically generated."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )

        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="test-123",
            nats_url="nats://localhost:4222",
        )

        assert isinstance(registration.created_at, datetime)
        assert isinstance(registration.updated_at, datetime)
        assert registration.created_at.tzinfo == UTC
        assert registration.updated_at.tzinfo == UTC
        assert registration.updated_at >= registration.created_at

    def test_nats_url_validation(self):
        """Test NATS URL format validation."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )

        # Valid URLs
        valid_urls = [
            "nats://localhost:4222",
            "nats://nats.example.com:4222",
            "tls://secure.nats.com:4222",
        ]
        for url in valid_urls:
            registration = ServiceRegistrationData(
                definition=definition,
                instance_id="test-123",
                nats_url=url,
            )
            assert registration.nats_url == url

        # Invalid URLs
        invalid_urls = [
            "http://localhost:4222",  # wrong protocol
            "localhost:4222",  # missing protocol
            "nats://",  # incomplete
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                ServiceRegistrationData(
                    definition=definition,
                    instance_id="test-123",
                    nats_url=url,
                )

    def test_to_service_definition_dict(self):
        """Test conversion to ServiceDefinition dict for monitor-api."""
        definition = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="Platform Team",
            description="Echo service",
            version="1.0.0",
        )

        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="echo-service-abc123",
            nats_url="nats://localhost:4222",
        )

        service_def_dict = registration.to_service_definition_dict()

        assert service_def_dict["service_name"] == "echo-service"
        assert service_def_dict["owner"] == "Platform Team"
        assert service_def_dict["description"] == "Echo service"
        assert service_def_dict["version"] == "1.0.0"
        assert "created_at" in service_def_dict
        assert "updated_at" in service_def_dict
        # Should be ISO format strings
        assert isinstance(service_def_dict["created_at"], str)
        assert isinstance(service_def_dict["updated_at"], str)
        assert "T" in service_def_dict["created_at"]  # ISO format check
        assert "T" in service_def_dict["updated_at"]  # ISO format check

    def test_model_immutability(self):
        """Test that model is frozen and immutable."""
        definition = ServiceDefinitionInfo(
            service_name="test",
            owner="Team",
            description="Test",
            version="1.0.0",
        )

        registration = ServiceRegistrationData(
            definition=definition,
            instance_id="test-123",
            nats_url="nats://localhost:4222",
        )

        with pytest.raises(ValidationError):
            registration.instance_id = "modified"
