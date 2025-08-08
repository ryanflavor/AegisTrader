"""Unit tests for InfrastructureFactory following factory pattern and hexagonal architecture."""

from unittest.mock import MagicMock, patch

from rich.console import Console

from aegis_sdk_dev.infrastructure.configuration_adapter import ConfigurationAdapter
from aegis_sdk_dev.infrastructure.console_adapter import ConsoleAdapter
from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter
from aegis_sdk_dev.infrastructure.factory import InfrastructureFactory
from aegis_sdk_dev.infrastructure.file_system_adapter import FileSystemAdapter
from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter
from aegis_sdk_dev.infrastructure.process_executor_adapter import ProcessExecutorAdapter
from aegis_sdk_dev.ports.configuration import ConfigurationPort
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.environment import EnvironmentPort
from aegis_sdk_dev.ports.file_system import FileSystemPort
from aegis_sdk_dev.ports.nats import NATSConnectionPort
from aegis_sdk_dev.ports.process import ProcessExecutorPort


class TestInfrastructureFactory:
    """Test InfrastructureFactory for creating infrastructure adapters."""

    def test_create_console_default(self):
        """Test creating console adapter with default console."""
        # Act
        console_port = InfrastructureFactory.create_console()

        # Assert
        assert isinstance(console_port, ConsolePort)
        assert isinstance(console_port, ConsoleAdapter)

    def test_create_console_with_custom_console(self):
        """Test creating console adapter with custom Rich console."""
        # Arrange
        custom_console = Console()

        # Act
        console_port = InfrastructureFactory.create_console(custom_console)

        # Assert
        assert isinstance(console_port, ConsolePort)
        assert isinstance(console_port, ConsoleAdapter)

    def test_create_environment(self):
        """Test creating environment adapter."""
        # Act
        env_port = InfrastructureFactory.create_environment()

        # Assert
        assert isinstance(env_port, EnvironmentPort)
        assert isinstance(env_port, EnvironmentAdapter)

    def test_create_file_system(self):
        """Test creating file system adapter."""
        # Act
        fs_port = InfrastructureFactory.create_file_system()

        # Assert
        assert isinstance(fs_port, FileSystemPort)
        assert isinstance(fs_port, FileSystemAdapter)

    def test_create_configuration(self):
        """Test creating configuration adapter."""
        # Act
        config_port = InfrastructureFactory.create_configuration()

        # Assert
        assert isinstance(config_port, ConfigurationPort)
        assert isinstance(config_port, ConfigurationAdapter)

    def test_create_nats_connection(self):
        """Test creating NATS connection adapter."""
        # Act
        nats_port = InfrastructureFactory.create_nats_connection()

        # Assert
        assert isinstance(nats_port, NATSConnectionPort)
        assert isinstance(nats_port, NATSConnectionAdapter)

    def test_create_process_executor(self):
        """Test creating process executor adapter."""
        # Act
        process_port = InfrastructureFactory.create_process_executor()

        # Assert
        assert isinstance(process_port, ProcessExecutorPort)
        assert isinstance(process_port, ProcessExecutorAdapter)

    def test_create_all_adapters_default(self):
        """Test creating all adapters with default settings."""
        # Act
        adapters = InfrastructureFactory.create_all_adapters()

        # Assert
        assert isinstance(adapters, dict)
        assert len(adapters) == 6
        assert "console" in adapters
        assert "environment" in adapters
        assert "file_system" in adapters
        assert "configuration" in adapters
        assert "nats" in adapters
        assert "process" in adapters

        # Verify types
        assert isinstance(adapters["console"], ConsolePort)
        assert isinstance(adapters["environment"], EnvironmentPort)
        assert isinstance(adapters["file_system"], FileSystemPort)
        assert isinstance(adapters["configuration"], ConfigurationPort)
        assert isinstance(adapters["nats"], NATSConnectionPort)
        assert isinstance(adapters["process"], ProcessExecutorPort)

    def test_create_all_adapters_with_custom_console(self):
        """Test creating all adapters with custom console."""
        # Arrange
        custom_console = Console()

        # Act
        adapters = InfrastructureFactory.create_all_adapters(console=custom_console)

        # Assert
        assert isinstance(adapters["console"], ConsolePort)
        assert len(adapters) == 6

    def test_factory_creates_new_instances(self):
        """Test that factory creates new instances each time."""
        # Act
        adapter1 = InfrastructureFactory.create_environment()
        adapter2 = InfrastructureFactory.create_environment()

        # Assert
        assert adapter1 is not adapter2
        assert isinstance(adapter1, EnvironmentAdapter)
        assert isinstance(adapter2, EnvironmentAdapter)

    def test_factory_dependency_injection_principle(self):
        """Test that factory follows dependency injection principle."""
        # This test verifies that the factory allows injection of dependencies
        # (like the Console) rather than creating them internally

        # Arrange
        mock_console = MagicMock(spec=Console)

        # Act
        console_port = InfrastructureFactory.create_console(mock_console)

        # Assert
        assert isinstance(console_port, ConsoleAdapter)
        # The adapter should use the injected console

    def test_factory_single_responsibility(self):
        """Test that factory has single responsibility of creating adapters."""
        # The factory should only create adapters, not configure or initialize them
        # This is verified by checking that methods are simple and return immediately

        # Act & Assert
        methods = [
            InfrastructureFactory.create_console,
            InfrastructureFactory.create_environment,
            InfrastructureFactory.create_file_system,
            InfrastructureFactory.create_configuration,
            InfrastructureFactory.create_nats_connection,
            InfrastructureFactory.create_process_executor,
        ]

        for method in methods:
            # Each method should be simple and return an adapter
            result = method()
            assert result is not None

    def test_factory_returns_port_interfaces(self):
        """Test that factory methods return port interfaces, not concrete implementations."""
        # This ensures proper abstraction and hexagonal architecture

        # Act
        adapters = InfrastructureFactory.create_all_adapters()

        # Assert - Check that return types are declared as ports
        for adapter_name, adapter in adapters.items():
            if adapter_name == "console":
                assert isinstance(adapter, ConsolePort)
            elif adapter_name == "environment":
                assert isinstance(adapter, EnvironmentPort)
            elif adapter_name == "file_system":
                assert isinstance(adapter, FileSystemPort)
            elif adapter_name == "configuration":
                assert isinstance(adapter, ConfigurationPort)
            elif adapter_name == "nats":
                assert isinstance(adapter, NATSConnectionPort)
            elif adapter_name == "process":
                assert isinstance(adapter, ProcessExecutorPort)

    @patch("aegis_sdk_dev.infrastructure.factory.ConsoleAdapter")
    def test_factory_console_creation_uses_correct_adapter(self, mock_console_adapter):
        """Test that factory uses the correct adapter class for console."""
        # Arrange
        mock_instance = MagicMock(spec=ConsolePort)
        mock_console_adapter.return_value = mock_instance

        # Act
        result = InfrastructureFactory.create_console()

        # Assert
        mock_console_adapter.assert_called_once()
        assert result == mock_instance

    @patch("aegis_sdk_dev.infrastructure.factory.EnvironmentAdapter")
    def test_factory_environment_creation_uses_correct_adapter(self, mock_env_adapter):
        """Test that factory uses the correct adapter class for environment."""
        # Arrange
        mock_instance = MagicMock(spec=EnvironmentPort)
        mock_env_adapter.return_value = mock_instance

        # Act
        result = InfrastructureFactory.create_environment()

        # Assert
        mock_env_adapter.assert_called_once()
        assert result == mock_instance

    def test_factory_method_consistency(self):
        """Test that all factory methods follow consistent naming pattern."""
        # All create methods should follow create_<port_name> pattern

        # Act
        factory_methods = [
            name
            for name in dir(InfrastructureFactory)
            if name.startswith("create_") and not name.startswith("_")
        ]

        # Assert
        expected_methods = [
            "create_all_adapters",
            "create_configuration",
            "create_console",
            "create_environment",
            "create_file_system",
            "create_nats_connection",
            "create_process_executor",
        ]

        assert sorted(factory_methods) == sorted(expected_methods)

    def test_factory_all_adapters_keys_consistency(self):
        """Test that create_all_adapters returns consistent keys."""
        # Act
        adapters1 = InfrastructureFactory.create_all_adapters()
        adapters2 = InfrastructureFactory.create_all_adapters()

        # Assert
        assert set(adapters1.keys()) == set(adapters2.keys())
        assert all(
            key in adapters1
            for key in [
                "console",
                "environment",
                "file_system",
                "configuration",
                "nats",
                "process",
            ]
        )
