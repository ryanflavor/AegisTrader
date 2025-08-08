#!/usr/bin/env python3
"""
AegisSDK Quickstart CLI Tool

Project scaffolding tool that helps developers quickly create
new AegisSDK services with best practices and patterns.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

import click
from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table


class ServiceTemplate(str, Enum):
    """Available service templates."""

    BASIC = "basic"  # Basic load-balanced service
    SINGLE_ACTIVE = "single_active"  # Single-active pattern
    EVENT_DRIVEN = "event_driven"  # Event publisher/subscriber
    FULL_FEATURED = "full_featured"  # All patterns combined
    EXTERNAL_CLIENT = "external_client"  # Management/monitoring tool


class ProjectConfig(BaseModel):
    """Configuration for a new project."""

    project_name: str = Field(description="Project name")
    service_name: str = Field(description="Service name for registration")
    template: ServiceTemplate = Field(description="Service template to use")
    include_tests: bool = Field(default=True, description="Include test files")
    include_docker: bool = Field(default=True, description="Include Dockerfile")
    include_k8s: bool = Field(default=True, description="Include K8s manifests")
    include_ci: bool = Field(default=True, description="Include CI/CD config")
    python_version: str = Field(default="3.13", description="Python version")
    author: str = Field(default="", description="Author name")
    description: str = Field(default="", description="Project description")


class QuickstartGenerator:
    """
    Generator for AegisSDK projects following DDD principles.

    Creates scaffolded projects with proper structure,
    configuration, and example implementations.
    """

    def __init__(self, console: Console | None = None):
        """Initialize the generator."""
        self.console = console or Console()

    def generate_project_structure(self, config: ProjectConfig, base_path: Path) -> None:
        """Generate the complete project structure."""
        # Create base directory
        project_path = base_path / config.project_name
        project_path.mkdir(parents=True, exist_ok=True)

        # Create directory structure
        self._create_directories(project_path)

        # Generate files based on template
        if config.template == ServiceTemplate.BASIC:
            self._generate_basic_service(config, project_path)
        elif config.template == ServiceTemplate.SINGLE_ACTIVE:
            self._generate_single_active_service(config, project_path)
        elif config.template == ServiceTemplate.EVENT_DRIVEN:
            self._generate_event_driven_service(config, project_path)
        elif config.template == ServiceTemplate.FULL_FEATURED:
            self._generate_full_featured_service(config, project_path)
        elif config.template == ServiceTemplate.EXTERNAL_CLIENT:
            self._generate_external_client(config, project_path)

        # Generate common files
        self._generate_common_files(config, project_path)

        # Generate optional files
        if config.include_tests:
            self._generate_test_files(config, project_path)
        if config.include_docker:
            self._generate_dockerfile(config, project_path)
        if config.include_k8s:
            self._generate_k8s_manifests(config, project_path)
        if config.include_ci:
            self._generate_ci_config(config, project_path)

    def _create_directories(self, project_path: Path) -> None:
        """Create project directory structure."""
        dirs = [
            "src",
            "src/domain",
            "src/application",
            "src/infrastructure",
            "src/ports",
            "tests",
            "tests/unit",
            "tests/integration",
            "scripts",
            "config",
            "docs",
        ]

        for dir_name in dirs:
            (project_path / dir_name).mkdir(parents=True, exist_ok=True)

    def _generate_basic_service(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate a basic load-balanced service."""
        # Main service file
        service_code = f'''"""
{config.service_name} - Basic Load-Balanced Service

{config.description or "A basic AegisSDK service with load balancing."}
"""

from __future__ import annotations

import asyncio
from typing import Any

from aegis_sdk.developer import quick_setup
from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Request model for processing."""

    data: str = Field(description="Data to process")
    options: dict[str, Any] = Field(default_factory=dict)


class ProcessResponse(BaseModel):
    """Response model for processing."""

    result: str = Field(description="Processing result")
    instance_id: str = Field(description="Instance that processed the request")
    processed_at: str = Field(description="Processing timestamp")


class {config.service_name.title().replace("-", "")}Service:
    """
    Main service implementation following DDD principles.

    This is a load-balanced service where multiple instances
    can handle requests concurrently.
    """

    def __init__(self):
        """Initialize the service."""
        self.service = None
        self.instance_id = None

    async def start(self) -> None:
        """Start the service."""
        # Use quick_setup for automatic configuration
        self.service = await quick_setup("{config.service_name}")
        self.instance_id = self.service.instance_id

        # Register RPC handlers
        @self.service.rpc("process")
        async def handle_process(params: dict[str, Any]) -> dict[str, Any]:
            """Handle process requests."""
            request = ProcessRequest(**params)

            # Process the request (your business logic here)
            result = await self._process_data(request.data, request.options)

            response = ProcessResponse(
                result=result,
                instance_id=self.instance_id,
                processed_at=datetime.now().isoformat()
            )

            return response.model_dump()

        @self.service.rpc("health")
        async def handle_health(params: dict[str, Any]) -> dict[str, Any]:
            """Health check endpoint."""
            return {{
                "status": "healthy",
                "instance_id": self.instance_id,
                "service": "{config.service_name}"
            }}

        # Start the service
        await self.service.start()
        print(f"Service {{self.instance_id}} started successfully")

    async def _process_data(self, data: str, options: dict[str, Any]) -> str:
        """Process data according to business logic."""
        # TODO: Implement your business logic here
        return f"Processed: {{data}}"

    async def stop(self) -> None:
        """Stop the service."""
        if self.service:
            await self.service.stop()
            print(f"Service {{self.instance_id}} stopped")


async def main():
    """Main entry point."""
    service = {config.service_name.title().replace("-", "")}Service()

    try:
        await service.start()
        # Keep running until interrupted
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\\nShutting down...")
    finally:
        await service.stop()


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
'''

        # Write service file
        service_file = project_path / "src" / "main.py"
        service_file.write_text(service_code)

    def _generate_single_active_service(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate a single-active pattern service."""
        service_code = f'''"""
{config.service_name} - Single-Active Service

{config.description or "A single-active service with automatic failover."}
"""

from __future__ import annotations

import asyncio
from typing import Any

from aegis_sdk.application.single_active_service import SingleActiveService, SingleActiveConfig
from aegis_sdk.developer import quick_setup
from aegis_sdk.domain.value_objects import FailoverPolicy
from pydantic import BaseModel, Field


class StateData(BaseModel):
    """Stateful data managed by the service."""

    counter: int = Field(default=0)
    last_processed: str | None = Field(default=None)
    state: dict[str, Any] = Field(default_factory=dict)


class {config.service_name.title().replace("-", "")}Service:
    """
    Single-active service implementation.

    Only the leader instance processes requests.
    Automatic failover ensures high availability.
    """

    def __init__(self):
        """Initialize the service."""
        self.service: SingleActiveService | None = None
        self.state = StateData()

    async def start(self) -> None:
        """Start the service."""
        # Configure single-active service
        config = SingleActiveConfig(
            service_name="{config.service_name}",
            failover_policy=FailoverPolicy.balanced(),  # 2-5 second failover
            enable_health_checks=True
        )

        # Create service
        self.service = SingleActiveService(config)

        # Register handlers (only leader will process)
        @self.service.rpc("process")
        async def handle_process(params: dict[str, Any]) -> dict[str, Any]:
            """Handle process requests - only on leader."""
            if not self.service.is_leader:
                return {{
                    "error": True,
                    "error_code": "NOT_ACTIVE",
                    "error_message": "Not the active leader"
                }}

            # Update state
            self.state.counter += 1
            self.state.last_processed = params.get("data", "")

            return {{
                "success": True,
                "counter": self.state.counter,
                "processed_by": self.service.instance_id,
                "is_leader": True
            }}

        @self.service.on_leadership_acquired
        async def on_become_leader():
            """Called when this instance becomes the leader."""
            print(f"🎉 Instance {{self.service.instance_id}} is now the LEADER")
            # TODO: Initialize leader-specific resources

        @self.service.on_leadership_lost
        async def on_lose_leadership():
            """Called when this instance loses leadership."""
            print(f"😔 Instance {{self.service.instance_id}} is no longer the leader")
            # TODO: Clean up leader-specific resources

        # Start the service
        await self.service.start()
        print(f"Single-active service started: {{self.service.instance_id}}")

    async def stop(self) -> None:
        """Stop the service."""
        if self.service:
            await self.service.stop()


async def main():
    """Main entry point."""
    service = {config.service_name.title().replace("-", "")}Service()

    try:
        await service.start()
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\\nShutting down...")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
'''

        service_file = project_path / "src" / "main.py"
        service_file.write_text(service_code)

    def _generate_event_driven_service(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate an event-driven service."""
        service_code = f'''"""
{config.service_name} - Event-Driven Service

{config.description or "An event-driven service with pub/sub patterns."}
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any

from aegis_sdk.developer import quick_setup
from aegis_sdk.domain.enums import SubscriptionMode
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Supported event types."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    PROCESSED = "processed"


class DomainEvent(BaseModel):
    """Base domain event."""

    event_id: str = Field(description="Unique event ID")
    event_type: EventType = Field(description="Type of event")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    data: dict[str, Any] = Field(description="Event data")
    metadata: dict[str, Any] = Field(default_factory=dict)


class {config.service_name.title().replace("-", "")}Service:
    """
    Event-driven service implementation.

    Publishes and subscribes to domain events.
    """

    def __init__(self):
        """Initialize the service."""
        self.service = None

    async def start(self) -> None:
        """Start the service."""
        self.service = await quick_setup("{config.service_name}")

        # Subscribe to events
        await self.service.subscribe(
            "events.>",  # Subscribe to all events
            callback=self._handle_event,
            mode=SubscriptionMode.COMPETE  # Load balance among instances
        )

        # Register RPC for triggering events
        @self.service.rpc("trigger_event")
        async def handle_trigger(params: dict[str, Any]) -> dict[str, Any]:
            """Trigger a new event."""
            event = DomainEvent(
                event_id=params.get("id", str(uuid.uuid4())),
                event_type=EventType(params.get("type", "created")),
                data=params.get("data", {{}})
            )

            await self._publish_event(event)

            return {{
                "success": True,
                "event_id": event.event_id,
                "published_at": event.timestamp
            }}

        await self.service.start()
        print(f"Event-driven service started: {{self.service.instance_id}}")

    async def _handle_event(self, msg: Any) -> None:
        """Handle incoming events."""
        try:
            event_data = json.loads(msg.data.decode())
            event = DomainEvent(**event_data)

            print(f"📨 Received event: {{event.event_type}} ({{event.event_id}})")

            # Process event based on type
            if event.event_type == EventType.CREATED:
                await self._handle_created(event)
            elif event.event_type == EventType.UPDATED:
                await self._handle_updated(event)
            # ... handle other event types

        except Exception as e:
            print(f"Error handling event: {{e}}")

    async def _publish_event(self, event: DomainEvent) -> None:
        """Publish an event."""
        topic = f"events.{config.service_name}.{{event.event_type.value}}"
        await self.service.publish(topic, event.model_dump_json().encode())
        print(f"📤 Published event to {{topic}}")

    async def _handle_created(self, event: DomainEvent) -> None:
        """Handle created events."""
        # TODO: Implement your business logic
        pass

    async def _handle_updated(self, event: DomainEvent) -> None:
        """Handle updated events."""
        # TODO: Implement your business logic
        pass

    async def stop(self) -> None:
        """Stop the service."""
        if self.service:
            await self.service.stop()


async def main():
    """Main entry point."""
    import uuid

    service = {config.service_name.title().replace("-", "")}Service()

    try:
        await service.start()
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\\nShutting down...")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
'''

        service_file = project_path / "src" / "main.py"
        service_file.write_text(service_code)

    def _generate_external_client(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate an external client/tool."""
        client_code = f'''"""
{config.service_name} - External Management Tool

{config.description or "An external client for monitoring and management."}
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from rich.console import Console
from rich.table import Table


class {config.service_name.title().replace("-", "")}Client:
    """
    External client implementation.

    This is NOT a service - it's a management/monitoring tool
    that interacts with the service infrastructure.
    """

    def __init__(self):
        """Initialize the client."""
        self.console = Console()
        self.nats_adapter = None
        self.discovery = None

    async def connect(self) -> None:
        """Connect to infrastructure."""
        # Direct infrastructure connection (not a service)
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect("nats://localhost:4222")

        # Set up service discovery
        kv_store = NATSKVStore(self.nats_adapter)
        await kv_store.connect("service_registry")
        registry = KVServiceRegistry(kv_store)
        self.discovery = BasicServiceDiscovery(registry)

        self.console.print("[green]✓ Connected to infrastructure[/green]")

    async def list_services(self) -> None:
        """List all registered services."""
        services = await self.discovery.list_all()

        table = Table(title="Registered Services")
        table.add_column("Service", style="cyan")
        table.add_column("Instance", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Endpoint")

        for service in services:
            table.add_row(
                service.service_name,
                service.instance_id[:12],
                service.status.value,
                service.endpoint
            )

        self.console.print(table)

    async def call_service(self, service_name: str, method: str, params: dict[str, Any]) -> Any:
        """Call a service method."""
        try:
            response = await self.nats_adapter.request(
                f"rpc.{{service_name}}.{{method}}",
                json.dumps(params).encode(),
                timeout=5.0
            )

            if response:
                return json.loads(response.data.decode())
            return None

        except Exception as e:
            self.console.print(f"[red]Error calling service: {{e}}[/red]")
            return None

    async def monitor_events(self, topic_pattern: str = ">") -> None:
        """Monitor events in real-time."""
        self.console.print(f"[yellow]Monitoring events: {{topic_pattern}}[/yellow]")

        async def handle_event(msg):
            """Handle incoming event."""
            try:
                data = json.loads(msg.data.decode())
                self.console.print(f"📨 {{msg.subject}}: {{data}}")
            except Exception as e:
                self.console.print(f"[red]Error: {{e}}[/red]")

        await self.nats_adapter.subscribe(topic_pattern, callback=handle_event)

        # Keep monitoring
        await asyncio.Event().wait()

    async def disconnect(self) -> None:
        """Disconnect from infrastructure."""
        if self.nats_adapter:
            await self.nats_adapter.disconnect()
            self.console.print("[yellow]Disconnected[/yellow]")


async def main():
    """Main entry point."""
    client = {config.service_name.title().replace("-", "")}Client()

    try:
        await client.connect()

        # Example operations
        await client.list_services()

        # Monitor events (uncomment to use)
        # await client.monitor_events("events.>")

    except KeyboardInterrupt:
        print("\\nStopping...")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
'''

        client_file = project_path / "src" / "main.py"
        client_file.write_text(client_code)

    def _generate_full_featured_service(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate a full-featured service with all patterns."""
        # This would be a combination of all patterns
        # For brevity, using the basic template with a note
        self._generate_basic_service(config, project_path)

        # Add README with additional patterns
        readme_content = f"""# {config.project_name}

Full-featured AegisSDK service with all patterns.

## Features

- Load-balanced RPC handling
- Single-active pattern support
- Event publishing and subscription
- Metrics collection
- Health monitoring
- Automatic failover

## Getting Started

See the examples in the `src/` directory for different patterns.

## Patterns Included

1. **Load-Balanced Service**: Multiple instances handle requests
2. **Single-Active Service**: Only leader processes exclusive operations
3. **Event-Driven**: Pub/sub with domain events
4. **Observability**: Metrics and health monitoring

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start service
python src/main.py
```
"""
        readme_file = project_path / "README.md"
        readme_file.write_text(readme_content)

    def _generate_common_files(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate common project files."""
        # pyproject.toml
        pyproject_content = f"""[project]
name = "{config.project_name}"
version = "0.1.0"
description = "{config.description}"
authors = [{{name = "{config.author}"}}]
requires-python = ">={config.python_version}"
dependencies = [
    "aegis-sdk>=0.1.0",
    "pydantic>=2.0.0",
    "asyncio",
    "rich",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio",
    "pytest-cov",
    "mypy",
    "ruff",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.mypy]
python_version = "{config.python_version}"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.ruff]
target-version = "py{config.python_version.replace(".", "")}"
line-length = 100
"""

        pyproject_file = project_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)

        # .gitignore
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.coverage
.pytest_cache/
htmlcov/

# Logs
*.log

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db
"""

        gitignore_file = project_path / ".gitignore"
        gitignore_file.write_text(gitignore_content)

        # README.md
        readme_content = f"""# {config.project_name}

{config.description}

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python src/main.py
```

## Architecture

This service follows Domain-Driven Design (DDD) principles with hexagonal architecture.

### Directory Structure

- `src/domain/` - Domain models and business logic
- `src/application/` - Application services and use cases
- `src/infrastructure/` - Technical implementations
- `src/ports/` - Interface definitions
- `tests/` - Unit and integration tests

## Configuration

The service uses automatic configuration discovery for K8s environments.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

## Deployment

See `k8s/` directory for Kubernetes manifests.

## Author

{config.author}
"""

        readme_file = project_path / "README.md"
        readme_file.write_text(readme_content)

    def _generate_test_files(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate test files."""
        test_content = f'''"""
Tests for {config.service_name} service.
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_service_starts():
    """Test that the service starts successfully."""
    # TODO: Implement test
    assert True


@pytest.mark.asyncio
async def test_rpc_handler():
    """Test RPC request handling."""
    # TODO: Implement test
    assert True


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    # TODO: Implement test
    assert True
'''

        test_file = project_path / "tests" / "test_service.py"
        test_file.write_text(test_content)

    def _generate_dockerfile(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate Dockerfile."""
        dockerfile_content = f"""FROM python:{config.python_version}-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Run service
CMD ["python", "src/main.py"]
"""

        dockerfile = project_path / "Dockerfile"
        dockerfile.write_text(dockerfile_content)

    def _generate_k8s_manifests(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate Kubernetes manifests."""
        k8s_dir = project_path / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        deployment_content = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {config.project_name}
  namespace: aegis-trader
spec:
  replicas: 3
  selector:
    matchLabels:
      app: {config.project_name}
  template:
    metadata:
      labels:
        app: {config.project_name}
    spec:
      containers:
      - name: {config.project_name}
        image: {config.project_name}:latest
        env:
        - name: SERVICE_NAME
          value: "{config.service_name}"
        - name: NATS_URL
          value: "nats://aegis-trader-nats:4222"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
"""

        deployment_file = k8s_dir / "deployment.yaml"
        deployment_file.write_text(deployment_content)

    def _generate_ci_config(self, config: ProjectConfig, project_path: Path) -> None:
        """Generate CI/CD configuration."""
        github_dir = project_path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)

        ci_content = f"""name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python {config.python_version}
      uses: actions/setup-python@v4
      with:
        python-version: {config.python_version}

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov

    - name: Run tests
      run: pytest --cov=src --cov-report=term-missing

    - name: Type checking
      run: mypy src/

    - name: Linting
      run: ruff check src/
"""

        ci_file = github_dir / "ci.yml"
        ci_file.write_text(ci_content)


@click.command()
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--name", "-n", help="Project name")
@click.option("--template", "-t", type=click.Choice([t.value for t in ServiceTemplate]))
@click.option("--path", "-p", type=click.Path(), default=".", help="Output path")
def main(interactive: bool, name: str | None, template: str | None, path: str) -> None:
    """AegisSDK Quickstart - Project scaffolding tool."""
    console = Console()
    generator = QuickstartGenerator(console)

    console.print("[bold blue]AegisSDK Quickstart[/bold blue]")
    console.print("Create a new AegisSDK project\n")

    if interactive or not (name and template):
        # Interactive mode
        name = name or Prompt.ask("Project name", default="my-aegis-service")

        # Show template options
        table = Table(title="Available Templates")
        table.add_column("Template", style="cyan")
        table.add_column("Description")

        table.add_row("basic", "Basic load-balanced service")
        table.add_row("single_active", "Single-active pattern with failover")
        table.add_row("event_driven", "Event publisher/subscriber")
        table.add_row("full_featured", "All patterns combined")
        table.add_row("external_client", "Management/monitoring tool")

        console.print(table)

        template = template or Prompt.ask(
            "Select template",
            choices=[t.value for t in ServiceTemplate],
            default=ServiceTemplate.BASIC.value,
        )

        # Additional options
        include_tests = Confirm.ask("Include tests?", default=True)
        include_docker = Confirm.ask("Include Dockerfile?", default=True)
        include_k8s = Confirm.ask("Include K8s manifests?", default=True)
        include_ci = Confirm.ask("Include CI/CD config?", default=True)

        author = Prompt.ask("Author name", default="")
        description = Prompt.ask("Project description", default="")

        config = ProjectConfig(
            project_name=name,
            service_name=name.lower().replace("_", "-"),
            template=ServiceTemplate(template),
            include_tests=include_tests,
            include_docker=include_docker,
            include_k8s=include_k8s,
            include_ci=include_ci,
            author=author,
            description=description,
        )
    else:
        # Non-interactive mode
        config = ProjectConfig(
            project_name=name,
            service_name=name.lower().replace("_", "-"),
            template=ServiceTemplate(template),
        )

    # Generate project
    base_path = Path(path)

    console.print(f"\n[yellow]Creating project: {config.project_name}[/yellow]")

    try:
        generator.generate_project_structure(config, base_path)

        console.print("\n[green]✓ Project created successfully![/green]")
        console.print("\nNext steps:")
        console.print(f"  cd {config.project_name}")
        console.print("  pip install -r requirements.txt")
        console.print("  python src/main.py")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
