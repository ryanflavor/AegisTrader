"""Shared pytest fixtures for monitor-api tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the app directory to Python path for imports
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


@pytest.fixture
def mock_kv_store():
    """Mock KV store for testing."""
    mock = AsyncMock()
    mock.keys = AsyncMock(return_value=[])
    mock.get = AsyncMock(return_value=None)
    mock.put = AsyncMock()
    mock.delete = AsyncMock()
    mock.exists = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_nats_connection():
    """Mock NATS connection for testing."""
    mock = MagicMock()
    mock.is_connected = True
    mock.jetstream = MagicMock()
    return mock
