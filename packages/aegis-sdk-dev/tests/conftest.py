"""Pytest configuration and shared fixtures for aegis-sdk-dev tests."""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ExecutionResult,
    ExecutionType,
    ProjectTemplate,
    RunConfiguration,
    ServiceConfiguration,
    ValidationResult,
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing.

    Yields:
        Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def service_config() -> ServiceConfiguration:
    """Create a sample service configuration.

    Returns:
        A valid ServiceConfiguration instance
    """
    return ServiceConfiguration(
        service_name="test-service",
        nats_url="nats://localhost:4222",
        environment="local",
        kv_bucket="test_registry",
        enable_watchable=True,
        debug=False,
    )


@pytest.fixture
def bootstrap_config(service_config: ServiceConfiguration) -> BootstrapConfig:
    """Create a sample bootstrap configuration.

    Args:
        service_config: Service configuration fixture

    Returns:
        A valid BootstrapConfig instance
    """
    return BootstrapConfig(
        project_name="test-project",
        template=ProjectTemplate.BASIC,
        service_config=service_config,
        output_dir=".",
        include_tests=True,
        include_docker=True,
        include_k8s=False,
    )


@pytest.fixture
def test_config() -> RunConfiguration:
    """Create a sample test configuration.

    Returns:
        A valid RunConfiguration instance
    """
    return RunConfiguration(
        test_type=ExecutionType.UNIT,
        verbose=True,
        coverage=True,
        min_coverage=80.0,
        test_path="tests",
        markers=[],
    )


@pytest.fixture
def validation_result() -> ValidationResult:
    """Create a sample validation result.

    Returns:
        A valid ValidationResult instance
    """
    return ValidationResult(
        environment="local",
        issues=[],
        diagnostics={},
        recommendations=[],
    )


@pytest.fixture
def test_result() -> ExecutionResult:
    """Create a sample test result.

    Returns:
        A valid ExecutionResult instance
    """
    return ExecutionResult(
        test_type=ExecutionType.UNIT,
        passed=10,
        failed=0,
        skipped=2,
        coverage_percentage=85.5,
        duration_seconds=5.3,
        errors=[],
    )


@pytest.fixture
def mock_console() -> MagicMock:
    """Create a mock console adapter.

    Returns:
        A mocked console adapter
    """
    mock = MagicMock()
    mock.print = MagicMock()
    mock.print_error = MagicMock()
    mock.print_success = MagicMock()
    mock.print_warning = MagicMock()
    mock.prompt = MagicMock(return_value="test-input")
    mock.confirm = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_file_system(temp_dir: Path) -> MagicMock:
    """Create a mock file system adapter.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        A mocked file system adapter
    """
    mock = MagicMock()
    mock.read_file = MagicMock(return_value="test content")
    mock.write_file = MagicMock()
    mock.exists = MagicMock(return_value=True)
    mock.create_directory = MagicMock()
    mock.delete = MagicMock()
    mock.list_directory = MagicMock(return_value=[])
    mock.get_size = MagicMock(return_value=1024)
    mock.copy = MagicMock()
    mock.move = MagicMock()
    return mock


@pytest.fixture
def mock_environment() -> MagicMock:
    """Create a mock environment adapter.

    Returns:
        A mocked environment adapter
    """
    mock = MagicMock()
    mock.get = MagicMock(return_value="test-value")
    mock.set = MagicMock()
    mock.get_all = MagicMock(return_value={"TEST_VAR": "test-value"})
    mock.detect_environment = MagicMock(return_value="local")
    mock.is_kubernetes = MagicMock(return_value=False)
    mock.is_docker = MagicMock(return_value=False)
    return mock


@pytest.fixture
def mock_process_executor() -> MagicMock:
    """Create a mock process executor adapter.

    Returns:
        A mocked process executor adapter
    """
    mock = MagicMock()
    mock.run = MagicMock(return_value=(0, "stdout", ""))
    mock.run_async = AsyncMock(return_value=(0, "stdout", ""))
    mock.check_command_exists = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_configuration() -> MagicMock:
    """Create a mock configuration adapter.

    Returns:
        A mocked configuration adapter
    """
    mock = MagicMock()
    mock.load = MagicMock(return_value={"key": "value"})
    mock.save = MagicMock()
    mock.validate = MagicMock(return_value=True)
    mock.get = MagicMock(return_value="value")
    mock.set = MagicMock()
    return mock


@pytest.fixture
async def mock_nats() -> AsyncMock:
    """Create a mock NATS adapter.

    Returns:
        A mocked NATS adapter
    """
    mock = AsyncMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.is_connected = MagicMock(return_value=True)
    mock.publish = AsyncMock()
    mock.subscribe = AsyncMock()
    mock.request = AsyncMock(return_value=b'{"result": "success"}')
    return mock


# Integration test fixtures (only used when NATS is available)
@pytest.fixture(scope="session")
def nats_url() -> str:
    """Get NATS URL for integration tests.

    Returns:
        NATS connection URL
    """
    return "nats://localhost:4222"


@pytest.fixture
async def nats_container():
    """Start NATS container for integration tests (if testcontainers available).

    This fixture is only used for integration tests and requires testcontainers.
    """
    pytest.importorskip("testcontainers")
    from testcontainers.nats import NatsContainer

    with NatsContainer() as nats:
        yield nats.get_connection_url()
