"""Unit tests for Bootstrap CLI following TDD principles."""

from unittest.mock import patch

from click.testing import CliRunner

from aegis_sdk_dev.cli.bootstrap import BootstrapCLI, main


class TestBootstrapCLI:
    """Test BootstrapCLI implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = BootstrapCLI()
        self.runner = CliRunner()

    def test_bootstrap_cli_instantiation(self):
        """Test that BootstrapCLI can be instantiated."""
        # Assert
        assert isinstance(self.cli, BootstrapCLI)

    def test_main_command_exists(self):
        """Test that main command is a click command."""
        # Assert
        assert callable(main)
        assert hasattr(main, "__click_params__")

    def test_main_command_execution(self):
        """Test main command executes successfully."""
        # Act
        result = self.runner.invoke(main)

        # Assert
        assert result.exit_code == 0
        assert "Bootstrap service" in result.output
        assert "aegis-sdk-examples" in result.output

    def test_main_command_help(self):
        """Test main command help text."""
        # Act
        result = self.runner.invoke(main, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "Bootstrap a new AegisSDK service" in result.output
        assert "Show this message and exit" in result.output

    @patch("aegis_sdk_dev.cli.bootstrap.click.echo")
    def test_main_command_output(self, mock_echo):
        """Test that main command produces expected output."""
        # Act
        result = self.runner.invoke(main)

        # Assert
        assert result.exit_code == 0
        mock_echo.assert_called_once_with(
            "Bootstrap service - see aegis-sdk-examples for templates"
        )

    def test_bootstrap_cli_class_empty(self):
        """Test BootstrapCLI class has no methods yet."""
        # Get all methods excluding special methods
        methods = [m for m in dir(self.cli) if not m.startswith("_")]

        # Assert - should be empty as the class is a placeholder
        assert len(methods) == 0

    def test_main_command_no_arguments(self):
        """Test main command requires no arguments."""
        # Act
        result = self.runner.invoke(main, ["unexpected-arg"])

        # Assert - Click should handle unexpected arguments
        assert result.exit_code != 0
        assert "Error" in result.output or "Usage" in result.output
