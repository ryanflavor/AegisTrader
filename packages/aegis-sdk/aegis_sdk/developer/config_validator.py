"""Configuration Validator and Troubleshooter following DDD principles.

This module provides comprehensive validation and troubleshooting for AegisSDK configurations.
It follows hexagonal architecture with clear separation between domain logic and infrastructure.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class ValidationResult(BaseModel):
    """Aggregate representing the complete validation result."""

    is_valid: bool = Field(..., description="Overall validation status")
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


class ConfigurationSpec(BaseModel):
    """Value Object representing configuration requirements."""

    service_name: str = Field(..., description="Service name to validate")
    nats_url: str = Field(..., description="NATS URL to validate")
    environment: str = Field(..., description="Expected environment")
    require_k8s: bool = Field(False, description="Whether K8s is required")
    require_port_forward: bool = Field(False, description="Whether port-forwarding is required")
    timeout_seconds: int = Field(5, description="Validation timeout")


class NATSConnectionValidator:
    """Domain Service for validating NATS connectivity."""

    async def validate(
        self, nats_url: str, timeout: int = 5
    ) -> tuple[bool, ValidationIssue | None]:
        """Validate NATS connection."""
        try:
            # Try to connect to NATS
            from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

            nats = NATSAdapter()
            await asyncio.wait_for(nats.connect(nats_url), timeout=timeout)
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


class K8sEnvironmentValidator:
    """Domain Service for validating Kubernetes environment."""

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        """Validate K8s environment and configuration."""
        issues = []

        # Check kubectl availability
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client", "--output=json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        category="K8S",
                        message="kubectl command failed",
                        resolution="Ensure kubectl is installed and configured",
                        details={"error": result.stderr},
                    )
                )
        except FileNotFoundError:
            issues.append(
                ValidationIssue(
                    level="ERROR",
                    category="K8S",
                    message="kubectl not found",
                    resolution="Install kubectl: https://kubernetes.io/docs/tasks/tools/",
                    details={},
                )
            )
        except subprocess.TimeoutExpired:
            issues.append(
                ValidationIssue(
                    level="WARNING",
                    category="K8S",
                    message="kubectl command timed out",
                    resolution="Check your kubectl configuration",
                    details={},
                )
            )

        # Check current context
        try:
            result = subprocess.run(
                ["kubectl", "config", "current-context"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                context = result.stdout.strip()
                issues.append(
                    ValidationIssue(
                        level="INFO",
                        category="K8S",
                        message=f"Using kubectl context: {context}",
                        resolution=None,
                        details={"context": context},
                    )
                )
        except Exception:
            pass  # Non-critical

        # Check aegis-trader namespace
        try:
            result = subprocess.run(
                ["kubectl", "get", "namespace", "aegis-trader", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        category="K8S",
                        message="aegis-trader namespace not found",
                        resolution="Create namespace: kubectl create namespace aegis-trader",
                        details={},
                    )
                )
        except Exception:
            pass  # Already handled kubectl availability

        # Check NATS service
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "service",
                    "aegis-trader-nats",
                    "-n",
                    "aegis-trader",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                service_info = json.loads(result.stdout)
                port = service_info["spec"]["ports"][0]["port"]
                issues.append(
                    ValidationIssue(
                        level="INFO",
                        category="K8S",
                        message=f"NATS service found on port {port}",
                        resolution=None,
                        details={"service": "aegis-trader-nats", "port": port},
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        category="K8S",
                        message="NATS service not found in aegis-trader namespace",
                        resolution="Deploy NATS to K8s or check namespace",
                        details={},
                    )
                )
        except Exception:
            pass  # Already handled kubectl availability

        # Check port-forwarding
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            if "kubectl port-forward" in result.stdout and "4222" in result.stdout:
                issues.append(
                    ValidationIssue(
                        level="INFO",
                        category="K8S",
                        message="Port-forwarding appears to be active",
                        resolution=None,
                        details={"port": 4222},
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        level="WARNING",
                        category="K8S",
                        message="No port-forwarding detected for NATS",
                        resolution="Run: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222",
                        details={},
                    )
                )
        except Exception:
            pass  # Non-critical

        has_errors = any(issue.level == "ERROR" for issue in issues)
        return not has_errors, issues


class ServiceConfigValidator:
    """Domain Service for validating service configuration."""

    def validate(self, config: dict[str, Any]) -> list[ValidationIssue]:
        """Validate service configuration."""
        issues = []

        # Check service name
        if not config.get("service_name"):
            issues.append(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message="Service name is missing",
                    resolution="Provide a service_name in your configuration",
                    details={},
                )
            )
        elif not isinstance(config["service_name"], str):
            issues.append(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message="Service name must be a string",
                    resolution="Ensure service_name is a valid string",
                    details={"value": config["service_name"]},
                )
            )
        elif len(config["service_name"]) < 3:
            issues.append(
                ValidationIssue(
                    level="WARNING",
                    category="CONFIG",
                    message="Service name is very short",
                    resolution="Consider using a more descriptive service name",
                    details={"value": config["service_name"]},
                )
            )

        # Check NATS URL
        nats_url = config.get("nats_url", "")
        if not nats_url or nats_url == "auto":
            issues.append(
                ValidationIssue(
                    level="INFO",
                    category="CONFIG",
                    message="Using auto-discovery for NATS URL",
                    resolution=None,
                    details={},
                )
            )
        elif not nats_url.startswith(("nats://", "tls://")):
            issues.append(
                ValidationIssue(
                    level="ERROR",
                    category="CONFIG",
                    message="Invalid NATS URL format",
                    resolution="URL should start with nats:// or tls://",
                    details={"value": nats_url},
                )
            )

        # Check environment
        env = config.get("environment", "")
        valid_envs = {"local-k8s", "docker", "production"}
        if env and env not in valid_envs:
            issues.append(
                ValidationIssue(
                    level="WARNING",
                    category="CONFIG",
                    message=f"Unknown environment: {env}",
                    resolution=f"Use one of: {', '.join(valid_envs)}",
                    details={"value": env},
                )
            )

        return issues


class ConfigurationValidator:
    """Application Service orchestrating configuration validation."""

    def __init__(self):
        """Initialize the validator with its dependencies."""
        self.nats_validator = NATSConnectionValidator()
        self.k8s_validator = K8sEnvironmentValidator()
        self.config_validator = ServiceConfigValidator()

    async def validate_all(
        self, config: dict[str, Any], spec: ConfigurationSpec | None = None
    ) -> ValidationResult:
        """Perform comprehensive configuration validation."""
        result = ValidationResult(
            is_valid=True,
            environment=config.get("environment", "unknown"),
            issues=[],
            diagnostics={},
            recommendations=[],
        )

        # Validate configuration structure
        config_issues = self.config_validator.validate(config)
        for issue in config_issues:
            result.add_issue(issue)

        # Validate K8s environment if needed
        if spec and spec.require_k8s:
            k8s_valid, k8s_issues = self.k8s_validator.validate()
            for issue in k8s_issues:
                result.add_issue(issue)
            result.diagnostics["k8s_available"] = k8s_valid

        # Validate NATS connectivity
        nats_url = config.get("nats_url", "nats://localhost:4222")
        if nats_url == "auto":
            nats_url = "nats://localhost:4222"  # Default for auto-discovery

        timeout = spec.timeout_seconds if spec else 5
        nats_valid, nats_issue = await self.nats_validator.validate(nats_url, timeout)
        if nats_issue:
            result.add_issue(nats_issue)
        result.diagnostics["nats_connected"] = nats_valid

        # Generate recommendations
        if result.get_issues_by_level("ERROR"):
            result.recommendations.append("Fix all ERROR issues before proceeding")

        if not result.diagnostics.get("nats_connected"):
            result.recommendations.append("Ensure NATS is running and accessible")
            result.recommendations.append(
                "Try: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222"
            )

        if result.get_issues_by_category("K8S"):
            result.recommendations.append("Review Kubernetes configuration and connectivity")

        if result.get_issues_by_level("WARNING"):
            result.recommendations.append("Consider addressing WARNING issues for better stability")

        return result

    def print_report(self, result: ValidationResult) -> None:
        """Print a formatted validation report."""
        print("\n" + "=" * 60)
        print("AegisSDK Configuration Validation Report")
        print("=" * 60)

        # Overall status
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        print(f"\nStatus: {status}")
        print(f"Environment: {result.environment}")

        # Diagnostics
        if result.diagnostics:
            print("\nDiagnostics:")
            for key, value in result.diagnostics.items():
                icon = "✓" if value else "✗"
                print(f"  {icon} {key}: {value}")

        # Issues by level
        for level in ["ERROR", "WARNING", "INFO"]:
            issues = result.get_issues_by_level(level)
            if issues:
                print(f"\n{level}S ({len(issues)}):")
                for issue in issues:
                    print(f"  [{issue.category}] {issue.message}")
                    if issue.resolution:
                        print(f"    → {issue.resolution}")

        # Recommendations
        if result.recommendations:
            print("\nRecommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")

        print("\n" + "=" * 60)


class TroubleshootingGuide:
    """Domain Service providing troubleshooting guidance."""

    def get_common_issues(self) -> dict[str, dict[str, str]]:
        """Get common issues and their solutions."""
        return {
            "connection_refused": {
                "symptom": "Connection refused when connecting to NATS",
                "causes": "NATS not running, wrong port, firewall blocking",
                "solution": "1. Check NATS is running: kubectl get pods -n aegis-trader\n"
                "2. Setup port-forwarding: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222\n"
                "3. Test connection: nc -zv localhost 4222",
            },
            "timeout": {
                "symptom": "Connection timeout to NATS",
                "causes": "Network issues, K8s service not accessible",
                "solution": "1. Check K8s service: kubectl get svc -n aegis-trader\n"
                "2. Check pod status: kubectl get pods -n aegis-trader\n"
                "3. Check logs: kubectl logs -n aegis-trader aegis-trader-nats-0",
            },
            "namespace_not_found": {
                "symptom": "aegis-trader namespace not found",
                "causes": "Namespace not created, wrong kubectl context",
                "solution": "1. Create namespace: kubectl create namespace aegis-trader\n"
                "2. Check context: kubectl config current-context\n"
                "3. Deploy NATS: helm install aegis-trader-nats nats/nats -n aegis-trader",
            },
            "service_not_registering": {
                "symptom": "Service not appearing in registry",
                "causes": "JetStream not enabled, KV bucket not created",
                "solution": "1. Check JetStream: nats stream ls\n"
                "2. Check KV bucket: nats kv ls\n"
                "3. Create bucket: nats kv add service_registry",
            },
            "failover_not_working": {
                "symptom": "Failover takes too long or doesn't happen",
                "causes": "Heartbeat interval too long, network partitioning",
                "solution": "1. Check heartbeat config (should be ~1 second)\n"
                "2. Check leader election: watch service registry\n"
                "3. Test network: ping between pods",
            },
        }

    def diagnose_issue(self, symptom: str) -> dict[str, str] | None:
        """Diagnose an issue based on symptom description."""
        issues = self.get_common_issues()

        # Simple keyword matching
        symptom_lower = symptom.lower()
        for key, issue in issues.items():
            if any(word in symptom_lower for word in key.split("_")):
                return issue
            if any(word in symptom_lower for word in issue["symptom"].lower().split()):
                return issue

        return None


async def main():
    """CLI entry point for configuration validation."""

    print("AegisSDK Configuration Validator")
    print("-" * 40)

    # Create a sample configuration
    config = {
        "service_name": "test-service",
        "nats_url": "nats://localhost:4222",
        "environment": "local-k8s",
    }

    # Create specification
    spec = ConfigurationSpec(
        service_name="test-service",
        nats_url="nats://localhost:4222",
        environment="local-k8s",
        require_k8s=True,
        require_port_forward=True,
        timeout_seconds=5,
    )

    # Run validation
    validator = ConfigurationValidator()
    result = await validator.validate_all(config, spec)

    # Print report
    validator.print_report(result)

    # Show troubleshooting guide if there are errors
    if not result.is_valid:
        print("\n" + "=" * 60)
        print("Troubleshooting Guide")
        print("=" * 60)

        guide = TroubleshootingGuide()
        shown_issues = set()

        for issue in result.get_issues_by_level("ERROR"):
            # Try to find relevant troubleshooting info
            diagnosis = guide.diagnose_issue(issue.message)
            if diagnosis and diagnosis["symptom"] not in shown_issues:
                shown_issues.add(diagnosis["symptom"])
                print(f"\nIssue: {diagnosis['symptom']}")
                print(f"Causes: {diagnosis['causes']}")
                print(f"Solution:\n{diagnosis['solution']}")

    return 0 if result.is_valid else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
