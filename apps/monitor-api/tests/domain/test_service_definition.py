"""Unit tests for ServiceDefinition domain model.

These tests ensure the ServiceDefinition model has proper validation
and follows Pydantic v2 strict mode requirements.
"""

from datetime import UTC, datetime

import pytest
from app.domain.models import ServiceDefinition
from pydantic import ValidationError


class TestServiceDefinition:
    """Test cases for ServiceDefinition model."""

    def test_valid_service_definition(self) -> None:
        """Test creating a valid service definition."""
        # Arrange
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        service_data = {
            "service_name": "payment-service",
            "owner": "payments-team",
            "description": "Handles payment processing",
            "version": "1.0.0",
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        # Act
        service = ServiceDefinition(**service_data)

        # Assert
        assert service.service_name == "payment-service"
        assert service.owner == "payments-team"
        assert service.description == "Handles payment processing"
        assert service.version == "1.0.0"
        # Timestamps are parsed as datetime objects, not strings
        assert isinstance(service.created_at, datetime)
        assert isinstance(service.updated_at, datetime)
        assert service.created_at == now
        assert service.updated_at == now

    def test_service_name_validation(self) -> None:
        """Test service name pattern validation."""
        now = datetime.now(UTC).isoformat()
        base_data = {
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
            "created_at": now,
            "updated_at": now,
        }

        # Valid names
        valid_names = ["api", "payment-service", "user-auth-service", "service123"]
        for name in valid_names:
            service = ServiceDefinition(service_name=name, **base_data)
            assert service.service_name == name

        # Invalid names
        invalid_names = [
            "API",  # Uppercase not allowed
            "payment_service",  # Underscore not allowed
            "123-service",  # Must start with letter
            "-service",  # Must start with letter
            "a",  # Too short (min 3)
            "a" * 65,  # Too long (max 64)
            "service-",  # Can't end with dash
            "",  # Empty not allowed
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ServiceDefinition(service_name=name, **base_data)

    def test_owner_validation(self) -> None:
        """Test owner field validation."""
        now = datetime.now(UTC).isoformat()
        base_data = {
            "service_name": "test-service",
            "description": "Test service",
            "version": "1.0.0",
            "created_at": now,
            "updated_at": now,
        }

        # Valid owner
        service = ServiceDefinition(owner="test-team", **base_data)
        assert service.owner == "test-team"

        # Invalid owners
        with pytest.raises(ValidationError):
            ServiceDefinition(owner="", **base_data)  # Empty

        with pytest.raises(ValidationError):
            ServiceDefinition(owner="a" * 101, **base_data)  # Too long

    def test_description_validation(self) -> None:
        """Test description field validation."""
        now = datetime.now(UTC).isoformat()
        base_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "version": "1.0.0",
            "created_at": now,
            "updated_at": now,
        }

        # Valid description
        service = ServiceDefinition(description="Valid description", **base_data)
        assert service.description == "Valid description"

        # Invalid descriptions
        with pytest.raises(ValidationError):
            ServiceDefinition(description="", **base_data)  # Empty

        with pytest.raises(ValidationError):
            ServiceDefinition(description="a" * 501, **base_data)  # Too long

    def test_version_validation(self) -> None:
        """Test version format validation."""
        now = datetime.now(UTC).isoformat()
        base_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "created_at": now,
            "updated_at": now,
        }

        # Valid versions
        valid_versions = ["1.0.0", "0.0.1", "10.20.30", "999.999.999"]
        for version in valid_versions:
            service = ServiceDefinition(version=version, **base_data)
            assert service.version == version

        # Invalid versions
        invalid_versions = [
            "1.0",  # Missing patch
            "1",  # Missing minor and patch
            "1.0.0.0",  # Too many parts
            "1.0.a",  # Non-numeric
            "v1.0.0",  # Prefix not allowed
            "1.0.0-beta",  # Suffix not allowed
            "",  # Empty
        ]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                ServiceDefinition(version=version, **base_data)

    def test_timestamp_validation(self) -> None:
        """Test timestamp ISO 8601 format validation."""
        base_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }

        # Valid timestamps - all should be parsed to datetime objects
        valid_timestamps = [
            ("2024-01-01T00:00:00Z", datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)),
            ("2024-01-01T00:00:00+00:00", datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)),
            ("2024-01-01T00:00:00.123456Z", datetime(2024, 1, 1, 0, 0, 0, 123456, tzinfo=UTC)),
        ]
        for timestamp_str, expected_dt in valid_timestamps:
            service = ServiceDefinition(
                created_at=timestamp_str, updated_at=timestamp_str, **base_data
            )
            assert isinstance(service.created_at, datetime)
            assert isinstance(service.updated_at, datetime)
            assert service.created_at == expected_dt
            assert service.updated_at == expected_dt

        # Test with datetime object directly
        now = datetime.now(UTC)
        service = ServiceDefinition(created_at=now, updated_at=now, **base_data)
        assert service.created_at == now
        assert service.updated_at == now

        # Invalid timestamps
        invalid_timestamps = [
            "2024-01-01",  # Date only
            "2024-01-01 00:00:00",  # Wrong format
            "not-a-timestamp",  # Invalid
            "",  # Empty
        ]
        for timestamp in invalid_timestamps:
            with pytest.raises(ValidationError):
                ServiceDefinition(created_at=timestamp, updated_at=timestamp, **base_data)

    def test_updated_after_created_validation(self) -> None:
        """Test that updated_at cannot be before created_at."""
        base_data = {
            "service_name": "test-service",
            "owner": "test-team",
            "description": "Test service",
            "version": "1.0.0",
        }

        # Valid: updated_at after created_at
        service = ServiceDefinition(
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:01Z",
            **base_data,
        )
        assert service.created_at < service.updated_at

        # Valid: updated_at equals created_at
        now = datetime.now(UTC).isoformat()
        service = ServiceDefinition(created_at=now, updated_at=now, **base_data)
        assert service.created_at == service.updated_at

        # Invalid: updated_at before created_at
        with pytest.raises(ValidationError) as exc_info:
            ServiceDefinition(
                created_at="2024-01-01T00:00:01Z",
                updated_at="2024-01-01T00:00:00Z",
                **base_data,
            )
        errors = exc_info.value.errors()
        assert any("updated_at cannot be before created_at" in str(e) for e in errors)

    def test_model_dump_json(self) -> None:
        """Test model serialization to JSON."""
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now_iso,
            updated_at=now_iso,
        )

        # Test JSON serialization
        json_str = service.model_dump_json()
        assert isinstance(json_str, str)
        assert "test-service" in json_str
        assert "test-team" in json_str
        # Check that timestamps are serialized as ISO strings
        assert now_iso in json_str

        # Test dict dump - timestamps should be serialized as ISO strings
        data = service.model_dump()
        assert data["service_name"] == "test-service"
        assert data["owner"] == "test-team"
        assert data["description"] == "Test service"
        assert data["version"] == "1.0.0"
        # The model serializes datetime objects to ISO strings
        assert data["created_at"] == now_iso
        assert data["updated_at"] == now_iso

    def test_to_iso_dict_method(self) -> None:
        """Test the to_iso_dict method returns ISO formatted timestamps."""
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        service = ServiceDefinition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.0.0",
            created_at=now_iso,
            updated_at=now_iso,
        )

        # Call to_iso_dict
        iso_dict = service.to_iso_dict()

        # Verify it's a dict with ISO timestamps
        assert isinstance(iso_dict, dict)
        assert iso_dict["service_name"] == "test-service"
        assert iso_dict["owner"] == "test-team"
        assert iso_dict["description"] == "Test service"
        assert iso_dict["version"] == "1.0.0"
        # Timestamps should be ISO strings
        assert isinstance(iso_dict["created_at"], str)
        assert isinstance(iso_dict["updated_at"], str)
        assert iso_dict["created_at"] == now_iso
        assert iso_dict["updated_at"] == now_iso

    def test_all_fields_required(self) -> None:
        """Test that all fields are required."""
        # Missing service_name
        with pytest.raises(ValidationError):
            ServiceDefinition(
                owner="test-team",
                description="Test",
                version="1.0.0",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # Missing owner
        with pytest.raises(ValidationError):
            ServiceDefinition(
                service_name="test-service",
                description="Test",
                version="1.0.0",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # Missing description
        with pytest.raises(ValidationError):
            ServiceDefinition(
                service_name="test-service",
                owner="test-team",
                version="1.0.0",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # Missing version
        with pytest.raises(ValidationError):
            ServiceDefinition(
                service_name="test-service",
                owner="test-team",
                description="Test",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # Missing timestamps
        with pytest.raises(ValidationError):
            ServiceDefinition(
                service_name="test-service",
                owner="test-team",
                description="Test",
                version="1.0.0",
            )
