"""Quickstart project generator for CLI."""

from pathlib import Path

from aegis_sdk_dev.domain.models import BootstrapConfig, ProjectTemplate, ServiceConfiguration
from aegis_sdk_dev.domain.simple_project_generator import SimpleProjectGenerator


class ProjectGenerator:
    """Project generator for quickstart CLI."""

    def __init__(self):
        """Initialize the generator."""
        self.generator = SimpleProjectGenerator()

    def generate_project(
        self,
        project_name: str,
        template_type: str = "enterprise_ddd",
        include_docker: bool = True,
        include_k8s: bool = True,
        helm_compatible: bool = True,
        package_manager: str = "uv",
        python_version: str = "3.13",
    ) -> None:
        """Generate a project with the given configuration."""
        # Create config object
        config = BootstrapConfig(
            project_name=project_name,
            template=ProjectTemplate.ENTERPRISE_DDD,  # Only support enterprise_ddd
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name=project_name,
                nats_url="nats://localhost:4222",
                environment="local",
            ),
            include_tests=True,
            include_docker=include_docker,
            include_k8s=include_k8s,
        )

        # Generate files
        files = self.generator.generate_project(config)

        # Write files to disk
        for file_path, content in files.items():
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Handle special parameters
            if package_manager == "uv" and "Dockerfile" in file_path:
                # Ensure uv is used in Dockerfile
                content = content.replace("pip install", "uv pip install --system")
                if "RUN pip install" not in content and "RUN uv" not in content:
                    # Add uv installation if not present
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("FROM python:"):
                            lines.insert(i + 1, "RUN pip install uv")
                            break
                    content = "\n".join(lines)

            if python_version and "Dockerfile" in file_path:
                # Update Python version
                content = content.replace("python:3.11", f"python:{python_version}")
                content = content.replace("python:3.12", f"python:{python_version}")
                content = content.replace(">=3.11", f">={python_version}")
                content = content.replace(">=3.12", f">={python_version}")

            if helm_compatible and "/k8s/" in file_path and not file_path.endswith(".tpl"):
                # Already handled in SimpleProjectGenerator
                pass

            path.write_text(content)
