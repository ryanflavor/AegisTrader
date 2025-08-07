"""Unit tests for domain models following TDD."""

from datetime import datetime
from uuid import uuid4

import pytest

from ..domain.models import Greeting, HelloRequest, HelloResponse, ServiceStatus


class TestGreeting:
    """Test Greeting value object."""

    def test_create_valid_greeting(self):
        """Test creating a valid greeting."""
        greeting = Greeting(message="Hello, World!")
        assert greeting.message == "Hello, World!"
        assert greeting.language == "en"

    def test_greeting_is_immutable(self):
        """Test that greeting is immutable (frozen)."""
        greeting = Greeting(message="Hello")
        with pytest.raises(AttributeError):
            greeting.message = "Goodbye"

    def test_greeting_with_custom_language(self):
        """Test greeting with custom language code."""
        greeting = Greeting(message="Bonjour", language="fr")
        assert greeting.language == "fr"

    def test_invalid_language_code(self):
        """Test that invalid language codes are rejected."""
        with pytest.raises(ValueError):
            Greeting(message="Hello", language="invalid")

    def test_empty_message_rejected(self):
        """Test that empty messages are rejected."""
        with pytest.raises(ValueError):
            Greeting(message="   ")

    def test_message_trimmed(self):
        """Test that messages are trimmed."""
        greeting = Greeting(message="  Hello  ")
        assert greeting.message == "Hello"


class TestHelloRequest:
    """Test HelloRequest entity."""

    def test_create_valid_request(self):
        """Test creating a valid hello request."""
        request = HelloRequest(name="Alice")
        assert request.name == "Alice"
        assert request.greeting_style == "formal"
        assert isinstance(request.id, uuid4().__class__)
        assert isinstance(request.timestamp, datetime)

    def test_name_sanitization(self):
        """Test that names are sanitized."""
        request = HelloRequest(name="  Bob  ")
        assert request.name == "Bob"

    def test_invalid_greeting_style(self):
        """Test that invalid greeting styles are rejected."""
        with pytest.raises(ValueError):
            HelloRequest(name="Alice", greeting_style="rude")

    def test_to_greeting_formal(self):
        """Test converting request to formal greeting."""
        request = HelloRequest(name="Dr. Smith", greeting_style="formal")
        greeting = request.to_greeting()
        assert "Good day, Dr. Smith" in greeting.message

    def test_to_greeting_casual(self):
        """Test converting request to casual greeting."""
        request = HelloRequest(name="Mike", greeting_style="casual")
        greeting = request.to_greeting()
        assert "Hey Mike!" in greeting.message

    def test_request_with_metadata(self):
        """Test request with metadata."""
        request = HelloRequest(name="Alice", metadata={"source": "api", "version": "1.0"})
        assert request.metadata["source"] == "api"


class TestHelloResponse:
    """Test HelloResponse value object."""

    def test_create_valid_response(self):
        """Test creating a valid response."""
        request_id = uuid4()
        greeting = Greeting(message="Hello!")
        response = HelloResponse(request_id=request_id, greeting=greeting, processing_time_ms=15.5)
        assert response.request_id == request_id
        assert response.greeting == greeting
        assert response.processing_time_ms == 15.5

    def test_response_is_immutable(self):
        """Test that response is immutable."""
        response = HelloResponse(request_id=uuid4(), greeting=Greeting(message="Hi"))
        with pytest.raises(AttributeError):
            response.request_id = uuid4()

    def test_negative_processing_time_rejected(self):
        """Test that negative processing times are rejected."""
        with pytest.raises(ValueError):
            HelloResponse(
                request_id=uuid4(), greeting=Greeting(message="Hi"), processing_time_ms=-1.0
            )


class TestServiceStatus:
    """Test ServiceStatus aggregate."""

    def test_create_valid_status(self):
        """Test creating a valid service status."""
        status = ServiceStatus(healthy=True, uptime_seconds=100.0)
        assert status.healthy is True
        assert status.uptime_seconds == 100.0
        assert status.requests_processed == 0

    def test_increment_requests(self):
        """Test incrementing request counter."""
        status = ServiceStatus(healthy=True, uptime_seconds=0)
        status.increment_requests()
        assert status.requests_processed == 1
        assert status.last_request_at is not None

    def test_multiple_increments(self):
        """Test multiple request increments."""
        status = ServiceStatus(healthy=True, uptime_seconds=0)
        for _ in range(5):
            status.increment_requests()
        assert status.requests_processed == 5

    def test_negative_uptime_rejected(self):
        """Test that negative uptime is rejected."""
        with pytest.raises(ValueError):
            ServiceStatus(healthy=True, uptime_seconds=-1.0)
