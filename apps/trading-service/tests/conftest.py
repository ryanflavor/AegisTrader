"""Pytest configuration and shared fixtures for trading services."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_message_bus():
    """Create a mock message bus for testing."""
    mock = AsyncMock()
    mock.is_connected = AsyncMock(return_value=True)
    mock.register_service = AsyncMock()
    mock.unregister_service = AsyncMock()
    mock.register_rpc_handler = AsyncMock()
    mock.subscribe_event = AsyncMock()
    mock.register_command_handler = AsyncMock()
    mock.call_rpc = AsyncMock()
    mock.publish_event = AsyncMock()
    mock.send_command = AsyncMock()
    mock.send_heartbeat = AsyncMock()
    return mock


@pytest.fixture
def mock_service_registry():
    """Create a mock service registry for testing."""
    mock = AsyncMock()
    mock.register = AsyncMock()
    mock.update_heartbeat = AsyncMock()
    mock.deregister = AsyncMock()
    mock.get_instance = AsyncMock()
    mock.list_instances = AsyncMock()
    mock.list_all_services = AsyncMock()
    return mock


@pytest.fixture
def mock_service_discovery():
    """Create a mock service discovery for testing."""
    mock = AsyncMock()
    mock.select_instance = AsyncMock()
    mock.invalidate_cache = AsyncMock()
    return mock


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    mock = MagicMock()
    mock.info = MagicMock()
    mock.warning = MagicMock()
    mock.error = MagicMock()
    mock.debug = MagicMock()
    return mock


@pytest.fixture
def mock_metrics():
    """Create a mock metrics for testing."""
    mock = MagicMock()
    mock.increment = MagicMock()
    mock.gauge = MagicMock()
    mock.record = MagicMock()
    mock.timer = MagicMock()
    mock.get_all = MagicMock(
        return_value={"uptime_seconds": 100, "counters": {}, "gauges": {}, "summaries": {}}
    )
    # Make timer return a context manager
    mock.timer.return_value.__enter__ = MagicMock(return_value=None)
    mock.timer.return_value.__exit__ = MagicMock(return_value=None)
    return mock


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
