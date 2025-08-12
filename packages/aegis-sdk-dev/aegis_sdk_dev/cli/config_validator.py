"""Configuration validator CLI tool for AegisSDK services."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

import click
from pydantic import BaseModel, Field, field_validator
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table


class ValidationIssue(BaseModel):
    """Value Object representing a configuration validation issue."""

    level: str = Field(..., description="Issue severity: ERROR, WARNING, INFO")
    category: str = Field(..., description="Issue category: NATS, K8S, CONFIG, etc.")
    message: str = Field(..., description="Human-readable issue description")
    resolution: str | None = Field(None, description="Suggested resolution steps")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Ensure level is valid."""
        valid_levels = {"ERROR", "WARNING", "INFO"}
        if v not in valid_levels:
            raise ValueError(f"Level must be one of {valid_levels}")
        return v

    model_config = {"strict": True}


class ValidationResult(BaseModel):
    """Aggregate representing the complete validation result."""

    is_valid: bool = Field(default=True, description="Overall validation status")
    environment: str = Field(..., description="Detected environment")
    issues: list[ValidationIssue] = Field(default_factory=list, description="All validation issues")
    diagnostics: dict[str, Any] = Field(default_factory=dict, description="Diagnostic information")
    recommendations: list[str] = Field(default_factory=list, description="Recommended actions")

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue to the result."""
        self.issues.append(issue)
        if issue.level == "ERROR":
            self.is_valid = False

    def get_issues_by_level(self, level: str) -> list[ValidationIssue]:
        """Get all issues of a specific level."""
        return [issue for issue in self.issues if issue.level == level]

    def get_issues_by_category(self, category: str) -> list[ValidationIssue]:
        """Get all issues of a specific category."""
        return [issue for issue in self.issues if issue.category == category.upper()]


class ConfigValidator:
    """Domain service for validating AegisSDK configurations."""

    def __init__(self, console: Console | None = None):
        """Initialize the validator.

        Args:
            console: Optional Rich console instance for output
        """
        self.console = console or Console()

    async def validate_all(
        self, service_name: str, nats_url: str | None = None, environment: str = "auto"
    ) -> ValidationResult:
        """Validate all aspects of the configuration."""
        result = ValidationResult(environment=environment)

        # Detect environment if auto
        if environment == "auto":
            result.environment = self._detect_environment()
            result.diagnostics["detected_environment"] = result.environment

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Validate service name
            task = progress.add_task("Validating service name...", total=1)
            self._validate_service_name(service_name, result)
            progress.update(task, advance=1)

            # Check project structure
            task = progress.add_task("Checking project structure...", total=1)
            self._check_project_structure(service_name, result)
            progress.update(task, advance=1)

            # Validate configuration files
            task = progress.add_task("Validating configuration files...", total=1)
            self._validate_config_files(service_name, result)
            progress.update(task, advance=1)

            # Check NATS connection if URL provided
            if nats_url:
                task = progress.add_task("Testing NATS connection...", total=1)
                await self._check_nats_connection(nats_url, result)
                progress.update(task, advance=1)

            # Check Docker setup
            task = progress.add_task("Checking Docker setup...", total=1)
            self._check_docker_setup(service_name, result)
            progress.update(task, advance=1)

            # Check Kubernetes setup if in k8s environment
            if result.environment == "kubernetes":
                task = progress.add_task("Checking Kubernetes setup...", total=1)
                self._check_kubernetes_setup(service_name, result)
                progress.update(task, advance=1)

            # Generate recommendations
            self._generate_recommendations(result)

        return result

    def _detect_environment(self) -> str:
        """Detect the current environment."""
        # Check if running in Kubernetes
        if os.path.exists("/var/run/secrets/kubernetes.io"):
            return "kubernetes"

        # Check for Docker
        if os.path.exists("/.dockerenv"):
            return "docker"

        # Check for common k8s environment variables
        if any(k.startswith("KUBERNETES_") for k in os.environ):
            return "kubernetes"

        return "local"

    def _validate_service_name(self, service_name: str, result: ValidationResult) -> None:
        """Validate service name format."""
        # Extract actual service name from path if it's a path
        from pathlib import Path

        path = Path(service_name)
        actual_name = path.name if path.is_absolute() else service_name

        if not actual_name:
            result.add_issue(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message="Service name is empty",
                    resolution="Provide a valid service name",
                )
            )
            return

        if len(actual_name) < 3:
            result.add_issue(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message=f"Service name '{actual_name}' is too short",
                    resolution="Use at least 3 characters for service name",
                )
            )

        if not actual_name.replace("-", "").replace("_", "").isalnum():
            result.add_issue(
                ValidationIssue(
                    level="WARNING",
                    category="CONFIG",
                    message=f"Service name '{actual_name}' contains special characters",
                    resolution="Use only alphanumeric characters, hyphens, and underscores",
                )
            )

        if actual_name != actual_name.lower():
            result.add_issue(
                ValidationIssue(
                    level="INFO",
                    category="CONFIG",
                    message="Service name contains uppercase letters",
                    resolution="Consider using lowercase for consistency",
                )
            )

    def _check_project_structure(self, service_name: str, result: ValidationResult) -> None:
        """Check if project structure exists and is valid."""
        # First check if we're already in a service directory
        current_dir = Path.cwd()

        if (current_dir / "pyproject.toml").exists() and (current_dir / "main.py").exists():
            # We're already in a service directory
            project_path = current_dir
        else:
            # Try to find the service directory
            project_path = Path(service_name)

            # If it's already an absolute path, use it directly
            if not project_path.is_absolute():
                project_path = Path.cwd() / service_name

        # Skip the directory exists check since we've already determined the path
        # If we reached here, project_path is either current dir or a valid subdirectory

        # Check for essential files
        essential_files = {
            "pyproject.toml": "Project configuration",
            "main.py": "Entry point",
            "README.md": "Documentation",
        }

        for file, description in essential_files.items():
            file_path = project_path / file
            if not file_path.exists():
                result.add_issue(
                    ValidationIssue(
                        level="WARNING",
                        category="PROJECT",
                        message=f"Missing {description}: {file}",
                        resolution=f"Create {file} or regenerate project",
                        details={"file": file, "expected_path": str(file_path)},
                    )
                )

        # Check for recommended directories (either at root or under app/)
        recommended_dirs = {
            "domain": ["domain"],
            "application": ["application"],
            "infra": ["infra", "infrastructure"],
            "tests": ["tests", "test"],
        }

        for dir_category, dir_variations in recommended_dirs.items():
            found = False
            for dir_name in dir_variations:
                dir_path = project_path / dir_name
                app_dir_path = project_path / "app" / dir_name

                # Check if exists in either location
                if dir_path.exists() or app_dir_path.exists():
                    found = True
                    break

            if not found:
                result.add_issue(
                    ValidationIssue(
                        level="INFO",
                        category="PROJECT",
                        message=f"Missing recommended directory: {dir_category}",
                        resolution=f"Consider adding {dir_category} directory for better organization",
                    )
                )

    def _validate_config_files(self, service_name: str, result: ValidationResult) -> None:
        """Validate configuration files."""
        # Always use current directory if it looks like a project
        current_dir = Path.cwd()
        if (current_dir / "pyproject.toml").exists() or (current_dir / "main.py").exists():
            project_path = current_dir
        else:
            # Fall back to subdirectory
            project_path = Path(service_name)
            if not project_path.is_absolute():
                project_path = Path.cwd() / service_name
            # If subdirectory doesn't exist, still use current dir
            if not project_path.exists():
                project_path = current_dir

        # Check pyproject.toml
        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib

                with open(pyproject_path, "rb") as f:
                    config = tomllib.load(f)

                # Check project metadata
                if "project" in config:
                    project = config["project"]
                    # Extract service name from path
                    expected_name = (
                        Path(service_name).name
                        if Path(service_name).is_absolute()
                        else service_name
                    )
                    if project.get("name") != expected_name:
                        result.add_issue(
                            ValidationIssue(
                                level="WARNING",
                                category="CONFIG",
                                message="Project name mismatch in pyproject.toml",
                                resolution=f"Update project name to '{expected_name}' in pyproject.toml",
                                details={
                                    "configured": project.get("name"),
                                    "expected": service_name,
                                },
                            )
                        )

                    # Check Python version
                    requires_python = project.get("requires-python", "")
                    if "3.13" not in requires_python and "3.12" not in requires_python:
                        result.add_issue(
                            ValidationIssue(
                                level="INFO",
                                category="CONFIG",
                                message="Consider using Python 3.13",
                                resolution="Update requires-python to '>=3.13' in pyproject.toml",
                            )
                        )
                else:
                    result.add_issue(
                        ValidationIssue(
                            level="ERROR",
                            category="CONFIG",
                            message="Missing [project] section in pyproject.toml",
                            resolution="Add project metadata to pyproject.toml",
                        )
                    )
            except Exception as e:
                result.add_issue(
                    ValidationIssue(
                        level="ERROR",
                        category="CONFIG",
                        message=f"Failed to parse pyproject.toml: {e}",
                        resolution="Fix syntax errors in pyproject.toml",
                    )
                )

        # Check .env file
        env_path = project_path / ".env"
        env_example_path = project_path / ".env.example"

        if not env_example_path.exists():
            result.add_issue(
                ValidationIssue(
                    level="WARNING",
                    category="CONFIG",
                    message="Missing .env.example file",
                    resolution="Create .env.example with sample configuration",
                )
            )

        if not env_path.exists() and env_example_path.exists():
            result.add_issue(
                ValidationIssue(
                    level="INFO",
                    category="CONFIG",
                    message="Missing .env file",
                    resolution="Copy .env.example to .env and configure",
                )
            )

    async def _check_nats_connection(self, nats_url: str, result: ValidationResult) -> None:
        """Check NATS server connectivity."""
        # Parse NATS URL
        try:
            from urllib.parse import urlparse

            parsed = urlparse(nats_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 4222

            # Try to connect
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            try:
                sock.connect((host, port))
                sock.close()
                result.add_issue(
                    ValidationIssue(
                        level="INFO",
                        category="NATS",
                        message=f"NATS server is reachable at {nats_url}",
                        details={"host": host, "port": port},
                    )
                )
            except (TimeoutError, OSError) as e:
                result.add_issue(
                    ValidationIssue(
                        level="ERROR",
                        category="NATS",
                        message=f"Cannot connect to NATS server at {nats_url}",
                        resolution="Ensure NATS server is running and accessible",
                        details={"error": str(e), "host": host, "port": port},
                    )
                )
        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    level="ERROR",
                    category="NATS",
                    message=f"Invalid NATS URL: {nats_url}",
                    resolution="Use format: nats://hostname:port",
                    details={"error": str(e)},
                )
            )

    async def validate_nats_connection(self, nats_url: str) -> tuple[bool, ValidationIssue | None]:
        """Validate NATS connection by attempting to connect.

        Args:
            nats_url: NATS server URL to test

        Returns:
            Tuple of (success, issue) where issue is None if successful
        """
        try:
            # Try using aegis_sdk's NATSAdapter
            from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

            nats = NATSAdapter()
            await nats.connect(nats_url, timeout=5.0)

            # Try to disconnect properly
            if hasattr(nats, "disconnect"):
                await nats.disconnect()
            elif hasattr(nats, "close"):
                await nats.close()

            return True, None

        except Exception as e:
            issue = ValidationIssue(
                level="ERROR",
                category="NATS",
                message=f"Failed to connect to NATS: {e!s}",
                resolution="Ensure NATS server is running and accessible",
                details={"url": nats_url, "error": str(e)},
            )
            return False, issue

    def validate_k8s_environment(self) -> tuple[bool, list[str]]:
        """Validate if running in Kubernetes environment.

        Returns:
            Tuple of (is_k8s, indicators) where indicators are the detected k8s signs
        """
        indicators = []

        # Check for k8s service account
        if os.path.exists("/var/run/secrets/kubernetes.io"):
            indicators.append("Service account token found")

        # Check environment variables
        k8s_env_vars = [k for k in os.environ if k.startswith("KUBERNETES_")]
        if k8s_env_vars:
            indicators.append(f"K8s environment variables: {', '.join(k8s_env_vars[:3])}")

        return len(indicators) > 0, indicators

    async def validate_configuration(
        self, service_name: str, nats_url: str | None = None
    ) -> ValidationResult:
        """Validate the complete configuration.

        Args:
            service_name: Name of the service to validate
            nats_url: Optional NATS URL to test

        Returns:
            ValidationResult with all validation issues
        """
        return await self.validate_all(service_name, nats_url)

    def display_results(self, result: ValidationResult) -> None:
        """Display validation results to console.

        Args:
            result: ValidationResult to display
        """
        # Title
        title = (
            "[green]✓ Configuration Valid[/green]"
            if result.is_valid
            else "[red]✗ Configuration Issues Found[/red]"
        )
        self.console.print(Panel(title, style="bold"))

        # Issues table if any
        if result.issues:
            table = Table(title="Validation Issues", box=box.ROUNDED)
            table.add_column("Level", style="bold")
            table.add_column("Category")
            table.add_column("Message")
            table.add_column("Resolution")

            for issue in result.issues:
                level_style = {"ERROR": "red", "WARNING": "yellow", "INFO": "cyan"}.get(
                    issue.level, "white"
                )

                table.add_row(
                    f"[{level_style}]{issue.level}[/{level_style}]",
                    issue.category,
                    issue.message,
                    issue.resolution or "-",
                )

            self.console.print(table)

        # Diagnostics
        if result.diagnostics:
            self.console.print("\n[bold]Diagnostics:[/bold]")
            for key, value in result.diagnostics.items():
                self.console.print(f"  • {key}: {value}")

        # Recommendations
        if result.recommendations:
            self.console.print("\n[bold]Recommendations:[/bold]")
            for rec in result.recommendations:
                self.console.print(f"  • {rec}")

    def _check_docker_setup(self, service_name: str, result: ValidationResult) -> None:
        """Check Docker configuration."""
        # Always use current directory if it looks like a project
        current_dir = Path.cwd()
        if (
            (current_dir / "pyproject.toml").exists()
            or (current_dir / "main.py").exists()
            or (current_dir / "Dockerfile").exists()
        ):
            project_path = current_dir
        else:
            # Fall back to subdirectory
            project_path = Path(service_name)
            if not project_path.is_absolute():
                project_path = Path.cwd() / service_name
            # If subdirectory doesn't exist, still use current dir
            if not project_path.exists():
                project_path = current_dir

        # Check Dockerfile
        dockerfile_path = project_path / "Dockerfile"
        if not dockerfile_path.exists():
            result.add_issue(
                ValidationIssue(
                    level="INFO",
                    category="DOCKER",
                    message="Missing Dockerfile",
                    resolution="Create Dockerfile for containerization",
                )
            )
        else:
            # Check Dockerfile content
            with open(dockerfile_path) as f:
                content = f.read()
                if "python:3.13" in content:
                    result.diagnostics["docker_python"] = "3.13"
                elif "python:3.12" in content:
                    result.add_issue(
                        ValidationIssue(
                            level="INFO",
                            category="DOCKER",
                            message="Consider upgrading to Python 3.13 in Dockerfile",
                            resolution="Change FROM python:3.12 to FROM python:3.13-slim",
                        )
                    )

                if "uv" in content:
                    result.diagnostics["docker_package_manager"] = "uv"

        # Check docker-compose.yml
        compose_path = project_path / "docker-compose.yml"
        if compose_path.exists():
            result.diagnostics["docker_compose"] = True

        # Check if Docker is installed
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)  # nosec B603,B607
            result.diagnostics["docker_installed"] = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            result.add_issue(
                ValidationIssue(
                    level="WARNING",
                    category="DOCKER",
                    message="Docker is not installed or not accessible",
                    resolution="Install Docker from https://docs.docker.com/get-docker/",
                )
            )

    def _check_kubernetes_setup(self, service_name: str, result: ValidationResult) -> None:
        """Check Kubernetes configuration."""
        # Always use current directory if it looks like a project
        current_dir = Path.cwd()
        if (
            (current_dir / "pyproject.toml").exists()
            or (current_dir / "main.py").exists()
            or (current_dir / "k8s").exists()
        ):
            project_path = current_dir
        else:
            # Fall back to subdirectory
            project_path = Path(service_name)
            if not project_path.is_absolute():
                project_path = Path.cwd() / service_name
            # If subdirectory doesn't exist, still use current dir
            if not project_path.exists():
                project_path = current_dir

        k8s_path = project_path / "k8s"

        if not k8s_path.exists():
            result.add_issue(
                ValidationIssue(
                    level="WARNING",
                    category="K8S",
                    message="Missing k8s directory",
                    resolution="Run bootstrap with --include-k8s flag",
                )
            )
            return

        # Check for Helm files (templates can be in templates/ subdirectory)
        helm_files = {
            "Chart.yaml": k8s_path / "Chart.yaml",
            "values.yaml": k8s_path / "values.yaml",
            "_helpers.tpl": k8s_path / "templates" / "_helpers.tpl",
        }
        # Also check if _helpers.tpl is in the root k8s directory (for backwards compatibility)
        if not helm_files["_helpers.tpl"].exists() and (k8s_path / "_helpers.tpl").exists():
            helm_files["_helpers.tpl"] = k8s_path / "_helpers.tpl"

        has_helm = all(path.exists() for path in helm_files.values())

        if has_helm:
            result.diagnostics["helm_ready"] = True
            result.add_issue(
                ValidationIssue(
                    level="INFO",
                    category="K8S",
                    message="Helm chart is configured",
                    details={"path": str(k8s_path)},
                )
            )
        else:
            missing = [name for name, path in helm_files.items() if not path.exists()]
            result.add_issue(
                ValidationIssue(
                    level="WARNING",
                    category="K8S",
                    message="Incomplete Helm configuration",
                    resolution="Missing files: " + ", ".join(missing),
                    details={"missing_files": missing},
                )
            )

        # Check kubectl
        try:
            subprocess.run(  # nosec B603,B607
                ["kubectl", "version", "--client"], capture_output=True, check=True, timeout=5
            )
            result.diagnostics["kubectl_installed"] = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            result.add_issue(
                ValidationIssue(
                    level="INFO",
                    category="K8S",
                    message="kubectl is not installed",
                    resolution="Install kubectl from https://kubernetes.io/docs/tasks/tools/",
                )
            )

    def _generate_recommendations(self, result: ValidationResult) -> None:
        """Generate recommendations based on validation results."""
        errors = result.get_issues_by_level("ERROR")
        warnings = result.get_issues_by_level("WARNING")

        if errors:
            result.recommendations.append("Fix all ERROR issues before proceeding")

        if warnings:
            result.recommendations.append("Address WARNING issues for better stability")

        if result.environment == "kubernetes" and not result.diagnostics.get("helm_ready"):
            result.recommendations.append("Configure Helm charts for Kubernetes deployment")

        if not result.diagnostics.get("docker_installed"):
            result.recommendations.append("Install Docker for containerization support")

        if not errors and not warnings:
            result.recommendations.append("Configuration looks good! Ready to deploy")


@click.command()
@click.option("--service-name", "-s", required=True, help="Name of the service to validate")
@click.option("--nats-url", "-n", help="NATS server URL to test connection")
@click.option(
    "--environment",
    "-e",
    type=click.Choice(["auto", "local", "kubernetes"]),
    default="auto",
    help="Target environment (auto-detect by default)",
)
@click.option("--json", is_flag=True, help="Output results as JSON")
def main(service_name: str, nats_url: str | None, environment: str, json: bool):
    """Validate AegisSDK configuration and troubleshoot issues."""
    validator = ConfigValidator()

    # Run validation
    result = asyncio.run(validator.validate_all(service_name, nats_url, environment))

    if json:
        # Output as JSON
        print(result.model_dump_json(indent=2))
    else:
        # Display formatted results
        validator.display_results(result)

    # Exit with appropriate code
    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
