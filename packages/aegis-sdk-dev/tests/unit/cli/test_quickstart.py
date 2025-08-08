"""Unit tests for Quickstart CLI following TDD principles."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from rich.console import Console

from aegis_sdk_dev.cli.quickstart import QuickstartCLI, main


class TestQuickstartCLI:
    """Test QuickstartCLI implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = QuickstartCLI()
        self.runner = CliRunner()

    def test_quickstart_cli_instantiation(self):
        """Test that QuickstartCLI can be instantiated."""
        # Assert
        assert isinstance(self.cli, QuickstartCLI)
        assert hasattr(self.cli, "console")
        assert isinstance(self.cli.console, Console)

    def test_quickstart_cli_has_console(self):
        """Test that QuickstartCLI has a console attribute."""
        # Assert
        assert self.cli.console is not None
        assert isinstance(self.cli.console, Console)

    @patch("aegis_sdk_dev.cli.quickstart.Console")
    def test_quickstart_cli_creates_console(self, MockConsole):
        """Test that QuickstartCLI creates its own console."""
        # Arrange
        mock_console = MagicMock()
        MockConsole.return_value = mock_console

        # Act
        cli = QuickstartCLI()

        # Assert
        MockConsole.assert_called_once()
        assert cli.console == mock_console

    def test_main_command_exists(self):
        """Test that main command is a click command."""
        # Assert
        assert callable(main)
        # Click decorated functions have callback attribute
        assert hasattr(main, "callback") or callable(main)

    def test_main_command_execution(self):
        """Test main command executes successfully."""
        # Act
        result = self.runner.invoke(main)

        # Assert
        assert result.exit_code == 0
        assert "AegisSDK Quickstart" in result.output
        assert "aegis-sdk-examples" in result.output

    def test_main_command_help(self):
        """Test main command help text."""
        # Act
        result = self.runner.invoke(main, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "Launch quickstart wizard" in result.output
        assert "creating new services" in result.output

    @patch("aegis_sdk_dev.cli.quickstart.Console")
    def test_main_command_console_output(self, MockConsole):
        """Test that main command uses Console for output."""
        # Arrange
        mock_console = MagicMock()
        MockConsole.return_value = mock_console

        # Act
        result = self.runner.invoke(main)

        # Assert
        assert result.exit_code == 0
        MockConsole.assert_called_once()
        # Verify print was called with expected content
        assert mock_console.print.call_count == 2
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("AegisSDK Quickstart" in call for call in calls)
        assert any("aegis-sdk-examples" in call for call in calls)

    def test_main_command_no_arguments(self):
        """Test main command requires no arguments."""
        # Act
        result = self.runner.invoke(main, ["unexpected-arg"])

        # Assert - Click should handle unexpected arguments
        assert result.exit_code != 0
        assert "Error" in result.output or "Usage" in result.output

    def test_quickstart_cli_methods(self):
        """Test QuickstartCLI has expected methods."""
        # Get all public methods
        methods = [m for m in dir(self.cli) if not m.startswith("_")]

        # Assert - should have console attribute
        assert "console" in methods
