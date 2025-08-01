"""Pytest configuration and shared fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_message_bus():
    """Create a mock message bus for testing."""
    mock = AsyncMock()
    mock.is_connected = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_nats_client():
    """Create a mock NATS client."""
    mock = MagicMock()
    mock.is_connected = True
    mock.jetstream = MagicMock()
    return mock
