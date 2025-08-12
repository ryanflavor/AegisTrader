"""Quickstart CLI for rapid service development."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from aegis_sdk_dev.domain.quickstart_generator import ProjectGenerator


class QuickstartWizard:
    """Interactive wizard for quickly starting AegisSDK projects."""

    def __init__(self):
        """Initialize the quickstart wizard."""
        self.console = Console()
        self.project_info: dict[str, Any] = {}

    def run(self) -> None:
        """Run the interactive quickstart wizard."""
        self._show_welcome()
        self._collect_project_info()
        self._select_features()
        self._confirm_and_create()
        self._setup_development_environment()
        self._generate_examples()
        self._show_next_steps()

    def _show_welcome(self) -> None:
        """Display welcome message."""
        self.console.print(
            Panel(
                "[bold cyan]Welcome to AegisSDK Quickstart Wizard![/bold cyan]\n\n"
                "This wizard will help you:\n"
                "• Create a new AegisSDK service project\n"
                "• Set up your development environment\n"
                "• Generate example code and test clients\n"
                "• Configure local testing with NATS and K8s\n\n"
                "[dim]Press Ctrl+C at any time to exit[/dim]",
                title="🚀 AegisSDK Quickstart",
                box=box.ROUNDED,
            )
        )
        self.console.print()

    def _collect_project_info(self) -> None:
        """Collect basic project information."""
        self.console.print("[bold]Step 1: Project Information[/bold]\n")

        # Project name
        while True:
            project_name = Prompt.ask(
                "Project name",
                default="my-aegis-service",
            )
            # Validate project name
            if not project_name or len(project_name) < 3:
                self.console.print("[red]Project name must be at least 3 characters[/red]")
                continue
            if not project_name.replace("-", "").replace("_", "").isalnum():
                self.console.print(
                    "[red]Project name should only contain letters, numbers, hyphens, and underscores[/red]"
                )
                continue
            break

        self.project_info["name"] = project_name

        # Project description
        self.project_info["description"] = Prompt.ask(
            "Project description",
            default=f"AegisSDK service: {project_name}",
        )

        # Use enterprise_ddd template (only supported template)
        self.project_info["template"] = "enterprise_ddd"
        self.console.print(
            "\n[dim]Using Enterprise DDD template (Domain-Driven Design with full architecture layers)[/dim]"
        )

        # Package manager
        use_uv = Confirm.ask("\nUse uv package manager?", default=True)
        self.project_info["package_manager"] = "uv" if use_uv else "pip"

        # Python version
        python_version = Prompt.ask(
            "Python version",
            default="3.13",
            choices=["3.11", "3.12", "3.13"],
        )
        self.project_info["python_version"] = python_version

    def _select_features(self) -> None:
        """Select additional features to include."""
        self.console.print("\n[bold]Step 2: Additional Features[/bold]\n")

        self.project_info["features"] = {}

        # Docker support
        self.project_info["features"]["docker"] = Confirm.ask(
            "Include Docker configuration?", default=True
        )

        # Kubernetes support
        self.project_info["features"]["kubernetes"] = Confirm.ask(
            "Include Kubernetes manifests?", default=True
        )

        if self.project_info["features"]["kubernetes"]:
            self.project_info["features"]["helm"] = Confirm.ask(
                "  → Make K8s files Helm-compatible?", default=True
            )

        # Test client
        self.project_info["features"]["test_client"] = Confirm.ask(
            "Generate test client?", default=True
        )

        # Example handlers
        self.project_info["features"]["examples"] = Confirm.ask(
            "Include example handlers?", default=True
        )

        # GitHub Actions
        self.project_info["features"]["github_actions"] = Confirm.ask(
            "Include GitHub Actions CI/CD?", default=False
        )

        # Pre-commit hooks
        self.project_info["features"]["pre_commit"] = Confirm.ask(
            "Include pre-commit hooks?", default=True
        )

    def _confirm_and_create(self, skip_confirm: bool = False) -> None:
        """Confirm settings and create project."""
        self.console.print("\n[bold]Step 3: Review Configuration[/bold]\n")

        # Display summary
        table = Table(title="Project Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Project Name", self.project_info["name"])
        table.add_row("Description", self.project_info["description"])
        table.add_row("Template", "Enterprise DDD")
        table.add_row("Package Manager", self.project_info["package_manager"])
        table.add_row("Python Version", self.project_info["python_version"])

        self.console.print(table)

        # Display features
        if self.project_info["features"]:
            self.console.print("\n[bold]Selected Features:[/bold]")
            for feature, enabled in self.project_info["features"].items():
                if enabled:
                    icon = "✅"
                    feature_name = feature.replace("_", " ").title()
                    self.console.print(f"  {icon} {feature_name}")

        # Confirm (skip in non-interactive mode)
        if not skip_confirm and not Confirm.ask(
            "\n[bold]Create project with these settings?[/bold]", default=True
        ):
            self.console.print("[yellow]Setup cancelled[/yellow]")
            sys.exit(0)

        # Create project
        self.console.print("\n[bold]Creating project...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("Generating project structure...", total=1)

            # Create project directory
            project_path = Path.cwd() / self.project_info["name"]
            if project_path.exists():
                if not skip_confirm:
                    if not Confirm.ask(
                        f"\n[yellow]Directory '{self.project_info['name']}' already exists. Overwrite?[/yellow]",
                        default=False,
                    ):
                        self.console.print("[red]Setup cancelled[/red]")
                        sys.exit(1)
                else:
                    # In non-interactive mode, exit if directory exists
                    self.console.print(
                        f"[red]Directory '{self.project_info['name']}' already exists[/red]"
                    )
                    sys.exit(1)

            # Generate project using ProjectGenerator
            generator = ProjectGenerator()
            generator.generate_project(
                project_name=self.project_info["name"],
                template_type=self.project_info["template"],
                include_docker=self.project_info["features"].get("docker", False),
                include_k8s=self.project_info["features"].get("kubernetes", False),
                helm_compatible=self.project_info["features"].get("helm", False),
                package_manager=self.project_info["package_manager"],
                python_version=self.project_info["python_version"],
            )

            progress.update(task, advance=1)

        self.console.print(f"[green]✅ Project created at: {project_path}[/green]\n")
        self.project_info["path"] = project_path

    def _setup_development_environment(self, skip_prompts: bool = False) -> None:
        """Set up the development environment."""
        self.console.print("[bold]Step 4: Development Environment Setup[/bold]\n")

        project_path = self.project_info["path"]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Initialize git repository
            if skip_prompts or Confirm.ask("Initialize git repository?", default=True):
                task = progress.add_task("Initializing git...", total=1)
                try:
                    subprocess.run(  # nosec B603,B607
                        ["git", "init"],
                        cwd=project_path,
                        capture_output=True,
                        check=True,
                    )
                    # Create .gitignore
                    gitignore_content = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv
build/
dist/
*.egg-info/
.eggs/
.pytest_cache/
.coverage
htmlcov/
.tox/
.env
.mypy_cache/
.ruff_cache/
.DS_Store
"""
                    (project_path / ".gitignore").write_text(gitignore_content)
                    progress.update(task, advance=1)
                    self.console.print("[green]✅ Git repository initialized[/green]")
                except Exception as e:
                    self.console.print(f"[yellow]⚠️  Git init failed: {e}[/yellow]")

            # Install dependencies
            if self.project_info["package_manager"] == "uv" and (
                skip_prompts or Confirm.ask("Install dependencies with uv?", default=True)
            ):
                task = progress.add_task("Installing dependencies...", total=1)
                try:
                    subprocess.run(  # nosec B603,B607
                        ["uv", "pip", "install", "-e", "."],
                        cwd=project_path,
                        capture_output=True,
                        check=True,
                    )
                    progress.update(task, advance=1)
                    self.console.print("[green]✅ Dependencies installed[/green]")
                except Exception as e:
                    self.console.print(f"[yellow]⚠️  Dependency installation failed: {e}[/yellow]")
                    self.console.print("[dim]Run 'uv pip install -e .' manually[/dim]")

            # Set up pre-commit hooks
            if self.project_info["features"].get("pre_commit"):
                task = progress.add_task("Setting up pre-commit hooks...", total=1)
                pre_commit_config = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
"""
                (project_path / ".pre-commit-config.yaml").write_text(pre_commit_config)
                progress.update(task, advance=1)
                self.console.print("[green]✅ Pre-commit hooks configured[/green]")

    def _generate_examples(self) -> None:
        """Generate example code and test clients."""
        if not self.project_info["features"].get("examples"):
            return

        self.console.print("\n[bold]Step 5: Generating Examples[/bold]\n")
        project_path = self.project_info["path"]

        # Generate example handler for enterprise_ddd
        example_handler = '''"""Example handler for demonstration."""

from aegis_sdk import AegisSDK


class ExampleHandler:
    """Example handler showing AegisSDK usage."""

    def __init__(self, sdk: AegisSDK):
        """Initialize the handler."""
        self.sdk = sdk

    async def handle_echo(self, message: dict) -> dict:
        """Echo handler that returns the input message."""
        return {"echo": message, "timestamp": self.sdk.get_timestamp()}

    async def handle_process(self, data: dict) -> dict:
        """Process handler that transforms data."""
        processed = {
            "original": data,
            "processed": True,
            "service": self.sdk.service_name,
        }
        return processed
'''
        examples_dir = project_path / "examples"
        examples_dir.mkdir(exist_ok=True)
        (examples_dir / "handler.py").write_text(example_handler)
        self.console.print("[green]✅ Example handler created[/green]")

        # Generate test client
        if self.project_info["features"].get("test_client"):
            test_client = f'''"""Test client for {self.project_info["name"]}."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis_sdk import AegisSDK


async def main():
    """Run test client."""
    # Initialize SDK
    sdk = AegisSDK(
        service_name="{self.project_info["name"]}-client",
        nats_url="nats://localhost:4222",
    )

    try:
        await sdk.connect()
        print(f"✅ Connected to NATS as {{sdk.service_name}}")

        # Example: Send echo request
        response = await sdk.request(
            "{self.project_info["name"]}.echo",
            {{"message": "Hello from test client!"}},
        )
        print(f"Echo response: {{response}}")

        # Example: Subscribe to events
        async def event_handler(message):
            print(f"Received event: {{message}}")

        await sdk.subscribe("{self.project_info["name"]}.events.*", event_handler)
        print("📡 Listening for events...")

        # Keep running
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\\n👋 Shutting down...")
    finally:
        await sdk.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
'''
            (project_path / "client.py").write_text(test_client)
            self.console.print("[green]✅ Test client created[/green]")

        # Generate docker-compose for local testing
        if self.project_info["features"].get("docker"):
            docker_compose = f"""version: '3.8'

services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"
      - "8222:8222"
    command: "-js -m 8222"
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "4222"]
      interval: 5s
      timeout: 3s
      retries: 5

  {self.project_info["name"]}:
    build: .
    depends_on:
      nats:
        condition: service_healthy
    environment:
      - NATS_URL=nats://nats:4222
      - SERVICE_NAME={self.project_info["name"]}
      - LOG_LEVEL=DEBUG
    volumes:
      - .:/app
    command: python main.py
"""
            (project_path / "docker-compose.yml").write_text(docker_compose)
            self.console.print("[green]✅ Docker Compose configuration created[/green]")

    def _show_next_steps(self) -> None:
        """Show next steps to the user."""
        self.console.print(
            Panel(
                f"[bold green]🎉 Project '{self.project_info['name']}' created successfully![/bold green]\n\n"
                "[bold]Next Steps:[/bold]\n\n"
                f"1. Navigate to project:\n"
                f"   [cyan]cd {self.project_info['name']}[/cyan]\n\n"
                "2. Start NATS server:\n"
                "   [cyan]docker-compose up nats[/cyan]\n\n"
                "3. Run your service:\n"
                "   [cyan]python main.py[/cyan]\n\n"
                "4. Test with client:\n"
                "   [cyan]python client.py[/cyan]\n\n"
                "5. Validate configuration:\n"
                f"   [cyan]aegis validate -s {self.project_info['name']}[/cyan]\n\n"
                "[bold]Useful Commands:[/bold]\n"
                "• Run tests: [cyan]pytest[/cyan]\n"
                "• Build Docker image: [cyan]docker build -t {self.project_info['name']} .[/cyan]\n"
                "• Deploy to K8s: [cyan]kubectl apply -f k8s/[/cyan]\n\n"
                "[dim]Documentation: https://github.com/your-org/aegis-sdk[/dim]",
                title="✨ Setup Complete",
                box=box.ROUNDED,
            )
        )


class QuickstartCLI:
    """CLI for quickstart operations."""

    def __init__(self):
        self.console = Console()
        self.wizard = QuickstartWizard()

    def run_wizard(self) -> None:
        """Run the interactive wizard."""
        try:
            self.wizard.run()
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup cancelled by user[/yellow]")
            sys.exit(0)
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)


@click.command()
@click.option(
    "--interactive/--no-interactive",
    "-i/-n",
    default=True,
    help="Run in interactive mode (default: interactive)",
)
@click.option(
    "--project-name",
    "-p",
    help="Project name (skips interactive prompt)",
)
@click.option(
    "--examples/--no-examples",
    default=None,
    help="Include example code",
)
def main(
    interactive: bool,
    project_name: str | None,
    examples: bool | None,
):
    """Launch quickstart wizard for creating new AegisSDK services.

    This wizard helps you:
    • Create a new service project with selected template
    • Set up your development environment
    • Generate example code and test clients
    • Configure local testing with NATS and K8s

    Examples:
        Interactive mode (recommended):
            aegis quickstart

        Quick mode with options:
            aegis quickstart -p my-service --examples
    """
    cli = QuickstartCLI()

    if interactive and not project_name:
        # Run full interactive wizard
        cli.run_wizard()
    else:
        # Quick mode with command-line options
        if not project_name:
            cli.console.print("[red]Project name is required in non-interactive mode[/red]")
            sys.exit(1)

        # Use defaults or provided options
        wizard = QuickstartWizard()
        wizard.project_info = {
            "name": project_name,
            "description": f"AegisSDK service: {project_name}",
            "template": "enterprise_ddd",
            "package_manager": "uv",
            "python_version": "3.13",
            "features": {
                "docker": True,
                "kubernetes": True,
                "helm": True,
                "test_client": True,
                "examples": examples if examples is not None else True,
                "github_actions": False,
                "pre_commit": True,
            },
        }

        # Create project directly (skip confirmations in non-interactive mode)
        wizard._confirm_and_create(skip_confirm=True)
        wizard._setup_development_environment(skip_prompts=True)
        wizard._generate_examples()
        wizard._show_next_steps()


if __name__ == "__main__":
    main()
