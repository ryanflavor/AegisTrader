"""Tests for CLI tools."""

from unittest.mock import Mock, patch

from click.testing import CliRunner

from aegis_sdk_dev.cli import bootstrap_cli, quickstart_cli, test_cli, validate_cli


class TestValidateCLI:
    """Test the validate CLI command."""

    def test_validate_help(self):
        """Test validate --help."""
        runner = CliRunner()
        result = runner.invoke(validate_cli, ["--help"])
        assert result.exit_code == 0
        assert "Configuration validation" in result.output

    @patch("aegis_sdk_dev.cli.validate_service_config")
    def test_validate_success(self, mock_validate):
        """Test successful validation."""
        mock_validate.return_value = (True, "Configuration is valid")

        runner = CliRunner()
        result = runner.invoke(validate_cli, ["--config", "test.yaml"])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    @patch("aegis_sdk_dev.cli.validate_service_config")
    def test_validate_failure(self, mock_validate):
        """Test validation failure."""
        mock_validate.return_value = (False, "Invalid configuration: missing field")

        runner = CliRunner()
        result = runner.invoke(validate_cli, ["--config", "test.yaml"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_validate_missing_config(self):
        """Test validation with missing config file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(validate_cli, ["--config", "nonexistent.yaml"])
            assert result.exit_code != 0


class TestQuickstartCLI:
    """Test the quickstart CLI command."""

    def test_quickstart_help(self):
        """Test quickstart --help."""
        runner = CliRunner()
        result = runner.invoke(quickstart_cli, ["--help"])
        assert result.exit_code == 0
        assert "Create a new AegisSDK service" in result.output

    @patch("aegis_sdk_dev.cli.create_project")
    def test_quickstart_interactive_mode(self, mock_create):
        """Test interactive mode project creation."""
        mock_create.return_value = True

        runner = CliRunner()
        # Simulate user input
        result = runner.invoke(quickstart_cli, input="test-service\nTest service\nbasic\ny\ny\ny\n")

        assert result.exit_code == 0
        assert mock_create.called

    @patch("aegis_sdk_dev.cli.create_project")
    def test_quickstart_with_args(self, mock_create):
        """Test quickstart with command line arguments."""
        mock_create.return_value = True

        runner = CliRunner()
        result = runner.invoke(quickstart_cli, ["--name", "test-service", "--template", "basic"])

        assert result.exit_code == 0
        assert mock_create.called

    def test_quickstart_invalid_template(self):
        """Test quickstart with invalid template."""
        runner = CliRunner()
        result = runner.invoke(quickstart_cli, ["--name", "test", "--template", "invalid"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()


class TestBootstrapCLI:
    """Test the bootstrap CLI command."""

    def test_bootstrap_help(self):
        """Test bootstrap --help."""
        runner = CliRunner()
        result = runner.invoke(bootstrap_cli, ["--help"])
        assert result.exit_code == 0
        assert "Bootstrap a service" in result.output

    @patch("aegis_sdk_dev.cli.bootstrap_service")
    def test_bootstrap_success(self, mock_bootstrap):
        """Test successful bootstrap."""
        mock_service = Mock()
        mock_bootstrap.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(bootstrap_cli, ["--service-name", "test", "--service-type", "basic"])

        assert result.exit_code == 0
        assert "bootstrapped" in result.output.lower()

    @patch("aegis_sdk_dev.cli.bootstrap_service")
    def test_bootstrap_with_nats_url(self, mock_bootstrap):
        """Test bootstrap with NATS URL."""
        mock_service = Mock()
        mock_bootstrap.return_value = mock_service

        runner = CliRunner()
        result = runner.invoke(
            bootstrap_cli,
            [
                "--service-name",
                "test",
                "--service-type",
                "basic",
                "--nats-url",
                "nats://localhost:4222",
            ],
        )

        assert result.exit_code == 0
        mock_bootstrap.assert_called_once()
        config = mock_bootstrap.call_args[0][0]
        assert config.nats_url == "nats://localhost:4222"


class TestTestCLI:
    """Test the test runner CLI command."""

    def test_test_help(self):
        """Test test --help."""
        runner = CliRunner()
        result = runner.invoke(test_cli, ["--help"])
        assert result.exit_code == 0
        assert "Run tests" in result.output

    @patch("aegis_sdk_dev.cli.run_tests")
    def test_run_unit_tests(self, mock_run):
        """Test running unit tests."""
        mock_run.return_value = 0  # Success

        runner = CliRunner()
        result = runner.invoke(test_cli, ["--type", "unit"])

        assert result.exit_code == 0
        mock_run.assert_called_with("unit", verbose=False)

    @patch("aegis_sdk_dev.cli.run_tests")
    def test_run_integration_tests(self, mock_run):
        """Test running integration tests."""
        mock_run.return_value = 0  # Success

        runner = CliRunner()
        result = runner.invoke(test_cli, ["--type", "integration", "--verbose"])

        assert result.exit_code == 0
        mock_run.assert_called_with("integration", verbose=True)

    @patch("aegis_sdk_dev.cli.run_tests")
    def test_test_failure(self, mock_run):
        """Test handling test failures."""
        mock_run.return_value = 1  # Failure

        runner = CliRunner()
        result = runner.invoke(test_cli, ["--type", "all"])

        assert result.exit_code == 1
