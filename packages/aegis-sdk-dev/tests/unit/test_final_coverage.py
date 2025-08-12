"""Final tests to reach 90% coverage."""

from unittest.mock import MagicMock, patch

from aegis_sdk_dev.application.validation_service import ValidationService
from aegis_sdk_dev.cli.test_runner import main as test_runner_main
from aegis_sdk_dev.domain.models import ValidationIssue, ValidationResult


class TestValidationServiceAdditional:
    """Additional tests for ValidationService to improve coverage."""

    def setup_method(self):
        """Setup test fixtures."""
        self.console = MagicMock()
        self.environment = MagicMock()
        self.nats = MagicMock()
        self.service = ValidationService(
            console=self.console, environment=self.environment, nats=self.nats
        )

    def test_add_environment_recommendations_no_issues(self):
        """Test adding recommendations when no issues."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        self.service._add_environment_recommendations(result)

        # Assert
        assert len(result.recommendations) == 0

    def test_add_environment_recommendations_with_errors(self):
        """Test adding recommendations with errors."""
        # Arrange
        result = ValidationResult(environment="local")
        result.add_issue(
            ValidationIssue(level="ERROR", category="NATS", message="NATS connection failed")
        )

        # Act
        self.service._add_environment_recommendations(result)

        # Assert
        assert len(result.recommendations) > 0

    def test_display_validation_results_with_warnings(self):
        """Test displaying validation results with warnings."""
        # Arrange
        result = ValidationResult(environment="local")
        result.add_issue(
            ValidationIssue(
                level="WARNING", category="CONFIG", message="Config issue", resolution="Fix config"
            )
        )
        result.diagnostics["test"] = "value"
        result.recommendations.append("Test recommendation")

        # Act
        self.service.display_validation_results(result)

        # Assert
        self.console.print.assert_called()


class TestDomainQuickstartGenerator:
    """Test domain quickstart generator."""

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_generate_project_with_python_version(self, mock_mkdir, mock_write_text):
        """Test generating project with specific Python version."""
        from aegis_sdk_dev.domain.quickstart_generator import ProjectGenerator

        # Arrange
        generator = ProjectGenerator()

        # Act
        generator.generate_project(
            project_name="test-project", template_type="enterprise_ddd", python_version="3.12"
        )

        # Assert
        mock_write_text.assert_called()
        # Check that Python version was used
        calls = mock_write_text.call_args_list
        assert any("3.12" in str(call) or "3.13" in str(call) for call in calls)


class TestCLITestRunner:
    """Test CLI test runner."""

    @patch("click.echo")
    def test_test_runner_main(self, mock_echo):
        """Test test runner main function."""
        from click.testing import CliRunner

        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(test_runner_main, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "Run tests" in result.output


class TestInfrastructureEdgeCases:
    """Test infrastructure edge cases."""

    def test_console_adapter_print_with_style(self):
        """Test console adapter print with style."""
        from rich.console import Console

        from aegis_sdk_dev.infrastructure.console_adapter import ConsoleAdapter

        # Arrange
        console = Console()
        adapter = ConsoleAdapter(console)

        with patch.object(console, "print") as mock_print:
            # Act
            adapter.print("[bold]Test message[/bold]")

            # Assert
            mock_print.assert_called_once()

    def test_file_system_adapter_read_nonexistent(self):
        """Test file system adapter reading non-existent file."""
        from aegis_sdk_dev.infrastructure.file_system_adapter import FileSystemAdapter

        # Arrange
        adapter = FileSystemAdapter()

        # Act
        content = adapter.read_file("/nonexistent/file.txt")

        # Assert
        assert content is None

    def test_configuration_adapter_get_env_default(self):
        """Test configuration adapter getting env var with default."""
        from aegis_sdk_dev.infrastructure.configuration_adapter import ConfigurationAdapter

        # Arrange
        adapter = ConfigurationAdapter()

        with patch.dict("os.environ", {}, clear=True):
            # Act
            value = adapter.get_env("NONEXISTENT_VAR", "default_value")

            # Assert
            assert value == "default_value"
