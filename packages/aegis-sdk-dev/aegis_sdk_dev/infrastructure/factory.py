"""Factory for creating infrastructure adapters."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from aegis_sdk_dev.infrastructure.configuration_adapter import ConfigurationAdapter
from aegis_sdk_dev.infrastructure.console_adapter import ConsoleAdapter
from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter
from aegis_sdk_dev.infrastructure.file_system_adapter import FileSystemAdapter
from aegis_sdk_dev.infrastructure.nats_adapter import NATSConnectionAdapter
from aegis_sdk_dev.infrastructure.process_executor_adapter import ProcessExecutorAdapter
from aegis_sdk_dev.ports.configuration import ConfigurationPort
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.environment import EnvironmentPort
from aegis_sdk_dev.ports.file_system import FileSystemPort
from aegis_sdk_dev.ports.nats import NATSConnectionPort
from aegis_sdk_dev.ports.process import ProcessExecutorPort


class InfrastructureFactory:
    """Factory for creating infrastructure adapters following hexagonal architecture."""

    @staticmethod
    def create_console(console: Console | None = None) -> ConsolePort:
        """Create a console adapter.

        Args:
            console: Optional Rich console instance

        Returns:
            ConsolePort implementation
        """
        return ConsoleAdapter(console)

    @staticmethod
    def create_environment() -> EnvironmentPort:
        """Create an environment adapter.

        Returns:
            EnvironmentPort implementation
        """
        return EnvironmentAdapter()

    @staticmethod
    def create_file_system() -> FileSystemPort:
        """Create a file system adapter.

        Returns:
            FileSystemPort implementation
        """
        return FileSystemAdapter()

    @staticmethod
    def create_configuration() -> ConfigurationPort:
        """Create a configuration adapter.

        Returns:
            ConfigurationPort implementation
        """
        return ConfigurationAdapter()

    @staticmethod
    def create_nats_connection() -> NATSConnectionPort:
        """Create a NATS connection adapter.

        Returns:
            NATSConnectionPort implementation
        """
        return NATSConnectionAdapter()

    @staticmethod
    def create_process_executor() -> ProcessExecutorPort:
        """Create a process executor adapter.

        Returns:
            ProcessExecutorPort implementation
        """
        return ProcessExecutorAdapter()

    @classmethod
    def create_all_adapters(cls, console: Console | None = None) -> dict[str, Any]:
        """Create all infrastructure adapters.

        Args:
            console: Optional Rich console instance

        Returns:
            Dictionary of all adapters keyed by port name
        """
        return {
            "console": cls.create_console(console),
            "environment": cls.create_environment(),
            "file_system": cls.create_file_system(),
            "configuration": cls.create_configuration(),
            "nats": cls.create_nats_connection(),
            "process": cls.create_process_executor(),
        }
