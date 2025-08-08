"""Tests for application layer."""

from unittest.mock import AsyncMock, Mock

import pytest
from app.application.greet_use_case import GreetUseCase
from app.application.hello_service import HelloService
from app.domain.models import GreetingRequest, GreetingResponse, GreetingType
from app.ports.audit import AuditPort
from app.ports.metrics import MetricsPort
from app.ports.notification import NotificationPort


class TestGreetUseCase:
    """Test GreetUseCase."""

    @pytest.fixture
    def mock_metrics(self):
        """Create mock metrics port."""
        return Mock(spec=MetricsPort)

    @pytest.fixture
    def mock_audit(self):
        """Create mock audit port."""
        mock = Mock(spec=AuditPort)
        mock.log_greeting = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_metrics, mock_audit):
        """Create use case with mocks."""
        return GreetUseCase(metrics=mock_metrics, audit=mock_audit)

    @pytest.mark.asyncio
    async def test_execute_simple_greeting(self, use_case, mock_metrics, mock_audit):
        """Test executing a simple greeting."""
        request = GreetingRequest(name="Alice", greeting_type=GreetingType.SIMPLE)

        response = await use_case.execute(request)

        assert isinstance(response, GreetingResponse)
        assert response.message == "Hello, Alice!"
        assert response.name == "Alice"
        assert response.greeting_type == GreetingType.SIMPLE

        mock_metrics.increment.assert_called_with("greetings.simple")
        mock_audit.log_greeting.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_formal_greeting(self, use_case, mock_metrics, mock_audit):
        """Test executing a formal greeting."""
        request = GreetingRequest(
            name="Dr. Smith", greeting_type=GreetingType.FORMAL, language="en"
        )

        response = await use_case.execute(request)

        assert response.message == "Good day, Dr. Smith. How may I assist you?"
        assert response.greeting_type == GreetingType.FORMAL

        mock_metrics.increment.assert_called_with("greetings.formal")

    @pytest.mark.asyncio
    async def test_execute_casual_greeting(self, use_case, mock_metrics, mock_audit):
        """Test executing a casual greeting."""
        request = GreetingRequest(name="Bob", greeting_type=GreetingType.CASUAL)

        response = await use_case.execute(request)

        assert response.message == "Hey Bob! What's up?"
        assert response.greeting_type == GreetingType.CASUAL

        mock_metrics.increment.assert_called_with("greetings.casual")

    @pytest.mark.asyncio
    async def test_execute_with_metadata(self, use_case):
        """Test that metadata is preserved in response."""
        request = GreetingRequest(
            name="Test",
            greeting_type=GreetingType.SIMPLE,
            metadata={"user_id": "123", "source": "api"},
        )

        response = await use_case.execute(request)

        assert response.metadata == {"user_id": "123", "source": "api"}

    @pytest.mark.asyncio
    async def test_execute_with_language(self, use_case):
        """Test greeting with different language."""
        request = GreetingRequest(name="Maria", greeting_type=GreetingType.SIMPLE, language="es")

        response = await use_case.execute(request)

        # Language stored but not yet implemented in formatting
        assert response.message == "Hello, Maria!"
        assert "language" in response.metadata
        assert response.metadata["language"] == "es"


class TestHelloService:
    """Test HelloService."""

    @pytest.fixture
    def mock_greet_use_case(self):
        """Create mock greet use case."""
        mock = Mock()
        mock.execute = AsyncMock()
        return mock

    @pytest.fixture
    def mock_notification(self):
        """Create mock notification port."""
        mock = Mock(spec=NotificationPort)
        mock.send_greeting_notification = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_greet_use_case, mock_notification):
        """Create service with mocks."""
        return HelloService(greet_use_case=mock_greet_use_case, notification=mock_notification)

    @pytest.mark.asyncio
    async def test_greet_simple(self, service, mock_greet_use_case, mock_notification):
        """Test simple greeting through service."""
        mock_response = GreetingResponse(
            message="Hello, Test!", name="Test", greeting_type=GreetingType.SIMPLE, metadata={}
        )
        mock_greet_use_case.execute.return_value = mock_response

        result = await service.greet("Test")

        assert result == "Hello, Test!"
        mock_greet_use_case.execute.assert_called_once()
        mock_notification.send_greeting_notification.assert_called_with("Test", "Hello, Test!")

    @pytest.mark.asyncio
    async def test_greet_with_type(self, service, mock_greet_use_case):
        """Test greeting with specific type."""
        mock_response = GreetingResponse(
            message="Good day, Alice. How may I assist you?",
            name="Alice",
            greeting_type=GreetingType.FORMAL,
            metadata={},
        )
        mock_greet_use_case.execute.return_value = mock_response

        result = await service.greet("Alice", greeting_type=GreetingType.FORMAL)

        assert result == "Good day, Alice. How may I assist you?"

        # Verify the request was created correctly
        call_args = mock_greet_use_case.execute.call_args[0][0]
        assert call_args.name == "Alice"
        assert call_args.greeting_type == GreetingType.FORMAL

    @pytest.mark.asyncio
    async def test_greet_with_metadata(self, service, mock_greet_use_case):
        """Test greeting with metadata."""
        mock_response = GreetingResponse(
            message="Hello, User!",
            name="User",
            greeting_type=GreetingType.SIMPLE,
            metadata={"session": "abc123"},
        )
        mock_greet_use_case.execute.return_value = mock_response

        result = await service.greet("User", metadata={"session": "abc123"})

        assert result == "Hello, User!"

        # Verify metadata was passed
        call_args = mock_greet_use_case.execute.call_args[0][0]
        assert call_args.metadata == {"session": "abc123"}

    @pytest.mark.asyncio
    async def test_notification_failure_doesnt_fail_greeting(
        self, service, mock_greet_use_case, mock_notification
    ):
        """Test that notification failure doesn't fail the greeting."""
        mock_response = GreetingResponse(
            message="Hello, Test!", name="Test", greeting_type=GreetingType.SIMPLE, metadata={}
        )
        mock_greet_use_case.execute.return_value = mock_response

        # Make notification fail
        mock_notification.send_greeting_notification.side_effect = Exception("Network error")

        # Should not raise
        result = await service.greet("Test")

        assert result == "Hello, Test!"  # Greeting still works
