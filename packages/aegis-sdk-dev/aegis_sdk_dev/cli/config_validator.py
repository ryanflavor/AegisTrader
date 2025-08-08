"""Configuration validator CLI tool with hexagonal architecture."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click
from pydantic import BaseModel, Field, field_validator
from rich import box
from rich.console import Console
from rich.panel import Panel
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
        """Get all issues in a specific category."""
        return [issue for issue in self.issues if issue.category == category]

    model_config = {"strict": True}


class ConfigValidator:
    """Application service for configuration validation."""

    def __init__(self, console: Console | None = None):
        """Initialize the validator with optional console for output."""
        self.console = console or Console()

    async def validate_nats_connection(
        self, nats_url: str, timeout: int = 5
    ) -> tuple[bool, ValidationIssue | None]:
        """Validate NATS connection."""
        try:
            from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

            nats = NATSAdapter()
            await asyncio.wait_for(nats.connect(nats_url), timeout=timeout)
            # NATSAdapter uses 'disconnect' method, not 'close'
            if hasattr(nats, "disconnect"):
                await nats.disconnect()
            elif hasattr(nats, "close"):
                await nats.close()
            return True, None

        except asyncio.TimeoutError:
            return False, ValidationIssue(
                level="ERROR",
                category="NATS",
                message=f"Connection to {nats_url} timed out after {timeout} seconds",
                resolution="Check if NATS is running and accessible. Try: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222",
                details={"url": nats_url, "timeout": timeout},
            )
        except Exception as e:
            return False, ValidationIssue(
                level="ERROR",
                category="NATS",
                message=f"Failed to connect to NATS: {e!s}",
                resolution="Verify NATS is running and the URL is correct",
                details={"url": nats_url, "error": str(e)},
            )

    async def validate_k8s_environment(self) -> tuple[bool, ValidationIssue | None]:
        """Check if running in Kubernetes environment."""
        import os

        if os.path.exists("/var/run/secrets/kubernetes.io"):
            return True, None

        # Check for common K8s environment variables
        k8s_vars = ["KUBERNETES_SERVICE_HOST", "KUBERNETES_SERVICE_PORT"]
        if all(os.getenv(var) for var in k8s_vars):
            return True, None

        return False, ValidationIssue(
            level="INFO",
            category="K8S",
            message="Not running in Kubernetes environment",
            resolution="This is expected for local development. Use port-forwarding to connect to K8s services.",
            details={"k8s_detected": False},
        )

    async def validate_configuration(
        self,
        service_name: str,
        nats_url: str,
        environment: str = "auto",
    ) -> ValidationResult:
        """Perform comprehensive configuration validation."""
        result = ValidationResult(environment=environment)

        # Validate service name
        if not service_name or len(service_name) < 3:
            result.add_issue(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message="Service name is invalid or too short",
                    resolution="Provide a meaningful service name (minimum 3 characters)",
                    details={"service_name": service_name},
                )
            )

        # Validate NATS connection
        self.console.print("[cyan]Validating NATS connection...[/cyan]")
        nats_valid, nats_issue = await self.validate_nats_connection(nats_url)
        if not nats_valid and nats_issue:
            result.add_issue(nats_issue)
        else:
            result.diagnostics["nats_connection"] = "OK"

        # Check K8s environment
        self.console.print("[cyan]Checking Kubernetes environment...[/cyan]")
        k8s_valid, k8s_issue = await self.validate_k8s_environment()
        if k8s_issue:
            result.add_issue(k8s_issue)
        result.diagnostics["k8s_environment"] = k8s_valid

        # Detect actual environment
        if environment == "auto":
            if k8s_valid:
                result.environment = "kubernetes"
            else:
                result.environment = "local"

        # Add recommendations based on issues
        if result.get_issues_by_category("NATS"):
            result.recommendations.append(
                "Ensure NATS is running and accessible. For K8s: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222"
            )

        return result

    def display_results(self, result: ValidationResult) -> None:
        """Display validation results in a formatted table."""
        # Create summary panel
        status_color = "green" if result.is_valid else "red"
        status_text = "✓ VALID" if result.is_valid else "✗ INVALID"

        self.console.print(
            Panel(
                f"[{status_color} bold]{status_text}[/{status_color} bold]\n"
                f"Environment: {result.environment}",
                title="Validation Summary",
                box=box.ROUNDED,
            )
        )

        # Display issues if any
        if result.issues:
            table = Table(title="Validation Issues", box=box.SIMPLE)
            table.add_column("Level", style="bold")
            table.add_column("Category")
            table.add_column("Message")
            table.add_column("Resolution", style="dim")

            for issue in result.issues:
                level_style = {
                    "ERROR": "red bold",
                    "WARNING": "yellow",
                    "INFO": "cyan",
                }.get(issue.level, "white")

                table.add_row(
                    f"[{level_style}]{issue.level}[/{level_style}]",
                    issue.category,
                    issue.message,
                    issue.resolution or "N/A",
                )

            self.console.print(table)

        # Display diagnostics
        if result.diagnostics:
            self.console.print("\n[bold]Diagnostics:[/bold]")
            for key, value in result.diagnostics.items():
                self.console.print(f"  • {key}: {value}")

        # Display recommendations
        if result.recommendations:
            self.console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            for rec in result.recommendations:
                self.console.print(f"  → {rec}")


@click.command()
@click.option(
    "--service-name",
    "-s",
    required=True,
    help="Name of the service to validate",
)
@click.option(
    "--nats-url",
    "-n",
    default="nats://localhost:4222",
    help="NATS server URL",
)
@click.option(
    "--environment",
    "-e",
    type=click.Choice(["auto", "local", "kubernetes"]),
    default="auto",
    help="Target environment",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def main(
    service_name: str,
    nats_url: str,
    environment: str,
    output_json: bool,
) -> None:
    """Validate AegisSDK configuration and troubleshoot issues."""
    console = Console()
    validator = ConfigValidator(console)

    async def run_validation():
        result = await validator.validate_configuration(
            service_name=service_name,
            nats_url=nats_url,
            environment=environment,
        )

        if output_json:
            print(json.dumps(result.model_dump(), indent=2))
        else:
            validator.display_results(result)

        return 0 if result.is_valid else 1

    exit_code = asyncio.run(run_validation())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
