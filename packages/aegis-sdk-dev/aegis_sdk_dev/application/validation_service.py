"""Validation application service."""

from __future__ import annotations

from aegis_sdk_dev.domain.models import (
    ServiceConfiguration,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)
from aegis_sdk_dev.domain.services import ConfigurationValidator
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.environment import EnvironmentPort
from aegis_sdk_dev.ports.nats import NATSConnectionPort


class ValidationService:
    """Application service for configuration validation use cases."""

    def __init__(
        self,
        console: ConsolePort,
        environment: EnvironmentPort,
        nats: NATSConnectionPort,
    ):
        """Initialize validation service with required ports.

        Args:
            console: Console port for output
            environment: Environment port for detection
            nats: NATS connection port for connectivity checks
        """
        self._console = console
        self._environment = environment
        self._nats = nats
        self._validator = ConfigurationValidator()

    async def validate_service_configuration(
        self,
        service_name: str,
        nats_url: str,
        environment: str = "auto",
    ) -> ValidationResult:
        """Validate service configuration comprehensively.

        Args:
            service_name: Name of the service
            nats_url: NATS server URL
            environment: Target environment (auto-detect if "auto")

        Returns:
            ValidationResult with all issues and diagnostics
        """
        # Create configuration object
        config = ServiceConfiguration(
            service_name=service_name,
            nats_url=nats_url,
            environment=environment,
        )

        # Start with domain validation
        result = self._validator.validate_configuration(config)

        # Perform infrastructure validations
        self._console.print("[cyan]Validating NATS connection...[/cyan]")
        nats_issue = await self._validate_nats_connection(nats_url)
        if nats_issue:
            result.add_issue(nats_issue)
        else:
            result.diagnostics["nats_connection"] = "OK"

        # Check environment
        self._console.print("[cyan]Checking environment...[/cyan]")
        env_issue = self._validate_environment()
        if env_issue:
            result.add_issue(env_issue)

        # Detect actual environment if auto
        if environment == "auto":
            detected_env = self._environment.detect_environment()
            result.environment = detected_env
            result.diagnostics["detected_environment"] = detected_env

        # Add environment-specific recommendations
        self._add_environment_recommendations(result)

        return result

    async def _validate_nats_connection(
        self, nats_url: str, timeout: float = 5.0
    ) -> ValidationIssue | None:
        """Validate NATS connection.

        Args:
            nats_url: NATS server URL
            timeout: Connection timeout

        Returns:
            ValidationIssue if connection fails, None otherwise
        """
        try:
            connected = await self._nats.connect(nats_url, timeout)
            if connected:
                await self._nats.disconnect()
                return None
        except ConnectionError as e:
            return ValidationIssue(
                level=ValidationLevel.ERROR,
                category="NATS",
                message=str(e),
                resolution="Check if NATS is running and accessible. For K8s: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222",
                details={"url": nats_url, "error": str(e)},
            )
        except Exception as e:
            return ValidationIssue(
                level=ValidationLevel.ERROR,
                category="NATS",
                message=f"Failed to connect to NATS: {e}",
                resolution="Verify NATS is running and the URL is correct",
                details={"url": nats_url, "error": str(e)},
            )

        return ValidationIssue(
            level=ValidationLevel.ERROR,
            category="NATS",
            message=f"Unable to connect to NATS at {nats_url}",
            resolution="Verify NATS server is running",
            details={"url": nats_url},
        )

    def _validate_environment(self) -> ValidationIssue | None:
        """Validate the runtime environment.

        Returns:
            ValidationIssue if environment check has warnings, None otherwise
        """
        if self._environment.is_kubernetes_environment():
            return None

        # Not in Kubernetes - this is informational
        return ValidationIssue(
            level=ValidationLevel.INFO,
            category="ENVIRONMENT",
            message="Not running in Kubernetes environment",
            resolution="This is expected for local development. Use port-forwarding to connect to K8s services.",
            details={"k8s_detected": False, "environment": self._environment.detect_environment()},
        )

    def _add_environment_recommendations(self, result: ValidationResult) -> None:
        """Add environment-specific recommendations.

        Args:
            result: ValidationResult to add recommendations to
        """
        # NATS connection issues
        if result.get_issues_by_category("NATS"):
            if result.environment == "kubernetes":
                result.recommendations.append(
                    "In Kubernetes, ensure NATS service is running in the correct namespace"
                )
            else:
                result.recommendations.append(
                    "For local development: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222"
                )

        # Environment-specific tips
        if result.environment == "kubernetes" and "localhost" in result.diagnostics.get(
            "nats_url", ""
        ):
            result.recommendations.append(
                "Consider using Kubernetes service DNS instead of localhost in K8s environment"
            )

    def display_validation_results(self, result: ValidationResult) -> None:
        """Display validation results in a formatted manner.

        Args:
            result: ValidationResult to display
        """
        # Display summary
        status_color = "green" if result.is_valid else "red"
        status_text = "✓ VALID" if result.is_valid else "✗ INVALID"

        self._console.print_panel(
            f"[{status_color} bold]{status_text}[/{status_color} bold]\n"
            f"Environment: {result.environment}",
            title="Validation Summary",
            style=status_color,
        )

        # Display issues if any
        if result.issues:
            headers = ["Level", "Category", "Message", "Resolution"]
            rows = []

            for issue in result.issues:
                level_style = {
                    ValidationLevel.ERROR: "[red bold]ERROR[/red bold]",
                    ValidationLevel.WARNING: "[yellow]WARNING[/yellow]",
                    ValidationLevel.INFO: "[cyan]INFO[/cyan]",
                }.get(issue.level, issue.level.value)

                rows.append(
                    [
                        level_style,
                        issue.category,
                        issue.message,
                        issue.resolution or "N/A",
                    ]
                )

            self._console.print_table(headers, rows, title="Validation Issues")

        # Display diagnostics
        if result.diagnostics:
            self._console.print("\n[bold]Diagnostics:[/bold]")
            for key, value in result.diagnostics.items():
                self._console.print(f"  • {key}: {value}")

        # Display recommendations
        if result.recommendations:
            self._console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            for rec in result.recommendations:
                self._console.print(f"  → {rec}")
