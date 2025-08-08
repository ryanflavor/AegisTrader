"""Simplified CLI error handling tests that test actual functionality."""

from unittest.mock import patch

from click.testing import CliRunner

from aegis_sdk_dev.cli.bootstrap import main as bootstrap_main
from aegis_sdk_dev.cli.config_validator import main as config_validator_main
from aegis_sdk_dev.cli.quickstart import main as quickstart_main
from aegis_sdk_dev.cli.test_runner import main as test_runner_main


class TestCLIBasicErrorHandling:
    """Test basic error handling for all CLIs."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_bootstrap_with_invalid_arguments(self):
        """Test bootstrap with invalid arguments."""
        # Act
        result = self.runner.invoke(bootstrap_main, ["--invalid-arg"])

        # Assert
        assert result.exit_code != 0
        assert "Error" in result.output or "no such option" in result.output

    def test_quickstart_with_invalid_arguments(self):
        """Test quickstart with invalid arguments."""
        # Act
        result = self.runner.invoke(quickstart_main, ["--invalid-arg"])

        # Assert
        assert result.exit_code != 0
        assert "Error" in result.output or "no such option" in result.output

    def test_test_runner_with_invalid_arguments(self):
        """Test test runner with invalid arguments."""
        # Act
        result = self.runner.invoke(test_runner_main, ["--invalid-arg"])

        # Assert
        assert result.exit_code != 0
        assert "Error" in result.output or "no such option" in result.output

    def test_config_validator_missing_required_argument(self):
        """Test config validator missing required argument."""
        # Act - service-name is required
        result = self.runner.invoke(config_validator_main, [])

        # Assert
        assert result.exit_code != 0
        assert "Missing" in result.output or "required" in result.output

    @patch("aegis_sdk_dev.cli.bootstrap.click.echo")
    def test_bootstrap_echo_failure(self, mock_echo):
        """Test bootstrap when echo fails."""
        # Arrange
        mock_echo.side_effect = RuntimeError("Echo failed")

        # Act
        result = self.runner.invoke(bootstrap_main)

        # Assert
        assert result.exit_code != 0
        assert "Echo failed" in str(result.exception)

    @patch("aegis_sdk_dev.cli.quickstart.Console")
    def test_quickstart_console_failure(self, mock_console_class):
        """Test quickstart when console creation fails."""
        # Arrange
        mock_console_class.side_effect = RuntimeError("Console init failed")

        # Act
        result = self.runner.invoke(quickstart_main)

        # Assert
        assert result.exit_code != 0
        assert "Console init failed" in str(result.exception)

    @patch("aegis_sdk_dev.cli.test_runner.click.echo")
    def test_test_runner_echo_failure(self, mock_echo):
        """Test test runner when echo fails."""
        # Arrange
        mock_echo.side_effect = RuntimeError("Echo failed")

        # Act
        result = self.runner.invoke(test_runner_main)

        # Assert
        assert result.exit_code != 0
        assert "Echo failed" in str(result.exception)
