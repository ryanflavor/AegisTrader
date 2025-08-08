"""Unit tests for TestEnvironment following TDD principles."""

import pytest
from pydantic import ValidationError

from aegis_sdk_dev.testing.environment import TestEnvironment


class TestTestEnvironment:
    """Test suite for TestEnvironment class following hexagonal architecture."""

    def test_create_with_defaults(self):
        """Test creating TestEnvironment with default values."""
        # Act
        env = TestEnvironment()

        # Assert
        assert env.nats_url == "nats://localhost:4222"
        assert env.service_name == "test-service"

    def test_create_with_custom_values(self):
        """Test creating TestEnvironment with custom values."""
        # Arrange
        custom_url = "nats://custom-host:1234"
        custom_name = "custom-service"

        # Act
        env = TestEnvironment(nats_url=custom_url, service_name=custom_name)

        # Assert
        assert env.nats_url == custom_url
        assert env.service_name == custom_name

    def test_strict_mode_enforced(self):
        """Test that strict mode is enforced preventing extra fields."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            TestEnvironment(
                nats_url="nats://localhost:4222",
                service_name="test-service",
                extra_field="not_allowed",  # type: ignore
            )

        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_immutable_after_creation(self):
        """Test that fields cannot be modified after creation due to strict mode."""
        # Arrange
        env = TestEnvironment()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            env.nats_url = "nats://modified:4222"  # type: ignore

        assert "Instance is immutable" in str(exc_info.value)

    def test_type_validation(self):
        """Test that type validation is enforced."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            TestEnvironment(nats_url=123, service_name="test")  # type: ignore

        assert "Input should be a valid string" in str(exc_info.value)

    def test_model_dump(self):
        """Test serialization to dictionary."""
        # Arrange
        env = TestEnvironment(nats_url="nats://test:4222", service_name="my-service")

        # Act
        data = env.model_dump()

        # Assert
        assert data == {"nats_url": "nats://test:4222", "service_name": "my-service"}

    def test_model_json_schema(self):
        """Test JSON schema generation."""
        # Act
        schema = TestEnvironment.model_json_schema()

        # Assert
        assert schema["type"] == "object"
        assert "nats_url" in schema["properties"]
        assert "service_name" in schema["properties"]
        assert schema["properties"]["nats_url"]["default"] == "nats://localhost:4222"
        assert schema["properties"]["service_name"]["default"] == "test-service"

    def test_from_dict(self):
        """Test creating instance from dictionary."""
        # Arrange
        data = {"nats_url": "nats://from-dict:4222", "service_name": "dict-service"}

        # Act
        env = TestEnvironment(**data)

        # Assert
        assert env.nats_url == "nats://from-dict:4222"
        assert env.service_name == "dict-service"

    def test_empty_string_values(self):
        """Test behavior with empty string values."""
        # Act
        env = TestEnvironment(nats_url="", service_name="")

        # Assert - empty strings are allowed as they are valid strings
        assert env.nats_url == ""
        assert env.service_name == ""

    def test_copy_with_update(self):
        """Test copying instance with updated values."""
        # Arrange
        original = TestEnvironment()

        # Act
        updated = original.model_copy(update={"service_name": "updated-service"})

        # Assert
        assert original.service_name == "test-service"
        assert updated.service_name == "updated-service"
        assert updated.nats_url == original.nats_url

    def test_comparison(self):
        """Test equality comparison between instances."""
        # Arrange
        env1 = TestEnvironment(nats_url="nats://test:4222", service_name="service")
        env2 = TestEnvironment(nats_url="nats://test:4222", service_name="service")
        env3 = TestEnvironment(nats_url="nats://other:4222", service_name="service")

        # Assert
        assert env1 == env2
        assert env1 != env3

    def test_repr(self):
        """Test string representation."""
        # Arrange
        env = TestEnvironment(nats_url="nats://repr-test:4222", service_name="repr-service")

        # Act
        repr_str = repr(env)

        # Assert
        assert "TestEnvironment" in repr_str
        assert "nats_url='nats://repr-test:4222'" in repr_str
        assert "service_name='repr-service'" in repr_str
