"""Pytest configuration and shared fixtures."""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from testcontainers.nats import NatsContainer


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


@pytest.fixture(scope="session")
def nats_container():
    """Start NATS container for integration tests."""
    # Skip if explicitly disabled
    if os.getenv("SKIP_INTEGRATION_TESTS", "").lower() == "true":
        pytest.skip("Integration tests disabled")

    # Use existing NATS if available
    if os.getenv("NATS_URL"):
        yield os.getenv("NATS_URL")
        return

    # Start NATS container
    container = NatsContainer("nats:2.10-alpine")
    container.with_command("-js")  # Enable JetStream
    container.start()

    # Wait for NATS to be ready
    time.sleep(2)

    nats_url = f"nats://localhost:{container.get_exposed_port(4222)}"
    yield nats_url

    container.stop()


@pytest_asyncio.fixture
async def nats_adapter(nats_container):
    """Create a real NATS adapter for integration tests."""
    adapter = NATSAdapter()
    await adapter.connect([nats_container])

    yield adapter

    await adapter.disconnect()


@pytest_asyncio.fixture
async def nats_adapter_msgpack(nats_container):
    """Create a real NATS adapter with msgpack serialization."""
    adapter = NATSAdapter(use_msgpack=True)
    await adapter.connect([nats_container])

    yield adapter

    await adapter.disconnect()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
