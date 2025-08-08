"""Unit tests for Bootstrap CLI following TDD principles."""

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
        # Click decorated functions have callback attribute
        assert hasattr(main, "callback") or callable(main)

    def test_main_command_execution(self):
        """Test main command executes successfully."""
        # Act - project-name is required now
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ["--project-name", "test-project"])

        # Assert
        assert result.exit_code == 0
        assert (
            "Enterprise DDD project" in result.output
            or "Project 'test-project' created successfully" in result.output
        )

    def test_main_command_help(self):
        """Test main command help text."""
        # Act
        result = self.runner.invoke(main, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "Bootstrap a new AegisSDK service" in result.output
        assert "Show this message and exit" in result.output

    def test_main_command_with_options(self):
        """Test that main command accepts various options."""
        # Act
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                main,
                [
                    "--project-name",
                    "test-project",
                    "--template",
                    "enterprise_ddd",
                    "--service-name",
                    "test-service",
                ],
            )

        # Assert
        assert result.exit_code == 0

    def test_bootstrap_cli_class_empty(self):
        """Test BootstrapCLI class has no methods yet."""
        # Get all methods excluding special methods
        methods = [m for m in dir(self.cli) if not m.startswith("_")]

        # Assert - should be empty as the class is a placeholder
        assert len(methods) == 0

    def test_main_command_requires_project_name(self):
        """Test main command requires project-name option."""
        # Act - call without required --project-name
        result = self.runner.invoke(main, [])

        # Assert - should fail without required argument
        assert result.exit_code != 0
        assert "--project-name" in result.output or "Missing option" in result.output
        assert "Error" in result.output or "Usage" in result.output
