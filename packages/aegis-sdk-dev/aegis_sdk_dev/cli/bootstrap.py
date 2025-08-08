"""Bootstrap CLI for service initialization."""

from pathlib import Path

import click

from aegis_sdk_dev.application.project_generator_service import ProjectGeneratorService
from aegis_sdk_dev.domain.models import BootstrapConfig, ProjectTemplate, ServiceConfiguration
from aegis_sdk_dev.infrastructure.factory import InfrastructureFactory


class BootstrapCLI:
    """Bootstrap CLI implementation for testing compatibility."""

    def __init__(self):
        """Initialize Bootstrap CLI."""
        pass


@click.command()
@click.option("--project-name", "-p", required=True, help="Name of the project to create")
@click.option(
    "--template",
    "-t",
    type=click.Choice(["enterprise_ddd"]),
    default="enterprise_ddd",
    help="Project template (enterprise_ddd only)",
)
@click.option("--service-name", "-s", help="Service name (defaults to project name)")
@click.option("--nats-url", "-n", default="nats://localhost:4222", help="NATS server URL")
@click.option(
    "--environment",
    "-e",
    type=click.Choice(["local", "docker", "kubernetes", "development", "staging", "production"]),
    default="local",
    help="Target environment",
)
@click.option("--output-dir", "-o", default=".", help="Output directory for the project")
@click.option("--include-tests/--no-tests", default=True, help="Include test files")
@click.option("--include-docker/--no-docker", default=True, help="Include Docker files")
@click.option("--include-k8s/--no-k8s", default=False, help="Include Kubernetes manifests")
def main(
    project_name,
    template,
    service_name,
    nats_url,
    environment,
    output_dir,
    include_tests,
    include_docker,
    include_k8s,
):
    """Bootstrap a new AegisSDK service with Enterprise DDD structure."""

    # Use project name as service name if not provided
    if not service_name:
        service_name = project_name

    # Map template string to enum (only enterprise_ddd supported)
    template_map = {
        "enterprise_ddd": ProjectTemplate.ENTERPRISE_DDD,
    }

    # Create configuration
    config = BootstrapConfig(
        project_name=project_name,
        template=template_map[template],
        output_dir=output_dir,
        service_config=ServiceConfiguration(
            service_name=service_name,
            nats_url=nats_url,
            environment=environment,
        ),
        include_tests=include_tests,
        include_docker=include_docker,
        include_k8s=include_k8s,
    )

    # Create infrastructure
    factory = InfrastructureFactory()
    console = factory.create_console()
    file_system = factory.create_file_system()
    template_generator = factory.create_template_generator()

    # Create project generator service
    service = ProjectGeneratorService(
        console=console,
        file_system=file_system,
        template_generator=template_generator,
    )

    # Generate project
    console.print(f"[cyan]Creating Enterprise DDD project '{project_name}'...[/cyan]")

    try:
        success = service.generate_project(config)

        if success:
            console.print_success(f"✅ Project '{project_name}' created successfully!")
            console.print(f"📁 Project location: {Path(output_dir) / project_name}")
            console.print("\n[bold]Next steps:[/bold]")
            console.print(f"  1. cd {project_name}")
            console.print("  2. uv venv && uv pip install -e .")
            console.print("  3. uv run python main.py")
        else:
            console.print_error("❌ Failed to create project")
    except Exception as e:
        console.print_error(f"❌ Error creating project: {e}")


if __name__ == "__main__":
    main()
