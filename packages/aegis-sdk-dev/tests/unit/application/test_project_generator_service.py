"""Unit tests for ProjectGeneratorService following TDD and hexagonal architecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aegis_sdk_dev.application.project_generator_service import ProjectGeneratorService
from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ProjectTemplate,
    ServiceConfiguration,
)


class TestProjectGeneratorService:
    """Test suite for ProjectGeneratorService."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Create mock ports (adapters)
        self.mock_console = MagicMock()
        self.mock_file_system = MagicMock()

        # Create service under test with mocked infrastructure
        self.service = ProjectGeneratorService(
            console=self.mock_console,
            file_system=self.mock_file_system,
        )

        # Create a sample configuration
        self.config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            output_dir="/tmp",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="development",
            ),
            include_tests=True,
            include_docker=True,
            include_k8s=True,
        )

    def test_generate_project_success(self):
        """Test successful project generation."""
        # Arrange
        expected_files = {
            "/tmp/test-project/main.py": "print('hello')",
            "/tmp/test-project/requirements.txt": "aegis-sdk>=1.0.0",
            "/tmp/test-project/domain/__init__.py": "",
            "/tmp/test-project/application/__init__.py": "",
        }

        with patch.object(
            self.service._generator,
            "generate_project",
            return_value=expected_files,
        ):
            self.mock_file_system.path_exists.return_value = False

            # Act
            result = self.service.generate_project(self.config)

            # Assert
            assert result is True

            # Verify console output
            self.mock_console.print.assert_any_call("[cyan]Generating project: test-project[/cyan]")
            self.mock_console.print.assert_any_call("Template: basic")
            self.mock_console.print.assert_any_call("Output directory: /tmp")
            self.mock_console.print_success.assert_called_once_with(
                "Project test-project generated successfully!"
            )

            # Verify file system operations
            assert self.mock_file_system.create_directory.call_count == 4
            assert self.mock_file_system.write_file.call_count == 4

            # Verify next steps displayed
            self.mock_console.print.assert_any_call("\n[bold green]Next Steps:[/bold green]")

    def test_generate_project_handles_exception(self):
        """Test project generation handles exceptions gracefully."""
        # Arrange
        with patch.object(
            self.service._generator,
            "generate_project",
            side_effect=ValueError("Invalid template"),
        ):
            # Act
            result = self.service.generate_project(self.config)

            # Assert
            assert result is False
            self.mock_console.print_error.assert_called_once_with(
                "Failed to generate project: Invalid template"
            )

    def test_write_project_file_creates_directory_if_not_exists(self):
        """Test file writing creates directories as needed."""
        # Arrange
        self.mock_file_system.path_exists.return_value = False

        # Act
        self.service._write_project_file("/tmp/test-project/domain/models.py", "# Domain models")

        # Assert
        self.mock_file_system.create_directory.assert_called_once_with("/tmp/test-project/domain")
        self.mock_file_system.write_file.assert_called_once_with(
            "/tmp/test-project/domain/models.py", "# Domain models"
        )
        self.mock_console.print.assert_called_with("  Created: /tmp/test-project/domain/models.py")

    def test_write_project_file_skips_directory_creation_if_exists(self):
        """Test file writing skips directory creation if it already exists."""
        # Arrange
        self.mock_file_system.path_exists.return_value = True

        # Act
        self.service._write_project_file("/tmp/test-project/main.py", "# Main file")

        # Assert
        self.mock_file_system.create_directory.assert_not_called()
        self.mock_file_system.write_file.assert_called_once()

    def test_write_project_file_handles_root_level_files(self):
        """Test writing files at root level without directory creation."""
        # Arrange
        self.mock_file_system.path_exists.return_value = True

        # Act
        self.service._write_project_file("README.md", "# Project")

        # Assert
        self.mock_file_system.create_directory.assert_not_called()
        self.mock_file_system.write_file.assert_called_once_with("README.md", "# Project")

    def test_display_next_steps_all_options(self):
        """Test display of next steps with all options enabled."""
        # Act
        self.service._display_next_steps(self.config)

        # Assert
        calls = self.mock_console.print.call_args_list

        # Verify all expected next steps are displayed
        assert any("Next Steps" in str(c) for c in calls)
        assert any("cd /tmp/test-project" in str(c) for c in calls)
        assert any("pip install -r requirements.txt" in str(c) for c in calls)
        assert any("pytest tests/" in str(c) for c in calls)
        assert any("docker build" in str(c) for c in calls)
        assert any("kubectl apply" in str(c) for c in calls)

        # Verify configuration display
        assert any("Service Name: test-service" in str(c) for c in calls)
        assert any("NATS URL: nats://localhost:4222" in str(c) for c in calls)
        assert any("Environment: development" in str(c) for c in calls)

    def test_display_next_steps_minimal_options(self):
        """Test display of next steps with minimal options."""
        # Arrange
        minimal_config = BootstrapConfig(
            project_name="minimal",
            template=ProjectTemplate.BASIC,
            output_dir="/home",
            service_config=ServiceConfiguration(
                service_name="minimal-service",
                nats_url="nats://nats:4222",
                environment="production",
            ),
            include_tests=False,
            include_docker=False,
            include_k8s=False,
        )

        # Act
        self.service._display_next_steps(minimal_config)

        # Assert
        calls = self.mock_console.print.call_args_list

        # Should not include optional steps
        assert not any("pytest" in str(c) for c in calls)
        assert not any("docker build" in str(c) for c in calls)
        assert not any("kubectl" in str(c) for c in calls)

        # Should still include basic steps
        assert any("cd /home/minimal" in str(c) for c in calls)
        assert any("pip install" in str(c) for c in calls)

    def test_validate_project_structure_valid_project(self):
        """Test validation of a valid project structure."""
        # Arrange
        project_path = "/tmp/valid-project"

        # Mock all required paths as existing
        def path_exists_side_effect(path):
            required_paths = [
                f"{project_path}/domain",
                f"{project_path}/application",
                f"{project_path}/ports",
                f"{project_path}/infrastructure",
                f"{project_path}/main.py",
                f"{project_path}/requirements.txt",
                f"{project_path}/domain/__init__.py",
                f"{project_path}/application/__init__.py",
                f"{project_path}/ports/__init__.py",
                f"{project_path}/infrastructure/__init__.py",
            ]
            return path in required_paths

        self.mock_file_system.path_exists.side_effect = path_exists_side_effect

        # Act
        is_valid, issues = self.service.validate_project_structure(project_path)

        # Assert
        assert is_valid is True
        assert issues == []

    def test_validate_project_structure_missing_directories(self):
        """Test validation detects missing directories."""
        # Arrange
        project_path = "/tmp/invalid-project"

        # Mock only some paths as existing
        def path_exists_side_effect(path):
            existing_paths = [
                f"{project_path}/domain",
                f"{project_path}/main.py",
                f"{project_path}/requirements.txt",
                f"{project_path}/domain/__init__.py",
            ]
            return path in existing_paths

        self.mock_file_system.path_exists.side_effect = path_exists_side_effect

        # Act
        is_valid, issues = self.service.validate_project_structure(project_path)

        # Assert
        assert is_valid is False
        assert "Missing required directory: application" in issues
        assert "Missing required directory: ports" in issues
        assert "Missing required directory: infrastructure" in issues

    def test_validate_project_structure_missing_files(self):
        """Test validation detects missing required files."""
        # Arrange
        project_path = "/tmp/partial-project"

        # Mock directories exist but files missing
        def path_exists_side_effect(path):
            existing_paths = [
                f"{project_path}/domain",
                f"{project_path}/application",
                f"{project_path}/ports",
                f"{project_path}/infrastructure",
                # main.py is missing
                f"{project_path}/requirements.txt",
                # __init__.py files are missing
            ]
            return path in existing_paths

        self.mock_file_system.path_exists.side_effect = path_exists_side_effect

        # Act
        is_valid, issues = self.service.validate_project_structure(project_path)

        # Assert
        assert is_valid is False
        assert "Missing required file: main.py" in issues
        assert "Missing __init__.py in domain" in issues
        assert "Missing __init__.py in application" in issues
        assert "Missing __init__.py in ports" in issues
        assert "Missing __init__.py in infrastructure" in issues

    def test_validate_project_structure_empty_project(self):
        """Test validation of completely empty project directory."""
        # Arrange
        self.mock_file_system.path_exists.return_value = False

        # Act
        is_valid, issues = self.service.validate_project_structure("/tmp/empty")

        # Assert
        assert is_valid is False
        assert len(issues) >= 6  # At least 4 dirs + 2 files missing

    def test_list_available_templates(self):
        """Test listing of available project templates."""
        # Act
        templates = self.service.list_available_templates()

        # Assert
        assert len(templates) >= 5  # Should have at least the basic templates
        assert any("basic" in t.lower() for t in templates)
        assert any("single_active" in t.lower() for t in templates)
        assert any("event_driven" in t.lower() for t in templates)
        assert any("full_featured" in t.lower() for t in templates)
        assert any("microservice" in t.lower() for t in templates)

        # Each template should have a description
        for template in templates:
            assert " - " in template  # Format: "name - description"

    def test_get_template_description_all_templates(self):
        """Test getting descriptions for all template types."""
        # Arrange
        templates_and_expected = [
            (ProjectTemplate.BASIC, "Simple service with minimal structure"),
            (ProjectTemplate.SINGLE_ACTIVE, "Service with single-active pattern"),
            (
                ProjectTemplate.EVENT_DRIVEN,
                "Event-driven service with message handlers",
            ),
            (ProjectTemplate.FULL_FEATURED, "Complete service with all features"),
            (
                ProjectTemplate.MICROSERVICE,
                "No description available",
            ),  # Test the default case
        ]

        # Act & Assert
        for template, expected_desc in templates_and_expected:
            description = self.service._get_template_description(template)
            assert description == expected_desc

    def test_generate_project_with_different_templates(self):
        """Test project generation with different template types."""
        # Arrange
        templates = [
            ProjectTemplate.BASIC,
            ProjectTemplate.SINGLE_ACTIVE,
            ProjectTemplate.EVENT_DRIVEN,
            ProjectTemplate.FULL_FEATURED,
            ProjectTemplate.MICROSERVICE,
        ]

        for template in templates:
            # Reset mocks
            self.mock_console.reset_mock()
            self.mock_file_system.reset_mock()

            config = BootstrapConfig(
                project_name=f"test-{template.value}",
                template=template,
                output_dir="/tmp",
                service_config=ServiceConfiguration(
                    service_name=f"service-{template.value}",
                    nats_url="nats://localhost:4222",
                    environment="local",
                ),
                include_tests=True,
                include_docker=False,
                include_k8s=False,
            )

            with patch.object(
                self.service._generator,
                "generate_project",
                return_value={"/tmp/test/main.py": "# Main"},
            ):
                # Act
                result = self.service.generate_project(config)

                # Assert
                assert result is True
                self.mock_console.print.assert_any_call(f"Template: {template.value}")

    def test_generate_project_handles_file_system_errors(self):
        """Test project generation handles file system errors gracefully."""
        # Arrange
        with patch.object(
            self.service._generator,
            "generate_project",
            return_value={"/tmp/test/main.py": "content"},
        ):
            self.mock_file_system.write_file.side_effect = OSError("Permission denied")

            # Act
            result = self.service.generate_project(self.config)

            # Assert
            assert result is False
            self.mock_console.print_error.assert_called_once()
            error_message = self.mock_console.print_error.call_args[0][0]
            assert "Permission denied" in error_message

    def test_generate_project_creates_multiple_nested_directories(self):
        """Test project generation handles deeply nested directory structures."""
        # Arrange
        nested_files = {
            "/tmp/proj/src/domain/models/user.py": "class User: pass",
            "/tmp/proj/src/infrastructure/adapters/db.py": "class DB: pass",
            "/tmp/proj/tests/unit/domain/test_user.py": "def test_user(): pass",
        }

        with patch.object(
            self.service._generator,
            "generate_project",
            return_value=nested_files,
        ):
            self.mock_file_system.path_exists.return_value = False

            # Act
            result = self.service.generate_project(self.config)

            # Assert
            assert result is True

            # Verify directories were created for each unique path
            expected_dirs = [
                "/tmp/proj/src/domain/models",
                "/tmp/proj/src/infrastructure/adapters",
                "/tmp/proj/tests/unit/domain",
            ]

            for expected_dir in expected_dirs:
                self.mock_file_system.create_directory.assert_any_call(expected_dir)

    def test_validate_project_structure_handles_partial_structure(self):
        """Test validation with partially valid structure."""
        # Arrange
        project_path = "/tmp/partial"

        def path_exists_side_effect(path):
            # Domain exists with __init__ but application doesn't
            existing = [
                f"{project_path}/domain",
                f"{project_path}/domain/__init__.py",
                f"{project_path}/ports",  # No __init__.py
                f"{project_path}/main.py",
                # requirements.txt missing
            ]
            return path in existing

        self.mock_file_system.path_exists.side_effect = path_exists_side_effect

        # Act
        is_valid, issues = self.service.validate_project_structure(project_path)

        # Assert
        assert is_valid is False
        assert len(issues) > 0

        # Check specific issues
        assert any("application" in issue for issue in issues)
        assert any("infrastructure" in issue for issue in issues)
        assert any("requirements.txt" in issue for issue in issues)
        assert any("ports" in issue and "__init__.py" in issue for issue in issues)

    def test_generate_project_with_empty_config(self):
        """Test project generation with minimal/empty optional config."""
        # Arrange
        minimal_config = BootstrapConfig(
            project_name="minimal",
            template=ProjectTemplate.BASIC,
            output_dir="/tmp",
            service_config=ServiceConfiguration(
                service_name="svc",
                nats_url="nats://localhost:4222",
                environment="dev",
            ),
            include_tests=False,
            include_docker=False,
            include_k8s=False,
        )

        with patch.object(
            self.service._generator,
            "generate_project",
            return_value={"/tmp/minimal/main.py": "# Minimal"},
        ):
            self.mock_file_system.path_exists.return_value = True

            # Act
            result = self.service.generate_project(minimal_config)

            # Assert
            assert result is True

            # Verify minimal next steps (no test/docker/k8s steps)
            calls = [str(c) for c in self.mock_console.print.call_args_list]
            assert not any("pytest" in str(c) for c in calls)
            assert not any("docker" in str(c) for c in calls)
            assert not any("kubectl" in str(c) for c in calls)
