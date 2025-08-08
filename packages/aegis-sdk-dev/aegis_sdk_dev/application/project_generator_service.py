"""Project generator application service."""

from __future__ import annotations

from aegis_sdk_dev.domain.models import BootstrapConfig
from aegis_sdk_dev.domain.simple_project_generator import SimpleProjectGenerator
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.file_system import FileSystemPort


class ProjectGeneratorService:
    """Application service for project generation use cases."""

    def __init__(
        self,
        console: ConsolePort,
        file_system: FileSystemPort,
        template_generator=None,
    ):
        """Initialize project generator service.

        Args:
            console: Console port for user interaction
            file_system: File system port for file operations
            template_generator: Optional template generator for enterprise DDD templates
        """
        self._console = console
        self._file_system = file_system
        self._generator = SimpleProjectGenerator(template_generator)

    def generate_project(self, config: BootstrapConfig) -> bool:
        """Generate a new project based on configuration.

        Args:
            config: Bootstrap configuration

        Returns:
            True if successful, False otherwise
        """
        self._console.print(f"[cyan]Generating project: {config.project_name}[/cyan]")
        self._console.print(f"Template: {config.template.value}")
        self._console.print(f"Output directory: {config.output_dir}")

        try:
            # Generate file structure
            files = self._generator.generate_project(config)

            # Create directories and write files
            for file_path, content in files.items():
                self._write_project_file(file_path, content)

            self._console.print_success(f"Project {config.project_name} generated successfully!")
            self._console.print(f"Created {len(files)} files")

            # Display next steps
            self._display_next_steps(config)

            return True

        except Exception as e:
            self._console.print_error(f"Failed to generate project: {e}")
            return False

    def _write_project_file(self, path: str, content: str) -> None:
        """Write a project file, creating directories as needed.

        Args:
            path: File path
            content: File content
        """
        # Extract directory from path
        import os

        directory = os.path.dirname(path)

        # Create directory if it doesn't exist
        if directory and not self._file_system.path_exists(directory):
            self._file_system.create_directory(directory)

        # Write file
        self._file_system.write_file(path, content)
        self._console.print(f"  Created: {path}")

    def _display_next_steps(self, config: BootstrapConfig) -> None:
        """Display next steps after project generation.

        Args:
            config: Bootstrap configuration
        """
        self._console.print("\n[bold green]Next Steps:[/bold green]")
        self._console.print(f"1. cd {config.output_dir}/{config.project_name}")
        self._console.print("2. pip install -r requirements.txt")

        if config.include_tests:
            self._console.print("3. pytest tests/")

        if config.include_docker:
            self._console.print(f"4. docker build -t {config.project_name} .")

        if config.include_k8s:
            self._console.print("5. kubectl apply -f k8s/")

        self._console.print("\n[bold]Configuration:[/bold]")
        self._console.print(f"  Service Name: {config.service_config.service_name}")
        self._console.print(f"  NATS URL: {config.service_config.nats_url}")
        self._console.print(f"  Environment: {config.service_config.environment}")

    def validate_project_structure(self, project_path: str) -> tuple[bool, list[str]]:
        """Validate an existing project structure.

        Args:
            project_path: Path to the project

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check required directories
        required_dirs = ["domain", "application", "ports", "infrastructure"]
        for dir_name in required_dirs:
            dir_path = f"{project_path}/{dir_name}"
            if not self._file_system.path_exists(dir_path):
                issues.append(f"Missing required directory: {dir_name}")

        # Check required files
        required_files = ["main.py", "requirements.txt"]
        for file_name in required_files:
            file_path = f"{project_path}/{file_name}"
            if not self._file_system.path_exists(file_path):
                issues.append(f"Missing required file: {file_name}")

        # Check for __init__.py files in Python packages
        for dir_name in required_dirs:
            init_file = f"{project_path}/{dir_name}/__init__.py"
            if self._file_system.path_exists(
                f"{project_path}/{dir_name}"
            ) and not self._file_system.path_exists(init_file):
                issues.append(f"Missing __init__.py in {dir_name}")

        is_valid = len(issues) == 0
        return is_valid, issues

    def list_available_templates(self) -> list[str]:
        """List available project templates.

        Returns:
            List of template names
        """
        from aegis_sdk_dev.domain.models import ProjectTemplate

        templates = []
        for template in ProjectTemplate:
            templates.append(f"{template.value} - {self._get_template_description(template)}")

        return templates

    def _get_template_description(self, template) -> str:
        """Get description for a project template.

        Args:
            template: Project template

        Returns:
            Template description
        """
        from aegis_sdk_dev.domain.models import ProjectTemplate

        descriptions = {
            ProjectTemplate.BASIC: "Simple service with minimal structure",
            ProjectTemplate.SINGLE_ACTIVE: "Service with single-active pattern",
            ProjectTemplate.EVENT_DRIVEN: "Event-driven service with message handlers",
            ProjectTemplate.FULL_FEATURED: "Complete service with all features",
        }
        return descriptions.get(template, "No description available")
