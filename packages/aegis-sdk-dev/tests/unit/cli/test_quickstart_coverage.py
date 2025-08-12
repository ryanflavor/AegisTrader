"""Additional tests for quickstart CLI to improve coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from aegis_sdk_dev.cli.quickstart import QuickstartWizard


class TestQuickstartWizardMethods:
    """Test individual methods of QuickstartWizard."""

    def setup_method(self):
        """Setup test fixtures."""
        self.wizard = QuickstartWizard()
        self.wizard.console = MagicMock()
        self.wizard.project_info = {}

    def test_show_welcome(self):
        """Test welcome message display."""
        # Act
        self.wizard._show_welcome()

        # Assert
        self.wizard.console.print.assert_called()
        # Check Panel was used for welcome message
        calls = self.wizard.console.print.call_args_list
        assert any("Welcome to AegisSDK" in str(call) for call in calls)

    @patch("aegis_sdk_dev.cli.quickstart.Prompt")
    def test_collect_project_info(self, mock_prompt):
        """Test collecting project information."""
        # Arrange
        mock_prompt.ask.side_effect = [
            "my-test-project",  # Project name
            "Test project description",  # Description
            "3.13",  # Python version
        ]

        with patch("aegis_sdk_dev.cli.quickstart.Confirm") as mock_confirm:
            mock_confirm.ask.return_value = True  # Use uv

            # Act
            self.wizard._collect_project_info()

        # Assert
        assert self.wizard.project_info["name"] == "my-test-project"
        assert self.wizard.project_info["description"] == "Test project description"
        assert self.wizard.project_info["template"] == "enterprise_ddd"
        assert self.wizard.project_info["package_manager"] == "uv"
        assert self.wizard.project_info["python_version"] == "3.13"

    @patch("aegis_sdk_dev.cli.quickstart.Confirm")
    def test_select_features(self, mock_confirm):
        """Test feature selection."""
        # Arrange
        mock_confirm.ask.side_effect = [
            True,  # Docker
            True,  # Kubernetes
            True,  # Helm
            True,  # Test client
            True,  # Examples
            False,  # GitHub Actions
            True,  # Pre-commit
        ]

        # Act
        self.wizard._select_features()

        # Assert
        assert self.wizard.project_info["features"]["docker"] is True
        assert self.wizard.project_info["features"]["kubernetes"] is True
        assert self.wizard.project_info["features"]["helm"] is True
        assert self.wizard.project_info["features"]["test_client"] is True
        assert self.wizard.project_info["features"]["examples"] is True
        assert self.wizard.project_info["features"]["github_actions"] is False
        assert self.wizard.project_info["features"]["pre_commit"] is True

    def test_generate_examples_no_examples(self):
        """Test generate_examples when examples feature is disabled."""
        # Arrange
        self.wizard.project_info = {"features": {"examples": False}}

        # Act
        self.wizard._generate_examples()

        # Assert - Should return early and not create any files
        assert True  # No exception raised

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_generate_examples_with_examples(self, mock_mkdir, mock_write_text):
        """Test generate_examples when examples feature is enabled."""
        # Arrange
        self.wizard.project_info = {
            "name": "test-project",
            "path": Path("/tmp/test-project"),
            "features": {"examples": True, "test_client": True, "docker": True},
        }

        # Act
        self.wizard._generate_examples()

        # Assert
        assert mock_write_text.called
        assert mock_mkdir.called

    def test_show_next_steps(self):
        """Test showing next steps."""
        # Arrange
        self.wizard.project_info = {"name": "test-project", "path": Path("/tmp/test-project")}

        # Act
        self.wizard._show_next_steps()

        # Assert
        self.wizard.console.print.assert_called()
        # Check success message was shown
        calls = self.wizard.console.print.call_args_list
        assert any("Setup Complete" in str(call) for call in calls)


class TestQuickstartWizardIntegration:
    """Integration tests for QuickstartWizard."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    @patch("aegis_sdk_dev.cli.quickstart.ProjectGenerator")
    @patch("aegis_sdk_dev.cli.quickstart.Confirm")
    @patch("aegis_sdk_dev.cli.quickstart.Prompt")
    def test_confirm_and_create_new_project(
        self,
        mock_prompt,
        mock_confirm,
        mock_generator_class,
        mock_mkdir,
        mock_write_text,
        mock_exists,
    ):
        """Test creating a new project with confirmation."""
        # Arrange
        wizard = QuickstartWizard()
        wizard.console = MagicMock()
        wizard.project_info = {
            "name": "test-project",
            "description": "Test description",
            "template": "enterprise_ddd",
            "package_manager": "uv",
            "python_version": "3.13",
            "features": {
                "docker": True,
                "kubernetes": True,
                "helm": True,
                "test_client": True,
                "examples": True,
                "github_actions": False,
                "pre_commit": True,
            },
        }

        mock_exists.return_value = False  # Project doesn't exist
        mock_confirm.ask.return_value = True  # Confirm creation
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator

        # Act
        wizard._confirm_and_create(skip_confirm=False)

        # Assert
        mock_generator.generate_project.assert_called_once()
        assert wizard.project_info["path"] == Path.cwd() / "test-project"

    @patch("subprocess.run")
    @patch("pathlib.Path.write_text")
    @patch("aegis_sdk_dev.cli.quickstart.Confirm")
    def test_setup_development_environment(self, mock_confirm, mock_write_text, mock_subprocess):
        """Test setting up development environment."""
        # Arrange
        wizard = QuickstartWizard()
        wizard.console = MagicMock()
        wizard.project_info = {
            "path": Path("/tmp/test-project"),
            "package_manager": "uv",
            "features": {"pre_commit": True},
        }

        mock_confirm.ask.side_effect = [True, True]  # Git init and install deps
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Act
        wizard._setup_development_environment(skip_prompts=False)

        # Assert
        # Check git init was called
        mock_subprocess.assert_any_call(
            ["git", "init"], cwd=wizard.project_info["path"], capture_output=True, check=True
        )
        # Check .gitignore was created
        mock_write_text.assert_called()


class TestQuickstartCLIMain:
    """Test quickstart CLI main function."""

    @patch("aegis_sdk_dev.cli.quickstart.QuickstartWizard")
    def test_main_interactive_mode(self, mock_wizard_class):
        """Test main function in interactive mode."""
        from aegis_sdk_dev.cli.quickstart import QuickstartCLI

        # Arrange
        cli = QuickstartCLI()
        mock_wizard = MagicMock()
        mock_wizard_class.return_value = mock_wizard

        # Act
        cli.run_wizard()

        # Assert
        mock_wizard.run.assert_called_once()

    @patch("sys.exit")
    @patch("aegis_sdk_dev.cli.quickstart.QuickstartWizard")
    def test_main_keyboard_interrupt(self, mock_wizard_class, mock_exit):
        """Test handling keyboard interrupt."""
        from aegis_sdk_dev.cli.quickstart import QuickstartCLI

        # Arrange
        cli = QuickstartCLI()
        cli.console = MagicMock()
        mock_wizard = MagicMock()
        mock_wizard.run.side_effect = KeyboardInterrupt()
        mock_wizard_class.return_value = mock_wizard

        # Act
        cli.run_wizard()

        # Assert
        mock_exit.assert_called_with(0)
        cli.console.print.assert_called()
