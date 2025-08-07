"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.fixture
def mock_configuration():
    """Create a mock configuration for testing."""
    from unittest.mock import MagicMock

    from app.ports.configuration import ConfigurationPort

    mock = MagicMock(spec=ConfigurationPort)
    mock.get_instance_id.return_value = "test-instance-1"
    mock.get_service_name.return_value = "echo-service-test"
    mock.get_service_version.return_value = "test-1.0.0"
    mock.get_service_type.return_value = "service"
    mock.is_debug_enabled.return_value = True
    mock.get_nats_url.return_value = None
    mock.get_config_value.return_value = None

    return mock


@pytest.fixture
def mock_service_bus():
    """Create a mock service bus for testing."""
    from unittest.mock import AsyncMock, MagicMock

    from app.ports.service_bus import ServiceBusPort

    mock = MagicMock(spec=ServiceBusPort)
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.register_rpc_handler = MagicMock()
    mock.call_rpc = AsyncMock()
    mock.get_instance_id.return_value = "test-service-id"
    mock.is_connected.return_value = True

    return mock
