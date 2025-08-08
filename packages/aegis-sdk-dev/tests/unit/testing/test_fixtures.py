"""Unit tests for ServiceFixture following TDD principles."""

import pytest
from pydantic import ValidationError

from aegis_sdk_dev.testing.fixtures import ServiceFixture


class TestServiceFixture:
    """Test suite for ServiceFixture class following hexagonal architecture."""

    def test_create_valid_fixture(self):
        """Test creating a valid ServiceFixture."""
        # Arrange
        name = "test-service"
        url = "http://localhost:8080"

        # Act
        fixture = ServiceFixture(name=name, url=url)

        # Assert
        assert fixture.name == name
        assert fixture.url == url

    def test_required_fields(self):
        """Test that required fields must be provided."""
        # Act & Assert - missing name
        with pytest.raises(ValidationError) as exc_info:
            ServiceFixture(url="http://localhost:8080")  # type: ignore

        assert "Field required" in str(exc_info.value)

        # Act & Assert - missing url
        with pytest.raises(ValidationError) as exc_info:
            ServiceFixture(name="test-service")  # type: ignore

        assert "Field required" in str(exc_info.value)

    def test_strict_mode_prevents_extra_fields(self):
        """Test that strict mode prevents extra fields."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ServiceFixture(
                name="test-service",
                url="http://localhost:8080",
                extra_field="not_allowed",  # type: ignore
            )

        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_type_validation(self):
        """Test that type validation is enforced."""
        # Act & Assert - invalid name type
        with pytest.raises(ValidationError) as exc_info:
            ServiceFixture(name=123, url="http://localhost:8080")  # type: ignore

        assert "Input should be a valid string" in str(exc_info.value)

        # Act & Assert - invalid url type
        with pytest.raises(ValidationError) as exc_info:
            ServiceFixture(name="test-service", url=456)  # type: ignore

        assert "Input should be a valid string" in str(exc_info.value)

    def test_empty_string_values(self):
        """Test behavior with empty string values."""
        # Act - empty strings are valid strings in Pydantic
        fixture = ServiceFixture(name="", url="")

        # Assert
        assert fixture.name == ""
        assert fixture.url == ""

    def test_model_dump(self):
        """Test serialization to dictionary."""
        # Arrange
        fixture = ServiceFixture(name="dump-service", url="http://dump-host:9000")

        # Act
        data = fixture.model_dump()

        # Assert
        assert data == {"name": "dump-service", "url": "http://dump-host:9000"}

    def test_model_json_schema(self):
        """Test JSON schema generation."""
        # Act
        schema = ServiceFixture.model_json_schema()

        # Assert
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "url" in schema["properties"]
        assert "name" in schema["required"]
        assert "url" in schema["required"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["url"]["type"] == "string"

    def test_from_dict(self):
        """Test creating instance from dictionary."""
        # Arrange
        data = {"name": "dict-service", "url": "http://dict-host:7000"}

        # Act
        fixture = ServiceFixture(**data)

        # Assert
        assert fixture.name == "dict-service"
        assert fixture.url == "http://dict-host:7000"

    def test_copy_with_update(self):
        """Test copying instance with updated values."""
        # Arrange
        original = ServiceFixture(name="original", url="http://original:8080")

        # Act
        updated = original.model_copy(update={"name": "updated"})

        # Assert
        assert original.name == "original"
        assert updated.name == "updated"
        assert updated.url == original.url

    def test_comparison(self):
        """Test equality comparison between instances."""
        # Arrange
        fixture1 = ServiceFixture(name="service", url="http://host:8080")
        fixture2 = ServiceFixture(name="service", url="http://host:8080")
        fixture3 = ServiceFixture(name="other", url="http://host:8080")

        # Assert
        assert fixture1 == fixture2
        assert fixture1 != fixture3

    def test_repr(self):
        """Test string representation."""
        # Arrange
        fixture = ServiceFixture(name="repr-service", url="http://repr-host:5000")

        # Act
        repr_str = repr(fixture)

        # Assert
        assert "ServiceFixture" in repr_str
        assert "name='repr-service'" in repr_str
        assert "url='http://repr-host:5000'" in repr_str

    def test_immutable_after_creation(self):
        """Test that fields cannot be modified after creation due to strict mode."""
        # Arrange
        fixture = ServiceFixture(name="test", url="http://test:8080")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            fixture.name = "modified"  # type: ignore

        assert "Instance is immutable" in str(exc_info.value)

    def test_various_url_formats(self):
        """Test that various URL formats are accepted."""
        # Test HTTP URL
        http_fixture = ServiceFixture(name="http", url="http://example.com")
        assert http_fixture.url == "http://example.com"

        # Test HTTPS URL
        https_fixture = ServiceFixture(name="https", url="https://secure.example.com")
        assert https_fixture.url == "https://secure.example.com"

        # Test URL with port
        port_fixture = ServiceFixture(name="port", url="http://localhost:3000")
        assert port_fixture.url == "http://localhost:3000"

        # Test URL with path
        path_fixture = ServiceFixture(name="path", url="http://api.example.com/v1/users")
        assert path_fixture.url == "http://api.example.com/v1/users"

        # Test URL with query parameters
        query_fixture = ServiceFixture(name="query", url="http://api.example.com?key=value")
        assert query_fixture.url == "http://api.example.com?key=value"

    def test_model_json(self):
        """Test JSON serialization."""
        # Arrange
        fixture = ServiceFixture(name="json-service", url="http://json:8080")

        # Act
        json_str = fixture.model_dump_json()

        # Assert
        assert '"name":"json-service"' in json_str
        assert '"url":"http://json:8080"' in json_str

    def test_model_validate(self):
        """Test model validation with model_validate method."""
        # Arrange
        data = {"name": "validate-service", "url": "http://validate:8080"}

        # Act
        fixture = ServiceFixture.model_validate(data)

        # Assert
        assert fixture.name == "validate-service"
        assert fixture.url == "http://validate:8080"

    def test_whitespace_handling(self):
        """Test handling of whitespace in fields."""
        # Act - whitespace is preserved in Pydantic by default
        fixture = ServiceFixture(name="  service with spaces  ", url="  http://example.com  ")

        # Assert
        assert fixture.name == "  service with spaces  "
        assert fixture.url == "  http://example.com  "
